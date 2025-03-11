from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import whisper
import shutil
import os
import subprocess
from models import Transcription
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()

# Load Whisper model once to avoid reloading on every request
model = whisper.load_model("tiny")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Check FFmpeg availability once at startup
try:
    ffmpeg_check = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
    print("FFmpeg is available:", ffmpeg_check.stdout.split("\n")[0])  # Print only first line for clarity
except subprocess.CalledProcessError:
    print("FFmpeg is not installed or not found. Please install it and add to PATH.")
    raise RuntimeError("FFmpeg is required but not found. Install it before running the server.")

@router.get("/")
def get_transcriptions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """Fetch all transcriptions for the logged-in user."""
    return db.query(Transcription).filter(Transcription.user_id == current_user["id"]).all()

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user_dependency)  # Use correct dependency
):
    try:
        # Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Debugging log: Check if the file exists
        if os.path.exists(file_path):
            print(f"File saved successfully: {file_path}")
        else:
            raise HTTPException(status_code=500, detail="Failed to save the file.")

        # Transcribe audio using Whisper
        result = model.transcribe(file_path)
        transcription_text = result["text"]

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

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"File not found: {str(e)}")
    except whisper.WhisperException as e:
        raise HTTPException(status_code=500, detail=f"Whisper error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@router.delete("/transcriptions/{transcription_id}")
def delete_transcription(transcription_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id, Transcription.user_id == current_user["id"]).first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    db.delete(transcription)
    db.commit()

    return {"message": "Transcription deleted successfully"}