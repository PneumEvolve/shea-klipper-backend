from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models import JournalEntry
from schemas import JournalEntryCreate, JournalEntryOut
from routers.auth import get_current_user_dependency
from openai import OpenAI
import os

router = APIRouter()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

@router.post("/journal/reflect/{entry_id}")
def reflect_on_entry(entry_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    prompt = (
        f"The user wrote the following journal entry:\n\n"
        f"Title: {entry.title}\n"
        f"Content: {entry.content}\n\n"
        f"Give a concise, thoughtful and compassionate reflection to help the user better understand their own thoughts."
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        reflection = response.choices[0].message.content.strip()
        return {"reflection": reflection}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI reflection failed: {str(e)}")