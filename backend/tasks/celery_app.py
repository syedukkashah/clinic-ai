import logging

from celery import Celery
from celery.schedules import crontab

from core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "mediflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.ops_task",
        "tasks.retrain_task",
        "tasks.scheduling_task",
        "tasks.resolve_predictions",
        "mlops.drift_detector",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Karachi",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "ops-monitor-check": {
        "task": "ops.run_scheduled_check",
        "schedule": crontab(minute="*/10"),
    },
    "weekly-retrain-wait-time": {
        "task": "training.retrain_model",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
        "kwargs": {"model_name": "wait_time_model", "reason": "scheduled_weekly"},
    },
    "weekly-retrain-load": {
        "task": "training.retrain_model",
        "schedule": crontab(hour=2, minute=30, day_of_week=0),
        "kwargs": {"model_name": "patient_load_model", "reason": "scheduled_weekly"},
    },
    "daily-drift-check": {
        "task": "mlops.drift_detector.run_daily_drift_check",
        "schedule": crontab(hour=3, minute=0),
    },
    "hourly-resolve-predictions": {
        "task": "tasks.resolve_predictions.run_hourly_resolution",
        "schedule": crontab(minute=0),
    },
}

