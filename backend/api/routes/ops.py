import time
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agents.ops_agent import ops_agent
from db import crud
from db.session import get_db
from schemas import schemas

router = APIRouter()


@router.get("/suggestions", response_model=List[schemas.Suggestion])
async def get_suggestions(db: AsyncSession = Depends(get_db)):
    metrics = await crud.get_dynamic_metrics(db)
    activity = await crud.get_activity_feed(db)
    doctors = await crud.get_doctors(db)
    return await ops_agent.get_suggestions(metrics, activity, doctors)


@router.get("/activity", response_model=List[schemas.ActivityEvent])
async def get_activity(db: AsyncSession = Depends(get_db)):
    return await crud.get_activity_feed(db)


@router.get("/agents", response_model=List[schemas.AgentStatus])
async def get_agents():
    _now = int(time.time() * 1000)
    return [
        {"id": "booking", "name": "Booking Agent", "state": "online", "lastAction": "Listening for requests", "lastSeenAt": _now},
        {"id": "calling", "name": "Calling Agent", "state": "online", "lastAction": "Idle", "lastSeenAt": _now - 10000},
        {"id": "scheduling", "name": "Scheduling Agent", "state": "online", "lastAction": "Next optimization in 30m", "lastSeenAt": _now - 50000},
        {"id": "ops_monitor", "name": "Ops Monitor Agent", "state": "online", "lastAction": "Analyzing drift", "lastSeenAt": _now - 2000},
    ]


@router.get("/metrics", response_model=schemas.ClinicMetrics)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    return await crud.get_dynamic_metrics(db)
