import random
import string
from datetime import datetime, timezone
 
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any
 
from database import SessionLocal
from routers.auth import get_current_user

from routers.ws_manager import RoomManager
from routers.ws_auth import get_ws_user
import json

from models import HomesteadRoom
 
_manager = RoomManager("homestead")
 
router = APIRouter()
 
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
 
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
        "town_state":       room.town_state       or {},   # ← NEW
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
 
class UpdateTownStateRequest(BaseModel):          # ← NEW
    town_state: dict[str, Any]
 
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
    user_id   = current_user["id"]
    join_code = _generate_join_code(db)
 
    room = HomesteadRoom(
        join_code=join_code,
        player1_id=user_id,
        status="waiting",
        chest_inventory={},
        placed_objects=[],
        town_state={},           # ← NEW
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
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()
 
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")
 
    return _room_response(room)
 
 
@router.get("/rooms/mine")
def get_my_room(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room = (
        db.query(HomesteadRoom)
        .filter(
            HomesteadRoom.status != "finished",
            (HomesteadRoom.player1_id == user_id) |
            (HomesteadRoom.player2_id == user_id),
        )
        .order_by(HomesteadRoom.updated_at.desc())
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="No active room found")
 
    role = "p1" if room.player1_id == user_id else "p2"
    return { **_room_response(room), "role": role }
 
 
@router.post("/rooms/join")
def join_room(
    body: JoinRoomRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
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
 
 
@router.patch("/rooms/{room_id}/town")                     # ← NEW ENDPOINT
def update_town_state(
    room_id: int,
    body: UpdateTownStateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Overwrite the town state (NPCs, treasury, Mayor assignment, etc.).
    Called by useTownState.js on a 2-second debounce, or immediately on
    important mutations (NPC arrives, Mayor assigned, quest delivered).
    The frontend is authoritative — we just persist whatever it sends.
    """
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()
 
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")
 
    room.town_state = body.town_state
    room.updated_at = datetime.now(timezone.utc)
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
    user_id = current_user["id"]
    room    = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()
 
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")
 
    objects = list(room.placed_objects or [])
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

@router.websocket("/ws/{room_id}")
async def homestead_websocket(websocket: WebSocket, room_id: int):
    """
    Real-time relay for Homestead co-op.
 
    Connect: ws://yourserver/homestead/ws/{room_id}?token={jwt}
 
    All messages are JSON with a required "event" field:
      { "event": "player_move", "x": 10, "y": 20, "facing": "right" }
 
    The server relays each message to the other player in the room.
    Nothing is written to the DB here — REST endpoints handle persistence.
    """
    # ── Auth ──────────────────────────────────────────────────────────────────
    user = await get_ws_user(websocket)
    if not user:
        return  # ws_auth already closed the connection
 
    user_id   = user["id"]
    room_key  = str(room_id)
 
    # ── Connect & announce ────────────────────────────────────────────────────
    peer_count = await _manager.connect(room_key, websocket)
 
    # Tell this client which player slot they are and how many peers are present
    await websocket.send_text(json.dumps({
        "event":      "connected",
        "user_id":    user_id,
        "peer_count": peer_count,          # 1 = waiting for partner, 2 = both here
    }))
 
    # Tell the other player that their partner just connected
    if peer_count == 2:
        await _manager.relay(room_key, websocket, json.dumps({
            "event":   "partner_connected",
            "user_id": user_id,
        }))
 
    # ── Main relay loop ───────────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()
            await _manager.relay(room_key, websocket, raw)
 
    except WebSocketDisconnect:
        _manager.disconnect(room_key, websocket)
 
        # Tell the remaining player their partner left
        await _manager.relay(room_key, websocket, json.dumps({
            "event":   "partner_disconnected",
            "user_id": user_id,
        }))