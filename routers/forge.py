# forge.py (FastAPI Router for Forge)
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from models import ForgeIdea, ForgeVote, ForgeWorker, InboxMessage, User
from database import get_db
from datetime import datetime
import uuid

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
    # Load ideas with workers' usernames
    ideas = db.query(ForgeIdea).options(joinedload(ForgeIdea.workers).joinedload(ForgeWorker.user)).all()

    return [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "status": i.status,
            "votes": i.votes,
            "user_email": i.user_email,
            "workers": [
                {"email": worker.user_email, "username": worker.user.username}  # Return username here
                for worker in i.workers
            ]
        }
        for i in ideas
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
        votes_count=0,
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
    
    # Log the incoming email and the idea's creator email for debugging
    print(f"Incoming user_email: {user_email}")
    
    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    print(f"Idea creator_email: {idea.user_email}")

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
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    workers = db.query(ForgeWorker).filter(ForgeWorker.idea_id == idea_id).all()
    workers_email = [worker.user_email for worker in workers]

    # Fetch the full user details for workers (optional)
    worker_users = db.query(User).filter(User.email.in_(workers_email)).all()
    workers_data = [{"email": worker.email, "username": worker.username} for worker in worker_users]

    return {
        "id": idea.id,
        "title": idea.title,
        "description": idea.description,
        "user_email": idea.user_email,
        "workers": workers_data,  # Adding workers data
    }

# === Vote on an Idea ===
@router.post("/forge/ideas/{idea_id}/vote")
def vote_idea(idea_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    user_id = request.headers.get("x-user-id")  # Get user_id from headers (sent manually)

    if not user_id:
        raise HTTPException(status_code=401, detail="Anonymous user identification required.")

    # Check if the user has already voted on this idea using user_id
    existing_vote = db.query(ForgeVote).filter_by(user_id=user_id, idea_id=idea_id).first()

    idea = db.query(ForgeIdea).get(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")

    if existing_vote:
        # If the user already voted, remove the vote and decrease the vote count
        db.delete(existing_vote)
        db.commit()

        # Recalculate the votes_count after removing the vote
        idea.votes_count = len(idea.votes)
        db.commit()

        return {"message": "Vote removed."}
    else:
        # If the user hasn't voted yet, add their vote
        vote = ForgeVote(user_id=user_id, user_email=user_email, idea_id=idea_id)
        db.add(vote)
        db.commit()

        # Recalculate the votes_count after adding the vote
        idea.votes_count = len(idea.votes)
        db.commit()

        return {"message": "Vote recorded."}

# === Join Idea ===
@router.post("/forge/ideas/{idea_id}/join")
def join_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to join idea.")

    # Fetch the user_id based on user_email
    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user_id = user.id  # Fetch the user_id from the User table

    # Check if the user has already joined the idea
    existing = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already joined this idea.")

    # Add the user to the idea's workers list, including the user_id
    join = ForgeWorker(user_email=user_email, idea_id=idea_id, user_id=user_id)  # Add user_id here
    db.add(join)
    db.commit()

    # Notify the creator of the idea
    idea = db.query(ForgeIdea).get(idea_id)
    if idea:
        creator_email = idea.user_email  # Assumes creator's email is stored in `user_email` field
        if creator_email and creator_email != user_email:
            content = f"👥 {user_email} has joined your idea \"{idea.title}\". They want to work on it!"

            # Fetch the user_id for the creator from the User table
            creator = db.query(User).filter_by(email=creator_email).first()
            if creator:
                # Creating the inbox notification for the creator
                inbox_message = InboxMessage(
                    user_id=creator.id,  # Using the user_id, not user_email
                    content=content,
                    timestamp=datetime.utcnow()  # Adding the timestamp
                )
                db.add(inbox_message)
                db.commit()

    return {"message": "You've joined this idea and notified the creator."}

# Remove a user from being a worker in an idea
@router.post("/forge/ideas/{idea_id}/remove-worker")
def remove_worker(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to remove worker.")

    # Find and remove the worker from the idea's workers list
    worker = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if not worker:
        raise HTTPException(status_code=400, detail="You are not a worker for this idea.")

    db.delete(worker)
    db.commit()

    return {"message": "You have left this idea."}


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