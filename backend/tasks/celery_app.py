import os
from celery import Celery

REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "clinic_ai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.retrain_task",
        "tasks.resolve_predictions",
        "tasks.ops_task"
    ]
)

celery_app.config_from_object("celeryconfig")
