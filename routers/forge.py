# routers/forge.py — Forge API (clean)
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field, ConfigDict, constr
from sqlalchemy import func, text, or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from routers.auth import get_current_user_dependency
from models import (
    # Core forge
    ForgeItem,
    ForgeItemVote,
    ForgeItemFollow,
    ForgePledge,
    ItemKind,
    ItemStatus,
    # Messaging (optional, kept minimal)
    InboxMessage,
    User,
    Conversation,
    ConversationUser,
    # Problems/solutions/notes
    Problem,
    Solution,
    ProblemNote,
    SolutionNote,
    SolutionVote,
)

router = APIRouter(prefix="/forge", tags=["forge"])

SYSTEM_EMAIL = "system@domain.com"

# --------------------------------------------------------------------------
# Pydantic / DTOs
# --------------------------------------------------------------------------

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# Enums mirrored on the wire as str (we’ll serialize to plain strings)
class ForgeKind(str):
    problem = "problem"
    idea = "idea"

class ForgeStatus(str):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"

class ForgeItemCreate(ORMBase):
    kind: str  # "problem" | "idea" (string to avoid enum bleed)
    title: constr(min_length=3, max_length=180)
    body: Optional[constr(max_length=5000)] = None
    domain: Optional[str] = None
    scope: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=5)
    location: Optional[str] = None
    tags: Optional[str] = None

class Ok(ORMBase):
    ok: bool = True

class PledgeIn(ORMBase):
    text: constr(min_length=3, max_length=200)

# --------------------------------------------------------------------------
# Helpers (serialization, conversations, user)
# --------------------------------------------------------------------------

def _val(x):
    """Return enum.value or primitive as-is (prevents [object Object] in JSON)."""
    return getattr(x, "value", x)

def _serialize_item(i: ForgeItem, db: Session = None) -> dict:
    username = None
    if db and i.created_by_email:
        u = db.query(User).filter(User.email == i.created_by_email).first()
        if u:
            username = getattr(u, "username", None)

    return {
        "id": i.id,
        "kind": i.kind.value if hasattr(i.kind, "value") else i.kind,
        "title": i.title,
        "body": i.body,
        "status": i.status.value if hasattr(i.status, "value") else i.status,
        "domain": i.domain,
        "scope": i.scope,
        "severity": i.severity,
        "location": i.location,
        "tags": i.tags,
        "votes_count": i.votes_count or 0,
        "followers_count": i.followers_count or 0,
        "pledges_count": i.pledges_count or 0,
        "pledges_done": i.pledges_done or 0,
        "created_by_email": i.created_by_email,
        "created_by_username": username,  # ✅
        "created_at": i.created_at,
    }

def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == SYSTEM_EMAIL).first()
    if sys:
        return sys
    sys = User(email=SYSTEM_EMAIL, username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys

def ensure_item_conversation(db: Session, item: ForgeItem) -> Conversation:
    canonical = f"forge:item:{item.id}"
    convo = db.query(Conversation).filter(Conversation.name == canonical).first()
    if not convo:
        convo = Conversation(name=canonical)
        db.add(convo)
        db.flush()

    if item.created_by_user_id:
        present = (
            db.query(ConversationUser)
            .filter_by(conversation_id=convo.id, user_id=item.created_by_user_id)
            .first()
        )
        if not present:
            db.add(ConversationUser(conversation_id=convo.id, user_id=item.created_by_user_id))

    db.commit()
    db.refresh(convo)
    return convo

def _serialize_msg(m: InboxMessage):
    u = getattr(m, "user", None)
    def _disp(u: Optional[User]) -> str:
        if not u:
            return "User"
        name = getattr(u, "username", None) or getattr(u, "display_name", None) or ""
        return name if (name and "@" not in name) else "User"
    return {
        "id": m.id,
        "content": m.content,
        "timestamp": m.timestamp,
        "read": bool(m.read),
        "from_email": getattr(u, "email", None),
        "from_username": getattr(u, "username", None),
        "from_user_id": getattr(u, "id", None),
        "from_display": _disp(u),
    }

def _optional_user_from_header(request: Request, db: Session) -> Optional[User]:
    email = (request.headers.get("x-user-email") or "").strip()
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()

def _get_problem_or_404(db: Session, problem_id: int) -> Problem:
    obj = db.query(Problem).filter(Problem.id == problem_id).first()
    if not obj:
        raise HTTPException(404, "Problem not found")
    return obj

def _get_solution_or_404(db: Session, solution_id: int) -> Solution:
    obj = db.query(Solution).filter(Solution.id == solution_id).first()
    if not obj:
        raise HTTPException(404, "Solution not found")
    return obj

def _get_problem_note_or_404(db: Session, note_id: int) -> ProblemNote:
    obj = db.query(ProblemNote).filter(ProblemNote.id == note_id).first()
    if not obj:
        raise HTTPException(404, "Problem note not found")
    return obj

def _get_solution_note_or_404(db: Session, note_id: int) -> SolutionNote:
    obj = db.query(SolutionNote).filter(SolutionNote.id == note_id).first()
    if not obj:
        raise HTTPException(404, "Solution note not found")
    return obj

def _inc_problem_notes_count(db: Session, problem_id: int, delta: int):
    db.query(Problem).filter(Problem.id == problem_id).update(
        {Problem.notes_count: Problem.notes_count + delta}
    )

def _inc_solution_notes_count(db: Session, solution_id: int, delta: int):
    db.query(Solution).filter(Solution.id == solution_id).update(
        {Solution.notes_count: Solution.notes_count + delta}
    )

def _ensure_item_for_problem(db: Session, problem: Problem) -> ForgeItem:
    """
    Find the ForgeItem that mirrors this Problem. If it doesn't exist yet
    (old legacy rows), create a minimal ForgeItem and link it.
    """
    fi = (
        db.query(ForgeItem)
        .filter(
            ForgeItem.kind == ItemKind.problem,
            ForgeItem.legacy_table == "problems",
            ForgeItem.legacy_id == problem.id,
        )
        .first()
    )
    if fi:
        return fi

    # Create a mirror ForgeItem from Problem fields
    author_user_id = None
    if problem.created_by_email:
        u = db.query(User).filter(User.email == problem.created_by_email).first()
        if u:
            author_user_id = u.id

    fi = ForgeItem(
        kind=ItemKind.problem,
        title=problem.title or f"Problem #{problem.id}",
        body=(problem.description or ""),
        domain=problem.domain,
        scope=problem.scope,
        severity=problem.severity or 3,
        status=ItemStatus.open,
        location=None,
        tags=None,
        created_by_email=problem.created_by_email,
        created_by_user_id=author_user_id,
        created_at=problem.created_at or datetime.utcnow(),
        legacy_table="problems",
        legacy_id=problem.id,
        votes_count=0,
        followers_count=0,
        pledges_count=0,
        pledges_done=0,
    )
    db.add(fi)
    db.commit()
    db.refresh(fi)
    return fi

# --------------------------------------------------------------------------
# Forge Items: list, detail, create, vote/follow/pledge, delete
# --------------------------------------------------------------------------

@router.get("/items")
def list_items(
    db: Session = Depends(get_db),
    kind: Optional[str] = Query(None),                # "problem" | "idea"
    sort: str = Query("new", pattern="^(new|top)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),              # "open" | "in_progress" | ...
    domain: Optional[str] = None,
    scope: Optional[str] = None,
    location: Optional[str] = None,
    tags: Optional[str] = None,
    severity_min: Optional[int] = Query(None, ge=1, le=5),
    severity_max: Optional[int] = Query(None, ge=1, le=5),
):
    qry = db.query(ForgeItem)

    if kind:
        qry = qry.filter(ForgeItem.kind == ItemKind(kind))
    if status:
        qry = qry.filter(ForgeItem.status == ItemStatus(status))
    if domain:
        qry = qry.filter(ForgeItem.domain == domain)
    if scope:
        qry = qry.filter(ForgeItem.scope == scope)
    if location:
        qry = qry.filter(ForgeItem.location == location)
    if tags:
        qry = qry.filter(ForgeItem.tags.ilike(f"%{tags}%"))
    if severity_min is not None:
        qry = qry.filter(ForgeItem.severity >= severity_min)
    if severity_max is not None:
        qry = qry.filter(ForgeItem.severity <= severity_max)
    if q:
        qlike = f"%{q.lower()}%"
        qry = qry.filter(
            or_(
                func.lower(ForgeItem.title).ilike(qlike),
                func.lower(ForgeItem.body).ilike(qlike),
                func.lower(ForgeItem.tags).ilike(qlike),
                func.lower(ForgeItem.location).ilike(qlike),
            )
        )

    if sort == "new":
        qry = qry.order_by(ForgeItem.created_at.desc())
    else:
        qry = qry.order_by(ForgeItem.votes_count.desc(), ForgeItem.created_at.desc())

    items = qry.offset(offset).limit(limit).all()

    out = []
    for i in items:
        d = _serialize_item(i)
        if i.kind == ItemKind.problem and getattr(i, "legacy_table", None) == "problems" and getattr(i, "legacy_id", None):
            d["problem_ref"] = {"id": i.legacy_id}
        out.append(d)
    return out

@router.get("/items/{item_id}", response_model=None)
def get_item(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    ident = (request.headers.get("x-user-email") or "").strip()
    has_voted = bool(
        ident and db.query(ForgeItemVote.id).filter_by(item_id=item_id, voter_identity=ident).first()
    )
    has_followed = bool(
        ident and db.query(ForgeItemFollow.id).filter_by(item_id=item_id, identity=ident).first()
    )

    convo = ensure_item_conversation(db, item)
    payload = _serialize_item(item)

    # username
    author = None
    if item.created_by_user_id:
        author = db.query(User).filter(User.id == item.created_by_user_id).first()
    payload["created_by_username"] = getattr(author, "username", None)

    if (
        item.kind == ItemKind.problem
        and getattr(item, "legacy_table", None) == "problems"
        and getattr(item, "legacy_id", None)
    ):
        payload["problem_ref"] = {"id": item.legacy_id}

    payload.update(
        {
            "has_voted": has_voted,
            "is_following": has_followed,
            "conversation_id": convo.id if convo else None,
        }
    )
    return payload

@router.post("/items")
def create_item(
    dto: ForgeItemCreate,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    # unwrap kind safely whether dto.kind is an Enum or a str
    kind_val = getattr(dto.kind, "value", dto.kind)

    # fetch full user to expose username in payload
    author = db.query(User).filter(User.id == user.id).first()

    # Create the ForgeItem
    item = ForgeItem(
        kind=ItemKind(kind_val),
        title=dto.title,
        body=dto.body,
        domain=dto.domain,
        scope=dto.scope,
        severity=dto.severity,
        location=dto.location,
        tags=dto.tags,
        status=ItemStatus.open,
        created_by_email=getattr(user, "email", None),
        created_by_user_id=getattr(user, "id", None),
        created_at=datetime.utcnow(),
    )
    db.add(item)
    db.flush()  # get item.id

    # If it’s a problem, also create a Problem row and link it
    if item.kind == ItemKind.problem:
        prob = Problem(
            title=item.title,
            description=item.body or "",
            domain=item.domain,
            scope=item.scope,
            severity=item.severity or 3,
            status="Open",
            created_by_email=item.created_by_email,
            created_at=datetime.utcnow(),
            votes_count=0,
            followers_count=0,
            notes_count=0,
        )
        db.add(prob)
        db.flush()
        item.legacy_table = "problems"
        item.legacy_id = prob.id

    db.commit()
    db.refresh(item)

    # Build response (plain dict) and include username + problem_ref
    out = _serialize_item(item)
    out["created_by_username"] = getattr(author, "username", None)
    if item.kind == ItemKind.problem and getattr(item, "legacy_id", None):
        out["problem_ref"] = {"id": item.legacy_id}
    return out

@router.post("/items/{item_id}/vote")
def vote_item(
    item_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    if not db.get(ForgeItem, item_id):
        raise HTTPException(404, "Item not found")

    identity = user.email or f"anon:{user.id}"
    exists = db.query(ForgeItemVote).filter_by(item_id=item_id, voter_identity=identity).first()
    if not exists:
        db.add(ForgeItemVote(item_id=item_id, voter_identity=identity))
        db.flush()
        db.execute(
            text(
                """
                UPDATE forge_items SET votes_count = (
                    SELECT COUNT(*) FROM forge_item_votes WHERE item_id = :id
                ) WHERE id = :id
                """
            ),
            {"id": item_id},
        )
        db.commit()
    return Ok()

@router.delete("/items/{item_id}/vote")
def unvote_item(
    item_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    identity = user.email or f"anon:{user.id}"
    db.query(ForgeItemVote).filter_by(item_id=item_id, voter_identity=identity).delete()
    db.execute(
        text(
            """
            UPDATE forge_items SET votes_count = (
                SELECT COUNT(*) FROM forge_item_votes WHERE item_id = :id
            ) WHERE id = :id
            """
        ),
        {"id": item_id},
    )
    db.commit()
    return Ok()

@router.post("/items/{item_id}/follow")
def follow_item(
    item_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    identity = user.email or f"anon:{user.id}"

    exists = db.query(ForgeItemFollow).filter_by(item_id=item_id, identity=identity).first()
    if not exists:
        db.add(ForgeItemFollow(item_id=item_id, identity=identity))
        db.flush()
        db.execute(
            text(
                """
                UPDATE forge_items SET followers_count = (
                    SELECT COUNT(*) FROM forge_item_follows WHERE item_id = :id
                ) WHERE id = :id
                """
            ),
            {"id": item_id},
        )

    convo = ensure_item_conversation(db, item)
    cu = db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first()
    if not cu:
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    db.commit()
    return Ok()

@router.delete("/items/{item_id}/follow")
def unfollow_item(
    item_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    identity = user.email or f"anon:{user.id}"

    db.query(ForgeItemFollow).filter_by(item_id=item_id, identity=identity).delete()
    db.execute(
        text(
            """
            UPDATE forge_items SET followers_count = (
                SELECT COUNT(*) FROM forge_item_follows WHERE item_id = :id
            ) WHERE id = :id
            """
        ),
        {"id": item_id},
    )

    convo = db.query(Conversation).filter(Conversation.name == f"forge:item:{item_id}").first()
    if convo and user.id and user.id != item.created_by_user_id:
        db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).delete()

    db.commit()
    return Ok()

@router.post("/items/{item_id}/pledges")
def add_pledge(
    item_id: int,
    dto: PledgeIn,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    if not db.get(ForgeItem, item_id):
        raise HTTPException(404, "Item not found")
    db.add(ForgePledge(item_id=item_id, user_id=user.id, text=dto.text))
    db.flush()
    db.execute(
        text(
            """
            UPDATE forge_items SET pledges_count = (
                SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id
            ) WHERE id = :id
            """
        ),
        {"id": item_id},
    )
    db.commit()
    return Ok()

@router.patch("/pledges/{pledge_id}/done")
def mark_pledge_done(
    pledge_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    p = db.get(ForgePledge, pledge_id)
    if not p:
        raise HTTPException(404, "Pledge not found")
    if p.user_id != user.id:
        raise HTTPException(403, "Only the pledge owner can mark done")
    if not p.done:
        p.done = True
        p.done_at = datetime.utcnow()
        db.flush()
        db.execute(
            text(
                """
                UPDATE forge_items SET pledges_done = (
                    SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id AND done = true
                ) WHERE id = :id
                """
            ),
            {"id": p.item_id},
        )
        db.commit()
    return Ok()

@router.get("/items/{item_id}/pledges")
def list_pledges(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # Join with User to fetch username
    pledges = (
        db.query(ForgePledge)
        .options(joinedload(ForgePledge.user))  # this ensures .user is loaded
        .filter(ForgePledge.item_id == item_id)
        .order_by(ForgePledge.created_at.asc(), ForgePledge.id.asc())
        .all()
    )

    ident = (request.headers.get("x-user-email") or "").strip().lower()

    def row(p: ForgePledge) -> dict:
        user_email = getattr(getattr(p, "user", None), "email", None)
        username = getattr(getattr(p, "user", None), "username", None)
        return {
            "id": p.id,
            "text": p.text,
            "done": bool(p.done),
            "done_at": p.done_at,
            "created_at": p.created_at,
            "user_email": user_email,
            "username": username,
            "is_mine": bool(ident and (user_email or "").lower() == ident),
        }

    return [row(p) for p in pledges]

@router.delete("/pledges/{pledge_id}")
def delete_pledge(
    pledge_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    p = db.get(ForgePledge, pledge_id)
    if not p:
        raise HTTPException(404, "Pledge not found")

    # Only creator (and optionally admin) can delete
    email = (getattr(user, "email", "") or "").lower()
    is_owner = (p.user_id == user.id)
    is_admin = (email == "sheaklipper@gmail.com")  # keep or remove if you want ONLY owner
    if not (is_owner or is_admin):
        raise HTTPException(403, "Only the pledge owner can delete")

    item_id = p.item_id

    db.delete(p)
    db.flush()

    # Recompute denorm counters on the ForgeItem
    db.execute(
        text(
            """
            UPDATE forge_items
            SET
              pledges_count = (SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id),
              pledges_done  = (SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id AND done = true)
            WHERE id = :id
            """
        ),
        {"id": item_id},
    )
    db.commit()
    return {"ok": True}

# --------------------------------------------------------------------------
# Conversations (minimal)
# --------------------------------------------------------------------------

@router.get("/items/{item_id}/conversation")
def get_item_conversation(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    convo = ensure_item_conversation(db, item)
    return {"conversation_id": convo.id}

@router.get("/items/{item_id}/conversation/messages")
def list_item_messages(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    convo = ensure_item_conversation(db, item)
    msgs = (
        db.query(InboxMessage)
        .options(joinedload(InboxMessage.user))
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc(), InboxMessage.id.asc())
        .all()
    )
    return [_serialize_msg(m) for m in msgs]

@router.post("/items/{item_id}/conversation/send")
def send_item_message(
    item_id: int,
    payload: Dict[str, str],
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    sender = payload.get("sender_email")
    content = payload.get("content", "")
    user = db.query(User).filter(User.email == sender).first()
    if not user:
        raise HTTPException(401, "Login required")

    convo = ensure_item_conversation(db, item)
    if not db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first():
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    msg = InboxMessage(
        user_id=user.id,
        content=content,
        conversation_id=convo.id,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"message": _serialize_msg(msg)}

# --------------------------------------------------------------------------
# Problems: detail, notes, solutions (+ solution notes)
# --------------------------------------------------------------------------

@router.get("/problems/{problem_id}")
def get_problem(
    problem_id: int,
    request: Request,
    db: Session = Depends(get_db),
    include_top_solutions: bool = True,
    top_n: int = 3,
):
    problem = (
        db.query(Problem)
        .options(joinedload(Problem.notes))
        .filter(Problem.id == problem_id)
        .first()
    )
    if not problem:
        raise HTTPException(404, "Problem not found")

    creator_user = None
    if problem.created_by_email:
        creator_user = db.query(User).filter(User.email == problem.created_by_email).first()

    result = {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "domain": _val(problem.domain),
        "scope": _val(problem.scope),
        "severity": problem.severity,
        "status": _val(problem.status),
        "created_by_email": problem.created_by_email,
        "created_by_username": getattr(creator_user, "username", None),
        "created_at": problem.created_at,
        "votes_count": problem.votes_count,
        "followers_count": problem.followers_count,
        "notes_count": problem.notes_count or 0,
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "is_public": n.is_public,
                "order_index": n.order_index,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "author_user_id": n.author_user_id,
            }
            for n in (problem.notes or [])
        ],
    }

    if include_top_solutions:
        sols = (
            db.query(Solution)
            .filter(Solution.problem_id == problem_id)
            .order_by(Solution.votes_count.desc(), Solution.created_at.desc())
            .limit(top_n)
            .all()
        )

        # Who am I (for has_voted)?
        ident = (request.headers.get("x-user-email") or "").strip()
        voted_ids: set[int] = set()
        if ident and sols:
            ids = [s.id for s in sols]
            voted_ids = {
                sid for (sid,) in db.query(SolutionVote.solution_id)
                .filter(SolutionVote.voter_identity == ident, SolutionVote.solution_id.in_(ids))
                .all()
            }

        def sol_user(s: Solution):
            return db.query(User).filter(User.email == s.created_by_email).first() if s.created_by_email else None

        result["top_solutions"] = [
            {
                "id": s.id,
                "problem_id": s.problem_id,
                "title": s.title,
                "description": s.description,
                "status": _val(s.status),
                "anonymous": s.anonymous,
                "created_by_email": s.created_by_email,
                "created_by_username": (getattr(sol_user(s), "username", None) if not s.anonymous else None),
                "created_at": s.created_at,
                "votes_count": s.votes_count,
                "followers_count": s.followers_count,
                "notes_count": s.notes_count,
                "featured_in_forge": s.featured_in_forge,
                "impact_score": s.impact_score,
                "has_voted": (s.id in voted_ids),
            }
            for s in sols
        ]

    return result

@router.get("/problems/{problem_id}/pledges")
def list_problem_pledges(
    problem_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    problem = _get_problem_or_404(db, problem_id)
    item = _ensure_item_for_problem(db, problem)

    pledges = (
        db.query(ForgePledge)
        .options(joinedload(ForgePledge.user))
        .filter(ForgePledge.item_id == item.id)
        .order_by(ForgePledge.created_at.asc(), ForgePledge.id.asc())
        .all()
    )

    ident = (request.headers.get("x-user-email") or "").strip().lower()

    def row(p: ForgePledge) -> dict:
        user_email = getattr(getattr(p, "user", None), "email", None)
        username = getattr(getattr(p, "user", None), "username", None)
        return {
            "id": p.id,
            "text": p.text,
            "done": bool(p.done),
            "done_at": p.done_at,
            "created_at": p.created_at,
            "user_email": user_email,
            "username": username,
            "is_mine": bool(ident and (user_email or "").lower() == ident),
        }

    return [row(p) for p in pledges]


@router.post("/problems/{problem_id}/pledges")
def add_problem_pledge(
    problem_id: int,
    dto: PledgeIn,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    problem = _get_problem_or_404(db, problem_id)
    item = _ensure_item_for_problem(db, problem)

    db.add(ForgePledge(item_id=item.id, user_id=user.id, text=dto.text))
    db.flush()
    # keep ForgeItem denorm in sync
    db.execute(
        text(
            """
            UPDATE forge_items SET pledges_count = (
                SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id
            ) WHERE id = :id
            """
        ),
        {"id": item.id},
    )
    db.execute(
        text(
            """
            UPDATE forge_items SET pledges_done = (
                SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id AND done = true
            ) WHERE id = :id
            """
        ),
        {"id": item.id},
    )
    db.commit()
    return Ok()



# Problem notes
class ProblemNoteCreate(ORMBase):
    title: Optional[str] = None
    body: str
    is_public: bool = True
    order_index: int = 0

class ProblemNoteUpdate(ORMBase):
    title: Optional[str] = None
    body: Optional[str] = None
    is_public: Optional[bool] = None
    order_index: Optional[int] = None

@router.post("/problems/{problem_id}/notes")
def create_problem_note(
    problem_id: int,
    payload: ProblemNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _get_problem_or_404(db, problem_id)
    author = _optional_user_from_header(request, db)
    note = ProblemNote(
        problem_id=problem_id,
        author_user_id=(author.id if author else None),
        title=payload.title,
        body=payload.body,
        is_public=payload.is_public,
        order_index=payload.order_index,
    )
    db.add(note)
    _inc_problem_notes_count(db, problem_id, +1)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "is_public": note.is_public,
        "order_index": note.order_index,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "author_user_id": note.author_user_id,
    }

@router.patch("/problem-notes/{note_id}")
def update_problem_note(
    note_id: int,
    payload: ProblemNoteUpdate,
    db: Session = Depends(get_db),
):
    note = _get_problem_note_or_404(db, note_id)
    if payload.title is not None:
        note.title = payload.title
    if payload.body is not None:
        note.body = payload.body
    if payload.is_public is not None:
        note.is_public = payload.is_public
    if payload.order_index is not None:
        note.order_index = payload.order_index
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "is_public": note.is_public,
        "order_index": note.order_index,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "author_user_id": note.author_user_id,
    }

@router.delete("/problem-notes/{note_id}", status_code=204)
def delete_problem_note(
    note_id: int,
    db: Session = Depends(get_db),
):
    note = _get_problem_note_or_404(db, note_id)
    pid = note.problem_id
    db.delete(note)
    _inc_problem_notes_count(db, pid, -1)
    db.commit()
    return None

# Solutions
class SolutionCreate(ORMBase):
    title: str
    description: str
    anonymous: bool = False
    created_by_email: Optional[str] = None

class SolutionPatch(ORMBase):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None   # Proposed | In Trial | Implementing | Accepted | Rejected | Archived
    featured_in_forge: Optional[bool] = None
    impact_score: Optional[float] = None

@router.post("/problems/{problem_id}/solutions")
def create_solution(
    problem_id: int,
    payload: SolutionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _get_problem_or_404(db, problem_id)
    author = _optional_user_from_header(request, db)
    created_by_email = payload.created_by_email or (author.email if author else None)
    sol = Solution(
        problem_id=problem_id,
        title=payload.title,
        description=payload.description,
        status="Proposed",
        anonymous=payload.anonymous,
        created_by_email=created_by_email,
        votes_count=0,
        followers_count=0,
        notes_count=0,
        featured_in_forge=False,
        impact_score=0.0,
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)
    return {
        "id": sol.id,
        "problem_id": sol.problem_id,
        "title": sol.title,
        "description": sol.description,
        "status": _val(sol.status),
        "anonymous": sol.anonymous,
        "created_by_email": sol.created_by_email,
        "created_at": sol.created_at,
        "votes_count": sol.votes_count,
        "followers_count": sol.followers_count,
        "notes_count": sol.notes_count,
        "featured_in_forge": sol.featured_in_forge,
        "impact_score": sol.impact_score,
    }

@router.patch("/solutions/{solution_id}")
def patch_solution(
    solution_id: int,
    payload: SolutionPatch,
    db: Session = Depends(get_db),
):
    sol = _get_solution_or_404(db, solution_id)
    if payload.title is not None:
        sol.title = payload.title
    if payload.description is not None:
        sol.description = payload.description
    if payload.status is not None:
        sol.status = payload.status
    if payload.featured_in_forge is not None:
        sol.featured_in_forge = payload.featured_in_forge
    if payload.impact_score is not None:
        sol.impact_score = float(payload.impact_score)
    db.commit()
    db.refresh(sol)
    return {
        "id": sol.id,
        "problem_id": sol.problem_id,
        "title": sol.title,
        "description": sol.description,
        "status": _val(sol.status),
        "anonymous": sol.anonymous,
        "created_by_email": sol.created_by_email,
        "created_at": sol.created_at,
        "votes_count": sol.votes_count,
        "followers_count": sol.followers_count,
        "notes_count": sol.notes_count,
        "featured_in_forge": sol.featured_in_forge,
        "impact_score": sol.impact_score,
    }

@router.post("/solutions/{solution_id}/vote")
def vote_solution(
    solution_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    sol = db.get(Solution, solution_id)
    if not sol:
        raise HTTPException(404, "Solution not found")

    identity = user.email or f"anon:{user.id}"
    exists = db.query(SolutionVote).filter_by(
        solution_id=solution_id, voter_identity=identity
    ).first()
    if not exists:
        db.add(SolutionVote(solution_id=solution_id, voter_identity=identity))
        db.flush()
        db.execute(
            text("""
                UPDATE solutions SET votes_count = (
                  SELECT COUNT(*) FROM solution_votes WHERE solution_id = :id
                ) WHERE id = :id
            """),
            {"id": solution_id},
        )
        db.commit()
    return {"ok": True}


@router.delete("/solutions/{solution_id}/vote")
def unvote_solution(
    solution_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    sol = db.get(Solution, solution_id)
    if not sol:
        raise HTTPException(404, "Solution not found")

    identity = user.email or f"anon:{user.id}"
    db.query(SolutionVote).filter_by(
        solution_id=solution_id, voter_identity=identity
    ).delete()

    db.execute(
        text("""
            UPDATE solutions SET votes_count = (
              SELECT COUNT(*) FROM solution_votes WHERE solution_id = :id
            ) WHERE id = :id
        """),
        {"id": solution_id},
    )
    db.commit()
    return {"ok": True}

# Solution notes
class SolutionNoteCreate(ORMBase):
    title: Optional[str] = None
    body: str
    is_public: bool = True
    order_index: int = 0

class SolutionNoteUpdate(ORMBase):
    title: Optional[str] = None
    body: Optional[str] = None
    is_public: Optional[bool] = None
    order_index: Optional[int] = None

@router.post("/solutions/{solution_id}/notes")
def create_solution_note(
    solution_id: int,
    payload: SolutionNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _get_solution_or_404(db, solution_id)
    author = _optional_user_from_header(request, db)
    note = SolutionNote(
        solution_id=solution_id,
        author_user_id=(author.id if author else None),
        title=payload.title,
        body=payload.body,
        is_public=payload.is_public,
        order_index=payload.order_index,
    )
    db.add(note)
    _inc_solution_notes_count(db, solution_id, +1)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "is_public": note.is_public,
        "order_index": note.order_index,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "author_user_id": note.author_user_id,
    }

@router.patch("/solution-notes/{note_id}")
def update_solution_note(
    note_id: int,
    payload: SolutionNoteUpdate,
    db: Session = Depends(get_db),
):
    note = _get_solution_note_or_404(db, note_id)
    if payload.title is not None:
        note.title = payload.title
    if payload.body is not None:
        note.body = payload.body
    if payload.is_public is not None:
        note.is_public = payload.is_public
    if payload.order_index is not None:
        note.order_index = payload.order_index
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "is_public": note.is_public,
        "order_index": note.order_index,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "author_user_id": note.author_user_id,
    }

@router.delete("/solution-notes/{note_id}", status_code=204)
def delete_solution_note(
    note_id: int,
    db: Session = Depends(get_db),
):
    note = _get_solution_note_or_404(db, note_id)
    sid = note.solution_id
    db.delete(note)
    _inc_solution_notes_count(db, sid, -1)
    db.commit()
    return None

# --------------------------------------------------------------------------
# Misc: resolve mapping (ForgeItem -> Problem)
# --------------------------------------------------------------------------

@router.get("/items/{item_id}/problem")
def resolve_problem(item_id: int, db: Session = Depends(get_db)):
    fi = db.query(ForgeItem).get(item_id)
    if (
        not fi
        or fi.kind != ItemKind.problem
        or fi.legacy_table != "problems"
        or not fi.legacy_id
    ):
        raise HTTPException(404, "No problem mapping")
    return {"id": fi.legacy_id}

@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    email = (getattr(user, "email", None) or "").lower()
    is_creator = email and email == (item.created_by_email or "").lower()
    is_shea = email == "sheaklipper@gmail.com"
    if not (is_creator or is_shea):
        raise HTTPException(403, "Not authorized to delete this item")

    # delete related problem if this item represents a problem
    if item.kind == ItemKind.problem and getattr(item, "legacy_table", None) == "problems" and getattr(item, "legacy_id", None):
        prob = db.query(Problem).filter(Problem.id == item.legacy_id).first()
        if prob:
            # delete solution notes
            sols = db.query(Solution).filter(Solution.problem_id == prob.id).all()
            for s in sols:
                db.query(SolutionNote).filter(SolutionNote.solution_id == s.id).delete()
            # delete solutions
            db.query(Solution).filter(Solution.problem_id == prob.id).delete()
            # delete problem notes
            db.query(ProblemNote).filter(ProblemNote.problem_id == prob.id).delete()
            # finally delete problem
            db.delete(prob)

    # delete item children
    db.query(ForgePledge).filter_by(item_id=item_id).delete()
    db.query(ForgeItemFollow).filter_by(item_id=item_id).delete()
    db.query(ForgeItemVote).filter_by(item_id=item_id).delete()

    db.delete(item)
    db.commit()
    return {"ok": True}

@router.get("/problems/{problem_id}/conversation")
def get_problem_conversation(problem_id: int, db: Session = Depends(get_db)):
    problem = _get_problem_or_404(db, problem_id)
    item = _ensure_item_for_problem(db, problem)
    convo = ensure_item_conversation(db, item)
    return {"conversation_id": convo.id}

@router.get("/problems/{problem_id}/conversation/messages")
def list_problem_messages(problem_id: int, db: Session = Depends(get_db)):
    problem = _get_problem_or_404(db, problem_id)
    item = _ensure_item_for_problem(db, problem)
    convo = ensure_item_conversation(db, item)
    msgs = (
        db.query(InboxMessage)
        .options(joinedload(InboxMessage.user))
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc(), InboxMessage.id.asc())
        .all()
    )
    return [_serialize_msg(m) for m in msgs]

@router.post("/problems/{problem_id}/conversation/send")
def send_problem_message(
    problem_id: int,
    payload: Dict[str, str],
    db: Session = Depends(get_db),
):
    problem = _get_problem_or_404(db, problem_id)
    item = _ensure_item_for_problem(db, problem)

    sender = payload.get("sender_email")
    content = payload.get("content", "")
    user = db.query(User).filter(User.email == sender).first()
    if not user:
        raise HTTPException(401, "Login required")

    convo = ensure_item_conversation(db, item)
    if not db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first():
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    msg = InboxMessage(
        user_id=user.id,
        content=content,
        conversation_id=convo.id,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"message": _serialize_msg(msg)}