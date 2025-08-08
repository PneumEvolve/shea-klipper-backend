# forge.py (FastAPI Router for Forge)
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import ForgeIdea, ForgeVote, ForgeWorker, InboxMessage
from database import get_db
from datetime import datetime

router = APIRouter()

# === Pydantic Schemas ===
class IdeaIn(BaseModel):
    title: str
    description: str

class IdeaOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    votes: int
    creator_email: str

# === Get All Ideas ===
@router.get("/forge/ideas")
def get_ideas(db: Session = Depends(get_db)):
    ideas = db.query(ForgeIdea).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "status": i.status,
            "votes": i.votes,
            "user_email": i.user_email
        } for i in ideas
    ]

# === Submit New Idea ===
@router.post("/forge/ideas")
def create_idea(idea: IdeaIn, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to submit ideas.")

    new_idea = ForgeIdea(
        title=idea.title,
        description=idea.description,
        status="Proposed",
        votes=0,
        user_email=user_email
    )
    db.add(new_idea)
    db.commit()
    db.refresh(new_idea)
    return {"message": "Idea submitted."}

@router.put("/forge/ideas/{idea_id}")
def update_idea(idea_id: int, updated_idea: IdeaIn, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to update idea.")

    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Check if the user is the creator
    if user_email != idea.user_email:
        raise HTTPException(status_code=403, detail="Not authorized to edit this idea.")

    # Update the fields, preserving votes
    idea.title = updated_idea.title
    idea.description = updated_idea.description
    db.commit()
    db.refresh(idea)

    return {"message": "Idea updated."}

@router.get("/forge/ideas/{idea_id}")
def get_idea(idea_id: int, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea

# === Vote on an Idea ===
@router.post("/forge/ideas/{idea_id}/vote")
def vote_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to vote.")
    
    print(f"User email: {user_email}")  # Add this line to debug

    existing_vote = db.query(ForgeVote).filter_by(user_email=user_email, idea_id=idea_id).first()
    if existing_vote:
        raise HTTPException(status_code=400, detail="You have already voted on this idea.")

    vote = ForgeVote(user_email=user_email, idea_id=idea_id)
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")

    idea.votes += 1
    db.add(vote)
    db.commit()
    return {"message": "Vote recorded."}

# === Join Idea ===
@router.post("/forge/ideas/{idea_id}/join")
def join_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to join idea.")

    # Check if the user has already joined the idea
    existing = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already joined this idea.")

    # Add the user to the idea's workers list
    join = ForgeWorker(user_email=user_email, idea_id=idea_id)
    db.add(join)
    db.commit()

    # Notify the creator of the idea
    idea = db.query(ForgeIdea).get(idea_id)
    if idea:
        creator_email = idea.user_email  # Assumes creator's email is stored in `user_email` field
        if creator_email and creator_email != user_email:
            content = f"👥 {user_email} has joined your idea \"{idea.title}\". They want to work on it!"
            
            # Creating the inbox notification for the creator
            inbox_message = InboxMessage(
                user_email=creator_email,  # Sending the notification to the creator
                content=content,
                timestamp=datetime.utcnow()  # Adding the timestamp
            )
            db.add(inbox_message)
            db.commit()

    return {"message": "You've joined this idea and notified the creator."}


# === Delete Idea ===
@router.delete("/forge/ideas/{idea_id}")
def delete_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Allow the creator or 'sheaklipper@gmail.com' to delete the idea
    if user_email != idea.user_email and user_email != "sheaklipper@gmail.com":
        raise HTTPException(status_code=403, detail="Not authorized to delete this idea.")

    db.delete(idea)
    db.commit()
    return {"message": "Idea deleted."}