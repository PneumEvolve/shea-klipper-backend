from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from typing import Optional
from sqlalchemy import func, distinct

from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db

router = APIRouter()

# ========= Schemas =========

class SendMessageIn(BaseModel):
    sender_email: str
    content: str

class DMSendIn(BaseModel):
    sender_email: str
    recipient_email: str
    content: str


# ========= Helpers =========

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

    # All conversation ids for this user
    convo_ids = [cid for (cid,) in (
        db.query(ConversationUser.conversation_id)
          .filter(ConversationUser.user_id == me.id)
          .all()
    )]
    if not convo_ids:
        return []

    # Last message per convo
    sub_last = (
        db.query(
            InboxMessage.conversation_id,
            func.max(InboxMessage.timestamp).label("last_ts"),
        )
        .filter(InboxMessage.conversation_id.in_(convo_ids))
        .group_by(InboxMessage.conversation_id)
        .subquery()
    )

    # Pull the last messages and eager-load relationships to avoid N+1
    last_msgs = (
        db.query(InboxMessage)
          .options(
              selectinload(InboxMessage.conversation).selectinload(Conversation.conversation_users).selectinload(ConversationUser.user),
              selectinload(InboxMessage.user)
          )
          .join(
              sub_last,
              (InboxMessage.conversation_id == sub_last.c.conversation_id)
              & (InboxMessage.timestamp == sub_last.c.last_ts),
          )
          .all()
    )

    # Unread counts per convo (global read flag in your current schema)
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

        # Default labels
        other_email = None
        other_username = None
        other_display = None

        if cname and cname.startswith("dm:"):
            # Find "the other" participant
            for cu in convo.conversation_users:
                if cu.user and cu.user.email != user_email:
                    other_email = cu.user.email
                    other_username = cu.user.username
                    break
            other_display = other_username or other_email or "Chat"
        elif cname and cname.startswith("system:"):
            other_display = "System"

        out.append({
            "conversation_id": m.conversation_id,
            "conversation_name": cname,                # e.g., system:{id} or dm:a:b
            "last_content": m.content,
            "last_timestamp": m.timestamp,
            "unread_count": unread_map.get(m.conversation_id, 0),
            "other_email": other_email,                # for DMs
            "other_username": other_username,          # for DMs
            "other_display": other_display,            # what the UI should show by default
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