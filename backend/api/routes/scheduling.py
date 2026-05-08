from fastapi import APIRouter

from agents.scheduling_agent import run_optimization
from schemas import schemas

router = APIRouter()


@router.post("/optimize", response_model=schemas.OptimizationResponse)
async def post_optimize(req: schemas.OptimizationRequest):
    return await run_optimization(req.windowHoursAhead)


@router.post("/reassign")
async def post_reassign(params: dict):
    # This could call a more specific reassignment function in scheduling_agent
    return {"success": True, "message": "Reassignment queued"}
