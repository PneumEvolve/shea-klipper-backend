from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from models import Thread, Comment
from schemas import ThreadCreate, CommentCreate, ThreadOut, CommentOut
from database import get_db
from typing import Optional, List

router = APIRouter()

def get_optional_user(request: Request) -> Optional[dict]:
    token = request.headers.get("Authorization")
    if token:
        try:
            return get_current_user_dependency(token)  # Your existing user checker
        except:
            return None
    return None

@router.post("/threads", response_model=ThreadOut)
def create_thread(thread: ThreadCreate, db: Session = Depends(get_db), user: Optional[dict] = Depends(get_optional_user)):
    new_thread = Thread(text=thread.text, user_id=user["id"] if user else None)
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)
    return new_thread

@router.get("/threads", response_model=List[ThreadOut])
def get_threads(db: Session = Depends(get_db)):
    return db.query(Thread).all()

@router.post("/comments", response_model=ThreadOut)
def add_comment(comment: CommentCreate, db: Session = Depends(get_db), user: Optional[dict] = Depends(get_optional_user)):
    thread = db.query(Thread).filter(Thread.id == comment.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    new_comment  = Comment(thread_id=comment.thread_id, text=comment.text, user_id=user["id"])
    db.commit()
    db.refresh(thread)
    return new_comment

@router.get("/comments/{comment_id}", response_model=CommentOut)
def get_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@router.get("/threads/{thread_id}/comments", response_model=List[CommentOut])
def get_comments_for_thread(thread_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.thread_id == thread_id).all()
    return comments

@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user_dependency)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread or thread.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this thread")
    db.delete(thread)
    db.commit()
    return {"detail": "Thread deleted"}

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user_dependency)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment or comment.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    db.delete(comment)
    db.commit()
    return {"detail": "Comment deleted"}