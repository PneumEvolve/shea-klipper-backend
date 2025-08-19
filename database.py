# database.py
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from settings import settings  # <-- single source of truth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

# Use exactly what settings provides (it already loads .env or OS env)
DATABASE_URL = settings.DATABASE_URL

# Local-friendly engine (prod may add ssl via DATABASE_URL itself)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    logger.info("📥 Opened DB connection")
    try:
        yield db
    finally:
        db.close()
        logger.info("📤 Closed DB connection")