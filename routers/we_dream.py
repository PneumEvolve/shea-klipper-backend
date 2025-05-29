from fastapi import APIRouter, Request
import openai  # or wherever your AI logic is

router = APIRouter()

# FastAPI example route
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

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return {"mantra": response['choices'][0]['message']['content'].strip()}