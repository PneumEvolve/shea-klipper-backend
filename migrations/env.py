import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine
from dotenv import load_dotenv

# -------- Load .env and make project importable --------
load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# -------- Alembic config / logging --------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Version locations (supports single-dir or multi-dir)
version_locations = config.get_main_option("version_locations")
if version_locations:
    version_locations = [p.strip() for p in version_locations.split()]
else:
    version_locations = None

# -------- Import your models + metadata (single Base!) --------
from models import Base  # ensure all models use this Base
import models  # side-effects to register models

target_metadata = Base.metadata

# -------- Resolve database URL priority (NO writing back to config!) --------
resolved_url = (
    os.getenv("ALEMBIC_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
)

# -------- Optional filters / connect args --------
def _include_object(obj, name, type_, reflected, compare_to):
    """Ignore non-public schemas during autogenerate (e.g., Supabase system schemas)."""
    schema = getattr(obj, "schema", None)
    if schema not in (None, "public"):
        return False
    return True

def _extra_connect_args():
    """Allow forcing IPv4 or SSL via env if needed."""
    args = {}
    hostaddr = os.getenv("DB_HOSTADDR")
    if hostaddr:
        args["hostaddr"] = hostaddr
    if os.getenv("DB_FORCE_SSL", "false").lower() == "true":
        args["sslmode"] = "require"
    return args

# -------- Configure contexts --------
def _configure_offline():
    context.configure(
        url=resolved_url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        version_locations=version_locations,
    )

def _configure_online(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        version_locations=version_locations,
    )

# -------- Entry points --------
def run_migrations_offline():
    _configure_offline()
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(
        resolved_url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure_online(connection)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()