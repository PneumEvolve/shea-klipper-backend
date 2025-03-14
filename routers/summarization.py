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

# ✅ Set up logging
logging.basicConfig(level=logging.INFO)

@router.post("/summarize/{transcription_id}")
async def summarize_transcription(
    transcription_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    try:
        # 🔹 Step 1: Fetch transcription from DB
        transcription = db.query(Transcription).filter(
            Transcription.id == transcription_id,
            Transcription.user_id == current_user["id"]
        ).first()

        if not transcription:
            logging.warning(f"⚠️ Transcription ID {transcription_id} not found for user {current_user['id']}")
            raise HTTPException(status_code=404, detail="Transcription not found.")

        logging.info(f"✅ Found transcription ID {transcription_id} for summarization.")

        # 🔹 Step 2: Send text to OpenAI for summarization & title generation
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

        # 🔹 Step 3: Extract summary text safely
        summary_text = response.choices[0].message.content.strip()

        # ✅ Log extracted summary
        logging.info(f"✅ Extracted Summary: {summary_text}")

        if not summary_text:
            logging.warning(f"⚠️ Empty summary returned for transcription ID {transcription_id}")
            raise HTTPException(status_code=500, detail="Summarization failed: OpenAI returned empty text.")

        # 🔹 Step 4: Store summary in DB
        transcription.summary_text = summary_text
        db.commit()  # ✅ Ensure changes are saved

        # ✅ Log after commit
        logging.info(f"📌 Summary successfully saved for transcription ID {transcription_id}")

        db.refresh(transcription)  # ✅ Refresh the object to confirm DB update

        return {
            "id": transcription.id,
            "filename": transcription.filename,
            "summary": transcription.summary_text  # ✅ Ensure correct field is returned
        }

    except Exception as e:
        logging.error(f"❌ Error summarizing transcription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error summarizing: {str(e)}")