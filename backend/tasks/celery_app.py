import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "mediflow",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.config_from_object("celeryconfig")

# Import tasks explicitly so they register
import tasks.resolve_predictions  # noqa
import mlops.drift_detector  # noqa
import tasks.retrain_task  # noqa
import tasks.scheduling_task  # noqa
