# routers/thoughts.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PingCreate(BaseModel):
    recipient_username: str

class PingOut(BaseModel):
    id: int
    sent_at: datetime
    other_username: str
    other_user_id: int
    direction: str  # "sent" | "received"


# ─── User search ──────────────────────────────────────────────────────────────

@router.get("/users/search")
def search_users(
    q: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    if len(q.strip()) < 2:
        return []
    rows = db.execute(
        text("""
            SELECT id, username
            FROM users
            WHERE username ILIKE :q
              AND id != :uid
              AND username IS NOT NULL
            ORDER BY username
            LIMIT 10
        """),
        {"q": f"%{q.strip()}%", "uid": user.id},
    ).mappings().all()
    return [dict(r) for r in rows]


# ─── Send a ping ──────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def send_ping(
    body: PingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    recipient = db.execute(
        text("SELECT id, username FROM users WHERE username = :u"),
        {"u": body.recipient_username},
    ).mappings().first()

    if not recipient:
        raise HTTPException(status_code=404, detail="User not found")

    if recipient["id"] == user.id:
        raise HTTPException(status_code=400, detail="You can't send a thought to yourself")

    # Prevent spamming — one ping per sender/recipient pair per hour
    recent = db.execute(
        text("""
            SELECT id FROM thought_pings
            WHERE sender_id = :sid
              AND recipient_id = :rid
              AND sent_at > now() - interval '1 hour'
        """),
        {"sid": user.id, "rid": recipient["id"]},
    ).first()

    if recent:
        raise HTTPException(
            status_code=429,
            detail="You already sent a thought to this person recently. Give it an hour."
        )

    db.execute(
        text("""
            INSERT INTO thought_pings (sender_id, recipient_id)
            VALUES (:sid, :rid)
        """),
        {"sid": user.id, "rid": recipient["id"]},
    )
    db.commit()

    return {"ok": True, "recipient": recipient["username"]}


# ─── Your received log ────────────────────────────────────────────────────────

@router.get("/received", response_model=list[PingOut])
def received_pings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    rows = db.execute(
        text("""
            SELECT
                tp.id,
                tp.sent_at,
                u.username AS other_username,
                u.id AS other_user_id
            FROM thought_pings tp
            JOIN users u ON u.id = tp.sender_id
            WHERE tp.recipient_id = :uid
            ORDER BY tp.sent_at DESC
            LIMIT 100
        """),
        {"uid": user.id},
    ).mappings().all()

    return [
        {**dict(r), "direction": "received"}
        for r in rows
    ]


# ─── Your sent log ────────────────────────────────────────────────────────────

@router.get("/sent", response_model=list[PingOut])
def sent_pings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    rows = db.execute(
        text("""
            SELECT
                tp.id,
                tp.sent_at,
                u.username AS other_username,
                u.id AS other_user_id
            FROM thought_pings tp
            JOIN users u ON u.id = tp.recipient_id
            WHERE tp.sender_id = :uid
            ORDER BY tp.sent_at DESC
            LIMIT 100
        """),
        {"uid": user.id},
    ).mappings().all()

    return [
        {**dict(r), "direction": "sent"}
        for r in rows
    ]