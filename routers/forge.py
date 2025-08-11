# forge.py (FastAPI Router for Forge)
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session, joinedload, aliased
from pydantic import BaseModel
from models import ForgeIdea, ForgeVote, ForgeWorker, InboxMessage, User, Conversation, ConversationUser
from database import get_db
from datetime import datetime
from typing import Optional
from sqlalchemy import func
import uuid

router = APIRouter()

SYSTEM_EMAIL = "system@domain.com"

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

class ForgeIdeaNoteBase(BaseModel):
    content: str

    class Config:
        orm_mode = True  # Ensure Pydantic models can handle SQLAlchemy models


class ForgeIdeaNoteCreate(ForgeIdeaNoteBase):
    idea_id: int  # Only need content and idea_id for creation


class ForgeIdeaNote(ForgeIdeaNoteBase):
    id: Optional[int]  # Will be added after creation in the database
    idea_id: int

    class Config:
        orm_mode = True  # Enable ORM mode to handle SQLAlchemy model

def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == SYSTEM_EMAIL).first()
    if sys:
        return sys
    sys = User(email=SYSTEM_EMAIL, username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys



def find_existing_system_convo(db: Session, user: User) -> Conversation | None:
    """
    Try to find a System DM by:
      1) canonical name: system:{user.email}
      2) any conversation that has BOTH (System, user) as participants
    """
    canonical = f"system:{user.email}"
    convo = db.query(Conversation).filter(Conversation.name == canonical).first()
    if convo:
        return convo

    sys_user = get_or_create_system_user(db)
    cu1 = aliased(ConversationUser)
    cu2 = aliased(ConversationUser)

    return (
        db.query(Conversation)
        .join(cu1, cu1.conversation_id == Conversation.id)
        .join(cu2, cu2.conversation_id == Conversation.id)
        .filter(cu1.user_id == user.id, cu2.user_id == sys_user.id)
        .first()
    )

def ensure_system_conversation(db: Session, user: User) -> Conversation:
    """
    Idempotent: reuses an existing System DM if present; otherwise creates one.
    Also normalizes the name to system:{user.email} and ensures both participants exist.
    """
    sys_user = get_or_create_system_user(db)
    convo = find_existing_system_convo(db, user)

    if convo:
        # normalize name if it wasn't in canonical form
        canonical = f"system:{user.email}"
        if (convo.name or "") != canonical:
            convo.name = canonical
        # ensure both participants exist
        existing = (
            db.query(ConversationUser)
            .filter(ConversationUser.conversation_id == convo.id,
                    ConversationUser.user_id.in_([sys_user.id, user.id]))
            .all()
        )
        present = {cu.user_id for cu in existing}
        if sys_user.id not in present:
            db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))
        if user.id not in present:
            db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
        db.commit()
        db.refresh(convo)
        return convo

    # create new canonical convo
    convo = Conversation(name=f"system:{user.email}")
    db.add(convo)
    db.flush()
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.commit()
    db.refresh(convo)
    return convo

def resolve_identity(request: Request) -> str:
    ident = request.headers.get("x-user-email")
    if ident and ident.strip():
        return ident.strip()
    legacy = request.headers.get("x-user-id")
    if legacy and legacy.strip():
        return f"anon:{legacy.strip()}"
    raise HTTPException(status_code=401, detail="Missing identity")

# === Get All Ideas ===
@router.get("/forge/ideas")
def get_ideas(db: Session = Depends(get_db)):
    # Load ideas with the votes relationship
    ideas = db.query(ForgeIdea).options(joinedload(ForgeIdea.votes)).all()

    return [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "status": i.status,
            "votes": [vote for vote in i.votes],  # Make sure votes are included
            "user_email": i.user_email,
            "workers": [
                {"email": worker.user_email, "username": worker.user.username}
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
    # Query to fetch the ForgeIdea
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    
    # If the idea is not found, raise a 404 error
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Query to fetch the workers associated with this idea
    workers = db.query(ForgeWorker).filter(ForgeWorker.idea_id == idea_id).all()
    workers_email = [worker.user_email for worker in workers]

    # Fetch the full user details for workers (optional)
    worker_users = db.query(User).filter(User.email.in_(workers_email)).all()
    workers_data = [{"email": worker.email, "username": worker.username} for worker in worker_users]

    # Return the idea along with the workers and notes data
    return {
        "id": idea.id,
        "title": idea.title,
        "description": idea.description,
        "user_email": idea.user_email,
        "workers": workers_data,  # Adding workers data
        "notes": idea.notes  # Return the notes directly, since it's now part of the ForgeIdea model
    }

# === Vote on an Idea ===
@router.post("/forge/ideas/{idea_id}/vote")
def toggle_vote(idea_id: int, request: Request, db: Session = Depends(get_db)):
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    identity = resolve_identity(request)  # real email or "anon:{uuid}"

    existing = (
        db.query(ForgeVote)
        .filter(ForgeVote.idea_id == idea_id, ForgeVote.user_email == identity)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        voted = False
    else:
        db.add(ForgeVote(idea_id=idea_id, user_email=identity))
        db.commit()
        voted = True

    votes_count = db.query(func.count(ForgeVote.id)).filter(ForgeVote.idea_id == idea_id).scalar()
    try:
        idea.votes_count = votes_count
        db.commit()
    except Exception:
        db.rollback()

    return {"status": "ok", "idea_id": idea_id, "voted": voted, "votes_count": votes_count}

# === Join Idea ===
@router.post("/forge/ideas/{idea_id}/join")
def join_idea(idea_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = request.headers.get("x-user-email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Login required to join idea.")

    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    existing = db.query(ForgeWorker).filter_by(user_email=user_email, idea_id=idea_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already joined this idea.")

    join = ForgeWorker(user_email=user_email, idea_id=idea_id, user_id=user.id)
    db.add(join)
    db.commit()

    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if idea:
        creator_email = idea.user_email
        if creator_email and creator_email != user_email:
            creator = db.query(User).filter_by(email=creator_email).first()
            if creator:
                convo = ensure_system_conversation(db, creator)
                sys_user = get_or_create_system_user(db)
                content = f"👥 {user_email} has joined your idea “{idea.title}”. They want to work on it!"
                db.add(InboxMessage(
                    user_id=sys_user.id,
                    content=content,
                    timestamp=datetime.utcnow(),
                    conversation_id=convo.id
                ))
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

# Create a Pydantic model to handle the incoming request
class NoteContent(BaseModel):
    content: str

@router.post("/forge/ideas/{idea_id}/notes")
async def update_notes(idea_id: int, note_content: NoteContent, db: Session = Depends(get_db)):
    # Fetch the idea from the database
    idea = db.query(ForgeIdea).filter(ForgeIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Update the notes field in the ForgeIdea model
    idea.notes = note_content.content  # Access content from the NoteContent model
    db.commit()  # Save the changes to the database
    db.refresh(idea)  # Refresh the idea instance to get updated data
    return {"message": "Note updated successfully", "idea": idea}