# routers/clear_and_calm.py

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CravingIn(BaseModel):
    intensity_before:   int  = Field(..., ge=1, le=10)
    intensity_after:    int  = Field(..., ge=0, le=10)
    skipped_breathing:  bool = False
    recorded_at:        Optional[datetime] = None  # client can supply; defaults to now


class MeditationIn(BaseModel):
    duration_secs: int = Field(..., ge=1)
    recorded_at:   Optional[datetime] = None


class GaveInIn(BaseModel):
    occurred_at:   datetime              # always user-supplied — matches the "earlier…" picker
    reset_streak:  bool = False


class SoberStartIn(BaseModel):
    started_at: datetime


class CravingOut(BaseModel):
    id:                 int
    recorded_at:        datetime
    intensity_before:   int
    intensity_after:    int
    reduction:          int
    skipped_breathing:  bool

    class Config:
        from_attributes = True


class MeditationOut(BaseModel):
    id:            int
    recorded_at:   datetime
    duration_secs: int

    class Config:
        from_attributes = True


class GaveInOut(BaseModel):
    id:          int
    occurred_at: datetime

    class Config:
        from_attributes = True


class SyncOut(BaseModel):
    sober_start:  Optional[datetime]
    cravings:     list[CravingOut]
    meditations:  list[MeditationOut]
    gave_in:      list[GaveInOut]


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/sync", response_model=SyncOut)
def sync(
    db:   Session = Depends(get_db),
    user = Depends(get_current_user_dependency),
):
    """Single call to hydrate the page on load."""

    sober_row = db.execute(
        text("SELECT started_at FROM cc_sober_starts WHERE user_id = :uid"),
        {"uid": user.id},
    ).mappings().first()

    cravings = db.execute(
        text("""
            SELECT id, recorded_at, intensity_before, intensity_after, reduction, skipped_breathing
            FROM cc_cravings
            WHERE user_id = :uid
            ORDER BY recorded_at DESC
        """),
        {"uid": user.id},
    ).mappings().all()

    meditations = db.execute(
        text("""
            SELECT id, recorded_at, duration_secs
            FROM cc_meditations
            WHERE user_id = :uid
            ORDER BY recorded_at DESC
        """),
        {"uid": user.id},
    ).mappings().all()

    gave_in = db.execute(
        text("""
            SELECT id, occurred_at
            FROM cc_gave_in
            WHERE user_id = :uid
            ORDER BY occurred_at DESC
        """),
        {"uid": user.id},
    ).mappings().all()

    return {
        "sober_start": sober_row["started_at"] if sober_row else None,
        "cravings":    [dict(r) for r in cravings],
        "meditations": [dict(r) for r in meditations],
        "gave_in":     [dict(r) for r in gave_in],
    }


@router.post("/cravings", response_model=CravingOut, status_code=status.HTTP_201_CREATED)
def log_craving(
    body: CravingIn,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user_dependency),
):
    reduction   = body.intensity_before - body.intensity_after
    recorded_at = body.recorded_at or datetime.now(timezone.utc)

    row = db.execute(
        text("""
            INSERT INTO cc_cravings
                (user_id, recorded_at, intensity_before, intensity_after, reduction, skipped_breathing)
            VALUES (:uid, :ts, :before, :after, :reduction, :skipped)
            RETURNING id, recorded_at, intensity_before, intensity_after, reduction, skipped_breathing
        """),
        {
            "uid":       user.id,
            "ts":        recorded_at,
            "before":    body.intensity_before,
            "after":     body.intensity_after,
            "reduction": reduction,
            "skipped":   body.skipped_breathing,
        },
    ).mappings().first()
    db.commit()
    return dict(row)


@router.post("/meditations", response_model=MeditationOut, status_code=status.HTTP_201_CREATED)
def log_meditation(
    body: MeditationIn,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user_dependency),
):
    recorded_at = body.recorded_at or datetime.now(timezone.utc)

    row = db.execute(
        text("""
            INSERT INTO cc_meditations (user_id, recorded_at, duration_secs)
            VALUES (:uid, :ts, :secs)
            RETURNING id, recorded_at, duration_secs
        """),
        {"uid": user.id, "ts": recorded_at, "secs": body.duration_secs},
    ).mappings().first()
    db.commit()
    return dict(row)


@router.post("/gave-in", response_model=GaveInOut, status_code=status.HTTP_201_CREATED)
def log_gave_in(
    body: GaveInIn,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user_dependency),
):
    """
    Logs a gave-in event. If reset_streak=true, atomically updates
    cc_sober_starts to occurred_at in the same transaction.
    """
    row = db.execute(
        text("""
            INSERT INTO cc_gave_in (user_id, occurred_at)
            VALUES (:uid, :ts)
            RETURNING id, occurred_at
        """),
        {"uid": user.id, "ts": body.occurred_at},
    ).mappings().first()

    if body.reset_streak:
        db.execute(
            text("""
                INSERT INTO cc_sober_starts (user_id, started_at)
                VALUES (:uid, :ts)
                ON CONFLICT (user_id)
                DO UPDATE SET started_at = :ts, updated_at = now()
            """),
            {"uid": user.id, "ts": body.occurred_at},
        )

    db.commit()
    return dict(row)


@router.put("/sober-start", status_code=status.HTTP_200_OK)
def set_sober_start(
    body: SoberStartIn,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user_dependency),
):
    db.execute(
        text("""
            INSERT INTO cc_sober_starts (user_id, started_at)
            VALUES (:uid, :ts)
            ON CONFLICT (user_id)
            DO UPDATE SET started_at = :ts, updated_at = now()
        """),
        {"uid": user.id, "ts": body.started_at},
    )
    db.commit()
    return {"ok": True}