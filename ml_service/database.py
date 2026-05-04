"""
database.py — Async SQLAlchemy engine and session dependency for ML service.

The ml_predictions table is created by M4 (the main backend). This module
only provides the engine and session factory so the ML service can INSERT
prediction rows.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://localhost/mediflow"
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        yield session
