from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import openai
import shutil
import os
from models import Transcription, TranscriptionUsage
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
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with open(file_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        transcription_text = response.text

        transcription = Transcription(
            user_id=current_user["id"],
            filename=file.filename,
            transcription_text=transcription_text,
            uploaded_at=datetime.utcnow()
        )
        db.add(transcription)
        db.commit()
        db.refresh(transcription)

        os.remove(file_path)

        # ✅ Estimate token usage and cost
        token_estimate = len(transcription_text) // 4
        cost = token_estimate * 0.000015  # Whisper pricing estimate

        usage_entry = TranscriptionUsage(
            user_id=current_user["id"],
            transcription_id=transcription.id,
            tokens_used=token_estimate,
            cost=cost,
            timestamp=datetime.utcnow()
        )
        db.add(usage_entry)
        db.commit()

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