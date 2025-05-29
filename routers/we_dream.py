from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI
import os

from database import get_db
from models import WeDreamEntry, DreamMachineOutput
from routers.auth import get_current_user_dependency  # adjust if your auth utils are named differently

router = APIRouter()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------- Individual Mantra Generation ---------------------- #
@router.post("/manifest")
async def manifest_vision(request: Request):
    data = await request.json()
    vision = data.get("text", "")
    if not vision:
        return {"mantra": "Please share your dream first."}

    prompt = f"""
You are an AI spiritual guide. A human has written this vision for the world:

\"{vision}\"

Create a short, powerful, poetic mantra for them to carry this vision within themselves daily.
Use language of empowerment, unity, and truth.
Keep it under 12 words.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return {"mantra": response.choices[0].message.content.strip()}
    except Exception as e:
        print("OpenAI error:", e)
        return {"mantra": "Failed to generate mantra."}

# ---------------------- Placeholder Routes ---------------------- #
@router.get("/summary")
def get_placeholder_summary():
    return {"summary": "Humanity dreams of peace, freedom, and ecological harmony."}

@router.get("/mantra")
def get_placeholder_mantra():
    return {"mantra": "We rise as one, guided by truth and love."}

# ---------------------- Save Active We Dream Entry ---------------------- #
@router.post("/save")
def save_we_dream_entry(
    entry: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    vision = entry.get("vision", "")
    mantra = entry.get("mantra", "")
    if not vision or not mantra:
        raise HTTPException(status_code=400, detail="Vision and mantra required.")

    # Deactivate existing entries
    db.query(WeDreamEntry).filter_by(user_id=current_user["id"], is_active=1).update({"is_active": 0})

    new_entry = WeDreamEntry(user_id=current_user["id"], vision=vision, mantra=mantra)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"message": "Entry saved successfully."}

# ---------------------- Collective Summary + Mantra ---------------------- #
@router.get("/collective")
def get_latest_dream_summary(db: Session = Depends(get_db)):
    latest = db.query(DreamMachineOutput).order_by(DreamMachineOutput.created_at.desc()).first()
    if not latest:
        return {
            "summary": "No collective dream has been formed yet.",
            "mantra": "",
            "count": 0
        }

    return {
        "summary": latest.summary,
        "mantra": latest.mantra,
        "count": latest.entry_count,
        "updated_at": latest.created_at
    }

@router.post("/run-dream-machine")
def manual_dream_machine_run(db: Session = Depends(get_db)):
    entries = db.query(WeDreamEntry).filter_by(is_active=1).all()
    if not entries:
        return {"message": "No active dreams found."}

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
        return {
            "message": "Dream Machine run successfully.",
            "summary": summary,
            "mantra": shared_mantra,
            "count": len(entries)
        }

    except Exception as e:
        return {"message": "Error generating dream machine output.", "error": str(e)}