from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from database import get_db
from models import (
    Problem, ProblemVote, ProblemFollow,
    User, Conversation, ConversationUser, InboxMessage
)

router = APIRouter()

TRIAGER_EMAILS = {"sheaklipper@gmail.com"}  # you’re the only triager for now

# ---------- helpers ----------

def get_identity_email(x_user_email: Optional[str]) -> str:
    """
    We standardize on a single "identity" string:
    - logged-in: real email
    - anonymous: "anon:{uuid}"
    """
    if not x_user_email:
        raise HTTPException(status_code=400, detail="Missing x-user-email identity")
    return x_user_email

def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == "system@domain.com").first()
    if sys:
        return sys
    sys = User(email="system@domain.com", username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys

def slugify(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "problem"

def ensure_problem_conversation(db: Session, problem: Problem, creator_email: Optional[str]) -> Conversation:
    """
    Create a dedicated conversation for the problem if missing.
    Name pattern: problem:{id}:{slug}
    Participants:
      - system user
      - creator (if logged in)
    """
    if problem.conversation_id:
        convo = db.query(Conversation).filter(Conversation.id == problem.conversation_id).first()
        if convo:
            return convo

    name = f"problem:{problem.id}:{slugify(problem.title)}"
    convo = Conversation(name=name)
    db.add(convo)
    db.flush()  # ensure convo.id

    sys_user = get_or_create_system_user(db)
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))

    if creator_email and not creator_email.startswith("anon:"):
        user = db.query(User).filter(User.email == creator_email).first()
        if user:
            db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))

    # optional: seed a welcome message
    db.add(InboxMessage(
        user_id=sys_user.id,
        content=f"New problem created: “{problem.title}”",
        timestamp=datetime.utcnow(),
        conversation_id=convo.id
    ))

    db.commit()
    db.refresh(convo)

    # store on problem
    problem.conversation_id = convo.id
    db.commit()
    db.refresh(problem)
    return convo

def annotate_flags_for_identity(db: Session, identity: Optional[str], problems: List[Problem]):
    """Attach has_voted and is_following flags per problem, for the caller."""
    if not identity:
        for p in problems:
            p.has_voted = False
            p.is_following = False
        return problems

    ids = [p.id for p in problems]
    if not ids:
        return problems

    votes = db.query(ProblemVote.problem_id)\
        .filter(ProblemVote.problem_id.in_(ids), ProblemVote.voter_identity == identity)\
        .all()
    follows = db.query(ProblemFollow.problem_id)\
        .filter(ProblemFollow.problem_id.in_(ids), ProblemFollow.identity == identity)\
        .all()

    voted_ids = {pid for (pid,) in votes}
    follow_ids = {pid for (pid,) in follows}

    for p in problems:
        p.has_voted = p.id in voted_ids
        p.is_following = p.id in follow_ids
    return problems

def recency_boost(created_at: datetime) -> float:
    """
    Boost very recent items only. (no decay over time beyond the boost window)
    < 7 days  -> +1.0
    < 30 days -> +0.5
    else      -> +0
    """
    delta = datetime.utcnow() - created_at
    if delta.days < 7:
        return 1.0
    if delta.days < 30:
        return 0.5
    return 0.0

# ---------- schemas ----------

class ProblemCreateIn(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    domain: Optional[str] = None
    scope: Optional[str] = "Systemic"   # Personal / Community / Systemic
    severity: Optional[int] = 3         # 1–5
    anonymous: Optional[bool] = False

class ProblemOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    domain: Optional[str] = None
    scope: Optional[str] = None
    tags: Optional[List[str]] = None
    severity: Optional[int] = None        # <-- was int
    votes_count: int = 0                  # default 0 if DB has NULL
    followers_count: int = 0              # default 0 if DB has NULL
    created_at: datetime
    conversation_id: Optional[int] = None

    class Config:
        from_attributes = True  # Pydantic v2; use orm_mode=True for v1

# ---------- routes ----------

@router.post("/problems", response_model=ProblemOut)
def create_problem(
    payload: ProblemCreateIn,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = None
):
    identity = x_user_email  # may be real email or anon:{uuid}
    if not identity:
        raise HTTPException(status_code=400, detail="x-user-email header required (email or anon:{uuid})")

    created_by = None if payload.anonymous or identity.startswith("anon:") else identity

    problem = Problem(
        title=payload.title.strip(),
        description=payload.description.strip(),
        domain=(payload.domain or "").strip() or None,
        scope=payload.scope or "Systemic",
        severity=int(payload.severity or 3),
        status="Open",
        anonymous=payload.anonymous or False,
        created_by_email=created_by,
        created_at=datetime.utcnow(),
    )
    db.add(problem)
    db.commit()
    db.refresh(problem)

    # Create conversation + add participants (system + creator if logged-in)
    ensure_problem_conversation(db, problem, creator_email=created_by)

    # Auto-vote and follow by the submitter (identity)
    _ = toggle_vote(db, problem.id, identity, commit=True)
    _ = toggle_follow(db, problem.id, identity, commit=True)

    # annotate response for caller
    problem.has_voted = True
    problem.is_following = True
    return problem


@router.get("/problems", response_model=List[ProblemOut])
def list_problems(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    scope: Optional[str] = None,
    domain: Optional[str] = None,
    sort: Optional[str] = "trending",     # 'trending' | 'votes' | 'new'
    near: Optional[str] = None,           # duplicate suggestion helper
    limit: int = 50,
    offset: int = 0
):
    qry = db.query(Problem)

    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(or_(
            func.lower(Problem.title).like(like),
            func.lower(Problem.description).like(like)
        ))

    if status:
        qry = qry.filter(Problem.status == status)
    if scope:
        qry = qry.filter(Problem.scope == scope)
    if domain:
        qry = qry.filter(Problem.domain == domain)

    # "near" = lightweight duplicate suggestion (title contains terms)
    if near:
        like = f"%{near.lower()}%"
        qry = qry.filter(func.lower(Problem.title).like(like))

    problems = qry.order_by(Problem.created_at.desc()).offset(offset).limit(limit).all()

    # annotate flags for caller
    problems = annotate_flags_for_identity(db, x_user_email, problems)

    # sort in Python to apply recency boost formula for 'trending'
    if sort == "votes":
        problems.sort(key=lambda p: (p.votes_count, p.created_at), reverse=True)
    elif sort == "new":
        problems.sort(key=lambda p: p.created_at, reverse=True)
    else:
        # trending: log(votes+1) + 0.5*severity + recency_boost
        import math
        def score(p: Problem):
            return math.log((p.votes_count or 0) + 1) + 0.5 * (p.severity or 3) + recency_boost(p.created_at)
        problems.sort(key=lambda p: (score(p), p.created_at), reverse=True)

    return problems


@router.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, db: Session = Depends(get_db), x_user_email: Optional[str] = None):
    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    # create conversation lazily if missing
    ensure_problem_conversation(db, p, creator_email=p.created_by_email)

    # flags
    p.has_voted = False
    p.is_following = False
    if x_user_email:
        p.has_voted = db.query(ProblemVote.id).filter(
            ProblemVote.problem_id == p.id,
            ProblemVote.voter_identity == x_user_email
        ).first() is not None
        p.is_following = db.query(ProblemFollow.id).filter(
            ProblemFollow.problem_id == p.id,
            ProblemFollow.identity == x_user_email
        ).first() is not None

    return p

# --- toggle helpers used by routes ---

def toggle_vote(db: Session, problem_id: int, identity: str, commit: bool = False) -> bool:
    vote = db.query(ProblemVote).filter(
        ProblemVote.problem_id == problem_id,
        ProblemVote.voter_identity == identity
    ).first()

    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    if vote:
        db.delete(vote)
        p.votes_count = max(0, (p.votes_count or 0) - 1)
        changed_to = False
    else:
        db.add(ProblemVote(problem_id=problem_id, voter_identity=identity))
        p.votes_count = (p.votes_count or 0) + 1
        changed_to = True

    if commit:
        db.commit()
    return changed_to

def toggle_follow(db: Session, problem_id: int, identity: str, commit: bool = False) -> bool:
    follow = db.query(ProblemFollow).filter(
        ProblemFollow.problem_id == problem_id,
        ProblemFollow.identity == identity
    ).first()

    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    if follow:
        db.delete(follow)
        p.followers_count = max(0, (p.followers_count or 0) - 1)
        changed_to = False
    else:
        db.add(ProblemFollow(problem_id=problem_id, identity=identity))
        p.followers_count = (p.followers_count or 0) + 1
        changed_to = True

        # If identity is a real user, add them to the conversation participants (so inbox sees it)
        if not identity.startswith("anon:"):
            user = db.query(User).filter(User.email == identity).first()
            if user and p.conversation_id:
                is_member = db.query(ConversationUser).filter(
                    ConversationUser.user_id == user.id,
                    ConversationUser.conversation_id == p.conversation_id
                ).first()
                if not is_member:
                    db.add(ConversationUser(user_id=user.id, conversation_id=p.conversation_id))

    if commit:
        db.commit()
    return changed_to

# --- actions ---

@router.post("/problems/{problem_id}/vote")
def vote_problem(problem_id: int, db: Session = Depends(get_db), x_user_email: Optional[str] = None):
    identity = get_identity_email(x_user_email)
    changed_to = toggle_vote(db, problem_id, identity, commit=True)
    return {"status": "ok", "voted": changed_to}

@router.post("/problems/{problem_id}/follow")
def follow_problem(problem_id: int, db: Session = Depends(get_db), x_user_email: Optional[str] = None):
    identity = get_identity_email(x_user_email)
    changed_to = toggle_follow(db, problem_id, identity, commit=True)
    return {"status": "ok", "following": changed_to}

# --- triage-only (you) ---

class StatusIn(BaseModel):
    status: str

@router.post("/problems/{problem_id}/status")
def update_status(problem_id: int, payload: StatusIn, db: Session = Depends(get_db), x_user_email: Optional[str] = None):
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    p.status = payload.status
    db.commit()
    return {"status": "ok"}

@router.post("/problems/{problem_id}/merge/{dup_id}")
def merge_duplicate(problem_id: int, dup_id: int, db: Session = Depends(get_db), x_user_email: Optional[str] = None):
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    master = db.query(Problem).filter(Problem.id == problem_id).first()
    dup = db.query(Problem).filter(Problem.id == dup_id).first()
    if not master or not dup:
        raise HTTPException(status_code=404, detail="Problem(s) not found")

    dup.duplicate_of_id = master.id
    db.commit()
    return {"status": "ok", "merged": dup_id, "into": problem_id}