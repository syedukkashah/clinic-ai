from celery import Celery
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "mediflow",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.config_from_object("celeryconfig")

# Import tasks explicitly so they register
import tasks.resolve_predictions  # noqa
import mlops.drift_detector  # noqa