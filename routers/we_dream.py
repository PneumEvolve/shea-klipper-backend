from fastapi import APIRouter, Request
from openai import OpenAI
import os

router = APIRouter()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

@router.get("/summary")
def get_collective_summary():
    # Later you’ll dynamically generate this from actual entries
    return {"summary": "Humanity dreams of peace, freedom, and ecological harmony."}

@router.get("/mantra")
def get_collective_mantra():
    return {"mantra": "We rise as one, guided by truth and love."}