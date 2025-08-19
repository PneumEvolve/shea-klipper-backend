import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Load .env and make your app importable
load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Alembic config / logging
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# pull the multi-dir setting from alembic.ini
version_locations = config.get_main_option("version_locations")
if version_locations:
    version_locations = [p.strip() for p in version_locations.split()]
else:
    version_locations = None


# Import your models + metadata
from models import Base  # adjust import if your Base lives elsewhere
import models  # keep for side-effects if needed

target_metadata = Base.metadata

# Prefer DATABASE_URL env var; fallback to alembic.ini
env_url = os.getenv("DATABASE_URL")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

def _configure_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_locations=version_locations,
    )

def _configure_online(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_locations=version_locations,
    )

def run_migrations_offline():
    _configure_offline()
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
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