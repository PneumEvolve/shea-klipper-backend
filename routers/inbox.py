# /routes/inbox.py
from fastapi import APIRouter, Depends
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
    messages = db.query(InboxMessage).filter_by(user_id=user_id).order_by(InboxMessage.timestamp.desc()).all()
    return [{"id": m.id, "content": m.content, "timestamp": m.timestamp} for m in messages]