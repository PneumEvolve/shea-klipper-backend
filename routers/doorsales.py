"""
Door Sales Tracker routes. Save as routers/doorsales.py and include with:
app.include_router(doorsales.router, prefix="/door-sales", tags=["Door Sales"])

Same scoping pattern as habits.py: every route is scoped to current_user via
get_current_user_model. Unlike HabitGrid, there's no client_id sync dance —
this isn't offline-first, so the server-assigned int id is used directly.
"""

import csv
import io
from datetime import datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from models import Neighborhood, DoorHouse, User
from schemas import (
    NeighborhoodIn, NeighborhoodOut,
    DoorHouseIn, DoorHouseUpdate, DoorHouseOut, AppointmentOut,
)
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from routers.auth import get_current_user_model

router = APIRouter()


# ---------- helpers ----------

def _get_neighborhood_or_404(db: Session, user: User, neighborhood_id: int) -> Neighborhood:
    n = db.query(Neighborhood).filter(
        Neighborhood.id == neighborhood_id, Neighborhood.user_id == user.id
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Neighborhood not found")
    return n


def _get_house_or_404(db: Session, user: User, house_id: int) -> DoorHouse:
    h = db.query(DoorHouse).filter(
        DoorHouse.id == house_id, DoorHouse.user_id == user.id
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="House not found")
    return h


def _csv_response(houses: List[DoorHouse], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Address", "Neighborhood", "Status", "Service Interest", "Notes", "Follow Up Date", "Visited At"])
    for h in houses:
        writer.writerow([
            h.address,
            h.neighborhood.name if h.neighborhood else "",
            h.status.value if hasattr(h.status, "value") else h.status,
            h.service_interest or "",
            h.notes or "",
            h.follow_up_date.isoformat() if h.follow_up_date else "",
            h.visited_at.isoformat() if h.visited_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/appointments", response_model=List[AppointmentOut])
def list_upcoming_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    rows = (
        db.query(DoorHouse, Neighborhood.name)
        .join(Neighborhood, Neighborhood.id == DoorHouse.neighborhood_id)
        .filter(
            DoorHouse.user_id == current_user.id,
            DoorHouse.appointment_at.isnot(None),
            DoorHouse.appointment_completed == False,  # noqa: E712
        )
        .order_by(DoorHouse.appointment_at.asc())
        .all()
    )
    return [
        AppointmentOut(
            house_id=h.id,
            neighborhood_id=h.neighborhood_id,
            neighborhood_name=name,
            address=h.address,
            status=h.status.value if hasattr(h.status, "value") else h.status,
            appointment_at=h.appointment_at,
        )
        for h, name in rows
    ]

# ---------- neighborhoods ----------

@router.get("/neighborhoods", response_model=List[NeighborhoodOut])
def list_neighborhoods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    neighborhoods = db.query(Neighborhood).filter(Neighborhood.user_id == current_user.id).order_by(Neighborhood.name).all()
    counts = dict(
        db.query(DoorHouse.neighborhood_id, func.count(DoorHouse.id))
        .filter(DoorHouse.user_id == current_user.id)
        .group_by(DoorHouse.neighborhood_id)
        .all()
    )
    out = []
    for n in neighborhoods:
        item = NeighborhoodOut.model_validate(n)
        item.house_count = counts.get(n.id, 0)
        out.append(item)
    return out


@router.post("/neighborhoods", response_model=NeighborhoodOut)
def create_neighborhood(
    payload: NeighborhoodIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    existing = db.query(Neighborhood).filter(
        Neighborhood.user_id == current_user.id, Neighborhood.name == payload.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Neighborhood already exists")
    n = Neighborhood(user_id=current_user.id, name=payload.name)
    db.add(n)
    db.commit()
    db.refresh(n)
    out = NeighborhoodOut.model_validate(n)
    out.house_count = 0
    return out


@router.delete("/neighborhoods/{neighborhood_id}")
def delete_neighborhood(
    neighborhood_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    n = _get_neighborhood_or_404(db, current_user, neighborhood_id)
    db.delete(n)  # cascades to houses
    db.commit()
    return {"ok": True}


# ---------- houses ----------

@router.get("/neighborhoods/{neighborhood_id}/houses", response_model=List[DoorHouseOut])
def list_houses(
    neighborhood_id: int,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    _get_neighborhood_or_404(db, current_user, neighborhood_id)
    q = db.query(DoorHouse).filter(
        DoorHouse.neighborhood_id == neighborhood_id, DoorHouse.user_id == current_user.id
    )
    if status:
        q = q.filter(DoorHouse.status == status)
    return q.order_by(DoorHouse.visited_at.desc()).all()


@router.post("/neighborhoods/{neighborhood_id}/houses", response_model=DoorHouseOut)
def create_house(
    neighborhood_id: int,
    payload: DoorHouseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    _get_neighborhood_or_404(db, current_user, neighborhood_id)
    house = DoorHouse(user_id=current_user.id, neighborhood_id=neighborhood_id, **payload.dict())
    db.add(house)
    db.commit()
    db.refresh(house)
    return house


@router.patch("/houses/{house_id}", response_model=DoorHouseOut)
def update_house(
    house_id: int,
    payload: DoorHouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    house = _get_house_or_404(db, current_user, house_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(house, field, value)
    db.commit()
    db.refresh(house)
    return house


@router.delete("/houses/{house_id}")
def delete_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    house = _get_house_or_404(db, current_user, house_id)
    db.delete(house)
    db.commit()
    return {"ok": True}


# ---------- export ----------

@router.get("/neighborhoods/{neighborhood_id}/export")
def export_neighborhood(
    neighborhood_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    n = _get_neighborhood_or_404(db, current_user, neighborhood_id)
    houses = db.query(DoorHouse).filter(
        DoorHouse.neighborhood_id == neighborhood_id, DoorHouse.user_id == current_user.id
    ).order_by(DoorHouse.visited_at.desc()).all()
    safe_name = "".join(c if c.isalnum() else "_" for c in n.name)
    filename = f"door-sales-{safe_name}-{datetime.utcnow().date().isoformat()}.csv"
    return _csv_response(houses, filename)


@router.get("/export")
def export_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    houses = db.query(DoorHouse).filter(DoorHouse.user_id == current_user.id).order_by(
        DoorHouse.neighborhood_id, DoorHouse.visited_at.desc()
    ).all()
    filename = f"door-sales-all-{datetime.utcnow().date().isoformat()}.csv"
    return _csv_response(houses, filename)