# inbox.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy import func, distinct

from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db

router = APIRouter()

# ===== Schemas =====
class SendMessageIn(BaseModel):
    sender_email: str  # who is sending
    content: str       # message content

# ===== Helpers =====
def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == "system@domain.com").first()
    if sys:
        return sys
    sys = User(email="system@domain.com", username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys

def get_or_create_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found")
    return user

def get_or_create_system_conversation_for_user(db: Session, user: User, sys_user: User) -> Conversation:
    # Find a conversation named "System" that includes this user
    convo = (
        db.query(Conversation)
        .join(ConversationUser)
        .filter(ConversationUser.user_id == user.id, Conversation.name == "System")
        .first()
    )
    if convo:
        return convo

    # Create new conversation
    convo = Conversation(name="System")
    db.add(convo)
    db.flush()        # <-- ensure convo.id exists
    # Attach both participants
    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))
    db.commit()
    db.refresh(convo)
    return convo

# ===== Routes =====

@router.post("/inbox/send")
def send_to_system(data: SendMessageIn, db: Session = Depends(get_db)):
    # Resolve identities
    sender = get_or_create_user_by_email(db, data.sender_email)
    system_user = get_or_create_system_user(db)

    # Ensure the per-user system conversation
    convo = get_or_create_system_conversation_for_user(db, sender, system_user)

    # If we're bootstrapping, optionally send a welcome only if convo is empty
    has_any = db.query(InboxMessage).filter(InboxMessage.conversation_id == convo.id).first()
    if not has_any:
        welcome = InboxMessage(
            user_id=system_user.id,
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=convo.id,
        )
        db.add(welcome)

    # Append the sender's message
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
    user = get_or_create_user_by_email(db, user_email)
    system_user = get_or_create_system_user(db)
    convo = get_or_create_system_conversation_for_user(db, user, system_user)

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
            # include who said it if you want
            "from_system": (m.user_id == system_user.id),
        }
        for m in messages
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

def get_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found")
    return user

def get_or_create_dm_conversation(db: Session, a: User, b: User) -> Conversation:
    # Deterministic key so A↔B always maps to the same convo
    key = f"dm:{min(a.id, b.id)}:{max(a.id, b.id)}"

    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    convo = Conversation(name=key)
    db.add(convo)
    db.flush()  # ensure convo.id is available

    db.add(ConversationUser(user_id=a.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=b.id, conversation_id=convo.id))

    db.commit()
    db.refresh(convo)
    return convo

from pydantic import BaseModel
class DMSendIn(BaseModel):
    sender_email: str
    recipient_email: str
    content: str

@router.post("/conversations/dm/send")
def send_dm(payload: DMSendIn, db: Session = Depends(get_db)):
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