from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import openai
import shutil
import os
from models import Transcription
from database import get_db
from routers.auth import get_current_user_dependency
from dotenv import load_dotenv

load_dotenv()  # Load OpenAI API key from .env

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
        # Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Send to OpenAI API
        with open(file_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        transcription_text = response.text  # ✅ Fixed this line!

        # Save transcription to database
        transcription = Transcription(
            user_id=current_user["id"],
            filename=file.filename,
            transcription_text=transcription_text
        )
        db.add(transcription)
        db.commit()
        db.refresh(transcription)

        # Clean up temporary file
        os.remove(file_path)

        return {
            "id": transcription.id,
            "filename": file.filename,
            "transcription_text": transcription_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
    ### 🟢 Fetch all transcriptions for the logged-in user
    
@router.get("/transcriptions")
async def get_all_transcriptions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    transcriptions = db.query(Transcription).filter(
        Transcription.user_id == current_user["id"]
    ).all()

    if not transcriptions:
        return {"message": "No transcriptions found."}

    return [
        {
            "id": t.id,
            "filename": t.filename,
            "transcription_text": t.transcription_text,
        }
        for t in transcriptions
    ]

### 🔴 Delete a transcription
@router.delete("/transcription/{transcription_id}")
async def delete_transcription(
    transcription_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id,
        Transcription.user_id == current_user["id"]
    ).first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found.")

    # Attempt to delete the audio file
    file_path = os.path.join(UPLOAD_DIR, transcription.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove from DB
    db.delete(transcription)
    db.commit()

    return {"message": "Transcription deleted successfully."}