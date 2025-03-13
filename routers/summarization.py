from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import openai
import logging  # ✅ Add logging
from models import Transcription
from database import get_db
from routers.auth import get_current_user_dependency
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

logging.basicConfig(level=logging.INFO)

@router.post("/summarize/{transcription_id}")
async def summarize_transcription(
    transcription_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    try:
        # Fetch transcription from DB
        transcription = db.query(Transcription).filter(
            Transcription.id == transcription_id,
            Transcription.user_id == current_user["id"]
        ).first()

        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found.")

        # Send text to OpenAI for summarization & title generation
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an assistant that summarizes text and generates short, meaningful titles."},
                {"role": "user", "content": f"Summarize this transcription:\n\n{transcription.transcription_text}"},
                {"role": "user", "content": "Now generate a short, catchy title for it."}
            ]
        )

        # ✅ Log OpenAI Response
        logging.info(f"🟡 OpenAI Response: {response}")

        # Extract response safely
        summary = response.choices[0].message.content.strip()

        # ✅ Log extracted summary
        logging.info(f"✅ Extracted Summary: {summary}")

        # Split into summary & title
        summary_parts = summary.split("\n")
        generated_title = summary_parts[0] if len(summary_parts) > 1 else "Untitled"
        summary_text = "\n".join(summary_parts[1:])

        # Store summary in DB
        transcription.summary_text = summary_text
        transcription.filename = generated_title  # Optionally update filename
        db.commit()
        db.refresh(transcription)

        return {
            "id": transcription.id,
            "filename": transcription.filename,
            "summary": transcription.summary_text  # ✅ Make sure the correct field is returned
        }

    except Exception as e:
        logging.error(f"❌ Error summarizing transcription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error summarizing: {str(e)}")