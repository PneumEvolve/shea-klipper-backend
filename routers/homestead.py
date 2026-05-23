"""
routers/homestead.py
Endpoints for Homestead multiplayer game rooms.
Mirrors the inkrun.py pattern exactly.
"""
import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any

from database import SessionLocal
from models import HomesteadRoom
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
        exists = db.query(HomesteadRoom).filter(
            HomesteadRoom.join_code == code,
            HomesteadRoom.status != "finished",
        ).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Could not generate a unique join code")


def _room_response(room: HomesteadRoom) -> dict:
    return {
        "id":               room.id,
        "join_code":        room.join_code,
        "player1_id":       room.player1_id,
        "player2_id":       room.player2_id,
        "status":           room.status,
        "chest_inventory":  room.chest_inventory or {},
        "placed_objects":   room.placed_objects  or [],
        "created_at":       room.created_at.isoformat() if room.created_at else None,
        "updated_at":       room.updated_at.isoformat() if room.updated_at else None,
    }


# ─── Schemas ──────────────────────────────────────────────────────────────────

class JoinRoomRequest(BaseModel):
    join_code: str

class UpdateChestRequest(BaseModel):
    chest_inventory: dict[str, Any]

class UpdateObjectsRequest(BaseModel):
    placed_objects: list[dict[str, Any]]

class PlaceObjectRequest(BaseModel):
    obj: dict[str, Any]

class RemoveObjectRequest(BaseModel):
    object_id: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/rooms")
def create_room(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new homestead room. Creator becomes player 1."""
    user_id   = current_user["id"]
    join_code = _generate_join_code(db)

    room = HomesteadRoom(
        join_code=join_code,
        player1_id=user_id,
        status="waiting",
        chest_inventory={},
        placed_objects=[],
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
    """Fetch a room by ID. Used on page load to hydrate world state."""
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()

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
    """Join an existing room by join code. Joiner becomes player 2."""
    user_id = current_user["id"]
    code    = body.join_code.strip().upper()

    room = db.query(HomesteadRoom).filter(
        HomesteadRoom.join_code == code,
        HomesteadRoom.status == "waiting",
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


@router.patch("/rooms/{room_id}/chest")
def update_chest(
    room_id: int,
    body: UpdateChestRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Overwrite the shared chest inventory.
    Called after a run completes or when the chest is modified on the homestead.
    The frontend merges loot before calling this — we just persist whatever it sends.
    """
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room.chest_inventory = body.chest_inventory
    room.updated_at      = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.patch("/rooms/{room_id}/objects")
def update_objects(
    room_id: int,
    body: UpdateObjectsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Overwrite the full placed_objects list.
    Used for bulk saves (e.g. after a building session).
    For incremental changes during a live session, use the Supabase
    broadcast events (object_placed / object_removed) instead —
    those are real-time and don't need a REST round-trip.
    """
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room.placed_objects = body.placed_objects
    room.updated_at     = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.post("/rooms/{room_id}/objects")
def place_object(
    room_id: int,
    body: PlaceObjectRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Append a single object to placed_objects.
    Convenience endpoint for single placements without sending the whole list.
    """
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    objects = list(room.placed_objects or [])
    # Prevent duplicate IDs
    objects = [o for o in objects if o.get("id") != body.obj.get("id")]
    objects.append(body.obj)

    room.placed_objects = objects
    room.updated_at     = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.delete("/rooms/{room_id}/objects/{object_id}")
def remove_object(
    room_id: int,
    object_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a single placed object by its id string."""
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room.placed_objects = [o for o in (room.placed_objects or []) if o.get("id") != object_id]
    room.updated_at     = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)