# /routes/inbox.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from models import InboxMessage
from database import get_db

router = APIRouter()

class MessageInput(BaseModel):
    user_id: str
    content: str

@router.post("/inbox/send")
def send_message(data: MessageInput, db=Depends(get_db)):
    msg = InboxMessage(user_id=data.user_id, content=data.content, timestamp=datetime.utcnow())
    db.add(msg)
    db.commit()
    return {"status": "sent"}

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
def mark_message_read(message_id: int, db=Depends(get_db)):
    message = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    message.read = True
    db.commit()
    return {"status": "marked_as_read"}