# /backend/routes/forge.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import ForgeIdea

router = APIRouter()

# ------------------- MODELS -------------------
class ForgeIdeaCreate(BaseModel):
    title: str
    description: str

class ForgeIdeaUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    votes: int | None = None

# ------------------- ROUTES -------------------

@router.post("/forge/ideas")
def create_idea(idea: ForgeIdeaCreate, db: Session = Depends(get_db)):
    new_idea = ForgeIdea(
        title=idea.title,
        description=idea.description,
        status="Idea",
        votes=0,
        created_at=datetime.utcnow(),
    )
    db.add(new_idea)
    db.commit()
    db.refresh(new_idea)
    return new_idea


@router.get("/forge/ideas")
def get_all_ideas(db: Session = Depends(get_db)):
    return db.query(ForgeIdea).order_by(ForgeIdea.created_at.desc()).all()


@router.patch("/forge/ideas/{idea_id}")
def update_idea(idea_id: int, updates: ForgeIdeaUpdate, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    for field, value in updates.dict(exclude_unset=True).items():
        setattr(idea, field, value)

    db.commit()
    db.refresh(idea)
    return idea


@router.delete("/forge/ideas/{idea_id}")
def delete_idea(idea_id: int, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    db.delete(idea)
    db.commit()
    return {"message": "Idea deleted"}


@router.post("/forge/ideas/{idea_id}/vote")
def vote_idea(idea_id: int, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea.votes += 1
    db.commit()
    return {"message": "Vote counted", "votes": idea.votes}