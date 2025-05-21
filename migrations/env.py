import os
import sys
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv

# Load .env file manually
load_dotenv()

# Add your app directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Logging config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your metadata
from models import Base

# Pull DB URL from env
DATABASE_URL = os.environ.get("DATABASE_URL")
print("Using database:", DATABASE_URL)
if not DATABASE_URL:
    raise Exception("DATABASE_URL not set. Check your .env file.")

# Set target metadata
target_metadata = Base.metadata

# ---- Offline mode
def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

# ---- Online mode
def run_migrations_online():
    engine = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

# ---- Execute appropriate path
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()