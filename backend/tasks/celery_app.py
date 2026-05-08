import logging

from celery import Celery

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

celery_app.config_from_object("celeryconfig")

# Import task modules explicitly so @shared_task registration is guaranteed.
import mlops.drift_detector  # noqa: E402,F401
import tasks.ops_task  # noqa: E402,F401
import tasks.resolve_predictions  # noqa: E402,F401
import tasks.retrain_task  # noqa: E402,F401
import tasks.scheduling_task  # noqa: E402,F401
