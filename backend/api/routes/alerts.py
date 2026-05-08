import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.session import get_db
from schemas import schemas

router = APIRouter()


@router.get("/", response_model=List[schemas.Alert])
async def get_alerts(db: AsyncSession = Depends(get_db)):
    return await crud.get_ops_alerts(db)


@router.post("/", response_model=schemas.Alert)
async def create_alert(payload: schemas.AlertCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    return await crud.create_ops_alert(db, data)


@router.post("/{id}/acknowledge")
async def acknowledge_alert(id: str, db: AsyncSession = Depends(get_db)):
    success = await crud.acknowledge_ops_alert(db, id)
    if not success:
        return {"success": False, "message": "Alert not found"}
    return {"success": True}
