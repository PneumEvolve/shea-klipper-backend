from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Problem, ProblemVote
from database import get_db
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# ---------- Pydantic Schemas ----------
class ProblemCreate(BaseModel):
    title: str
    description: str = ""

class ProblemResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    created_at: datetime
    vote_count: int

    class Config:
        orm_mode = True

class VoteRequest(BaseModel):
    user_id: str
    vote_type: str = "upvote"

@router.post("/problems", response_model=ProblemResponse)
def create_problem(problem: ProblemCreate, db: Session = Depends(get_db)):
    db_problem = Problem(**problem.dict())
    db.add(db_problem)
    db.commit()
    db.refresh(db_problem)
    return {
        **db_problem.__dict__,
        "vote_count": 0
    }

@router.get("/problems", response_model=list[ProblemResponse])
def get_problems(db: Session = Depends(get_db)):
    problems = db.query(Problem).all()

    results = []
    for p in problems:
        vote_count = db.query(ProblemVote).filter_by(problem_id=p.id).count()
        results.append({
            **p.__dict__,
            "vote_count": vote_count
        })

    # Sort by vote count descending
    return sorted(results, key=lambda x: x["vote_count"], reverse=True)

@router.post("/problems/{problem_id}/vote")
def vote_on_problem(problem_id: int, vote: VoteRequest, db: Session = Depends(get_db)):
    # Prevent double voting by same user
    existing = db.query(ProblemVote).filter_by(user_id=vote.user_id, problem_id=problem_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User has already voted on this problem.")

    db_vote = ProblemVote(
        user_id=vote.user_id,
        problem_id=problem_id,
        vote_type=vote.vote_type
    )
    db.add(db_vote)
    db.commit()
    return {"message": "Vote recorded."}

@router.get("/problems/{problem_id}", response_model=ProblemResponse)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter_by(id=problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    vote_count = db.query(ProblemVote).filter_by(problem_id=problem_id).count()
    return {
        **problem.__dict__,
        "vote_count": vote_count
    }