from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, transcriptions, summarization, meal_planning, grocery_list, payments, visitors_flame, ramblings, journal, forum  # ✅ Make sure meal_planning is included
from dotenv import load_dotenv
load_dotenv()
app = FastAPI()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "https://sheas-app.netlify.app", 
                   "https://pneumevolve.com/" ],  # Adjust this in production
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