# routers/we_dream.py
#
# Dream Machine — no AI API required.
# The nightly job weaves visions together without any external calls.
# When you have enough users to make AI summarization meaningful, 
# swap regenerate_dream_machine() back in from main.py.
 
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import random
 
from database import get_db
from models import WeDreamEntry, DreamMachineOutput
from routers.auth import get_current_user_dependency
 
router = APIRouter()
 
 
# ─── Collective output ────────────────────────────────────────────────────────
 
@router.get("/collective")
def get_latest_dream_summary(db: Session = Depends(get_db)):
    latest = (
        db.query(DreamMachineOutput)
        .order_by(DreamMachineOutput.created_at.desc())
        .first()
    )
    if not latest:
        return {
            "summary": "No collective dream has been formed yet. Add yours.",
            "mantra": "",
            "count": 0,
            "updated_at": None,
            "featured": None,
        }
    return {
        "summary": latest.summary,
        "mantra": latest.mantra,
        "count": latest.entry_count,
        "updated_at": latest.created_at,
        "featured": getattr(latest, "featured_vision", None),
    }
 
 
# ─── Individual dream pages ───────────────────────────────────────────────────
 
@router.get("/active")
def get_active_we_dream_entry(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency),
):
    entry = (
        db.query(WeDreamEntry)
        .filter_by(user_id=current_user.id, is_active=1)
        .order_by(WeDreamEntry.created_at.desc())
        .first()
    )
    if not entry:
        return {"vision": "", "mantra": "", "exists": False}
    return {"vision": entry.vision, "mantra": entry.mantra, "exists": True}
 
 
@router.post("/save")
def save_we_dream_entry(
    entry: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency),
):
    vision = entry.get("vision", "")
    mantra = entry.get("mantra", "") or ""
    if not vision:
        raise HTTPException(status_code=400, detail="Vision is required.")
 
    db.query(WeDreamEntry).filter_by(user_id=current_user.id, is_active=1).update(
        {"is_active": 0}
    )
    new_entry = WeDreamEntry(user_id=current_user.id, vision=vision, mantra=mantra)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"message": "Entry saved successfully."}
 
 
@router.post("/clear")
def clear_we_dream_entry(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency),
):
    updated = (
        db.query(WeDreamEntry)
        .filter_by(user_id=current_user.id, is_active=1)
        .update({"is_active": 0})
    )
    db.commit()
    return {"message": "Dream entry cleared."} if updated else {"message": "No active dream to clear."}
 
 
# ─── Mantra generation — no AI, returns the user's own vision as their mantra ─
# Replace this with an API call later when it's worth it.
 
@router.post("/manifest")
async def manifest_vision(request):
    data = await request.json()
    vision = data.get("text", "")
    if not vision:
        return {"mantra": "Please share your dream first."}
    # For now: distill the first sentence of their own vision back to them.
    # It's surprisingly meaningful — your own words, reflected.
    first_sentence = vision.split(".")[0].strip()
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:80].rsplit(" ", 1)[0] + "…"
    return {"mantra": first_sentence or vision[:80]}
 
 
# ─── Manual trigger (useful for testing + admin) ──────────────────────────────
 
@router.post("/run-dream-machine")
def manual_dream_machine_run(db: Session = Depends(get_db)):
    return _run_dream_machine(db)
 
 
@router.get("/ping-dream-machine")
def ping_dream_machine(db: Session = Depends(get_db)):
    return _run_dream_machine(db)
 
 
# ─── Core weaving logic — no AI required ─────────────────────────────────────
 
def _run_dream_machine(db: Session):
    """
    Weaves active visions into a collective output without any AI API.
 
    What it does:
    - Counts active dreamers
    - Picks one vision at random to feature
    - Builds a summary from the first line of each vision
    - Derives a collective mantra from the most common meaningful words
    """
    entries = db.query(WeDreamEntry).filter_by(is_active=1).all()
    if not entries:
        return {"message": "No active dreams found."}
 
    count = len(entries)
 
    # Pick a featured vision at random
    featured = random.choice(entries).vision
 
    # Build a simple summary: one line per dreamer, anonymised
    lines = []
    for i, entry in enumerate(entries, 1):
        # Take the first sentence or first 120 chars of each vision
        first = entry.vision.split(".")[0].strip()
        if len(first) > 120:
            first = first[:120].rsplit(" ", 1)[0] + "…"
        lines.append(f"— {first}")
 
    summary = (
        f"{count} {'person is' if count == 1 else 'people are'} dreaming together.\n\n"
        + "\n".join(lines)
    )
 
    # Derive a collective mantra from shared words
    mantra = _derive_mantra([e.vision for e in entries])
 
    result = DreamMachineOutput(
        summary=summary,
        mantra=mantra,
        entry_count=count,
    )
    # Store featured vision if the model supports it
    if hasattr(result, "featured_vision"):
        result.featured_vision = featured
 
    db.add(result)
    db.commit()
 
    return {
        "message": f"Dream Machine woven from {count} dreams.",
        "summary": summary,
        "mantra": mantra,
        "count": count,
        "featured": featured,
    }
 
 
def _derive_mantra(visions: list[str]) -> str:
    """
    Finds the most frequently used meaningful words across all visions
    and weaves them into a short mantra.
    No API needed — just frequency analysis.
    """
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "are", "was", "be", "i", "we", "my", "our", "that",
        "this", "it", "its", "have", "has", "do", "not", "so", "if", "as",
        "by", "from", "where", "when", "what", "how", "who", "can", "will",
        "would", "could", "should", "want", "need", "more", "all", "one",
        "there", "they", "their", "them", "into", "which", "about", "just",
        "like", "get", "make", "know", "see", "think", "feel",
    }
 
    word_counts: dict[str, int] = {}
    for vision in visions:
        words = vision.lower().replace(",", "").replace(".", "").split()
        for word in words:
            if word not in STOPWORDS and len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1
 
    if not word_counts:
        return "Together we build the world we wish to see."
 
    # Take the top 5 most common words and build a mantra from them
    top = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_words = [w for w, _ in top]
 
    if len(top_words) >= 3:
        return f"Together: {top_words[0]}, {top_words[1]}, {top_words[2]}."
    elif len(top_words) == 2:
        return f"We rise through {top_words[0]} and {top_words[1]}."
    else:
        return f"We carry {top_words[0]} forward together."