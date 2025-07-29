import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

# Optional retry tools (not required right away)
# from tenacity import retry, stop_after_attempt, wait_fixed

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

# Environment variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

# Database URL
DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, pool_size=2, max_overflow=20)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# 🔁 Optional retry logic for later (disabled for now)
# @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
# def get_retrying_db():
#     db = SessionLocal()
#     logger.info("📥 Opened DB connection (retryable)")
#     return db

# 🚀 FastAPI-compatible session dependency
def get_db():
    db = SessionLocal()
    logger.info("📥 Opened DB connection")
    try:
        yield db
    finally:
        db.close()
        logger.info("📤 Closed DB connection")