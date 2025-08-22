import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# --- Load environment & path tweaks (your originals, kept) --------------------
load_dotenv()  # load .env into process env

# Make sure the app package is importable (adjust if your structure differs)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Alembic Config / Logging -------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Import your metadata (your originals, kept) ------------------------------
# Ensure this import points to the module where Base.metadata lives
from models import Base  # noqa: E402
import models  # noqa: F401  (kept for side-effect imports if you rely on model module-level definitions)

target_metadata = Base.metadata

# --- Prefer DATABASE_URL; fallback to alembic.ini -----------------------------
# If DATABASE_URL is present, override sqlalchemy.url in alembic.ini.
# Otherwise, Alembic will use whatever is configured in alembic.ini.
env_url = os.getenv("DATABASE_URL")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

# NOTE: Avoid printing DATABASE_URL — it includes credentials.
# If you want to log which DB you’re hitting, log only the host/dbname.
# Example (optional):
# from urllib.parse import urlparse
# parsed = urlparse(config.get_main_option("sqlalchemy.url"))
# context.get_context().logger.info("Running migrations against: %s://%s:%s/%s",
#                                   parsed.scheme, parsed.hostname, parsed.port, parsed.path.lstrip('/'))

# --- Configure helpers --------------------------------------------------------
def _configure_offline():
    """Configure Alembic in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

def _configure_online(connection):
    """Configure Alembic in 'online' mode with a live connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

# --- Offline / Online runners -------------------------------------------------
def run_migrations_offline():
    _configure_offline()
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # Use Alembic config to build the engine; respects sqlalchemy.url (possibly overridden by env var)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure_online(connection)
        with context.begin_transaction():
            context.run_migrations()

# --- Entrypoint ---------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()