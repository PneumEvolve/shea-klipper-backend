"""
routers/inkrun.py
Endpoints for InkRun multiplayer game rooms.
"""
import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import InkRunRoom
from routers.auth import get_current_user

router = APIRouter()


# ─── DB dependency ────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(random.choices(string.ascii_uppercase, k=6))
        exists = db.query(InkRunRoom).filter(
            InkRunRoom.join_code == code,
            InkRunRoom.status != "finished",
        ).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Could not generate a unique join code")


def _room_response(room: InkRunRoom) -> dict:
    return {
        "id":          room.id,
        "join_code":   room.join_code,
        "player1_id":  room.player1_id,
        "player2_id":  room.player2_id,
        "status":      room.status,
        "map_seed":    room.map_seed,
        "final_score": room.final_score,
        "created_at":  room.created_at.isoformat() if room.created_at else None,
        "ended_at":    room.ended_at.isoformat()   if room.ended_at   else None,
    }


# ─── Schemas ──────────────────────────────────────────────────────────────────

class JoinRoomRequest(BaseModel):
    join_code: str

class SaveScoreRequest(BaseModel):
    final_score: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/rooms")
def create_room(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id   = current_user["id"]
    join_code = _generate_join_code(db)
    map_seed  = random.randint(1, 2**31 - 1)

    room = InkRunRoom(
        join_code=join_code,
        player1_id=user_id,
        map_seed=map_seed,
        status="waiting",
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.get("/rooms/{room_id}")
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room    = db.query(InkRunRoom).filter(InkRunRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    return _room_response(room)


@router.post("/rooms/join")
def join_room(
    body: JoinRoomRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    code    = body.join_code.strip().upper()

    room = db.query(InkRunRoom).filter(
        InkRunRoom.join_code == code,
        InkRunRoom.status == "waiting",
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found or already started")
    if room.player1_id == user_id:
        raise HTTPException(status_code=400, detail="You can't join your own room as player 2")

    room.player2_id = user_id
    room.status     = "active"
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.patch("/rooms/{room_id}")
def save_score(
    room_id: int,
    body: SaveScoreRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room    = db.query(InkRunRoom).filter(InkRunRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room.final_score = body.final_score
    room.status      = "finished"
    room.ended_at    = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)