"""Health-check routes — includes DB connectivity probe."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.session import get_db

router = APIRouter()


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """Verify database connectivity and return table row counts."""
    return await crud.check_db(db)
