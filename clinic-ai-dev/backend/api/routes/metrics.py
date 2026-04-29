from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def get_metrics():
    return {
        "appointments_today": 5,
        "average_wait_time": 22,
        "active_doctors": 3,
        "system_status": "healthy"
    }