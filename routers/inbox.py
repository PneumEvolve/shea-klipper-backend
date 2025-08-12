from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List
from sqlalchemy import func, distinct

from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db
from models import ForgeIdea as IdeaModel

router = APIRouter()

ADMIN_EMAIL = "sheaklipper@gmail.com"

# ========= Schemas =========

class SendMessageIn(BaseModel):
    sender_email: str
    content: str

class DMSendIn(BaseModel):
    sender_email: str
    recipient_email: str
    content: str

class IdeaSendIn(BaseModel):
    sender_email: str
    content: str

class FeedbackIn(BaseModel):
    contact: str
    interests: List[str] = []
    idea: Optional[str] = ""
    bugs: Optional[str] = ""
    skills: Optional[str] = ""
    extra: Optional[str] = ""


# ========= Helpers =========

def get_idea_title(db: Session, idea_id: int) -> str:
    row = db.query(IdeaModel).filter(IdeaModel.id == idea_id).first()
    return (row.title or f"Idea #{idea_id}") if row else f"Idea #{idea_id}"

def get_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found")
    return user

def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == "system@domain.com").first()
    if sys:
        return sys
    sys = User(email="system@domain.com", username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys

def get_or_create_system_conversation_for_user(db: Session, user: User, sys_user: User) -> Conversation:
    """
    Ensure the user has a private System conversation named 'system:{user.id}'.
    If we find an old-style convo named 'System' that includes the user, we rename it,
    attach the system user if missing, and seed a welcome if empty.
    """
    key = f"system:{user.id}"

    # Fast path: already migrated to deterministic key
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    # Legacy path: an old conversation literally named "System" that includes this user
    legacy = (
        db.query(Conversation)
        .join(ConversationUser)
        .filter(ConversationUser.user_id == user.id, Conversation.name == "System")
        .first()
    )
    if legacy:
        legacy.name = key

        # Ensure system user is attached
        has_sys = (
            db.query(ConversationUser)
            .filter(
                ConversationUser.conversation_id == legacy.id,
                ConversationUser.user_id == sys_user.id,
            )
            .first()
        )
        if not has_sys:
            db.add(ConversationUser(user_id=sys_user.id, conversation_id=legacy.id))

        # Seed welcome if empty
        has_msg = (
            db.query(InboxMessage.id)
            .filter(InboxMessage.conversation_id == legacy.id)
            .first()
        )
        if not has_msg:
            db.add(
                InboxMessage(
                    user_id=sys_user.id,
                    content="Welcome to your inbox! This is a system-generated message.",
                    timestamp=datetime.utcnow(),
                    conversation_id=legacy.id,
                )
            )

        db.commit()
        db.refresh(legacy)
        return legacy

    # Create fresh conversation with deterministic key
    convo = Conversation(name=key)
    db.add(convo)
    db.flush()  # ensure convo.id is available

    # Attach both participants
    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))

    # Seed welcome
    db.add(
        InboxMessage(
            user_id=sys_user.id,
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=convo.id,
        )
    )

    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_dm_conversation(db: Session, a: User, b: User) -> Conversation:
    """
    Deterministic key so A↔B always maps to the same DM conversation,
    and we never collide with System or other named convos.
    """
    key = f"dm:{min(a.id, b.id)}:{max(a.id, b.id)}"
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    convo = Conversation(name=key)
    db.add(convo)
    db.flush()

    db.add(ConversationUser(user_id=a.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=b.id, conversation_id=convo.id))

    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_idea_conversation(db: Session, idea_id: int) -> Conversation:
    """
    One conversation per idea, named 'idea:{idea_id}'.
    We don't attach participants on creation; we add people when they send or 'follow'.
    """
    key = f"idea:{idea_id}"
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    convo = Conversation(name=key)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_user_by_email_or_create(db: Session, email: str, username: Optional[str] = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(email=email, username=username or (email.split("@")[0] if "@" in email else email))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_or_create_feedback_conversation(db: Session, system_user: User, admin_user: User) -> Conversation:
    # Try to find an existing "feedback" conversation that includes the admin
    convo = (
        db.query(Conversation)
        .join(ConversationUser)
        .filter(Conversation.name == "feedback", ConversationUser.user_id == admin_user.id)
        .first()
    )
    if convo:
        # Ensure system is in it
        has_sys = (
            db.query(ConversationUser)
            .filter(ConversationUser.conversation_id == convo.id, ConversationUser.user_id == system_user.id)
            .first()
        )
        if not has_sys:
            db.add(ConversationUser(user_id=system_user.id, conversation_id=convo.id))
            db.commit()
        return convo

    # Create fresh
    convo = Conversation(name="feedback")
    db.add(convo)
    db.flush()  # ensure convo.id

    db.add(ConversationUser(user_id=admin_user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=system_user.id, conversation_id=convo.id))
    db.commit()
    db.refresh(convo)
    return convo

# ========= Routes =========

@router.post("/inbox/send")
def send_to_system(data: SendMessageIn, db: Session = Depends(get_db)):
    """
    Send a message into the caller's System conversation (auto-creates on first use).
    """
    sender = get_user_by_email(db, data.sender_email)
    system_user = get_or_create_system_user(db)

    convo = get_or_create_system_conversation_for_user(db, sender, system_user)

    msg = InboxMessage(
        user_id=sender.id,
        content=data.content,
        timestamp=datetime.utcnow(),
        conversation_id=convo.id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "conversation_id": convo.id, "message_id": msg.id}

@router.get("/inbox/{user_email}")
def get_inbox(user_email: str, db: Session = Depends(get_db)):
    """
    Return ONLY the System conversation for the given user.
    """
    user = get_user_by_email(db, user_email)
    system_user = get_or_create_system_user(db)
    convo = get_or_create_system_conversation_for_user(db, user, system_user)

    # Safety: backfill welcome if somehow empty
    has_any = (
        db.query(InboxMessage.id)
        .filter(InboxMessage.conversation_id == convo.id)
        .first()
    )
    if not has_any:
        db.add(
            InboxMessage(
                user_id=system_user.id,
                content="Welcome to your inbox! This is a system-generated message.",
                timestamp=datetime.utcnow(),
                conversation_id=convo.id,
            )
        )
        db.commit()

    messages = (
        db.query(InboxMessage)
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_system": (m.user_id == system_user.id),
        }
        for m in messages
    ]

@router.get("/inbox/feed/{user_email}")
def get_inbox_feed(user_email: str, db: Session = Depends(get_db)):
    """
    Return a unified feed: System + all DMs for the user.
    Bootstraps the System convo (and welcome) if missing.
    """
    user = get_user_by_email(db, user_email)
    system_user = get_or_create_system_user(db)

    # Ensure System convo exists (and seeded)
    convo = get_or_create_system_conversation_for_user(db, user, system_user)

    # Safety: backfill welcome if somehow empty
    has_any = (
        db.query(InboxMessage.id)
        .filter(InboxMessage.conversation_id == convo.id)
        .first()
    )
    if not has_any:
        db.add(
            InboxMessage(
                user_id=system_user.id,
                content="Welcome to your inbox! This is a system-generated message.",
                timestamp=datetime.utcnow(),
                conversation_id=convo.id,
            )
        )
        db.commit()

    # Collect all conversation IDs the user participates in
    convo_ids = [
        row[0]
        for row in db.query(ConversationUser.conversation_id)
                     .filter(ConversationUser.user_id == user.id)
                     .all()
    ]
    if not convo_ids:
        return []

    msgs = (
        db.query(InboxMessage)
        .filter(InboxMessage.conversation_id.in_(convo_ids))
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "conversation_name": m.conversation.name if getattr(m, "conversation", None) else None,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_system": (m.user_id == system_user.id),
            "from_email": m.user.email if getattr(m, "user", None) else None,
        }
        for m in msgs
    ]

@router.post("/inbox/read/{message_id}")
def mark_read(message_id: int, db: Session = Depends(get_db)):
    msg = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.read:
        return {"status": "ok", "message": "already_read"}
    msg.read = True
    db.commit()
    return {"status": "ok", "message": "updated"}

@router.post("/conversations/dm/send")
def send_dm(payload: DMSendIn, db: Session = Depends(get_db)):
    """
    Send a direct message between two users. Creates or reuses the DM conversation.
    """
    sender = get_user_by_email(db, payload.sender_email)
    recipient = get_user_by_email(db, payload.recipient_email)

    convo = get_or_create_dm_conversation(db, sender, recipient)

    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=convo.id,
        content=payload.content,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "conversation_id": convo.id, "message_id": msg.id}

@router.get("/conversations/summaries/{user_email}")
def conversation_summaries(user_email: str, db: Session = Depends(get_db)):
    me = get_user_by_email(db, user_email)

    convo_ids = [cid for (cid,) in db.query(ConversationUser.conversation_id)
                                 .filter(ConversationUser.user_id == me.id)
                                 .all()]
    if not convo_ids:
        return []

    sub_last = (
        db.query(
            InboxMessage.conversation_id,
            func.max(InboxMessage.timestamp).label("last_ts"),
        )
        .filter(InboxMessage.conversation_id.in_(convo_ids))
        .group_by(InboxMessage.conversation_id)
        .subquery()
    )

    last_msgs = (
        db.query(InboxMessage)
          .options(
              selectinload(InboxMessage.conversation)
                  .selectinload(Conversation.conversation_users)
                  .selectinload(ConversationUser.user),
              selectinload(InboxMessage.user),
          )
          .join(
              sub_last,
              (InboxMessage.conversation_id == sub_last.c.conversation_id)
              & (InboxMessage.timestamp == sub_last.c.last_ts),
          )
          .all()
    )

    unread_map = {
        cid: cnt
        for cid, cnt in (
            db.query(InboxMessage.conversation_id, func.count(InboxMessage.id))
              .filter(
                  InboxMessage.conversation_id.in_(convo_ids),
                  InboxMessage.read == False,  # noqa: E712
              )
              .group_by(InboxMessage.conversation_id)
              .all()
        )
    }

    out = []
    for m in last_msgs:
        convo = m.conversation
        cname = convo.name if convo else None

        other_email = None
        other_username = None
        other_display = None
        idea_id = None
        idea_title = None

        if cname and cname.startswith("dm:"):
            for cu in convo.conversation_users:
                if cu.user and cu.user.email != user_email:
                    other_email = cu.user.email
                    other_username = cu.user.username
                    break
            other_display = other_username or other_email or "Chat"

        elif cname and cname.startswith("system:"):
            other_display = "System"

        elif cname and cname.startswith("idea:"):
            try:
                idea_id = int(cname.split(":", 1)[1])
            except Exception:
                idea_id = None
            if idea_id is not None:
                idea_title = get_idea_title(db, idea_id)
                other_display = idea_title or f"Idea #{idea_id}"
            else:
                other_display = "Idea"

        out.append({
            "conversation_id": m.conversation_id,
            "conversation_name": cname,      # system:{id}, dm:..., idea:{id}
            "last_content": m.content,
            "last_timestamp": m.timestamp,
            "unread_count": unread_map.get(m.conversation_id, 0),
            "other_email": other_email,
            "other_username": other_username,
            "other_display": other_display,  # what the UI should show
            "idea_id": idea_id,
            "idea_title": idea_title,
        })

    out.sort(key=lambda x: x["last_timestamp"] or datetime.min, reverse=True)
    return out

@router.get("/conversations/dm/thread")
def get_dm_thread(
    me: str, them: str, limit: int = 50, before: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    a = get_user_by_email(db, me)
    b = get_user_by_email(db, them)
    convo = get_or_create_dm_conversation(db, a, b)

    q = db.query(InboxMessage).filter(InboxMessage.conversation_id == convo.id)
    if before:
        q = q.filter(InboxMessage.timestamp < before)
    msgs = q.order_by(InboxMessage.timestamp.desc()).limit(limit).all()
    msgs.reverse()

    return {
        "conversation_id": convo.id,
        "messages": [{
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_email": m.user.email if m.user else None,
        } for m in msgs]
    }

@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    msgs = (
        db.query(InboxMessage)
          .options(selectinload(InboxMessage.user))
          .filter(InboxMessage.conversation_id == conversation_id)
          .order_by(InboxMessage.timestamp.asc())
          .all()
    )
    out = []
    for m in msgs:
        from_email = m.user.email if m.user else None
        from_username = m.user.username if m.user else None
        if m.user_id == system_user.id:
            from_display = "System"
        else:
            from_display = from_username or from_email or "User"
        out.append({
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_email": from_email,
            "from_username": from_username,
            "from_display": from_display,
        })
    return out

# ---- Request schema ----
class ConversationSendIn(BaseModel):
    sender_email: str
    content: str

@router.post("/conversations/{conversation_id}/send")
def send_to_conversation(conversation_id: int, data: ConversationSendIn, db: Session = Depends(get_db)):
    sender = get_user_by_email(db, data.sender_email)

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Ensure sender participates in this conversation
    is_member = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == conversation_id,
            ConversationUser.user_id == sender.id,
        )
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    # Create message
    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=conversation_id,
        content=data.content,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Build a UI-friendly payload (matches /conversations/{id}/messages shape)
    from_email = sender.email
    from_username = sender.username
    from_display = from_username or from_email or "User"

    return {
        "status": "ok",
        "message": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "read": msg.read,
            "from_email": from_email,
            "from_username": from_username,
            "from_display": from_display,
        },
    }

@router.get("/ideas/{idea_id}/conversation")
def get_idea_conversation(idea_id: int, db: Session = Depends(get_db)):
    convo = get_or_create_idea_conversation(db, idea_id)
    return {
        "conversation_id": convo.id,
        "conversation_name": convo.name,                 # e.g., "idea:6"
        "conversation_title": get_idea_title(db, idea_id)  # human-friendly title
    }


@router.get("/ideas/{idea_id}/conversation/messages")
def get_idea_conversation_messages(idea_id: int, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    convo = get_or_create_idea_conversation(db, idea_id)

    msgs = (
        db.query(InboxMessage)
        .options(selectinload(InboxMessage.user))
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    def safe_display(m):
        if m.user_id == system_user.id:
            return "System"
        if m.user and getattr(m.user, "username", None):
            return m.user.username
        if m.user_id:
            return f"User {m.user_id}"
        return "User"

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_username": (m.user.username if m.user else None),
            "from_user_id": m.user_id,
            "from_system": (m.user_id == system_user.id),
            "from_display": safe_display(m),   # ← never email
        }
        for m in msgs
    ]


@router.post("/ideas/{idea_id}/conversation/send")
def send_to_idea_conversation(
    idea_id: int,
    payload: IdeaSendIn,
    db: Session = Depends(get_db),
):
    """
    Send a message into the idea conversation.
    Automatically enrolls the sender as a participant so it appears in their feed.
    """
    sender = get_user_by_email(db, (payload.sender_email or "").strip().lower())
    if not sender:
        raise HTTPException(status_code=401, detail="User not found")

    convo = get_or_create_idea_conversation(db, idea_id)

    # Ensure membership so convo shows in sender's feed
    link = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == sender.id,
        )
        .first()
    )
    if not link:
        db.add(ConversationUser(user_id=sender.id, conversation_id=convo.id))

    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=convo.id,
        content=(payload.content or "").strip(),
        timestamp=datetime.utcnow(),
    )
    if not msg.content:
        raise HTTPException(status_code=400, detail="Empty message")

    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Build a privacy-safe display (never email)
    display = sender.username if sender.username else f"User {msg.user_id}"

    return {
        "status": "ok",
        "conversation_id": convo.id,
        "message": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "read": msg.read,
            "from_user_id": msg.user_id,
            "from_username": sender.username if sender.username else None,
            "from_display": display,   # ← username or "User <id>", never email
        },
    }


@router.post("/ideas/{idea_id}/conversation/join")
def join_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Optional: let users follow an idea thread without sending a message yet.
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)

    exists = (
        db.query(ConversationUser)
        .filter(ConversationUser.conversation_id == convo.id, ConversationUser.user_id == user.id)
        .first()
    )
    if exists:
        return {"status": "ok", "message": "already_member", "conversation_id": convo.id}

    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.commit()
    return {"status": "ok", "message": "joined", "conversation_id": convo.id}

@router.get("/ideas/{idea_id}/conversation/following")
def is_following_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Return whether the user is a participant of the idea conversation.
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)
    exists = (
        db.query(ConversationUser.id)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == user.id,
        )
        .first()
    )
    return {"conversation_id": convo.id, "following": bool(exists)}


@router.post("/ideas/{idea_id}/conversation/unfollow")
def unfollow_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Remove the user from the idea conversation participants (their feed won't show it).
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)
    link = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == user.id,
        )
        .first()
    )
    if not link:
        return {"status": "ok", "message": "not_following", "conversation_id": convo.id}

    db.delete(link)
    db.commit()
    return {"status": "ok", "message": "unfollowed", "conversation_id": convo.id}

@router.post("/feedback")
def receive_feedback(payload: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    admin_user = get_or_create_user_by_email_or_create(db, ADMIN_EMAIL, username="Admin")

    convo = get_or_create_feedback_conversation(db, system_user, admin_user)

    # Format a readable message
    lines = [
        "📝 New Contribution",
        f"• Contact: {payload.contact or '—'}",
        f"• Interests: {', '.join(payload.interests) if payload.interests else '—'}",
        "",
        f"💡 Idea:\n{payload.idea or '—'}",
        "",
        f"🐞 Bugs:\n{payload.bugs or '—'}",
        "",
        f"🧰 Skills:\n{payload.skills or '—'}",
        "",
        f"➕ Extra:\n{payload.extra or '—'}",
    ]
    content = "\n".join(lines)

    msg = InboxMessage(
        user_id=system_user.id,            # message appears from System
        content=content,
        timestamp=datetime.utcnow(),
        conversation_id=convo.id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "message_id": msg.id, "conversation_id": convo.id}