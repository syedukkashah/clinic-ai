from typing import Any, Mapping
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.session import get_db
from schemas import schemas

router = APIRouter()

_ALERT_TYPES = {"surge", "latency", "drift", "capacity"}


def _public_severity(value: Any) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "").strip().lower()
    if text in {"critical", "high"}:
        return "High"
    if text in {"warning", "warn", "medium"}:
        return "Medium"
    if text in {"info", "low"}:
        return "Low"
    return "Medium"


def _public_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in _ALERT_TYPES:
        return text
    if text == "anomaly":
        return "surge"
    return "surge"


def _valid_actions(actions: Any) -> list[dict[str, Any]] | None:
    if not isinstance(actions, list):
        return None
    structured_actions = [item for item in actions if isinstance(item, dict)]
    return structured_actions or None


def _alert_to_schema(alert: Any) -> dict[str, Any]:
    details = getattr(alert, "details", {}) or {}
    if not isinstance(details, Mapping):
        details = {}

    created_at = getattr(alert, "created_at", None)
    timestamp = created_at.isoformat() if created_at else "just now"
    message = getattr(alert, "message", None) or "Alert"

    return {
        "id": f"alt-{getattr(alert, 'id', '')}",
        "severity": _public_severity(getattr(alert, "severity", None)),
        "title": message,
        "reasoning": details.get("reasoning") or details.get("steps_taken") or message,
        "timestamp": timestamp,
        "type": _public_type(details.get("type") or details.get("triggered_by")),
        "trace": details.get("trace") if isinstance(details.get("trace"), list) else None,
        "recommendedActions": _valid_actions(details.get("recommendedActions")),
        "acknowledged": bool(details.get("acknowledged", False)),
    }


@router.get("/", response_model=List[schemas.Alert])
async def get_alerts(db: AsyncSession = Depends(get_db)):
    alerts = await crud.get_ops_alerts(db)
    return [_alert_to_schema(alert) for alert in alerts]


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
