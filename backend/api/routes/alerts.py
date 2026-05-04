import time
from typing import List

from fastapi import APIRouter

from schemas import schemas

router = APIRouter()

MOCK_ALERTS = [
    {
        "id": "alt-1",
        "severity": "High",
        "title": "Booking surge anomaly detected",
        "reasoning": "Booking volume up 220% vs forecast.",
        "type": "surge",
        "acknowledged": False,
        "timestamp": "2026-04-26T19:00:00Z",
        "trace": ["trigger=prometheus_alert", "query_booking_volume(30m) => 42"],
        "recommendedActions": [{"kind": "open_slots", "count": 8}],
    }
]


@router.get("/", response_model=List[schemas.Alert])
def get_alerts():
    return MOCK_ALERTS


@router.post("/", response_model=schemas.Alert)
def create_alert(payload: schemas.AlertCreate):
    now = int(time.time() * 1000)
    created = {
        "id": f"alt-{now}",
        "severity": payload.severity,
        "title": payload.title,
        "reasoning": payload.reasoning,
        "type": payload.type,
        "timestamp": "just now",
        "trace": payload.trace,
        "recommendedActions": payload.recommendedActions,
        "acknowledged": False,
    }
    MOCK_ALERTS.insert(0, created)
    return created


@router.post("/{id}/acknowledge")
def acknowledge_alert(id: str):
    for alert in MOCK_ALERTS:
        if alert["id"] == id:
            alert["acknowledged"] = True
            return {"success": True}
    return {"success": False, "message": "Alert not found"}
