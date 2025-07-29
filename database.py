import os
import logging
from dotenv import load_dotenv
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_fixed

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

# Load DB credentials
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

# Full database URL
DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

# Create engine and session
engine = create_engine(DATABASE_URL, pool_size=2, max_overflow=20)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Add retry logic to DB dependency
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_db():
    try:
        db = SessionLocal()
        logger.info("📥 Opened DB connection")
        yield db
    except OperationalError as e:
        logger.warning("❌ Database connection failed. Retrying...")
        raise e
    finally:
        db.close()
        logger.info("📤 Closed DB connection")