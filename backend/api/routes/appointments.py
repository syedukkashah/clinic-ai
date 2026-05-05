from __future__ import annotations

import random
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db import crud
from db.models import AppointmentStatus
from schemas import schemas

router = APIRouter()


@router.get("/", response_model=List[schemas.Appointment])
async def get_appointments(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await crud.get_appointments(db, limit=limit, offset=offset)


@router.post("/", response_model=schemas.Appointment)
async def create_appointment(
    appointment: schemas.AppointmentCreate,
    db: AsyncSession = Depends(get_db),
):
    data = appointment.model_dump()
    data["predictedWaitMin"] = random.randint(0, 40)
    return await crud.create_appointment(db, data)


@router.post("/book")
def book_appointment():
    raise HTTPException(
        status_code=501,
        detail="Booking endpoint is not implemented yet. It will be connected to the scheduling agent later.",
    )


@router.put("/{id}", response_model=schemas.Appointment)
async def update_appointment(
    id: str,
    appointment_update: schemas.AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    patch = appointment_update.model_dump(exclude_unset=True)
    result = await crud.update_appointment(db, id, patch)
    if result is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return result


@router.delete("/{id}")
async def delete_appointment(id: str, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_appointment(db, id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"message": "Deleted successfully"}
