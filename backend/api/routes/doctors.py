from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db import crud
from schemas import schemas

router = APIRouter()


@router.get("/", response_model=List[schemas.Doctor])
async def get_doctors(db: AsyncSession = Depends(get_db)):
    return await crud.get_doctors(db)


@router.get("/{id}/availability")
async def get_doctor_availability(id: int, db: AsyncSession = Depends(get_db)):
    return await crud.get_doctor_availability(db, id)
