import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, transcriptions, summarization

app = FastAPI()

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication and transcription routes
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(transcriptions.router, prefix="/transcriptions", tags=["transcriptions"])
app.include_router(summarization.router, prefix="/summarization", tags=["summarization"])

@app.get("/")
def root():
    return {"message": "Shea Klipper Backend Running Successfully"}

# Ensure Render assigns the correct port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Default to 8000 locally
    uvicorn.run(app, host="0.0.0.0", port=port)