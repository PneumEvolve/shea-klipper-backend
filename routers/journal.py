from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models import JournalEntry
from schemas import JournalEntryCreate, JournalEntryOut
from routers.auth import get_current_user_dependency

router = APIRouter()

@router.post("/journal", response_model=JournalEntryOut)
def create_entry(entry: JournalEntryCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    new_entry = JournalEntry(user_id=current_user.id, **entry.dict())
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

@router.get("/journal", response_model=List[JournalEntryOut])
def get_entries(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    return db.query(JournalEntry).filter(JournalEntry.user_id == current_user.id).order_by(JournalEntry.created_at.desc()).all()

@router.delete("/journal/{entry_id}", response_model=dict)
def delete_entry(entry_id: int = Path(..., gt=0), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found.")

    db.delete(entry)
    db.commit()
    return {"message": "Journal entry deleted."}