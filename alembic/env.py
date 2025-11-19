import sys
import os
from dotenv import load_dotenv

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# --- Project-specific setup ---
# Add the 'app' directory to the Python path so Alembic can find the models
# This assumes the alembic command is run from the project root.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
from app.models import Base
# -----------------------------

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Project-specific setup ---
# Set the target metadata for autogeneration
target_metadata = Base.metadata
# -----------------------------

# --- Database URL Configuration ---
# Load .env file and set the sqlalchemy.url from DATABASE_URL
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
else:
    # Handle case where DATABASE_URL is not in .env
    # You might want to raise an error or use a default
    pass
# ---------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    print(f"DEBUG: Alembic connecting to engine: {connectable.url}")
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
