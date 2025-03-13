from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, transcriptions, summarization
import os

app = FastAPI()

# ✅ Explicitly Allow Netlify Frontend
origins = [
    "https://sheas-app.netlify.app",  # ✅ Allow only this frontend
    "http://localhost:5173",  # ✅ Allow local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ✅ Explicitly set allowed origins
    allow_credentials=True,  # ✅ Allow cookies and authentication tokens
    allow_methods=["*"],  # ✅ Allow all HTTP methods (GET, POST, DELETE, etc.)
    allow_headers=["*"],  # ✅ Allow all headers
)

# ✅ Include Routers
app.include_router(auth.router, prefix="/auth")
app.include_router(transcriptions.router, prefix="/transcriptions")
app.include_router(summarization.router, prefix="/summarization")