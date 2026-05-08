import logging
import subprocess
import sys

from celery import shared_task

logger = logging.getLogger(__name__)

SCRIPT_MAP = {
    "wait_time_model": "training/train_wait_time.py",
    "patient_load_model": "training/train_load_forecast.py",
}


@shared_task(name="training.retrain_model", bind=True, max_retries=1)
def retrain_model(self, model_name: str, reason: str):
    script = SCRIPT_MAP.get(model_name)
    if not script:
        logger.error("Unknown model: %s", model_name)
        return {"error": f"Unknown model: {model_name}"}

    logger.info("Retraining %s — reason: %s", model_name, reason)
    try:
        result = subprocess.run(
            [sys.executable, script, "--reason", reason],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        logger.info("Retrain complete: %s", model_name)
        return {"model_name": model_name, "status": "completed"}
    except Exception as exc:
        logger.error("Retrain failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)