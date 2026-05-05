from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db import crud
from schemas import schemas

router = APIRouter()


@router.get("/overview", response_model=schemas.OverviewStats)
async def get_overview(db: AsyncSession = Depends(get_db)):
    return await crud.get_overview_stats(db)


@router.get("/wait-series", response_model=List[schemas.WaitSeriesPoint])
async def get_wait_series(db: AsyncSession = Depends(get_db)):
    return await crud.get_wait_series(db)


@router.get("/load-forecast", response_model=List[schemas.LoadForecastPoint])
async def get_load_forecast(db: AsyncSession = Depends(get_db)):
    return await crud.get_load_forecast(db)
