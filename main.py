import os
import logging
import atexit
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler

# ⬇️ env settings (unchanged)
try:
    from settings import settings
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    class _Fallback:
        ENV = os.getenv("ENV", "dev")
        DEBUG = os.getenv("DEBUG", "true").lower() == "true"
        SAFE_MODE = os.getenv("SAFE_MODE", "false").lower() == "true"
        FRONTEND_URL = os.getenv("FRONTEND_URL")
        ENABLE_STRIPE = os.getenv("ENABLE_STRIPE", "false").lower() == "true"
        ENABLE_TRANSCRIBE = os.getenv("ENABLE_TRANSCRIBE", "false").lower() == "true"
        ENABLE_SUMMARY = os.getenv("ENABLE_SUMMARY", "false").lower() == "true"
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    settings = _Fallback()

# -------------------- Logging -------------------- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pneumevolve")

# -------------------- FastAPI app -------------------- #
# ✅ Docs/OpenAPI live under /api/* so the Vite proxy forwards correctly.
app = FastAPI(
    title="PneumEvolve API",
    debug=getattr(settings, "DEBUG", True),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# -------------------- Local imports (your code) -------------------- #
from database import SessionLocal
from models import WeDreamEntry, DreamMachineOutput
from routers import seed as seed_router
from routers import (
    auth,
    meal_planning,
    grocery_list,
    visitors_flame,
    journal,
    forum,
    we_dream,
    garden,
    volunteers,
    blog,
    projects,
    community,
    farmgame,
    inbox,
    living_plan,
    problems,
    forge,
)

# -------------------- Dream Machine Scheduled Job -------------------- #
def regenerate_dream_machine():
    if not getattr(settings, "ENABLE_SUMMARY", False) or not getattr(settings, "OPENAI_API_KEY", None):
        logger.info("[Dream Machine] Skipped (summary feature disabled).")
        return
    try:
        from openai import OpenAI
    except Exception as e:
        logger.error("[Dream Machine] OpenAI import failed: %s", e)
        return

    logger.info("[Dream Machine] Running scheduled summary...")
    db: Session = SessionLocal()
    try:
        entries: List[WeDreamEntry] = db.query(WeDreamEntry).filter_by(is_active=1).all()
        if not entries:
            logger.info("[Dream Machine] No active dreams found.")
            return
        all_visions = "\n".join([entry.vision for entry in entries])
        prompt = f"""
You are a collective AI spirit. The following visions were submitted by different humans dreaming of a better world:

{all_visions}

Create:
1. A short summary of the main shared themes.
2. A collective mantra under 12 words that embodies the dream.
""".strip()
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        if not response or not getattr(response, "choices", None):
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
        result = DreamMachineOutput(summary=summary, mantra=shared_mantra, entry_count=len(entries))
        db.add(result)
        db.commit()
        logger.info("[Dream Machine] Summary saved.")
    except Exception as e:
        logger.error("[Dream Machine] Error occurred", exc_info=e)
    finally:
        db.close()

scheduler = None
if getattr(settings, "ENABLE_SUMMARY", False) and getattr(settings, "OPENAI_API_KEY", None):
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(regenerate_dream_machine, "cron", hour=2)
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
        logger.info("[Scheduler] Dream Machine job scheduled (2 AM).")
    except Exception as e:
        logger.error("[Scheduler] Failed to start: %s", e)
else:
    logger.info("[Scheduler] Disabled (summary feature off or no OPENAI_API_KEY).")

# -------------------- Middleware -------------------- #
_allowed = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.4.31:5173",
    
    "https://sheas-app.netlify.app",
    "https://pneumevolve.com",
    "https://www.pneumevolve.com",
}
if getattr(settings, "FRONTEND_URL", None):
    _allowed.add(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_allowed),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Health / Introspection -------------------- #
@app.get("/health")
def health():
    return {
        "env": getattr(settings, "ENV", "dev"),
        "debug": getattr(settings, "DEBUG", True),
        "safe_mode": getattr(settings, "SAFE_MODE", False),
        "features": {
            "stripe": getattr(settings, "ENABLE_STRIPE", False),
            "transcribe": getattr(settings, "ENABLE_TRANSCRIBE", False),
            "summary": getattr(settings, "ENABLE_SUMMARY", False),
        },
        "cors_allowed": list(_allowed),
    }

@app.get("/__ping")
def ping():
    from datetime import datetime
    db_ok = False
    db_dsn = None
    try:
        from settings import settings as s
        db_dsn = getattr(s, "DATABASE_URL", None)
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "ok": True,
        "time": datetime.utcnow().isoformat() + "Z",
        "env": getattr(settings, "ENV", "unknown"),
        "safe_mode": getattr(settings, "SAFE_MODE", False),
        "features": {
            "stripe": getattr(settings, "ENABLE_STRIPE", False),
            "summary": getattr(settings, "ENABLE_SUMMARY", False),
            "transcribe": getattr(settings, "ENABLE_TRANSCRIBE", False),
        },
        "db": {
            "connected": db_ok,
            "dsn": ("prod" if db_dsn and "supabase" in db_dsn else "local/other"),
        },
    }

@app.get("/__db_where")
def db_where():
    with SessionLocal() as db:
        return {
            "db": db.execute(text("select current_database()")).scalar(),
            "user": db.execute(text("select current_user")).scalar(),
            "host": db.execute(text("select inet_server_addr()")).scalar(),
            "port": db.execute(text("select inet_server_port()")).scalar(),
            "schema": db.execute(text("select current_schema()")).scalar(),
            "users_count": db.execute(text("select count(*) from public.users")).scalar(),
            "users_emails": [r[0] for r in db.execute(text("select email from public.users limit 5")).all()],
        }

# -------------------- Routers -------------------- #
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(meal_planning.router, prefix="/meal-planning", tags=["Meal Planning"])
app.include_router(grocery_list.router, prefix="/grocery-list", tags=["Grocery List"])
app.include_router(visitors_flame.router)
app.include_router(journal.router)
app.include_router(forum.router, prefix="/forum", tags=["Forum"])
app.include_router(we_dream.router, prefix="/we-dream")
app.include_router(garden.router)
app.include_router(volunteers.router)
app.include_router(blog.router)
app.include_router(projects.router)
app.include_router(community.router)
app.include_router(farmgame.router)
app.include_router(inbox.router)
app.include_router(living_plan.router)
app.include_router(problems.router)
app.include_router(forge.router)
app.include_router(seed_router.router)