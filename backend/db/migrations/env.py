from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

import os
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def normalize_sync_postgres_url(url: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "ssl" in query and "sslmode" not in query:
        query["sslmode"] = query.pop("ssl")
    return urlunsplit(
        ("postgresql", parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def get_url():
    # Priority 1: Use the full DATABASE_URL if available (set in docker-compose)
    url = os.environ.get("DATABASE_URL")
    if url:
        return normalize_sync_postgres_url(url)
    
    # Priority 2: Build it from components (fallback for local runs)
    password = os.environ.get("POSTGRES_PASSWORD", "mediflow")
    host = os.environ.get("POSTGRES_HOST", "postgres") # 'postgres' is the service name in docker-compose
    return f"postgresql://mediflow:{password}@{host}:5432/mediflow"

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
