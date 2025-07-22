# /routes/inbox.py
from fastapi import APIRouter, Depends
from datetime import datetime
from models import InboxMessage
from database import get_db

router = APIRouter()

@router.post("/inbox/send")
def send_message(user_id: str, content: str, db=Depends(get_db)):
    msg = InboxMessage(user_id=user_id, content=content, timestamp=datetime.utcnow())
    db.add(msg)
    db.commit()
    return {"status": "sent"}

@router.get("/inbox/{user_id}")
def get_inbox(user_id: str, db=Depends(get_db)):
    messages = db.query(InboxMessage).filter_by(user_id=user_id).order_by(InboxMessage.timestamp.desc()).all()
    return [{"id": m.id, "content": m.content, "timestamp": m.timestamp} for m in messages]