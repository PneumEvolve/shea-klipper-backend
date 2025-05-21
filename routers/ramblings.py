from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Rambling
from schemas import RamblingCreate, RamblingOut
from typing import List

router = APIRouter()

@router.get("/ramblings", response_model=List[RamblingOut])
def get_ramblings(db: Session = Depends(get_db)):
    return db.query(Rambling).order_by(Rambling.id.desc()).all()

@router.post("/ramblings", response_model=RamblingOut)
def create_rambling(data: RamblingCreate, db: Session = Depends(get_db)):
    new_idea = Rambling(content=data.content, tag=data.tag)
    db.add(new_idea)
    db.commit()
    db.refresh(new_idea)
    return new_idea

@router.delete("/ramblings/{rambling_id}")
def delete_rambling(rambling_id: int, db: Session = Depends(get_db)):
    idea = db.query(Rambling).filter(Rambling.id == rambling_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    db.delete(idea)
    db.commit()
    return {"ok": True}