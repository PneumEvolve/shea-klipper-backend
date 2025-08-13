# seed.py
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import get_db
from models import SeedEvent

router = APIRouter(prefix="/seed", tags=["seed"])

# who can view raw identities in global exports
ADMINS = {"sheaklipper@gmail.com"}

def is_admin(email: str | None) -> bool:
    return bool(email and email in ADMINS)

def mask_identity(identity: str) -> str:
    # anon stays as-is; emails are partially masked: ab***@domain.com
    if not identity:
        return ""
    if identity.startswith("anon:"):
        return identity
    if "@" in identity:
        local, domain = identity.split("@", 1)
        head = local[:2] if len(local) >= 2 else local[:1]
        return f"{head}***@{domain}"
    # any other style (future-proof)
    return identity[:3] + "***"

# ------------ config knobs ------------
DAILY_EARN_CAP = 30                 # max points per user per UTC day
PER_LINK_COOLDOWN_HOURS = 24        # earn once per link per 24h
ALLOWED_CLICK_REFS = None           # set to a set([...]) to strictly allowlist link ids; None = skip check

# ------------ helpers ------------
def require_login(x_user_email: Optional[str]) -> str:
    if not x_user_email or x_user_email.startswith("anon:"):
        raise HTTPException(status_code=401, detail="Login required")
    return x_user_email

def today_utc_range():
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return start, end

def user_balance(db: Session, identity: str) -> int:
    total = db.query(func.coalesce(func.sum(SeedEvent.delta), 0)).filter(SeedEvent.identity == identity).scalar()
    return int(total or 0)

def has_event_today(db: Session, identity: str, event_type: str) -> bool:
    start, end = today_utc_range()
    q = (
        db.query(SeedEvent.id)
        .filter(
            SeedEvent.identity == identity,
            SeedEvent.event_type == event_type,
            SeedEvent.created_at >= start,
            SeedEvent.created_at < end,
        )
        .first()
    )
    return q is not None

# ------------ schemas ------------
class ClickIn(BaseModel):
    ref: str = Field(..., min_length=1, max_length=200)     # your link id (not the raw URL)

class SpendIn(BaseModel):
    amount: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=50)   # e.g., "JOURNAL", "AI", "GAME"

class LedgerRow(BaseModel):
    created_at: datetime
    event_type: str
    delta: int
    ref: Optional[str] = None
    balance_after: Optional[int] = None

# ------------ routes ------------
@router.get("/balance")
def get_balance(db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    ident = require_login(x_user_email)
    return {"balance": user_balance(db, ident)}

@router.post("/click")
def click_earn(payload: ClickIn, db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    ident = require_login(x_user_email)

    if ALLOWED_CLICK_REFS is not None and payload.ref not in ALLOWED_CLICK_REFS:
        raise HTTPException(status_code=400, detail="Unknown link")

    start, end = today_utc_range()

    # daily cap
    earned_today = db.query(func.coalesce(func.sum(SeedEvent.delta), 0))\
        .filter(SeedEvent.identity == ident, SeedEvent.created_at >= start, SeedEvent.created_at < end, SeedEvent.delta > 0)\
        .scalar() or 0
    if earned_today >= DAILY_EARN_CAP:
        raise HTTPException(status_code=429, detail="Daily earn cap reached")

    # per-link cooldown
    since = datetime.utcnow() - timedelta(hours=PER_LINK_COOLDOWN_HOURS)
    recent = db.query(SeedEvent.id).filter(
        SeedEvent.identity == ident,
        SeedEvent.event_type == "CLICK_EARN",
        SeedEvent.ref == payload.ref,
        SeedEvent.created_at >= since
    ).first()
    if recent:
        raise HTTPException(status_code=409, detail="Already earned for this link recently")

    ev = SeedEvent(identity=ident, event_type="CLICK_EARN", delta=1, ref=payload.ref, meta=None, created_at=datetime.utcnow())
    db.add(ev)
    db.commit()
    return {"ok": True, "balance": user_balance(db, ident)}

@router.post("/spend")
def spend_tokens(payload: SpendIn, db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    ident = require_login(x_user_email)
    bal = user_balance(db, ident)
    if bal < payload.amount:
        raise HTTPException(status_code=402, detail="Insufficient SEED")

    ev = SeedEvent(identity=ident, event_type=f"SPEND_{payload.reason.upper()}", delta=-int(payload.amount), created_at=datetime.utcnow())
    db.add(ev)
    db.commit()
    return {"ok": True, "balance": user_balance(db, ident)}

@router.get("/ledger")
def ledger(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    ident = require_login(x_user_email)

    rows = db.query(SeedEvent).filter(SeedEvent.identity == ident).order_by(SeedEvent.created_at.desc()).offset(offset).limit(limit).all()

    # compute running balance after each event (from newest → oldest, simple pass)
    bal = user_balance(db, ident)
    out = []
    for ev in rows:
        out.append({
            "created_at": ev.created_at,
            "event_type": ev.event_type,
            "delta": ev.delta,
            "ref": ev.ref,
            "balance_after": bal,
        })
        bal -= ev.delta

    return out

@router.get("/ledger.csv")
def ledger_csv(db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    ident = require_login(x_user_email)

    rows = db.query(SeedEvent).filter(SeedEvent.identity == ident).order_by(SeedEvent.created_at.asc()).all()

    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at","event_type","delta","ref","meta_json"])
    for ev in rows:
        w.writerow([ev.created_at.isoformat(), ev.event_type, ev.delta, ev.ref or "", (ev.meta or {})])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=seed_ledger.csv"})

@router.get("/ledger.json")
def ledger_json(db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    ident = require_login(x_user_email)
    rows = db.query(SeedEvent).filter(SeedEvent.identity == ident).order_by(SeedEvent.created_at.asc()).all()
    data = [{"created_at": ev.created_at.isoformat(), "event_type": ev.event_type, "delta": ev.delta, "ref": ev.ref, "meta": ev.meta} for ev in rows]
    return JSONResponse(data)

@router.get("/ledger/global")
def ledger_global(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    raw: int = Query(0, ge=0, le=1),  # admins may set raw=1 to see real identities
):
    rows = (
        db.query(SeedEvent)
        .order_by(SeedEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    show_raw = bool(raw and is_admin(x_user_email))
    out = []
    for ev in rows:
        out.append({
            "created_at": ev.created_at.isoformat(),
            "identity": ev.identity if show_raw else mask_identity(ev.identity),
            "event_type": ev.event_type,
            "delta": ev.delta,
            "ref": ev.ref,
            # no balance_after here; global balances don't make sense
        })
    return JSONResponse(out)


@router.get("/ledger.global.csv")
def ledger_global_csv(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    raw: int = Query(0, ge=0, le=1),
):
    rows = db.query(SeedEvent).order_by(SeedEvent.created_at.asc()).all()
    show_raw = bool(raw and is_admin(x_user_email))

    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at","identity","event_type","delta","ref","meta_json"])
    for ev in rows:
        ident = ev.identity if show_raw else mask_identity(ev.identity)
        w.writerow([ev.created_at.isoformat(), ident, ev.event_type, ev.delta, ev.ref or "", (ev.meta or {})])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=seed_ledger_global.csv"},
    )


@router.get("/ledger.global.json")
def ledger_global_json(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
    raw: int = Query(0, ge=0, le=1),
):
    rows = db.query(SeedEvent).order_by(SeedEvent.created_at.asc()).all()
    show_raw = bool(raw and is_admin(x_user_email))
    data = [{
        "created_at": ev.created_at.isoformat(),
        "identity": ev.identity if show_raw else mask_identity(ev.identity),
        "event_type": ev.event_type,
        "delta": ev.delta,
        "ref": ev.ref,
        "meta": ev.meta,
    } for ev in rows]
    return JSONResponse(data)

class MintIn(BaseModel):
    amount: int = Field(..., ge=1)
    wallet_address: Optional[str] = None

@router.post("/mint-deposit")
def mint_deposit(payload: MintIn, db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None, convert_underscores=True)):
    # mock mode: just acknowledge; do NOT credit or debit yet
    ident = require_login(x_user_email)
    return {"ok": False, "mode": "mock", "message": "On-chain deposit coming soon. Connect wallet next."}

@router.post("/reward/journal")
def reward_journal(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    ident = require_login(x_user_email)
    EVENT = "JOURNAL_DAILY"
    AMOUNT = 5

    if has_event_today(db, ident, EVENT):
        # already rewarded today – no error, just report status
        return {"ok": True, "claimed": False, "message": "Already rewarded today"}

    ev = SeedEvent(
        identity=ident,
        event_type=EVENT,
        delta=AMOUNT,
        ref=None,
        meta={"source": "journal"},
        created_at=datetime.utcnow(),
    )
    db.add(ev)
    db.commit()
    return {"ok": True, "claimed": True, "balance": user_balance(db, ident)}

@router.get("/daily")
def get_daily_status(
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None, convert_underscores=True),
):
    ident = require_login(x_user_email)
    start, end = today_utc_range()

    journal_done = has_event_today(db, ident, "JOURNAL_DAILY")
    earned_today = (
        db.query(func.coalesce(func.sum(SeedEvent.delta), 0))
        .filter(
            SeedEvent.identity == ident,
            SeedEvent.created_at >= start,
            SeedEvent.created_at < end,
        )
        .scalar()
        or 0
    )
    return {
        "journal_done_today": bool(journal_done),
        "earned_today": int(earned_today),
        "daily_cap": DAILY_EARN_CAP,  # for UI hints
    }