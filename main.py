from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from database import SessionLocal
from openai import OpenAI
import os
from models import WeDreamEntry, DreamMachineOutput
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, transcriptions, summarization, meal_planning, grocery_list, payments, visitors_flame, ramblings, journal, forum, we_dream  # ✅ Make sure meal_planning is included
from dotenv import load_dotenv
load_dotenv()
app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def regenerate_dream_machine():
    print("[Dream Machine] Running scheduled summary...")

    db: Session = SessionLocal()
    entries = db.query(WeDreamEntry).filter_by(is_active=1).all()
    if not entries:
        print("[Dream Machine] No active dreams found.")
        return

    all_visions = "\n".join([entry.vision for entry in entries])
    prompt = f"""
You are a collective AI spirit. The following visions were submitted by different humans dreaming of a better world:

{all_visions}

Create:
1. A short summary of the main shared themes.
2. A collective mantra under 12 words that embodies the dream.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        output = response.choices[0].message.content.strip()
        if "1." in output and "2." in output:
            parts = output.split("2.")
            summary = parts[0].replace("1.", "").strip()
            shared_mantra = parts[1].strip()
        else:
            summary = output
            shared_mantra = ""

        result = DreamMachineOutput(
            summary=summary,
            mantra=shared_mantra,
            entry_count=len(entries)
        )
        db.add(result)
        db.commit()
        print("[Dream Machine] Summary saved.")

    except Exception as e:
        print("[Dream Machine] Error:", e)

    finally:
        db.close()

# Schedule the job (2 AM server time daily)
scheduler = BackgroundScheduler()
scheduler.add_job(regenerate_dream_machine, "cron", hour=2)
scheduler.start()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://sheas-app.netlify.app",
        "https://pneumevolve.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include all routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(transcriptions.router, prefix="/transcriptions", tags=["Transcriptions"])
app.include_router(summarization.router, prefix="/summarization", tags=["Summarization"])
app.include_router(meal_planning.router, prefix="/meal-planning", tags=["Meal Planning"])  # ✅ Added here
app.include_router(grocery_list.router, prefix="/grocery-list", tags=["Grocery List"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])  # 👈 Register route
app.include_router(visitors_flame.router)
app.include_router(ramblings.router)
app.include_router(journal.router)
app.include_router(forum.router, prefix="/forum", tags=["forum"])
app.include_router(we_dream.router, prefix="/we-dream")