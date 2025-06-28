from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import BlogPost, BlogComment, User
from schemas import BlogPostCreate, BlogPostOut, BlogCommentCreate, BlogCommentOut
from routers.auth import get_current_user  # Assuming you already use this

router = APIRouter(
    prefix="/blog",
    tags=["Blog"]
)

# ✅ Get all blog posts
@router.get("/", response_model=List[BlogPostOut])
def get_all_posts(db: Session = Depends(get_db)):
    return db.query(BlogPost).order_by(BlogPost.created_at.desc()).all()

# ✅ Get a single blog post
@router.get("/{post_id}", response_model=BlogPostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

# ✅ Create new blog post (only if user is sheaklipper@gmail.com)
@router.post("/", response_model=BlogPostOut)
def create_post(
    post_data: BlogPostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.email != "sheaklipper@gmail.com":
        raise HTTPException(status_code=403, detail="Only Shea can post")

    new_post = BlogPost(
        title=post_data.title,
        content=post_data.content,
        user_id=current_user.id
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

# ✅ Add a comment to a post (auth optional)
@router.post("/comment", response_model=BlogCommentOut)
def add_comment(
    comment: BlogCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_comment = BlogComment(
        content=comment.content,
        post_id=comment.post_id,
        user_id=current_user.id if current_user else None
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

# ✅ Get comments for a blog post
@router.get("/{post_id}/comments", response_model=List[BlogCommentOut])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    return db.query(BlogComment).filter(BlogComment.post_id == post_id).order_by(BlogComment.created_at.asc()).all()