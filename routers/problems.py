# problems.py
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import math

from database import get_db
from models import (
    Problem, ProblemVote, ProblemFollow,
    User, Conversation, ConversationUser, InboxMessage
)

router = APIRouter()

TRIAGER_EMAILS = {"sheaklipper@gmail.com"}  # you’re the only triager for now

ALLOWED_STATUSES = {
  "Open","Triaged","In Discovery","In Design","In Experiment","In Rollout","Solved","Archived"
}

# Allowed statuses for solutions
ALLOWED_SOLUTION_STATUSES = {"Proposed", "In Trial", "Implementing", "Accepted", "Rejected", "Archived"}


# ---------- helpers ----------

def get_identity_email(x_user_email: Optional[str]) -> str:
    """
    Standardize on a single "identity" string:
    - logged-in: real email
    - anonymous: "anon:{uuid}"
    """
    if not x_user_email:
        raise HTTPException(status_code=400, detail="x-user-email header required (email or anon:{uuid})")
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

    votes = (
        db.query(ProblemVote.problem_id)
        .filter(ProblemVote.problem_id.in_(ids), ProblemVote.voter_identity == identity)
        .all()
    )
    follows = (
        db.query(ProblemFollow.problem_id)
        .filter(ProblemFollow.problem_id.in_(ids), ProblemFollow.identity == identity)
        .all()
    )

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

def ensure_solution_conversation(db: Session, solution, creator_email: Optional[str]):
    if solution.conversation_id:
        convo = db.query(Conversation).filter(Conversation.id == solution.conversation_id).first()
        if convo:
            return convo

    name = f"solution:{solution.id}:{slugify(solution.title)}"
    convo = Conversation(name=name)
    db.add(convo)
    db.flush()

    sys_user = get_or_create_system_user(db)
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))

    if creator_email and not (creator_email or "").startswith("anon:"):
        user = db.query(User).filter(User.email == creator_email).first()
        if user:
            db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))

    # seed message in the solution convo
    db.add(InboxMessage(
        user_id=sys_user.id,
        content=f"New solution proposed: “{solution.title}”",
        timestamp=datetime.utcnow(),
        conversation_id=convo.id
    ))

    db.commit()
    db.refresh(convo)

    solution.conversation_id = convo.id
    db.commit()
    db.refresh(solution)
    return convo


def annotate_solution_flags_for_identity(db: Session, identity: Optional[str], solutions):
    if not identity or not solutions:
        for s in solutions:
            s.has_voted = False
            s.is_following = False
        return solutions

    ids = [s.id for s in solutions]
    from models import SolutionVote, SolutionFollow  # if not already imported at top

    v_ids = db.query(SolutionVote.solution_id).filter(
        SolutionVote.solution_id.in_(ids),
        SolutionVote.voter_identity == identity
    ).all()
    f_ids = db.query(SolutionFollow.solution_id).filter(
        SolutionFollow.solution_id.in_(ids),
        SolutionFollow.identity == identity
    ).all()

    voted = {i for (i,) in v_ids}
    followed = {i for (i,) in f_ids}

    for s in solutions:
        s.has_voted = s.id in voted
        s.is_following = s.id in followed

    return solutions

def toggle_solution_vote(db: Session, solution_id: int, identity: str, commit: bool = False) -> bool:
    from models import Solution, SolutionVote

    s = db.query(Solution).filter(Solution.id == solution_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Solution not found")

    v = db.query(SolutionVote).filter(
        SolutionVote.solution_id == solution_id,
        SolutionVote.voter_identity == identity
    ).first()

    if v:
        db.delete(v)
        s.votes_count = max(0, (s.votes_count or 0) - 1)
        changed_to = False
    else:
        db.add(SolutionVote(solution_id=solution_id, voter_identity=identity))
        s.votes_count = (s.votes_count or 0) + 1
        changed_to = True

    if commit:
        db.commit()
    return changed_to


def toggle_solution_follow(db: Session, solution_id: int, identity: str, commit: bool = False) -> bool:
    from models import Solution, SolutionFollow

    s = db.query(Solution).filter(Solution.id == solution_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Solution not found")

    f = db.query(SolutionFollow).filter(
        SolutionFollow.solution_id == solution_id,
        SolutionFollow.identity == identity
    ).first()

    if f:
        db.delete(f)
        s.followers_count = max(0, (s.followers_count or 0) - 1)
        changed_to = False
    else:
        db.add(SolutionFollow(solution_id=solution_id, identity=identity))
        s.followers_count = (s.followers_count or 0) + 1
        changed_to = True

        # add real users to the solution conversation
        if not identity.startswith("anon:") and s.conversation_id:
            user = db.query(User).filter(User.email == identity).first()
            if user:
                is_member = db.query(ConversationUser).filter(
                    ConversationUser.user_id == user.id,
                    ConversationUser.conversation_id == s.conversation_id
                ).first()
                if not is_member:
                    db.add(ConversationUser(user_id=user.id, conversation_id=s.conversation_id))

    if commit:
        db.commit()
    return changed_to

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
    severity: Optional[int] = None          # nullable in DB -> optional here
    votes_count: Optional[int] = 0          # nullable in DB -> optional here
    followers_count: Optional[int] = 0      # nullable in DB -> optional here
    created_at: datetime
    conversation_id: Optional[int] = None
    # client-facing flags
    has_voted: bool = False
    is_following: bool = False
    created_by_email: Optional[str] = None
    duplicate_of_id: Optional[int] = None
    accepted_solution_id: Optional[int] = None         # NEW
    solved_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2; use from_attributes=True for v1

class ProblemCreateIn(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=8000)
    domain: Optional[str] = None
    scope: str = Field("Systemic", pattern="^(Personal|Community|Systemic)$")
    severity: int = Field(3, ge=1, le=5)
    anonymous: bool = False

class SolutionCreateIn(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=50, max_length=10000)
    anonymous: bool = False


class SolutionOut(BaseModel):
    id: int
    problem_id: int
    title: str
    description: str
    status: str
    votes_count: int = 0
    followers_count: int = 0
    created_at: datetime
    conversation_id: Optional[int] = None
    created_by_email: Optional[str] = None
    # flags
    has_voted: bool = False
    is_following: bool = False

    class Config:
        from_attributes = True


# ---------- toggle helpers used by routes ----------

def toggle_vote(db: Session, problem_id: int, identity: str, commit: bool = False) -> bool:
    vote = (
        db.query(ProblemVote)
        .filter(ProblemVote.problem_id == problem_id, ProblemVote.voter_identity == identity)
        .first()
    )

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
    follow = (
        db.query(ProblemFollow)
        .filter(ProblemFollow.problem_id == problem_id, ProblemFollow.identity == identity)
        .first()
    )

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
        if not identity.startswith("anon:") and p.conversation_id:
            user = db.query(User).filter(User.email == identity).first()
            if user:
                is_member = (
                    db.query(ConversationUser)
                    .filter(
                        ConversationUser.user_id == user.id,
                        ConversationUser.conversation_id == p.conversation_id,
                    )
                    .first()
                )
                if not is_member:
                    db.add(ConversationUser(user_id=user.id, conversation_id=p.conversation_id))

    if commit:
        db.commit()
    return changed_to


# ---------- routes ----------

@router.post("/problems", response_model=ProblemOut)
def create_problem(
    payload: ProblemCreateIn,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    identity = get_identity_email(x_user_email)  # real email or anon:{uuid}
    created_by = None if payload.anonymous or identity.startswith("anon:") else identity

    problem = Problem(
        title=payload.title.strip(),
        description=payload.description.strip(),
        domain=(payload.domain or "").strip() or None,
        scope=payload.scope or "Systemic",
        severity=int(payload.severity or 3),
        status="Open",
        anonymous=bool(payload.anonymous),
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
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    q: Optional[str] = None,
    status: Optional[str] = None,
    scope: Optional[str] = None,
    domain: Optional[str] = None,
    sort: Optional[str] = "trending",     # 'trending' | 'votes' | 'new'
    near: Optional[str] = None,           # duplicate suggestion helper
    limit: int = 50,
    offset: int = 0,
):
    qry = db.query(Problem)

    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(or_(
            func.lower(Problem.title).like(like),
            func.lower(Problem.description).like(like),
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

    problems = (
        qry.order_by(Problem.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # annotate flags for caller
    problems = annotate_flags_for_identity(db, x_user_email, problems)

    # sort in Python to apply recency boost formula for 'trending'
    

    now = datetime.utcnow()  # compute once per request

    def score(p: Problem):
        # Age penalty: slowly pushes very old, low-vote items down; caps after ~6 months
        age_days = (now - p.created_at).days if p.created_at else 0
        age_penalty = -0.02 * min(age_days, 180)

        # Clamp severity to [1,5] to avoid weird data skew
        sev = max(min(p.severity or 3, 5), 1)

        return (
            math.log((p.votes_count or 0) + 1)
            + 0.5 * sev
            + recency_boost(p.created_at)
            + age_penalty
        )

    if sort == "votes":
        problems.sort(key=lambda p: ((p.votes_count or 0), p.created_at), reverse=True)
    elif sort == "new":
        problems.sort(key=lambda p: p.created_at, reverse=True)
    else:
        # trending
        problems.sort(key=lambda p: (score(p), p.created_at), reverse=True)

    return problems


@router.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    # create conversation lazily if missing
    ensure_problem_conversation(db, p, creator_email=p.created_by_email)

    # flags for caller
    if x_user_email:
        p.has_voted = (
            db.query(ProblemVote.id)
            .filter(
                ProblemVote.problem_id == p.id,
                ProblemVote.voter_identity == x_user_email,
            )
            .first()
            is not None
        )
        p.is_following = (
            db.query(ProblemFollow.id)
            .filter(
                ProblemFollow.problem_id == p.id,
                ProblemFollow.identity == x_user_email,
            )
            .first()
            is not None
        )
    else:
        p.has_voted = False
        p.is_following = False

    return p

@router.delete("/problems/{problem_id}")
def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(None),  # <-- read header properly
):
    if not x_user_email:
        raise HTTPException(status_code=400, detail="x-user-email required")

    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    is_creator = (p.created_by_email and x_user_email == p.created_by_email)
    is_triager = x_user_email in TRIAGER_EMAILS
    if not (is_creator or is_triager):
        raise HTTPException(status_code=403, detail="Not authorized to delete")

    db.delete(p)  # votes/follows should cascade
    db.commit()
    return {"status": "ok"}


@router.post("/problems/{problem_id}/vote")
def vote_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    identity = get_identity_email(x_user_email)
    changed_to = toggle_vote(db, problem_id, identity, commit=True)
    return {"status": "ok", "voted": changed_to}


@router.post("/problems/{problem_id}/follow")
def follow_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    identity = get_identity_email(x_user_email)
    if identity.startswith("anon:"):
        # Not logged in → cannot follow
        raise HTTPException(status_code=401, detail="Login required to follow")

    changed_to = toggle_follow(db, problem_id, identity, commit=True)
    return {"status": "ok", "following": changed_to}


# ---------- triage-only (you) ----------

class StatusIn(BaseModel):
    status: str


@router.post("/problems/{problem_id}/status")
def update_status(
    problem_id: int,
    payload: StatusIn,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    # only triager(s)
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    new_status = (payload.status or "").strip()
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    old_status = p.status
    if old_status == new_status:
        # no-op; nothing to announce
        return {"status": "ok", "from": old_status, "to": new_status}

    p.status = new_status
    db.add(p)

    # Announce into the conversation so followers get the update
    if p.conversation_id:
        sys_user = get_or_create_system_user(db)
        db.add(InboxMessage(
            user_id=sys_user.id,
            content=f"Status changed: {old_status} → {new_status}",
            timestamp=datetime.utcnow(),
            conversation_id=p.conversation_id
        ))

    db.commit()
    return {"status": "ok", "from": old_status, "to": new_status}


@router.post("/problems/{problem_id}/merge/{dup_id}")
def merge_duplicate(
    problem_id: int,
    dup_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    # only triager(s)
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    if problem_id == dup_id:
        raise HTTPException(status_code=400, detail="Cannot merge a problem into itself")

    master = db.query(Problem).filter(Problem.id == problem_id).first()
    dup = db.query(Problem).filter(Problem.id == dup_id).first()
    if not master or not dup:
        raise HTTPException(status_code=404, detail="Problem(s) not found")

    # --- transfer votes (dedupe on unique constraint) ---
    dup_vote_idents = [
        row[0] for row in db.query(ProblemVote.voter_identity)
        .filter(ProblemVote.problem_id == dup.id).all()
    ]
    for ident in set(dup_vote_idents):
        exists = db.query(ProblemVote.id).filter(
            ProblemVote.problem_id == master.id,
            ProblemVote.voter_identity == ident
        ).first()
        if not exists:
            db.add(ProblemVote(problem_id=master.id, voter_identity=ident))

    # --- transfer follows (dedupe on unique constraint) ---
    dup_follow_idents = [
        row[0] for row in db.query(ProblemFollow.identity)
        .filter(ProblemFollow.problem_id == dup.id).all()
    ]
    for ident in set(dup_follow_idents):
        exists = db.query(ProblemFollow.id).filter(
            ProblemFollow.problem_id == master.id,
            ProblemFollow.identity == ident
        ).first()
        if not exists:
            db.add(ProblemFollow(problem_id=master.id, identity=ident))

    # --- recalc counts on master ---
    master.votes_count = db.query(func.count(ProblemVote.id))\
        .filter(ProblemVote.problem_id == master.id).scalar() or 0
    master.followers_count = db.query(func.count(ProblemFollow.id))\
        .filter(ProblemFollow.problem_id == master.id).scalar() or 0
    db.add(master)

    # --- move conversation participants from dup -> master ---
    if dup.conversation_id and master.conversation_id:
        uids = [
            row[0] for row in db.query(ConversationUser.user_id)
            .filter(ConversationUser.conversation_id == dup.conversation_id).all()
        ]
        for uid in set(uids):
            present = db.query(ConversationUser.id).filter(
                ConversationUser.user_id == uid,
                ConversationUser.conversation_id == master.conversation_id
            ).first()
            if not present:
                db.add(ConversationUser(user_id=uid, conversation_id=master.conversation_id))

    # --- post system messages in both conversations ---
    sys_user = get_or_create_system_user(db)
    if master.conversation_id:
        db.add(InboxMessage(
            user_id=sys_user.id,
            content=f"Merged problem #{dup.id} into this one.",
            timestamp=datetime.utcnow(),
            conversation_id=master.conversation_id
        ))
    if dup.conversation_id:
        db.add(InboxMessage(
            user_id=sys_user.id,
            content=f"This problem was merged into #{master.id}. Further discussion continues there.",
            timestamp=datetime.utcnow(),
            conversation_id=dup.conversation_id
        ))

    # mark duplicate
    dup.duplicate_of_id = master.id
    db.add(dup)

    db.commit()
    return {
        "status": "ok",
        "merged": dup_id,
        "into": problem_id,
        "master_counts": {"votes": master.votes_count, "followers": master.followers_count},
    }


# --- SOLUTIONS ---

@router.post("/problems/{problem_id}/solutions", response_model=SolutionOut)
def create_solution(
    problem_id: int,
    payload: SolutionCreateIn,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    from models import Solution

    identity = get_identity_email(x_user_email)
    created_by = None if payload.anonymous or identity.startswith("anon:") else identity

    # ensure problem exists
    p = db.query(Problem).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")

    # (optional) require login to propose solutions
    if identity.startswith("anon:"):
        raise HTTPException(status_code=401, detail="Login required to propose a solution")

    s = Solution(
        problem_id=p.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status="Proposed",
        anonymous=bool(payload.anonymous),
        created_by_email=created_by,
        created_at=datetime.utcnow(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # conversation + participants
    ensure_solution_conversation(db, s, creator_email=created_by)

    # auto-vote & follow by submitter
    _ = toggle_solution_vote(db, s.id, identity, commit=True)
    _ = toggle_solution_follow(db, s.id, identity, commit=True)

    # announce into the problem conversation
    if p.conversation_id:
        sys = get_or_create_system_user(db)
        db.add(InboxMessage(
            user_id=sys.id,
            content=f"New solution proposed for this problem: “{s.title}”",
            timestamp=datetime.utcnow(),
            conversation_id=p.conversation_id
        ))
        db.commit()

    s.has_voted = True
    s.is_following = True
    return s


@router.get("/problems/{problem_id}/solutions", response_model=List[SolutionOut])
def list_solutions_for_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    sort: Optional[str] = "trending",     # 'trending' | 'votes' | 'new'
):
    from models import Solution

    # ensure problem exists
    if not db.query(Problem.id).filter(Problem.id == problem_id).first():
        raise HTTPException(status_code=404, detail="Problem not found")

    solutions = db.query(Solution).filter(Solution.problem_id == problem_id).all()

    # flags
    annotate_solution_flags_for_identity(db, x_user_email, solutions)

    # sort
    import math
    def recency(created_at: datetime) -> float:
        delta = datetime.utcnow() - created_at
        if delta.days < 7: return 1.0
        if delta.days < 30: return 0.5
        return 0.0

    def score(s):
        return math.log((s.votes_count or 0) + 1) + 0.5 * recency(s.created_at)

    if sort == "votes":
        solutions.sort(key=lambda s: ((s.votes_count or 0), s.created_at), reverse=True)
    elif sort == "new":
        solutions.sort(key=lambda s: s.created_at, reverse=True)
    else:
        solutions.sort(key=lambda s: (score(s), s.created_at), reverse=True)

    # pin accepted solution on top if present
    prob = db.query(Problem).filter(Problem.id == problem_id).first()
    if prob and prob.accepted_solution_id:
        solutions.sort(key=lambda s: (s.id == prob.accepted_solution_id, ), reverse=True)

    return solutions


@router.get("/solutions/{solution_id}", response_model=SolutionOut)
def get_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    from models import Solution
    s = db.query(Solution).filter(Solution.id == solution_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Solution not found")

    ensure_solution_conversation(db, s, creator_email=s.created_by_email)

    # flags
    if x_user_email:
        from models import SolutionVote, SolutionFollow
        s.has_voted = db.query(SolutionVote.id).filter(
            SolutionVote.solution_id == s.id,
            SolutionVote.voter_identity == x_user_email
        ).first() is not None
        s.is_following = db.query(SolutionFollow.id).filter(
            SolutionFollow.solution_id == s.id,
            SolutionFollow.identity == x_user_email
        ).first() is not None
    else:
        s.has_voted = False
        s.is_following = False

    return s


@router.post("/solutions/{solution_id}/vote")
def vote_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    identity = get_identity_email(x_user_email)
    changed = toggle_solution_vote(db, solution_id, identity, commit=True)
    return {"status": "ok", "voted": changed}


@router.post("/solutions/{solution_id}/follow")
def follow_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    identity = get_identity_email(x_user_email)
    if identity.startswith("anon:"):
        raise HTTPException(status_code=401, detail="Login required to follow")
    changed = toggle_solution_follow(db, solution_id, identity, commit=True)
    return {"status": "ok", "following": changed}


class SolutionStatusIn(BaseModel):
    status: str

@router.post("/solutions/{solution_id}/status")
def update_solution_status(
    solution_id: int,
    payload: SolutionStatusIn,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    from models import Solution
    s = db.query(Solution).filter(Solution.id == solution_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Solution not found")

    new_status = (payload.status or "").strip()
    if new_status not in ALLOWED_SOLUTION_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    old = s.status
    if old == new_status:
        return {"status": "ok", "from": old, "to": new_status}

    s.status = new_status
    db.add(s)

    # announce in its conversation
    if s.conversation_id:
        sys = get_or_create_system_user(db)
        db.add(InboxMessage(
            user_id=sys.id,
            content=f"Solution status changed: {old} → {new_status}",
            timestamp=datetime.utcnow(),
            conversation_id=s.conversation_id
        ))

    db.commit()
    return {"status": "ok", "from": old, "to": new_status}

@router.post("/problems/{problem_id}/accept/{solution_id}")
def accept_solution(
    problem_id: int,
    solution_id: int,
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    if x_user_email not in TRIAGER_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")

    from models import Solution
    p = db.query(Problem).filter(Problem.id == problem_id).first()
    s = db.query(Solution).filter(Solution.id == solution_id, Solution.problem_id == problem_id).first()

    if not p or not s:
        raise HTTPException(status_code=404, detail="Problem or Solution not found")

    # update problem
    p.accepted_solution_id = s.id
    p.solved_at = datetime.utcnow()
    p.status = "Solved"
    db.add(p)

    # mark solution accepted
    s.status = "Accepted"
    db.add(s)

    # system messages to both convos
    sys = get_or_create_system_user(db)
    if p.conversation_id:
        db.add(InboxMessage(
            user_id=sys.id,
            content=f"✅ Accepted solution “{s.title}”. Problem marked Solved.",
            timestamp=datetime.utcnow(),
            conversation_id=p.conversation_id
        ))
    if s.conversation_id:
        db.add(InboxMessage(
            user_id=sys.id,
            content=f"✅ This solution was accepted for Problem #{p.id}.",
            timestamp=datetime.utcnow(),
            conversation_id=s.conversation_id
        ))

    db.commit()
    return {"status": "ok", "accepted_solution_id": s.id}