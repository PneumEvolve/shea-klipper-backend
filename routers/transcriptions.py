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

        transcription_text = response.get("text", "")  # Make sure response is used correctly

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