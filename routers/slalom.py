"""
routers/slalom.py
Endpoints for Freeskate Slalom multiplayer game rooms — and the leaderboard.
"""
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import SlalomRoom, SlalomScore
from routers.auth import get_current_user

from routers.ws_manager import RoomManager
from routers.ws_auth import get_ws_user
import json
 
_manager = RoomManager("slalom")

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
        exists = db.query(SlalomRoom).filter(
            SlalomRoom.join_code == code,
            SlalomRoom.status != "finished",
        ).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Could not generate a unique join code")


def _room_response(room: SlalomRoom) -> dict:
    return {
        "id":         room.id,
        "join_code":  room.join_code,
        "player1_id": room.player1_id,
        "player2_id": room.player2_id,
        "status":     room.status,
        "final_gems": room.final_gems,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "ended_at":   room.ended_at.isoformat()   if room.ended_at   else None,
    }


# ─── Schemas ──────────────────────────────────────────────────────────────────

class JoinRoomRequest(BaseModel):
    join_code: str

class SaveScoreRequest(BaseModel):
    final_gems: int

class LeaderboardSubmitRequest(BaseModel):
    mode: str                    # "solo" | "coop"
    gates_passed: int
    gems: int
    duration_ms: int             # wall-clock time of the run, for the plausibility check
    room_id: Optional[int] = None  # required when mode == "coop"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/rooms")
def create_room(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    join_code = _generate_join_code(db)

    room = SlalomRoom(
        join_code=join_code,
        player1_id=user_id,
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
    room = db.query(SlalomRoom).filter(SlalomRoom.id == room_id).first()
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
    code = body.join_code.strip().upper()

    room = db.query(SlalomRoom).filter(
        SlalomRoom.join_code == code,
        SlalomRoom.status == "waiting",
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found or already started")
    if room.player1_id == user_id:
        raise HTTPException(status_code=400, detail="You can't join your own room as player 2")

    room.player2_id = user_id
    room.status = "active"
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
    room = db.query(SlalomRoom).filter(SlalomRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room.final_gems = body.final_gems
    room.status = "finished"
    room.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(room)
    return _room_response(room)


# ─── Leaderboard ──────────────────────────────────────────────────────────────
#
# Two boards: "solo" and "coop". Ranked by gates_passed desc, gems as the
# tiebreaker — same ordering the client already uses for its local hi-score.
#
# Coop is the interesting case: P1 and P2 are two separate browser sessions
# with no shared login, so each submits their own half independently, keyed
# by room_id. Whoever submits first creates the row; whoever submits second
# fills in the other name slot. If only one side ever submits, the row stays
# hidden from reads for a short window, then shows up with the missing name
# as "Anonymous" rather than disappearing forever.

MIN_SECONDS_PER_GATE = 0.8     # generous floor: max speed (~5px/frame @60fps) over the
                                # narrowest gate spacing (240px) — see FreeskateSlalom.jsx
GATE_GRACE = 3                 # a few free gates for the slow-speed opening stretch
MAX_GEMS_PER_GATE = 4          # generous — gate chunks spawn at most 0-3 gems each
GEMS_GRACE = 10
COOP_PENDING_WINDOW = timedelta(minutes=2)


def _validate_plausible(gates_passed: int, gems: int, duration_ms: int):
    """
    Not real anti-cheat — just a speed bump against trivially-faked scores,
    since the score is computed client-side and POSTed as plain numbers.
    Rejects runs that couldn't physically have happened in the reported time.
    """
    if gates_passed < 0 or gems < 0 or duration_ms < 0:
        raise HTTPException(status_code=400, detail="Invalid score")

    duration_s = duration_ms / 1000
    max_plausible_gates = (duration_s / MIN_SECONDS_PER_GATE) + GATE_GRACE
    if gates_passed > max_plausible_gates:
        raise HTTPException(status_code=422, detail="Score isn't plausible for the time elapsed")

    max_plausible_gems = gates_passed * MAX_GEMS_PER_GATE + GEMS_GRACE
    if gems > max_plausible_gems:
        raise HTTPException(status_code=422, detail="Gem count isn't plausible for gates passed")


def _score_response(score: SlalomScore) -> dict:
    return {
        "id":            score.id,
        "mode":          score.mode,
        "player1_name":  score.player1_name,
        "player2_name":  score.player2_name,
        "gates_passed":  score.gates_passed,
        "gems":          score.gems,
        "created_at":    score.created_at.isoformat() if score.created_at else None,
    }


@router.get("/leaderboard")
def get_leaderboard(
    mode: str,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    if mode not in ("solo", "coop"):
        raise HTTPException(status_code=400, detail="mode must be 'solo' or 'coop'")
    limit = max(1, min(limit, 100))

    # Overfetch for coop since some rows may still be in their pending window
    # and get filtered out below.
    fetch_limit = limit * 2 if mode == "coop" else limit

    rows = (
        db.query(SlalomScore)
        .filter(SlalomScore.mode == mode)
        .order_by(
            SlalomScore.gates_passed.desc(),
            SlalomScore.gems.desc(),
            SlalomScore.created_at.asc(),
        )
        .limit(fetch_limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    entries = []
    for row in rows:
        if mode == "coop" and row.player2_name is None:
            age = now - row.created_at
            if age < COOP_PENDING_WINDOW:
                continue  # still waiting on the partner's submission — hide for now
        entry = _score_response(row)
        if mode == "coop" and entry["player2_name"] is None:
            entry["player2_name"] = "Anonymous"
        entries.append(entry)
        if len(entries) >= limit:
            break

    return {"mode": mode, "entries": entries}


@router.post("/leaderboard")
def submit_leaderboard_score(
    body: LeaderboardSubmitRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if body.mode not in ("solo", "coop"):
        raise HTTPException(status_code=400, detail="mode must be 'solo' or 'coop'")

    _validate_plausible(body.gates_passed, body.gems, body.duration_ms)

    user_id = current_user["id"]
    name = current_user.get("username")
    if not name:
        raise HTTPException(status_code=400, detail="Set a username before submitting a score")

    if body.mode == "solo":
        score = SlalomScore(
            mode="solo",
            player1_id=user_id,
            player1_name=name,
            gates_passed=body.gates_passed,
            gems=body.gems,
        )
        db.add(score)
        db.commit()
        db.refresh(score)
        return _score_response(score)

    # ── coop ──
    if not body.room_id:
        raise HTTPException(status_code=400, detail="room_id is required for coop scores")

    room = db.query(SlalomRoom).filter(SlalomRoom.id == body.room_id).first()
    if not room or user_id not in (room.player1_id, room.player2_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    existing = (
        db.query(SlalomScore)
        .filter(SlalomScore.mode == "coop", SlalomScore.room_id == body.room_id)
        .first()
    )

    if existing:
        # Partner (or this same player, retrying) already created the row —
        # fill in whichever slot is this user's.
        if existing.player1_id == user_id:
            existing.player1_name = name
        elif existing.player2_id is None:
            existing.player2_id = user_id
            existing.player2_name = name
        elif existing.player2_id == user_id:
            existing.player2_name = name
        # The two sides should report the same numbers since P2 mirrors P1's
        # broadcast state, but take the max defensively in case one side's
        # last broadcast lagged behind game-over.
        existing.gates_passed = max(existing.gates_passed, body.gates_passed)
        existing.gems = max(existing.gems, body.gems)
        db.commit()
        db.refresh(existing)
        return _score_response(existing)

    score = SlalomScore(
        mode="coop",
        room_id=body.room_id,
        player1_id=user_id,
        player1_name=name,
        gates_passed=body.gates_passed,
        gems=body.gems,
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return _score_response(score)


@router.websocket("/ws/{room_id}")
async def slalom_websocket(websocket: WebSocket, room_id: int):
    user = await get_ws_user(websocket)
    if not user:
        return
 
    room_key   = str(room_id)
    user_id    = user["id"]
    peer_count = await _manager.connect(room_key, websocket)
 
    await websocket.send_text(json.dumps({
        "event": "connected", "user_id": user_id, "peer_count": peer_count
    }))
 
    if peer_count == 2:
        await _manager.relay(room_key, websocket, json.dumps({
            "event": "partner_connected", "user_id": user_id
        }))
 
    try:
        while True:
            raw = await websocket.receive_text()
            await _manager.relay(room_key, websocket, raw)
    except WebSocketDisconnect:
        _manager.disconnect(room_key, websocket)
        await _manager.relay(room_key, websocket, json.dumps({
            "event": "partner_disconnected", "user_id": user_id
        }))