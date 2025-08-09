# /routes/inbox.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter()

class MessageInput(BaseModel):
    user_id: str
    content: str

@router.post("/inbox/start-conversation")
def start_conversation(users: list[str], db: Session = Depends(get_db)):
    if len(users) < 2:
        raise HTTPException(status_code=400, detail="At least two users are required to start a conversation.")
    
    # Check if the conversation already exists between these users
    existing_conversation = db.query(Conversation).join(ConversationUser).filter(
        ConversationUser.user_id.in_(users)
    ).group_by(Conversation.id).having(func.count(Conversation.id) == len(users)).first()
    
    if existing_conversation:
        return {"conversation_id": existing_conversation.id}

    # Create a new conversation
    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # Add users to the conversation
    for user_email in users:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
            db.add(conversation_user)
    db.commit()

    return {"conversation_id": conversation.id}

@router.post("/inbox/send")
def send_message(data: MessageInput, db: Session = Depends(get_db)):
    # Check if the conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == data.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    msg = InboxMessage(user_id=data.user_id, content=data.content, timestamp=datetime.utcnow(), conversation_id=conversation.id)
    db.add(msg)
    db.commit()
    
    return {"status": "sent"}

@router.get("/inbox/{conversation_id}")
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    messages = db.query(InboxMessage).filter(InboxMessage.conversation_id == conversation_id).order_by(InboxMessage.timestamp).all()
    
    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "user_id": m.user_id
        }
        for m in messages
    ]

@router.get("/inbox/{user_id}")
def get_inbox(user_id: str, db=Depends(get_db)):
    messages = db.query(InboxMessage)\
        .filter_by(user_id=user_id)\
        .order_by(InboxMessage.timestamp.desc())\
        .all()
        
    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read  # ✅ include the read flag
        }
        for m in messages
    ]

@router.post("/inbox/read/{message_id}")
def mark_message_read(message_id: int, db: Session = Depends(get_db)):
    message = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    message.read = True
    db.commit()
    return {"status": "marked_as_read"}

@router.post("/inbox/contribute")
def submit_contribution(data: dict, db=Depends(get_db)):
    content = f"""
📬 **New Contributor Submission**

📧 Contact: {data.get('contact', 'N/A')}
🎯 Interests: {', '.join(data.get('interests', []))}
💡 Idea: {data.get('idea', '')}
🐞 Bugs: {data.get('bugs', '')}
🛠 Skills: {data.get('skills', '')}
🗨 Extra: {data.get('extra', '')}
""".strip()

    msg = InboxMessage(
        user_id="1",  # 📥 send to your inbox
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    return {"status": "received"}