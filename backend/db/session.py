"""
db/session.py — Database engine & session factories.

Provides both async (for FastAPI routes) and sync (for Alembic) engines.
Uses core.config.settings as the single source of truth for DATABASE_URL.
"""

from core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ── Resolve URLs ──────────────────────────────────────────────────────────────
import os
_base_url = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)


def _rewrite_scheme(url: str, scheme: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _normalize_query(url: str, *, driver: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if driver == "asyncpg":
        if "sslmode" in query and "ssl" not in query:
            query["ssl"] = query.pop("sslmode")
        query.pop("channel_binding", None)
    else:
        if "ssl" in query and "sslmode" not in query:
            query["sslmode"] = query.pop("ssl")

    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgresql+")


# Async engine for FastAPI routes (uses asyncpg driver)
if _base_url.startswith("sqlite"):
    ASYNC_URL = _base_url.replace("sqlite://", "sqlite+aiosqlite://")
elif _is_postgres_url(_base_url):
    ASYNC_URL = _normalize_query(
        _rewrite_scheme(_base_url, "postgresql+asyncpg"),
        driver="asyncpg",
    )
else:
    ASYNC_URL = _base_url
async_engine_args = {
    "echo": False,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,
}
if ASYNC_URL.startswith("sqlite"):
    # Async engine for SQLite needs this too, and pool settings are different
    async_engine_args = {"echo": False}
    async_engine_args["connect_args"] = {"check_same_thread": False}

async_engine = create_async_engine(ASYNC_URL, **async_engine_args)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine for Alembic migrations only
if _is_postgres_url(_base_url):
    SYNC_URL = _normalize_query(_rewrite_scheme(_base_url, "postgresql"), driver="psycopg2")
else:
    SYNC_URL = _base_url
sync_engine_args = {}
if SYNC_URL.startswith("sqlite"):
    sync_engine_args["connect_args"] = {"check_same_thread": False}

sync_engine = create_engine(SYNC_URL, **sync_engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


async def get_db():
    """FastAPI dependency — yields an async session with auto-commit/rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_db():
    """Sync session generator for Alembic or scripts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
