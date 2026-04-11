# routers/rootwork.py
 
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
 
from database import get_db
from routers.auth import get_current_user
from models import User
 
logger = logging.getLogger(__name__)
 
router = APIRouter()
 
 
class RootWorkStateIn(BaseModel):
    data: str  # JSON-serialized game state
 
 
# ─── GET /rootwork/state ──────────────────────────────────────────────────────
 
@router.get("/rootwork/state")
def get_rootwork_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load the player's saved RootWork game state."""
    row = db.execute(
        text("SELECT data FROM rootwork_states WHERE user_id = :uid"),
        {"uid": current_user.id},
    ).first()
 
    if not row:
        return {"data": None}
 
    return {"data": row[0]}
 
 
# ─── POST /rootwork/state ─────────────────────────────────────────────────────
 
@router.post("/rootwork/state")
def save_rootwork_state(
    payload: RootWorkStateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the player's RootWork game state (upsert)."""
    if not payload.data:
        raise HTTPException(status_code=400, detail="No data provided.")
 
    db.execute(
        text("""
            INSERT INTO rootwork_states (user_id, data, updated_at)
            VALUES (:uid, :data, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
        """),
        {"uid": current_user.id, "data": payload.data},
    )
    db.commit()
 
    return {"status": "ok"}