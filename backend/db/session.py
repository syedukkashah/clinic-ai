"""
db/session.py — Database engine & session factories.

Provides both async (for FastAPI routes) and sync (for Alembic) engines.
Uses core.config.settings as the single source of truth for DATABASE_URL.
"""

from core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Resolve URLs ──────────────────────────────────────────────────────────────
_base_url = settings.DATABASE_URL

# Async engine for FastAPI routes (uses asyncpg driver)
ASYNC_URL = (
    _base_url
    .replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    .replace("postgresql://", "postgresql+asyncpg://")
)
async_engine = create_async_engine(
    ASYNC_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine for Alembic migrations only
SYNC_URL = (
    _base_url
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql+psycopg2://", "postgresql://")
)
sync_engine = create_engine(SYNC_URL)
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