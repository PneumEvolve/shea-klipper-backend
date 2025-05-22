from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Rambling
from schemas import RamblingCreate, RamblingOut, User
from typing import List
from .auth import get_current_user_dependency as get_current_user
from schemas import UserResponse as UserSchema

router = APIRouter()

@router.get("/ramblings")
def get_user_ramblings(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    return db.query(Rambling).filter(Rambling.user_id == current_user.id).all()

@router.post("/ramblings")
def create_rambling(
    rambling_data: RamblingCreate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    new_rambling = Rambling(
        content=rambling_data.content,
        tag=rambling_data.tag,
        user_id=current_user.id
    )
    db.add(new_rambling)
    db.commit()
    db.refresh(new_rambling)
    return new_rambling

@router.delete("/ramblings/{rambling_id}")
def delete_rambling(rambling_id: int, db: Session = Depends(get_db)):
    idea = db.query(Rambling).filter(Rambling.id == rambling_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    db.delete(idea)
    db.commit()
    return {"ok": True}

@router.put("/ramblings/{rambling_id}")
def update_rambling(
    rambling_id: int,
    rambling_data: RamblingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rambling = db.query(Rambling).filter(Rambling.id == rambling_id).first()

    if not rambling:
        raise HTTPException(status_code=404, detail="Idea not found")

    if rambling.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this idea")

    rambling.content = rambling_data.content
    rambling.tag = rambling_data.tag
    db.commit()
    db.refresh(rambling)
    return rambling