# backend/tasks/celery_app.py
from celery import Celery
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "mediflow",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.scheduling_task",
        "tasks.resolve_predictions",
        "mlops.drift_detector",
    ]
)

celery_app.config_from_object("celeryconfig")