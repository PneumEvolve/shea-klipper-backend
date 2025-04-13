from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import openai
from sqlalchemy import func
import shutil
import os
from models import Transcription, TranscriptionUsage, Payment
from database import get_db
from routers.auth import get_current_user_dependency
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    try:
        # ✅ Check token balance
        total_tokens_used = db.query(func.sum(TranscriptionUsage.tokens_used)).filter(
            TranscriptionUsage.user_id == current_user["id"]
        ).scalar() or 0

        total_tokens_paid = db.query(func.sum(Payment.tokens_purchased)).filter(
            Payment.user_id == current_user["id"]
        ).scalar() or 0

        tokens_remaining = total_tokens_paid - total_tokens_used
        if tokens_remaining <= 0:
            raise HTTPException(status_code=402, detail="You’ve run out of tokens. Please purchase more to continue.")

        # ✅ Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with open(file_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        transcription_text = response.text

        # ✅ Estimate token usage and cost
        token_estimate = len(transcription_text) // 4
        if token_estimate > tokens_remaining:
            raise HTTPException(status_code=402, detail="Not enough tokens to cover this transcription.")

        cost = token_estimate * 0.000015  # Whisper pricing estimate

        # ✅ Store the transcription
        transcription = Transcription(
            user_id=current_user["id"],
            filename=file.filename,
            transcription_text=transcription_text,
            uploaded_at=datetime.utcnow()
        )
        db.add(transcription)
        db.commit()
        db.refresh(transcription)

        # ✅ Store usage
        usage_entry = TranscriptionUsage(
            user_id=current_user["id"],
            transcription_id=transcription.id,
            tokens_used=token_estimate,
            cost=cost,
            timestamp=datetime.utcnow()
        )
        db.add(usage_entry)
        db.commit()

        os.remove(file_path)

        return {
            "id": transcription.id,
            "filename": file.filename,
            "transcription_text": transcription_text,
            "uploaded_at": transcription.uploaded_at.isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@router.get("/transcriptions")
def get_transcriptions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    transcriptions = db.query(Transcription).filter(Transcription.user_id == current_user["id"]).all()

    return [
        {
            "id": t.id,
            "filename": t.filename,
            "transcription_text": t.transcription_text,
            "summary_text": t.summary_text,
            "uploaded_at": t.uploaded_at.isoformat() if t.uploaded_at else None
        }
        for t in transcriptions
    ]

@router.delete("/transcription/{transcription_id}")
async def delete_transcription(
    transcription_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency),
):
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id,
        Transcription.user_id == current_user["id"]
    ).first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found.")

    file_path = os.path.join(UPLOAD_DIR, transcription.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(transcription)
    db.commit()

    return {"message": "✅ Transcription deleted successfully."}