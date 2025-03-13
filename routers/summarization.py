from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import openai
from models import Transcription
from database import get_db
from routers.auth import get_current_user_dependency
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

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

        # Extract response safely
        summary = getattr(response, "choices", [{}])[0].message.content.strip()

        # Split into summary & title
        summary_parts = summary.split("\n", 1)  # Ensure it only splits once
        generated_title = summary_parts[0].strip() if len(summary_parts) > 1 else "Untitled"
        summary_text = summary_parts[1].strip() if len(summary_parts) > 1 else summary_parts[0]

        # Store summary in DB
        transcription.transcription_text = summary_text  # Overwrite with summary
        transcription.filename = generated_title  # Change filename to title

        # 🔹 **Now categorize the transcription**
        category_response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Categorize this transcription based on its content. Keep the category concise."},
                {"role": "user", "content": f"Categorize this text:\n\n{transcription.transcription_text}"}
            ]
        )

        transcription.category = getattr(category_response, "choices", [{}])[0].message.content.strip()

        # ✅ Save everything to the database
        db.commit()
        db.refresh(transcription)

        return {
            "id": transcription.id,
            "filename": transcription.filename,
            "summary": transcription.transcription_text,
            "category": transcription.category
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error summarizing: {str(e)}")