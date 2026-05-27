import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Optional

from database import SessionLocal
from routers.auth import get_current_user
from routers.ws_manager import RoomManager
from routers.ws_auth import get_ws_user
import json

from models import HomesteadRoom, HomesteadPlayerState

_manager = RoomManager("homestead")

router = APIRouter()

MAX_OWNED_ROOMS = 3
HOTBAR_BASE_SLOTS = 2  # must match Items.js HOTBAR_BASE_SLOTS


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


def _room_response(room: HomesteadRoom, role: str | None = None) -> dict:
    data = {
        "id":               room.id,
        "join_code":        room.join_code,
        "name":             room.name,
        "player1_id":       room.player1_id,
        "player2_id":       room.player2_id,
        "status":           room.status,
        "chest_inventory":  room.chest_inventory or {},
        "placed_objects":   room.placed_objects  or [],
        "town_state":       room.town_state       or {},
        "last_played_at":   room.last_played_at.isoformat() if room.last_played_at else None,
        "created_at":       room.created_at.isoformat()     if room.created_at     else None,
        "updated_at":       room.updated_at.isoformat()     if room.updated_at     else None,
    }
    if role is not None:
        data["role"] = role
    return data


def _player_state_response(ps: HomesteadPlayerState) -> dict:
    return {
        "role":         ps.role,
        "inventory":    ps.inventory    or {},
        "hotbar":       ps.hotbar       or [],
        "hotbar_slots": ps.hotbar_slots if ps.hotbar_slots is not None else HOTBAR_BASE_SLOTS,
        "equipment":    ps.equipment    or {"weapon": None, "armor": None, "accessory": None},
        "character":    ps.character    or {},
        "farm_plots":   ps.farm_plots   or {},
        "node_state":   ps.node_state   or {},
        # Daily run gate. Use `is not None` (not `or`) so a legitimate day-0 value
        # is never replaced by the default. NULL on legacy rows falls back to -1.
        "last_run_day": ps.last_run_day if ps.last_run_day is not None else -1,
        "updated_at":   ps.updated_at.isoformat() if ps.updated_at else None,
    }


def _default_player_state(role: str) -> dict:
    return {
        "role":         role,
        "inventory":    {},
        "hotbar":       [],
        "hotbar_slots": HOTBAR_BASE_SLOTS,
        "equipment":    {"weapon": None, "armor": None, "accessory": None},
        "character":    {},
        "farm_plots":   {},
        "node_state":   {},
        "last_run_day": -1,
        "updated_at":   None,
    }


def _bump_last_played(room: HomesteadRoom, db: Session):
    """Bump last_played_at and updated_at on any meaningful write."""
    now = datetime.now(timezone.utc)
    room.last_played_at = now
    room.updated_at     = now


def _get_room_for_member(room_id: int, user_id: int, db: Session) -> HomesteadRoom:
    """Fetch a room and verify the caller is a member. Raises 404/403."""
    room = db.query(HomesteadRoom).filter(HomesteadRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")
    return room


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateRoomRequest(BaseModel):
    name: Optional[str] = "My Homestead"

class RenameRoomRequest(BaseModel):
    name: str

class JoinRoomRequest(BaseModel):
    join_code: str

class UpdateChestRequest(BaseModel):
    chest_inventory: dict[str, Any]

class UpdateObjectsRequest(BaseModel):
    placed_objects: list[dict[str, Any]]

class UpdateTownStateRequest(BaseModel):
    town_state: dict[str, Any]

class PlaceObjectRequest(BaseModel):
    obj: dict[str, Any]

class UpdatePlayerStateRequest(BaseModel):
    inventory:    dict[str, Any]         = {}
    hotbar:       list[Any]              = []
    hotbar_slots: int                    = HOTBAR_BASE_SLOTS
    equipment:    dict[str, Any]         = {"weapon": None, "armor": None, "accessory": None}
    character:    dict[str, Any]         = {}
    farm_plots:   dict[str, Any]         = {}
    node_state:   dict[str, Any]         = {}
    # Daily run gate. Defaults to -1 so older clients that don't send it still
    # validate (and simply don't change the stored value meaningfully).
    last_run_day: int                    = -1


# ─── Room endpoints ───────────────────────────────────────────────────────────

@router.get("/rooms/mine")
def get_my_rooms(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Return all rooms the authenticated user belongs to (as p1 or p2),
    ordered by last_played_at descending. Replaces the old single-room endpoint.
    """
    user_id = current_user["id"]
    rooms = (
        db.query(HomesteadRoom)
        .filter(
            HomesteadRoom.status != "finished",
            (HomesteadRoom.player1_id == user_id) |
            (HomesteadRoom.player2_id == user_id),
        )
        .order_by(HomesteadRoom.last_played_at.desc())
        .limit(10)
        .all()
    )
    return [
        _room_response(room, role="p1" if room.player1_id == user_id else "p2")
        for room in rooms
    ]


@router.post("/rooms")
def create_room(
    body: CreateRoomRequest = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new homestead room. The caller becomes p1 (host).
    Enforces a cap of MAX_OWNED_ROOMS rooms per user.
    """
    user_id = current_user["id"]

    owned_count = db.query(HomesteadRoom).filter(
        HomesteadRoom.player1_id == user_id,
        HomesteadRoom.status != "finished",
    ).count()

    if owned_count >= MAX_OWNED_ROOMS:
        raise HTTPException(
            status_code=400,
            detail=f"Save limit reached. You can have up to {MAX_OWNED_ROOMS} homesteads.",
        )

    join_code = _generate_join_code(db)
    name      = (body.name.strip() if body and body.name and body.name.strip() else "My Homestead")

    room = HomesteadRoom(
        join_code=join_code,
        name=name,
        player1_id=user_id,
        status="waiting",
        chest_inventory={},
        placed_objects=[],
        town_state={},
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_response(room, role="p1")


@router.get("/rooms/{room_id}")
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)
    role    = "p1" if room.player1_id == user_id else "p2"
    return _room_response(room, role=role)


@router.patch("/rooms/{room_id}")
def rename_room(
    room_id: int,
    body: RenameRoomRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Rename a homestead. Host (p1) only."""
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)

    if room.player1_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can rename this homestead")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    room.name       = name
    room.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room, role="p1")


@router.delete("/rooms/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Permanently delete a homestead and all its player states.
    Host (p1) only. CASCADE on the FK handles HomesteadPlayerState rows.
    """
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)

    if room.player1_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can delete this homestead")

    db.delete(room)
    db.commit()
    return {"ok": True}


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
    _bump_last_played(room, db)
    db.commit()
    db.refresh(room)
    return _room_response(room, role="p2")


# ─── Shared room state ────────────────────────────────────────────────────────

@router.patch("/rooms/{room_id}/chest")
def update_chest(
    room_id: int,
    body: UpdateChestRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)

    room.chest_inventory = body.chest_inventory
    _bump_last_played(room, db)
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
    room    = _get_room_for_member(room_id, user_id, db)

    room.placed_objects = body.placed_objects
    _bump_last_played(room, db)
    db.commit()
    db.refresh(room)
    return _room_response(room)


@router.patch("/rooms/{room_id}/town")
def update_town_state(
    room_id: int,
    body: UpdateTownStateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)

    room.town_state = body.town_state
    _bump_last_played(room, db)
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
    room    = _get_room_for_member(room_id, user_id, db)

    objects = list(room.placed_objects or [])
    objects = [o for o in objects if o.get("id") != body.obj.get("id")]
    objects.append(body.obj)

    room.placed_objects = objects
    _bump_last_played(room, db)
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
    room    = _get_room_for_member(room_id, user_id, db)

    room.placed_objects = [o for o in (room.placed_objects or []) if o.get("id") != object_id]
    _bump_last_played(room, db)
    db.commit()
    db.refresh(room)
    return _room_response(room)


# ─── Player state (per-player, per-room) ─────────────────────────────────────

@router.get("/rooms/{room_id}/player-state")
def get_player_state(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Load the calling user's player state for this room.
    Returns empty defaults (not 404) if no record exists yet —
    this handles new players and the one-time localStorage migration.
    """
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)
    role    = "p1" if room.player1_id == user_id else "p2"

    ps = db.query(HomesteadPlayerState).filter(
        HomesteadPlayerState.room_id == room_id,
        HomesteadPlayerState.user_id == user_id,
    ).first()

    if not ps:
        return _default_player_state(role)

    return _player_state_response(ps)


@router.put("/rooms/{room_id}/player-state")
def upsert_player_state(
    room_id: int,
    body: UpdatePlayerStateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Upsert the calling user's player state for this room.
    Called on a ~2s debounce after any inventory / hotbar / equipment /
    character / farm / node / run-gate change. Also bumps last_played_at on the room.
    """
    user_id = current_user["id"]
    room    = _get_room_for_member(room_id, user_id, db)
    role    = "p1" if room.player1_id == user_id else "p2"

    ps = db.query(HomesteadPlayerState).filter(
        HomesteadPlayerState.room_id == room_id,
        HomesteadPlayerState.user_id == user_id,
    ).first()

    if ps:
        ps.inventory    = body.inventory
        ps.hotbar       = body.hotbar
        ps.hotbar_slots = body.hotbar_slots
        ps.equipment    = body.equipment
        ps.character    = body.character
        ps.farm_plots   = body.farm_plots
        ps.node_state   = body.node_state
        ps.last_run_day = body.last_run_day
        ps.updated_at   = datetime.now(timezone.utc)
    else:
        ps = HomesteadPlayerState(
            room_id=room_id,
            user_id=user_id,
            role=role,
            inventory=body.inventory,
            hotbar=body.hotbar,
            hotbar_slots=body.hotbar_slots,
            equipment=body.equipment,
            character=body.character,
            farm_plots=body.farm_plots,
            node_state=body.node_state,
            last_run_day=body.last_run_day,
        )
        db.add(ps)

    _bump_last_played(room, db)
    db.commit()
    db.refresh(ps)
    return _player_state_response(ps)


# ─── WebSocket ────────────────────────────────────────────────────────────────

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
    user = await get_ws_user(websocket)
    if not user:
        return

    user_id  = user["id"]
    room_key = str(room_id)

    peer_count = await _manager.connect(room_key, websocket)

    await websocket.send_text(json.dumps({
        "event":      "connected",
        "user_id":    user_id,
        "peer_count": peer_count,
    }))

    if peer_count == 2:
        await _manager.relay(room_key, websocket, json.dumps({
            "event":   "partner_connected",
            "user_id": user_id,
        }))

    try:
        while True:
            raw = await websocket.receive_text()
            await _manager.relay(room_key, websocket, raw)

    except WebSocketDisconnect:
        _manager.disconnect(room_key, websocket)
        await _manager.relay(room_key, websocket, json.dumps({
            "event":   "partner_disconnected",
            "user_id": user_id,
        }))