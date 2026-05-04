from datetime import datetime
from typing import List

from fastapi import APIRouter

from schemas import schemas
from .appointments import MOCK_APPOINTMENTS

router = APIRouter()


def _today() -> str:
    return datetime.utcnow().date().isoformat()


@router.get("/overview", response_model=schemas.OverviewStats)
def get_overview():
    date = _today()
    todays = [a for a in MOCK_APPOINTMENTS if a.date == date]
    in_queue = [a for a in todays if a.status in ("Waiting", "Confirmed")]
    avg_wait = int(round(sum((a.predictedWaitMin for a in in_queue), 0) / max(1, len(in_queue))))
    health = max(20, min(100, 100 - int(avg_wait * 1.2)))
    return {"totalToday": len(todays), "inQueue": len(in_queue), "avgWait": avg_wait, "health": health}


@router.get("/wait-series", response_model=List[schemas.WaitSeriesPoint])
def get_wait_series():
    base_hours = list(range(8, 20))
    out: List[schemas.WaitSeriesPoint] = []
    for i, h in enumerate(base_hours[:12]):
        wait = max(5, int(12 + (i / 2) + ((i % 3) * 3)))
        out.append({"time": f"{h:02d}:00", "wait": wait, "threshold": 30})
    return out


@router.get("/load-forecast", response_model=List[schemas.LoadForecastPoint])
def get_load_forecast():
    base_hours = list(range(8, 20))
    out: List[schemas.LoadForecastPoint] = []
    for i, h in enumerate(base_hours[:12]):
        peak = i in (5, 7)
        predicted = int(22 + (i % 4) * 3 + (18 if peak else 0))
        actual = int(20 + (i % 3) * 4) if i < 6 else None
        out.append({"hour": f"{h:02d}:00", "actual": actual, "predicted": predicted})
    return out
