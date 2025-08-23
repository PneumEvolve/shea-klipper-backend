# forge.py (FastAPI Router for Forge)
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy.orm import Session, joinedload, aliased, selectinload
from pydantic import BaseModel, Field, constr
from enum import Enum
from models import ForgeIdea, ForgeVote, ForgeWorker, InboxMessage, User, Conversation, ConversationUser, ForgeItem, ForgeItemVote, ForgeItemFollow, ForgePledge, ItemKind, ItemStatus
from database import get_db
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import func, desc, text, or_, and_
import uuid
from routers.auth import get_current_user_dependency

router = APIRouter(prefix="/forge", tags=["forge"])

SYSTEM_EMAIL = "system@domain.com"

# === Pydantic Schemas ===
# mirror your DB enums
class ForgeKind(str, Enum):
    problem = "problem"
    idea = "idea"

class ForgeStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"

class ForgeItemCreate(BaseModel):
    kind: ForgeKind
    title: constr(min_length=3, max_length=180)
    body: Optional[constr(max_length=5000)] = None
    domain: Optional[str] = None
    scope: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=5)
    location: Optional[str] = None
    tags: Optional[str] = None

class ForgeItemOut(BaseModel):
    id: int
    kind: ForgeKind
    title: str
    body: Optional[str] = None
    status: ForgeStatus
    domain: Optional[str] = None
    scope: Optional[str] = None
    severity: Optional[int] = None
    location: Optional[str] = None
    tags: Optional[str] = None
    votes_count: int
    followers_count: int
    pledges_count: int
    pledges_done: int
    created_by_email: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class PledgeIn(BaseModel):
    text: constr(min_length=3, max_length=200)

class Ok(BaseModel):
    ok: bool = True

class IdeaIn(BaseModel):
    title: str
    description: str

class IdeaOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    votes: int
    creator_email: str

class ForgeIdeaNoteBase(BaseModel):
    content: str

    class Config:
        from_attributes = True  # Ensure Pydantic models can handle SQLAlchemy models


class ForgeIdeaNoteCreate(ForgeIdeaNoteBase):
    idea_id: int  # Only need content and idea_id for creation


class ForgeIdeaNote(ForgeIdeaNoteBase):
    id: Optional[int]  # Will be added after creation in the database
    idea_id: int

    class Config:
        from_attributes = True  # Enable ORM mode to handle SQLAlchemy model ORM Mode renamed from_attributes

class IdeaStatus(str, Enum):
    Proposed = "Proposed"
    Brainstorming = "Brainstorming"
    Working = "Working On"
    Complete = "Complete"

class IdeaStatusUpdate(BaseModel):
    status: IdeaStatus

class ForgeItemDetail(ForgeItemOut):
    has_voted: bool = False
    has_followed: bool = False

class ForgeItemDetailOut(ForgeItemOut):
    has_voted: bool = False
    is_following: bool = False
    conversation_id: int | None = None

class SendIn(BaseModel):
    sender_email: str
    content: constr(min_length=1, max_length=5000)

def _serialize_item(i: ForgeItem) -> Dict:
    # Safe serializer that tolerates SA enums or plain strings
    kind = i.kind.value if hasattr(i.kind, "value") else i.kind
    status = i.status.value if hasattr(i.status, "value") else i.status
    return {
        "id": i.id,
        "kind": kind,
        "title": i.title,
        "body": i.body,
        "status": status,
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



def find_existing_system_convo(db: Session, user: User) -> Conversation | None:
    """
    Try to find a System DM by:
      1) canonical name: system:{user.email}
      2) any conversation that has BOTH (System, user) as participants
    """
    canonical = f"system:{user.email}"
    convo = db.query(Conversation).filter(Conversation.name == canonical).first()
    if convo:
        return convo

    sys_user = get_or_create_system_user(db)
    cu1 = aliased(ConversationUser)
    cu2 = aliased(ConversationUser)

    return (
        db.query(Conversation)
        .join(cu1, cu1.conversation_id == Conversation.id)
        .join(cu2, cu2.conversation_id == Conversation.id)
        .filter(cu1.user_id == user.id, cu2.user_id == sys_user.id)
        .first()
    )

def ensure_system_conversation(db: Session, user: User) -> Conversation:
    """
    Idempotent: reuses an existing System DM if present; otherwise creates one.
    Also normalizes the name to system:{user.email} and ensures both participants exist.
    """
    sys_user = get_or_create_system_user(db)
    convo = find_existing_system_convo(db, user)

    if convo:
        # normalize name if it wasn't in canonical form
        canonical = f"system:{user.email}"
        if (convo.name or "") != canonical:
            convo.name = canonical
        # ensure both participants exist
        existing = (
            db.query(ConversationUser)
            .filter(ConversationUser.conversation_id == convo.id,
                    ConversationUser.user_id.in_([sys_user.id, user.id]))
            .all()
        )
        present = {cu.user_id for cu in existing}
        if sys_user.id not in present:
            db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))
        if user.id not in present:
            db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
        db.commit()
        db.refresh(convo)
        return convo

    # create new canonical convo
    convo = Conversation(name=f"system:{user.email}")
    db.add(convo)
    db.flush()
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.commit()
    db.refresh(convo)
    return convo

def ensure_item_conversation(db: Session, item: ForgeItem) -> Conversation:
    """
    Idempotently create/find the conversation for this Forge item.
    Name: forge:item:{id}. Ensure creator is a participant.
    """
    canonical = f"forge:item:{item.id}"
    convo = db.query(Conversation).filter(Conversation.name == canonical).first()
    if not convo:
        convo = Conversation(name=canonical)
        db.add(convo)
        db.flush()

    # ensure creator is in the room
    if item.created_by_user_id:
        present = db.query(ConversationUser).filter_by(
            conversation_id=convo.id, user_id=item.created_by_user_id
        ).first()
        if not present:
            db.add(ConversationUser(conversation_id=convo.id, user_id=item.created_by_user_id))

    db.commit()
    db.refresh(convo)
    return convo

def resolve_identity(request: Request) -> str:
    ident = request.headers.get("x-user-email")
    if ident and ident.strip():
        return ident.strip()
    legacy = request.headers.get("x-user-id")
    if legacy and legacy.strip():
        return f"anon:{legacy.strip()}"
    raise HTTPException(status_code=401, detail="Missing identity")

def _msg_display_for_user(u: User | None) -> str:
    if not u:
        return "User"
    # prefer username/display that isn't an email-looking string
    name = getattr(u, "username", None) or getattr(u, "display_name", None) or ""
    if name and "@" not in name:
        return name
    return "User"

def _serialize_msg(m: InboxMessage):
    u = getattr(m, "user", None)
    return {
        "id": m.id,
        "content": m.content,
        "timestamp": m.timestamp,
        "read": bool(m.read),
        "from_email": getattr(u, "email", None),
        "from_username": getattr(u, "username", None),
        "from_user_id": getattr(u, "id", None),
        "from_display": _msg_display_for_user(u),
    }

@router.get("/items", response_model=List[ForgeItemOut])
def list_items(
    db: Session = Depends(get_db),
    kind: Optional[ForgeKind] = Query(None),
    sort: str = Query("new", pattern="^(new|top)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    status: Optional[ForgeStatus] = Query(None),
    domain: Optional[str] = None,
    scope: Optional[str] = None,
    location: Optional[str] = None,
    tags: Optional[str] = None,
    severity_min: Optional[int] = Query(None, ge=1, le=5),
    severity_max: Optional[int] = Query(None, ge=1, le=5),
):
    qry = db.query(ForgeItem)

    if kind:
        qry = qry.filter(ForgeItem.kind == ItemKind(kind.value))
    if status:
        qry = qry.filter(ForgeItem.status == ItemStatus(status.value))
    if domain:
        qry = qry.filter(ForgeItem.domain == domain)
    if scope:
        qry = qry.filter(ForgeItem.scope == scope)
    if location:
        qry = qry.filter(ForgeItem.location == location)
    if tags:
        # simple contains match on CSV field
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
    return items

@router.get("/items/{item_id}")
def get_item(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    ident = (request.headers.get("x-user-email") or "").strip()
    has_voted = has_followed = False
    if ident:
        has_voted = db.query(ForgeItemVote.id).filter_by(item_id=item_id, voter_identity=ident).first() is not None
        has_followed = db.query(ForgeItemFollow.id).filter_by(item_id=item_id, identity=ident).first() is not None

    convo = ensure_item_conversation(db, item)

    payload = _serialize_item(item)
    payload.update({
        "has_voted": has_voted,
        "has_followed": has_followed,
        "conversation_id": convo.id if convo else None,
    })
    return payload

@router.post("/items", response_model=ForgeItemOut)
def create_item(
    dto: ForgeItemCreate,
    user = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    item = ForgeItem(
        kind=ItemKind(dto.kind.value),
        title=dto.title,
        body=dto.body,
        domain=dto.domain,
        scope=dto.scope,
        severity=dto.severity,
        location=dto.location,
        tags=dto.tags,
        status=ItemStatus.open,
        created_by_email=user.email if hasattr(user, "email") else None,
        created_by_user_id=user.id if hasattr(user, "id") else None,
        created_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.post("/items/{item_id}/vote", response_model=Ok)
def vote_item(
    item_id: int,
    user = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    if not db.get(ForgeItem, item_id):
        raise HTTPException(404, "Item not found")

    identity = user.email or f"anon:{user.id}"
    # idempotent insert
    exists = db.query(ForgeItemVote).filter_by(item_id=item_id, voter_identity=identity).first()
    if not exists:
        db.add(ForgeItemVote(item_id=item_id, voter_identity=identity))
        db.flush()
        # recompute safely (handles races)
        db.execute(text("""
            UPDATE forge_items SET votes_count = (
                SELECT COUNT(*) FROM forge_item_votes WHERE item_id = :id
            ) WHERE id = :id
        """), {"id": item_id})
        db.commit()
    return Ok()

@router.delete("/items/{item_id}/vote", response_model=Ok)
def unvote_item(
    item_id: int,
    user = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    identity = user.email or f"anon:{user.id}"
    db.query(ForgeItemVote).filter_by(item_id=item_id, voter_identity=identity).delete()
    db.execute(text("""
        UPDATE forge_items SET votes_count = (
            SELECT COUNT(*) FROM forge_item_votes WHERE item_id = :id
        ) WHERE id = :id
    """), {"id": item_id})
    db.commit()
    return Ok()

@router.post("/items/{item_id}/follow", response_model=Ok)
def follow_item(
    item_id: int,
    user = Depends(get_current_user_dependency),
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
        db.execute(text("""
            UPDATE forge_items SET followers_count = (
                SELECT COUNT(*) FROM forge_item_follows WHERE item_id = :id
            ) WHERE id = :id
        """), {"id": item_id})

    # join conversation as a participant
    convo = ensure_item_conversation(db, item)
    cu = db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first()
    if not cu:
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    db.commit()
    return Ok()

@router.delete("/items/{item_id}/follow", response_model=Ok)
def unfollow_item(
    item_id: int,
    user = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    identity = user.email or f"anon:{user.id}"

    db.query(ForgeItemFollow).filter_by(item_id=item_id, identity=identity).delete()
    db.execute(text("""
        UPDATE forge_items SET followers_count = (
            SELECT COUNT(*) FROM forge_item_follows WHERE item_id = :id
        ) WHERE id = :id
    """), {"id": item_id})

    # (optional) leave conversation, but keep creator
    convo = db.query(Conversation).filter(Conversation.name == f"forge:item:{item_id}").first()
    if convo and user.id and user.id != item.created_by_user_id:
        db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).delete()

    db.commit()
    return Ok()

@router.post("/items/{item_id}/pledges", response_model=Ok)
def add_pledge(
    item_id: int,
    dto: PledgeIn,
    user = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    if not db.get(ForgeItem, item_id):
        raise HTTPException(404, "Item not found")
    db.add(ForgePledge(item_id=item_id, user_id=user.id, text=dto.text))
    db.flush()
    db.execute(text("""
        UPDATE forge_items SET pledges_count = (
            SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id
        ) WHERE id = :id
    """), {"id": item_id})
    db.commit()
    return Ok()

@router.patch("/pledges/{pledge_id}/done", response_model=Ok)
def mark_pledge_done(
    pledge_id: int,
    user = Depends(get_current_user_dependency),
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
        db.execute(text("""
            UPDATE forge_items SET pledges_done = (
                SELECT COUNT(*) FROM forge_pledges WHERE item_id = :id AND done = true
            ) WHERE id = :id
        """), {"id": p.item_id})
        db.commit()
    return Ok()

@router.get("/items/{item_id}/pledges")
def list_pledges(item_id: int, request: Request, db: Session = Depends(get_db)):
  item = db.get(ForgeItem, item_id)
  if not item:
      raise HTTPException(404, "Item not found")

  pledges = (
      db.query(ForgePledge)
      .filter(ForgePledge.item_id == item_id)
      .order_by(ForgePledge.created_at.asc(), ForgePledge.id.asc())
      .all()
  )

  ident = (request.headers.get("x-user-email") or "").strip().lower()

  def row(p: ForgePledge) -> Dict:
      return {
          "id": p.id,
          "text": p.text,
          "done": bool(p.done),
          "done_at": p.done_at,
          "created_at": p.created_at,
          "user_email": getattr(getattr(p, "user", None), "email", None) or None,
          "is_mine": bool(ident and getattr(getattr(p, "user", None), "email", "").lower() == ident),
      }

  return [row(p) for p in pledges]

# ---- Delete an item (creator or Shea) ----
@router.delete("/items/{item_id}", response_model=Ok)
def delete_item(
    item_id: int,
    user = Depends(get_current_user_dependency),
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

    # Cascades are set on FKs; but be explicit if needed:
    db.query(ForgePledge).filter_by(item_id=item_id).delete()
    db.query(ForgeItemFollow).filter_by(item_id=item_id).delete()
    db.query(ForgeItemVote).filter_by(item_id=item_id).delete()

    db.delete(item)
    db.commit()
    return Ok()

# GET /forge/items/{item_id}/conversation  → ensure + return id
@router.get("/items/{item_id}/conversation")
def get_item_conversation(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    convo = ensure_item_conversation(db, item)
    return {"conversation_id": convo.id}

# GET /forge/items/{item_id}/conversation/messages  → list thread
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

# POST /forge/items/{item_id}/conversation/send  → append message
@router.post("/items/{item_id}/conversation/send")
def send_item_message(
    item_id: int,
    payload: SendIn,
    db: Session = Depends(get_db),
):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    user = db.query(User).filter(User.email == payload.sender_email).first()
    if not user:
        raise HTTPException(401, "Login required")

    convo = ensure_item_conversation(db, item)

    # ensure participant
    if not db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first():
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    msg = InboxMessage(
        user_id=user.id,
        content=payload.content,
        conversation_id=convo.id,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"message": _serialize_msg(msg)}

# GET /forge/items/{item_id}/conversation/following?user_email=...
@router.get("/items/{item_id}/conversation/following")
def is_following_item(item_id: int, user_email: str, db: Session = Depends(get_db)):
    if not user_email:
        return {"following": False}
    exists = (
        db.query(ForgeItemFollow.id)
        .filter_by(item_id=item_id, identity=user_email)
        .first()
        is not None
    )
    return {"following": exists}

# POST /forge/items/{item_id}/conversation/join?user_email=...
@router.post("/items/{item_id}/conversation/join")
def join_item_conversation(item_id: int, user_email: str, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "Login required")

    # follow row
    if not db.query(ForgeItemFollow.id).filter_by(item_id=item_id, identity=user_email).first():
        db.add(ForgeItemFollow(item_id=item_id, identity=user_email))

    # participant row
    convo = ensure_item_conversation(db, item)
    if not db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).first():
        db.add(ConversationUser(conversation_id=convo.id, user_id=user.id))

    db.commit()
    return {"ok": True}

# POST /forge/items/{item_id}/conversation/unfollow?user_email=...
@router.post("/items/{item_id}/conversation/unfollow")
def unfollow_item_conversation(item_id: int, user_email: str, db: Session = Depends(get_db)):
    item = db.get(ForgeItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "Login required")

    db.query(ForgeItemFollow).filter_by(item_id=item_id, identity=user_email).delete()

    convo = db.query(Conversation).filter(Conversation.name == f"forge:item:{item_id}").first()
    if convo and user.id and user.id != item.created_by_user_id:
        db.query(ConversationUser).filter_by(conversation_id=convo.id, user_id=user.id).delete()

    db.commit()
    return {"ok": True}

# === Get All Ideas ===
@router.get("/ideas")
def get_ideas(db: Session = Depends(get_db), limit: int = 100):
    ideas = (
        db.query(ForgeIdea)
        .options(
            selectinload(ForgeIdea.votes),
            selectinload(ForgeIdea.workers).selectinload(ForgeWorker.user),
        )
        .order_by(desc(ForgeIdea.created_at), desc(ForgeIdea.id))  # newest first
        .limit(limit)
        .all()
    )

    return [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "status": i.status,
            "created_at": i.created_at,             # <-- FE can sort or display
            "user_email": i.user_email,
            "votes_count": len(i.votes or []),      # <-- quick count
            "votes": [v for v in (i.votes or [])],  # <-- keep your existing shape
            "workers": [
                {"email": w.user_email, "username": getattr(w.user, "username", None)}
                for w in (i.workers or [])
            ],
        }
        for i in ideas
    ]

# === Submit New Idea ===
@router.post("/ideas")
def create_idea(idea: IdeaIn, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to submit ideas.")

    new_idea = ForgeIdea(
        title=idea.title,
        description=idea.description,
        status="Proposed",
        votes_count=0,
        user_email=user_email
    )
    db.add(new_idea)
    db.commit()
    db.refresh(new_idea)
    return {"message": "Idea submitted."}

@router.put("/ideas/{idea_id}")
def update_idea(idea_id: int, updated_idea: IdeaIn, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to update idea.")
    
    # Log the incoming email and the idea's creator email for debugging
    print(f"Incoming user_email: {user_email}")
    
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    print(f"Idea creator_email: {idea.user_email}")

    # Check if the user is the creator
    if user_email != idea.user_email:
        raise HTTPException(status_code=403, detail="Not authorized to edit this idea.")
    
    # Update the fields, preserving votes
    idea.title = updated_idea.title
    idea.description = updated_idea.description
    db.commit()
    db.refresh(idea)

    return {"message": "Idea updated."}

@router.get("/ideas/{idea_id}")
def get_idea(idea_id: int, db: Session = Depends(get_db)):
    # Query to fetch the ForgeIdea
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    
    # If the idea is not found, raise a 404 error
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Query to fetch the workers associated with this idea
    workers = db.query(ForgeWorker).filter(ForgeWorker.idea_id == idea_id).all()
    workers_email = [worker.user_email for worker in workers]

    # Fetch the full user details for workers (optional)
    worker_users = db.query(User).filter(User.email.in_(workers_email)).all()
    workers_data = [{"email": worker.email, "username": worker.username} for worker in worker_users]

    # Return the idea along with the workers and notes data
    return {
        "id": idea.id,
        "title": idea.title,
        "description": idea.description,
        "status": idea.status,
        "user_email": idea.user_email,
        "workers": workers_data,  # Adding workers data
        "notes": idea.notes  # Return the notes directly, since it's now part of the ForgeIdea model
    }

# === Vote on an Idea ===
@router.post("/ideas/{idea_id}/vote")
def toggle_vote(idea_id: int, request: Request, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    identity = resolve_identity(request)  # real email or "anon:{uuid}"

    existing = (
        db.query(ForgeVote)
        .filter(ForgeVote.idea_id == idea_id, ForgeVote.user_email == identity)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        voted = False
    else:
        db.add(ForgeVote(idea_id=idea_id, user_email=identity))
        db.commit()
        voted = True

    votes_count = db.query(func.count(ForgeVote.id)).filter(ForgeVote.idea_id == idea_id).scalar()
    try:
        idea.votes_count = votes_count
        db.commit()
    except Exception:
        db.rollback()

    return {"status": "ok", "idea_id": idea_id, "voted": voted, "votes_count": votes_count}

# === Join Idea ===
@router.post("/ideas/{idea_id}/join")
def join_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to join idea.")

    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    existing = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already joined this idea.")

    join = ForgeWorker(user_email=user_email, idea_id=idea_id, user_id=user.id)
    db.add(join)
    db.commit()

    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if idea:
        creator_email = idea.user_email
        if creator_email and creator_email != user_email:
            creator = db.query(User).filter_by(email=creator_email).first()
            if creator:
                convo = ensure_system_conversation(db, creator)
                sys_user = get_or_create_system_user(db)
                content = f"👥 {user_email} has joined your idea “{idea.title}”. They want to work on it!"
                db.add(InboxMessage(
                    user_id=sys_user.id,
                    content=content,
                    timestamp=datetime.utcnow(),
                    conversation_id=convo.id
                ))
                db.commit()

    return {"message": "You've joined this idea and notified the creator."}

# Remove a user from being a worker in an idea
@router.post("/ideas/{idea_id}/remove-worker")
def remove_worker(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to remove worker.")

    # Find and remove the worker from the idea's workers list
    worker = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if not worker:
        raise HTTPException(status_code=400, detail="You are not a worker for this idea.")

    db.delete(worker)
    db.commit()

    return {"message": "You have left this idea."}


# === Delete Idea ===
@router.delete("/ideas/{idea_id}")
def delete_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Allow the creator or 'sheaklipper@gmail.com' to delete the idea
    if user_email != idea.user_email and user_email != "sheaklipper@gmail.com":
        raise HTTPException(status_code=403, detail="Not authorized to delete this idea.")

    db.delete(idea)
    db.commit()
    return {"message": "Idea deleted."}

# Create a Pydantic model to handle the incoming request
class NoteContent(BaseModel):
    content: str

@router.post("/ideas/{idea_id}/notes")
async def update_notes(idea_id: int, note_content: NoteContent, db: Session = Depends(get_db)):
    # Fetch the idea from the database
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Update the notes field in the ForgeIdea model
    idea.notes = note_content.content  # Access content from the NoteContent model
    db.commit()  # Save the changes to the database
    db.refresh(idea)  # Refresh the idea instance to get updated data
    return {"message": "Note updated successfully", "idea": idea}

@router.patch("/ideas/{idea_id}/status")
def set_idea_status(
    idea_id: int,
    payload: IdeaStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required")

    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Only creator or Shea can change status
    if user_email != idea.user_email and user_email != "sheaklipper@gmail.com":
        raise HTTPException(status_code=403, detail="Not authorized to change status")

    old = idea.status
    new = payload.status.value
    if old == new:
        return {"message": "No change", "idea_id": idea_id, "status": new}

    idea.status = new
    db.commit()
    db.refresh(idea)

    # (Optional) Notify the creator (and/or workers) via System DM
    try:
        creator = db.query(User).filter_by(email=idea.user_email).first()
        if creator:
            convo = ensure_system_conversation(db, creator)
            sys_user = get_or_create_system_user(db)
            db.add(InboxMessage(
                user_id=sys_user.id,
                content=f"🔄 Status of “{idea.title}” changed: {old} → {new}",
                timestamp=datetime.utcnow(),
                conversation_id=convo.id,
            ))
            db.commit()
    except Exception:
        db.rollback()  # don’t fail the status change if notification fails

    return {"message": "Status updated", "idea_id": idea_id, "status": new}