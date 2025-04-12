import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("DATABASE_URL")
engine = create_engine(url)

try:
    with engine.connect() as conn:
        print("✅ Connection successful!")
except Exception as e:
        print("❌ Connection failed:", e)