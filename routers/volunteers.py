from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
from auth import get_current_user  # if needed
from models import User

router = APIRouter(prefix="/volunteers", tags=["Volunteers"])

@router.post("/request", response_model=schemas.VolunteerRequestResponse)
def create_volunteer_request(request: schemas.VolunteerRequestCreate, db: Session = Depends(get_db)):
    new_request = models.VolunteerRequest(**request.dict())
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request

@router.get("/requests/{garden_id}", response_model=list[schemas.VolunteerRequestResponse])
def get_requests_by_garden(garden_id: int, db: Session = Depends(get_db)):
    return db.query(models.VolunteerRequest).filter_by(garden_id=garden_id).all()

@router.patch("/approve/{request_id}", response_model=schemas.VolunteerRequestResponse)
def update_request_status(
    request_id: int,
    update: schemas.VolunteerRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    request = db.query(models.VolunteerRequest).get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    garden = db.query(models.Garden).filter_by(id=request.garden_id).first()
    if not garden:
        raise HTTPException(status_code=404, detail="Garden not found")

    if garden.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the garden host can update request status")

    request.status = update.status
    db.commit()
    db.refresh(request)
    return request