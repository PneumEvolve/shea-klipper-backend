from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from typing import List
from datetime import datetime
from auth import get_current_user_dependency as get_current_user  # if you have this in your auth file
from models import User

router = APIRouter(prefix="/gardens", tags=["Gardens"])

# Create a garden
@router.post("/", response_model=schemas.GardenOut)
def create_garden(
    garden: schemas.GardenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_garden = models.Garden(
        **garden.dict(),
        host_id=current_user.id,  # <-- LINK garden to user
        created_at=datetime.utcnow()
    )
    db.add(db_garden)
    db.commit()
    db.refresh(db_garden)
    return db_garden

# Get all gardens
@router.get("/", response_model=List[schemas.GardenOut])
def get_all_gardens(db: Session = Depends(get_db)):
    return db.query(models.Garden).all()

# Submit volunteer application
@router.post("/volunteer", response_model=schemas.VolunteerApplicationOut)
def apply_to_volunteer(application: schemas.VolunteerApplicationCreate, db: Session = Depends(get_db)):
    if not db.query(models.Garden).filter_by(id=application.garden_id).first():
        raise HTTPException(status_code=404, detail="Garden not found")
    db_app = models.VolunteerApplication(
        **application.dict(),
        submitted_at=datetime.utcnow(),
        approved=None
    )
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return db_app

# Get volunteer applications (optional: for admin dashboard)
@router.get("/volunteer", response_model=List[schemas.VolunteerApplicationOut])
def get_all_applications(db: Session = Depends(get_db)):
    return db.query(models.VolunteerApplication).all()