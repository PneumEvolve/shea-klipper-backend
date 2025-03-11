from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import openai
from database import get_db
from models import Transcription
from routers.auth import get_current_user_dependency
import os

router = APIRouter()

# Load OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Make sure you set this in your .env file or system variables

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)  # Initialize OpenAI client

@router.post("/summarize/{transcription_id}")
def summarize_transcription(
    transcription_id: int, 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user_dependency)
):
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id,
        Transcription.user_id == current_user["id"]
    ).first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Summarize this: {transcription.transcription_text}"}]
        )
        summary = response.choices[0].message.content

        return {"transcription_id": transcription.id, "summary": summary}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error summarizing transcription: {str(e)}")