from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import LivingPlanSection
from database import get_db
from schemas import LivingPlanSectionSchema
from routers.auth import get_current_user_dependency

router = APIRouter()

@router.get("/living-plan", response_model=list[LivingPlanSectionSchema])
def get_sections(db: Session = Depends(get_db)):
    return db.query(LivingPlanSection).order_by(LivingPlanSection.id).all()

@router.post("/living-plan")
def save_sections(
    sections: list[LivingPlanSectionSchema],
    db: Session = Depends(get_db),
    user=Depends(get_current_user_dependency)
):
    if user.email != "sheaklipper@gmail.com":
        raise HTTPException(status_code=403, detail="Unauthorized")

    db.query(LivingPlanSection).delete()
    for s in sections:
        section = LivingPlanSection(**s.dict(), owner_email=user.email)
        db.add(section)
    db.commit()
    return {"message": "Saved"}