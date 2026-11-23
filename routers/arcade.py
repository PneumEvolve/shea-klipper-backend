"""
Bash & Dad's Arcade — the shared multiplayer + save backbone for every arcade game.

  • Rooms   are saved to both players' accounts. Host (p1) makes one, shares the
            4-letter code once, and after that both players just tap the room in
            their list to jump back in. Host = p1.
  • Saves   belong to the user's ACCOUNT, per game — not to a room — so progress
            follows you to any device you sign in on.
  • The WebSocket is a dumb relay. It never looks inside game events, so adding
            a new game needs zero backend changes beyond adding its id to
            KNOWN_GAMES.

Mount in main.py:
    from routers import arcade
    app.include_router(arcade.router, prefix="/arcade", tags=["Arcade"])
"""
import json
import random
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from database import SessionLocal
from models import ArcadeRoom, ArcadeSave
from routers.auth import get_current_user
from routers.ws_auth import get_ws_user
from routers.ws_manager import RoomManager

router = APIRouter()
_manager = RoomManager("arcade")

# Add a game's id here when you add it to the frontend registry.
KNOWN_GAMES = {"blob-test", "creature-crashers"}

MAX_ROOMS_PER_GAME = 3            # rooms a player can HOST per game (like Homestead's 3 saves)
MAX_SAVE_BYTES     = 256_000      # plenty for unlocks/levels/XP; stops runaway blobs
CODE_ALPHABET      = "ABCDEFGHJKMNPQRSTUVWXYZ"   # no I / L / O — easy to read off a screen
CODE_LENGTH        = 4


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_game(game_id: str) -> None:
    if game_id not in KNOWN_GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")


def _live_rooms(db: Session):
    """Rooms that haven't been deleted."""
    return db.query(ArcadeRoom).filter(ArcadeRoom.status != "finished")


def _generate_join_code(db: Session) -> str:
    # Codes only need to be unique among live rooms; deleted rooms free theirs up.
    for _ in range(30):
        code = "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
        if not _live_rooms(db).filter(ArcadeRoom.join_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Could not generate a join code")


def _role_for(room: ArcadeRoom, user_id: int) -> str | None:
    if room.player1_id == user_id:
        return "p1"
    if room.player2_id == user_id:
        return "p2"
    return None


def _display_name(user) -> Optional[str]:
    if user is None:
        return None
    if getattr(user, "username", None):
        return user.username
    email = getattr(user, "email", None) or ""
    return email.split("@")[0] or "player"


def _room_response(room: ArcadeRoom, user_id: int) -> dict:
    return {
        "id":           room.id,
        "game_id":      room.game_id,
        "join_code":    room.join_code,
        "status":       room.status,
        "player1_id":   room.player1_id,
        "player2_id":   room.player2_id,
        "player1_name": _display_name(room.player1),
        "player2_name": _display_name(room.player2),
        "role":         _role_for(room, user_id),
        "created_at":   room.created_at.isoformat() if room.created_at else None,
        "last_played_at": room.updated_at.isoformat() if room.updated_at else None,
    }


def _get_room_for_member(room_id: int, user_id: int, db: Session) -> ArcadeRoom:
    room = _live_rooms(db).filter(ArcadeRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if _role_for(room, user_id) is None:
        raise HTTPException(status_code=403, detail="Not a member of this room")
    return room


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateRoomRequest(BaseModel):
    game_id: str

class JoinRoomRequest(BaseModel):
    join_code: str

class SaveRequest(BaseModel):
    data: dict[str, Any]


# ─── Rooms ────────────────────────────────────────────────────────────────────
# NOTE: /rooms/mine must stay above /rooms/{room_id} so "mine" isn't read as an id.

@router.get("/rooms/mine")
def my_rooms(
    game_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Every live room this player is in for a game, most recently played first."""
    _check_game(game_id)
    user_id = current_user["id"]
    rooms = (
        _live_rooms(db)
        .filter(
            ArcadeRoom.game_id == game_id,
            (ArcadeRoom.player1_id == user_id) | (ArcadeRoom.player2_id == user_id),
        )
        .order_by(ArcadeRoom.updated_at.desc())
        .limit(20)
        .all()
    )
    return [_room_response(r, user_id) for r in rooms]


@router.post("/rooms")
def create_room(
    body: CreateRoomRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Make a room. The caller becomes p1 (host). It stays on both accounts until deleted."""
    _check_game(body.game_id)
    user_id = current_user["id"]

    hosted = _live_rooms(db).filter(
        ArcadeRoom.player1_id == user_id,
        ArcadeRoom.game_id == body.game_id,
    ).count()
    if hosted >= MAX_ROOMS_PER_GAME:
        raise HTTPException(
            status_code=400,
            detail=f"You can host up to {MAX_ROOMS_PER_GAME} rooms for this game. Delete one to make another.",
        )

    room = ArcadeRoom(
        game_id=body.game_id,
        join_code=_generate_join_code(db),
        player1_id=user_id,
        status="waiting",
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_response(room, user_id)


@router.post("/rooms/join")
def join_room(
    body: JoinRoomRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """First-time join with a code. After this the room shows in the player's list."""
    user_id = current_user["id"]
    code = body.join_code.strip().upper()

    room = (
        _live_rooms(db)
        .filter(ArcadeRoom.join_code == code)
        .order_by(ArcadeRoom.created_at.desc())
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="No room with that code")

    if room.player1_id == user_id:
        # Same account on both devices would make both of them the host.
        raise HTTPException(
            status_code=400,
            detail="You're the host of this room. The other player needs to sign in with their own account.",
        )
    if room.player2_id == user_id:
        return _room_response(room, user_id)          # already in it — just let them back in
    if room.player2_id is not None:
        raise HTTPException(status_code=409, detail="That room already has two players")

    room.player2_id = user_id
    room.status = "active"
    room.updated_at = _now()
    db.commit()
    db.refresh(room)
    return _room_response(room, user_id)


@router.get("/rooms/{room_id}")
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Used to resume a room from the list."""
    room = _get_room_for_member(room_id, current_user["id"], db)
    return _room_response(room, current_user["id"])


@router.delete("/rooms/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Host: deletes the room for both players.
    Guest: leaves the room (it disappears from their list, and the host's code
           works again for someone new).
    """
    user_id = current_user["id"]
    room = _get_room_for_member(room_id, user_id, db)
    if room.player1_id == user_id:
        room.status = "finished"
    else:
        room.player2_id = None
        room.status = "waiting"
    room.updated_at = _now()
    db.commit()
    return {"ok": True}


# ─── Account saves (per user, per game) ───────────────────────────────────────

def _save_response(save: ArcadeSave | None, game_id: str, user_id: int) -> dict:
    return {
        "game_id":    game_id,
        "user_id":    user_id,
        "data":       (save.data if save and save.data is not None else {}),
        "updated_at": save.updated_at.isoformat() if save and save.updated_at else None,
    }


@router.get("/saves/{game_id}")
def get_save(
    game_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Returns empty data (not 404) when the player has never saved this game."""
    _check_game(game_id)
    user_id = current_user["id"]
    save = db.query(ArcadeSave).filter(
        ArcadeSave.user_id == user_id, ArcadeSave.game_id == game_id
    ).first()
    return _save_response(save, game_id, user_id)


@router.put("/saves/{game_id}")
def put_save(
    game_id: str,
    body: SaveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _check_game(game_id)
    if len(json.dumps(body.data)) > MAX_SAVE_BYTES:
        raise HTTPException(status_code=413, detail="Save is too large")

    user_id = current_user["id"]
    save = db.query(ArcadeSave).filter(
        ArcadeSave.user_id == user_id, ArcadeSave.game_id == game_id
    ).first()
    if save:
        save.data = body.data
        save.updated_at = _now()
    else:
        save = ArcadeSave(user_id=user_id, game_id=game_id, data=body.data, updated_at=_now())
        db.add(save)
    db.commit()
    db.refresh(save)
    return _save_response(save, game_id, user_id)


# ─── WebSocket relay ──────────────────────────────────────────────────────────

@router.websocket("/ws/{room_id}")
async def arcade_websocket(websocket: WebSocket, room_id: int):
    """
    Connect: wss://yourserver/arcade/ws/{room_id}?token={jwt}

    Every message is JSON with an "event" field. The server forwards it to the
    other player untouched. Server-sent events:
        connected            { user_id, role, peer_count }   (to you)
        partner_connected    { user_id, role }               (to the other player)
        partner_disconnected { user_id }                     (to the other player)
    Close code 4003 = room deleted or you're not in it (client stops retrying).
    """
    user = await get_ws_user(websocket)
    if not user:
        return
    user_id = user["id"]

    db = SessionLocal()
    try:
        room = _live_rooms(db).filter(ArcadeRoom.id == room_id).first()
        role = _role_for(room, user_id) if room else None
        if role:
            room.updated_at = _now()      # "last played" for the room list
            db.commit()
    finally:
        db.close()

    if role is None:
        # Accept first so the browser actually receives our 4003 close code.
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
        await websocket.close(code=4003)
        return

    room_key = str(room_id)
    peer_count = await _manager.connect(room_key, websocket)

    await websocket.send_text(json.dumps({
        "event":      "connected",
        "user_id":    user_id,
        "role":       role,
        "peer_count": peer_count,
    }))
    if peer_count >= 2:
        await _manager.relay(room_key, websocket, json.dumps({
            "event":   "partner_connected",
            "user_id": user_id,
            "role":    role,
        }))

    try:
        while True:
            raw = await websocket.receive_text()
            await _manager.relay(room_key, websocket, raw)
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect(room_key, websocket)
        try:
            await _manager.relay(room_key, websocket, json.dumps({
                "event":   "partner_disconnected",
                "user_id": user_id,
            }))
        except Exception:
            pass