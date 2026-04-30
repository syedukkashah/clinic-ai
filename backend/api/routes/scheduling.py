from fastapi import APIRouter

from agents.scheduling_agent import run_optimization
from schemas import schemas

router = APIRouter()


@router.post("/optimize", response_model=schemas.OptimizationResponse)
def post_optimize(req: schemas.OptimizationRequest):
    return run_optimization(req.windowHoursAhead)


@router.post("/reassign")
def post_reassign(params: dict):
    return {"success": True, "message": "Reassignment queued"}
