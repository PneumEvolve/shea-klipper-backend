# routers/stillness.py
 
import os
import jwt
import secrets
import string
from datetime import datetime, timezone, timedelta, time
from typing import Optional
 
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
 
from database import get_db
from routers.auth import get_current_user_dependency
 
router = APIRouter()
 
WINDOW_SECONDS = 300  # 5 minute presence window
 
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
ALGORITHM = "HS256"
 
 
# ─── Helpers ──────────────────────────────────────────────────────────────────
 
def _make_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
 
 
def _get_group_or_404(group_id: int, db: Session):
    row = db.execute(
        text("SELECT * FROM stillness_groups WHERE id = :id"),
        {"id": group_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")
    return row
 
 
def _assert_member(group_id: int, user_id: int, db: Session):
    row = db.execute(
        text("SELECT id FROM stillness_members WHERE group_id = :g AND user_id = :u"),
        {"g": group_id, "u": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this group")
 
 
def _normalize_time(t) -> time:
    if isinstance(t, str):
        return time.fromisoformat(t)
    return t
 
 
def _next_window_start(daily_time_utc: time, now: datetime) -> datetime:
    today_start = datetime(
        now.year, now.month, now.day,
        daily_time_utc.hour, daily_time_utc.minute, 0,
        tzinfo=timezone.utc,
    )
    window_end = today_start + timedelta(seconds=WINDOW_SECONDS)
    if now < window_end:
        return today_start
    return today_start + timedelta(days=1)
 
 
def _get_or_create_session(group_id: int, db: Session):
    now = datetime.now(timezone.utc)
 
    group = db.execute(
        text("SELECT * FROM stillness_groups WHERE id = :id"),
        {"id": group_id},
    ).mappings().first()
 
    if not group or not group["daily_time_utc"]:
        raise HTTPException(
            status_code=400,
            detail="This group has no scheduled time. The owner needs to set one."
        )
 
    daily_time = _normalize_time(group["daily_time_utc"])
    window_start = _next_window_start(daily_time, now)
 
    existing = db.execute(
        text("SELECT * FROM stillness_sessions WHERE group_id = :g AND scheduled_for = :s"),
        {"g": group_id, "s": window_start},
    ).mappings().first()
 
    if existing:
        return dict(existing)
 
    result = db.execute(
        text("""
            INSERT INTO stillness_sessions (group_id, scheduled_for, window_seconds)
            VALUES (:g, :s, :w)
            ON CONFLICT DO NOTHING
            RETURNING *
        """),
        {"g": group_id, "s": window_start, "w": WINDOW_SECONDS},
    ).mappings().first()
 
    if not result:
        result = db.execute(
            text("SELECT * FROM stillness_sessions WHERE group_id = :g AND scheduled_for = :s"),
            {"g": group_id, "s": window_start},
        ).mappings().first()
 
    db.commit()
    return dict(result)
 
 
# ─── Unsubscribe token helpers ────────────────────────────────────────────────
 
def make_unsubscribe_token(user_id: int, group_id: int) -> str:
    """Create a signed token that encodes who is unsubscribing from which group."""
    payload = {
        "sub": "stillness_unsub",
        "user_id": user_id,
        "group_id": group_id,
        # No expiry — unsubscribe links should work forever
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
 
 
def verify_unsubscribe_token(token: str) -> tuple[int, int]:
    """Returns (user_id, group_id) or raises HTTPException."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != "stillness_unsub":
            raise HTTPException(status_code=400, detail="Invalid unsubscribe token")
        return payload["user_id"], payload["group_id"]
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid or malformed unsubscribe token")
 
 
# ─── Schemas ──────────────────────────────────────────────────────────────────
 
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    daily_time_utc: str = Field(..., description="UTC time string e.g. '08:00'")
 
 
class GroupOut(BaseModel):
    id: int
    name: str
    invite_code: str
    created_by: int
    is_owner: bool
    member_count: int
    created_at: datetime
    daily_time_utc: Optional[str] = None
 
 
class SessionOut(BaseModel):
    session_id: int
    group_id: int
    scheduled_for: datetime
    window_seconds: int
    window_open: bool
    seconds_until_open: float
    seconds_remaining: Optional[float]
    checked_in_user_ids: list[int]
    present_members: list[dict]
    your_checkin: bool
 
 
class PresenceOut(BaseModel):
    window_open: bool
    seconds_remaining: Optional[float]
    present_members: list[dict]
    your_checkin: bool
 
 
# ─── Routes ───────────────────────────────────────────────────────────────────
 
@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    try:
        parsed_time = time.fromisoformat(body.daily_time_utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM e.g. '08:00'")
 
    invite_code = _make_invite_code()
    for _ in range(5):
        exists = db.execute(
            text("SELECT id FROM stillness_groups WHERE invite_code = :c"),
            {"c": invite_code},
        ).first()
        if not exists:
            break
        invite_code = _make_invite_code()
 
    group = db.execute(
        text("""
            INSERT INTO stillness_groups (name, created_by, invite_code, daily_time_utc)
            VALUES (:name, :user_id, :invite_code, :daily_time_utc)
            RETURNING *
        """),
        {
            "name": body.name,
            "user_id": user.id,
            "invite_code": invite_code,
            "daily_time_utc": parsed_time,
        },
    ).mappings().first()
 
    db.execute(
        text("INSERT INTO stillness_members (group_id, user_id) VALUES (:g, :u)"),
        {"g": group["id"], "u": user.id},
    )
    db.commit()
 
    return {
        **dict(group),
        "is_owner": True,
        "member_count": 1,
        "daily_time_utc": body.daily_time_utc,
    }
 
 
@router.get("/groups/mine", response_model=list[GroupOut])
def my_groups(db: Session = Depends(get_db), user=Depends(get_current_user_dependency)):
    rows = db.execute(
        text("""
            SELECT
                g.*,
                (g.created_by = :uid) AS is_owner,
                COUNT(m2.id) AS member_count
            FROM stillness_groups g
            JOIN stillness_members m ON m.group_id = g.id AND m.user_id = :uid
            LEFT JOIN stillness_members m2 ON m2.group_id = g.id
            GROUP BY g.id
            ORDER BY g.created_at DESC
        """),
        {"uid": user.id},
    ).mappings().all()
 
    result = []
    for r in rows:
        row = dict(r)
        t = row.get("daily_time_utc")
        if t and not isinstance(t, str):
            row["daily_time_utc"] = t.strftime("%H:%M")
        result.append(row)
    return result
 
 
@router.post("/join/{invite_code}", response_model=GroupOut)
def join_group(
    invite_code: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    group = db.execute(
        text("SELECT * FROM stillness_groups WHERE invite_code = :c"),
        {"c": invite_code},
    ).mappings().first()
    if not group:
        raise HTTPException(status_code=404, detail="Invite link not found")
 
    db.execute(
        text("""
            INSERT INTO stillness_members (group_id, user_id)
            VALUES (:g, :u)
            ON CONFLICT (group_id, user_id) DO NOTHING
        """),
        {"g": group["id"], "u": user.id},
    )
    db.commit()
 
    member_count = db.execute(
        text("SELECT COUNT(*) FROM stillness_members WHERE group_id = :g"),
        {"g": group["id"]},
    ).scalar()
 
    t = group["daily_time_utc"]
    daily_time_str = t.strftime("%H:%M") if t and not isinstance(t, str) else t
 
    return {
        **dict(group),
        "is_owner": group["created_by"] == user.id,
        "member_count": member_count,
        "daily_time_utc": daily_time_str,
    }
 
 
@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    group = _get_group_or_404(group_id, db)
    if group["created_by"] != user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can delete it")
    db.execute(text("DELETE FROM stillness_groups WHERE id = :id"), {"id": group_id})
    db.commit()
 
 
@router.delete("/groups/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_group(
    group_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    group = _get_group_or_404(group_id, db)
    if group["created_by"] == user.id:
        raise HTTPException(
            status_code=400,
            detail="You created this group. Use delete instead of leave.",
        )
    _assert_member(group_id, user.id, db)
    db.execute(
        text("DELETE FROM stillness_members WHERE group_id = :g AND user_id = :u"),
        {"g": group_id, "u": user.id},
    )
    db.commit()

class GroupUpdate(BaseModel):
    daily_time_utc: str = Field(..., description="UTC time string e.g. '08:00'")

@router.patch("/groups/{group_id}", response_model=GroupOut)
def update_group_time(
    group_id: int,
    body: GroupUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    group = _get_group_or_404(group_id, db)
    if group["created_by"] != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can change the time")

    try:
        parsed_time = time.fromisoformat(body.daily_time_utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")

    updated = db.execute(
        text("""
            UPDATE stillness_groups
            SET daily_time_utc = :t
            WHERE id = :id
            RETURNING *
        """),
        {"t": parsed_time, "id": group_id},
    ).mappings().first()

    # Clear today's sent records so everyone gets notified at the new time
    db.execute(
        text("""
            DELETE FROM stillness_notifications_sent
            WHERE group_id = :g AND sent_for_date = CURRENT_DATE
        """),
        {"g": group_id},
    )
    db.commit()

    member_count = db.execute(
        text("SELECT COUNT(*) FROM stillness_members WHERE group_id = :g"),
        {"g": group_id},
    ).scalar()

    t = updated["daily_time_utc"]
    daily_time_str = t.strftime("%H:%M") if t and not isinstance(t, str) else t

    return {
        **dict(updated),
        "is_owner": True,
        "member_count": member_count,
        "daily_time_utc": daily_time_str,
    }
 
 
@router.get("/groups/{group_id}/session", response_model=SessionOut)
def get_session(
    group_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    _assert_member(group_id, user.id, db)
    session = _get_or_create_session(group_id, db)
 
    now = datetime.now(timezone.utc)
    scheduled = session["scheduled_for"]
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
 
    window_end = scheduled + timedelta(seconds=session["window_seconds"])
    window_open = scheduled <= now < window_end
    seconds_until_open = max(0.0, (scheduled - now).total_seconds())
    seconds_remaining = max(0.0, (window_end - now).total_seconds()) if window_open else None
 
    checkins = db.execute(
        text("""
            SELECT c.user_id, u.username
            FROM stillness_checkins c
            JOIN users u ON u.id = c.user_id
            WHERE c.session_id = :sid
        """),
        {"sid": session["id"]},
    ).mappings().all()
 
    present_members = [{"id": r["user_id"], "display_name": r["username"]} for r in checkins]
    checked_in_user_ids = [r["user_id"] for r in checkins]
    your_checkin = user.id in checked_in_user_ids
 
    return {
        "session_id": session["id"],
        "group_id": group_id,
        "scheduled_for": scheduled,
        "window_seconds": session["window_seconds"],
        "window_open": window_open,
        "seconds_until_open": seconds_until_open,
        "seconds_remaining": seconds_remaining,
        "checked_in_user_ids": checked_in_user_ids,
        "present_members": present_members,
        "your_checkin": your_checkin,
    }
 
 
@router.post("/groups/{group_id}/checkin", status_code=status.HTTP_200_OK)
def checkin(
    group_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    _assert_member(group_id, user.id, db)
    session = _get_or_create_session(group_id, db)
 
    now = datetime.now(timezone.utc)
    scheduled = session["scheduled_for"]
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    window_end = scheduled + timedelta(seconds=session["window_seconds"])
 
    if not (scheduled <= now < window_end):
        raise HTTPException(status_code=400, detail="No window is currently open")
 
    db.execute(
        text("""
            INSERT INTO stillness_checkins (session_id, user_id)
            VALUES (:sid, :uid)
            ON CONFLICT (session_id, user_id) DO NOTHING
        """),
        {"sid": session["id"], "uid": user.id},
    )
    db.commit()
    return {"ok": True}
 
 
@router.get("/groups/{group_id}/presence", response_model=PresenceOut)
def get_presence(
    group_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency),
):
    _assert_member(group_id, user.id, db)
    session = _get_or_create_session(group_id, db)
 
    now = datetime.now(timezone.utc)
    scheduled = session["scheduled_for"]
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    window_end = scheduled + timedelta(seconds=session["window_seconds"])
    window_open = scheduled <= now < window_end
    seconds_remaining = max(0.0, (window_end - now).total_seconds()) if window_open else None
 
    checkins = db.execute(
        text("""
            SELECT c.user_id, u.username
            FROM stillness_checkins c
            JOIN users u ON u.id = c.user_id
            WHERE c.session_id = :sid
        """),
        {"sid": session["id"]},
    ).mappings().all()
 
    present_members = [{"id": r["user_id"], "display_name": r["username"]} for r in checkins]
    your_checkin = any(r["user_id"] == user.id for r in checkins)
 
    return {
        "window_open": window_open,
        "seconds_remaining": seconds_remaining,
        "present_members": present_members,
        "your_checkin": your_checkin,
    }
 
 
@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    """
    One-click unsubscribe — linked from every notification email.
    No login required. Verifies the signed token and sets email_enabled = false.
    """
    try:
        user_id, group_id = verify_unsubscribe_token(token)
    except HTTPException:
        return HTMLResponse(_unsubscribe_page(success=False), status_code=400)
 
    # Get group name for the confirmation message
    group = db.execute(
        text("SELECT name FROM stillness_groups WHERE id = :id"),
        {"id": group_id},
    ).mappings().first()
 
    group_name = group["name"] if group else "this group"
 
    # Upsert the pref — create it if it doesn't exist, set to false if it does
    db.execute(
        text("""
            INSERT INTO stillness_notification_prefs (user_id, group_id, email_enabled)
            VALUES (:u, :g, false)
            ON CONFLICT (user_id, group_id)
            DO UPDATE SET email_enabled = false, updated_at = now()
        """),
        {"u": user_id, "g": group_id},
    )
    db.commit()
 
    return HTMLResponse(_unsubscribe_page(success=True, group_name=group_name))
 
 
def _unsubscribe_page(success: bool, group_name: str = "") -> str:
    if success:
        message = f"You've been unsubscribed from email notifications for <strong>{group_name}</strong>."
        sub = "You can still use Shared Stillness — you just won't receive email reminders for this group."
        color = "#2c2c2a"
    else:
        message = "This unsubscribe link is invalid or has expired."
        sub = "If you'd like to stop notifications, you can manage them from within the app."
        color = "#a33"
 
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Unsubscribed — PneumEvolve</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="margin:0;padding:0;background:#faf9f7;font-family:Georgia,serif;color:{color};">
      <div style="max-width:480px;margin:4rem auto;padding:2rem;text-align:center;">
        <p style="font-size:1.8rem;font-style:italic;opacity:0.6;margin-bottom:1.5rem;">
          PneumEvolve
        </p>
        <p style="font-size:1.1rem;line-height:1.7;margin-bottom:1rem;">
          {message}
        </p>
        <p style="font-size:0.85rem;opacity:0.5;line-height:1.7;margin-bottom:2rem;">
          {sub}
        </p>
        <a href="https://pneumevolve.com/stillness"
           style="display:inline-block;padding:0.75rem 1.5rem;
                  background:#f5f0e8;border:1px solid #d4c9b0;
                  border-radius:8px;text-decoration:none;
                  color:#2c2c2a;font-size:0.9rem;">
          Back to PneumEvolve →
        </a>
      </div>
    </body>
    </html>
    """