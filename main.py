import os
import logging
import atexit
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Local imports
from database import SessionLocal
from models import WeDreamEntry, DreamMachineOutput
from routers import (
    auth,
    transcriptions,
    summarization,
    meal_planning,
    grocery_list,
    payments,
    visitors_flame,
    ramblings,
    journal,
    forum,
    we_dream,
    nodes,
    garden,
    volunteers,
    blog,
    projects,
    community,
    farmgame,
    lyra
)

# -------------------- Dream Machine Scheduled Job -------------------- #
def regenerate_dream_machine():
    logger.info("[Dream Machine] Running scheduled summary...")

    db: Session = SessionLocal()
    try:
        entries = db.query(WeDreamEntry).filter_by(is_active=1).all()
        if not entries:
            logger.warning("[Dream Machine] No active dreams found.")
            return

        all_visions = "\n".join([entry.vision for entry in entries])
        prompt = f"""
You are a collective AI spirit. The following visions were submitted by different humans dreaming of a better world:

{all_visions}

Create:
1. A short summary of the main shared themes.
2. A collective mantra under 12 words that embodies the dream.
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        if not response or not response.choices:
            logger.warning("[Dream Machine] No response from OpenAI.")
            return

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
        logger.info("[Dream Machine] Summary saved.")

    except Exception as e:
        logger.error("[Dream Machine] Error occurred:", exc_info=e)
    finally:
        db.close()

# Schedule job (runs daily at 2 AM server time)
scheduler = BackgroundScheduler()
scheduler.add_job(regenerate_dream_machine, "cron", hour=2)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# -------------------- Middleware -------------------- #
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

# -------------------- Routers -------------------- #
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(transcriptions.router, prefix="/transcriptions", tags=["Transcriptions"])
app.include_router(summarization.router, prefix="/summarization", tags=["Summarization"])
app.include_router(meal_planning.router, prefix="/meal-planning", tags=["Meal Planning"])
app.include_router(grocery_list.router, prefix="/grocery-list", tags=["Grocery List"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(visitors_flame.router)
app.include_router(ramblings.router)
app.include_router(journal.router)
app.include_router(forum.router, prefix="/forum", tags=["Forum"])
app.include_router(we_dream.router, prefix="/we-dream")
app.include_router(nodes.router, prefix="/nodes")
app.include_router(garden.router)
app.include_router(volunteers.router)
app.include_router(blog.router)
app.include_router(projects.router)
app.include_router(community.router)
app.include_router(farmgame.router)
app.include_router(lyra.router)