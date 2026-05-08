import asyncio
import logging
import subprocess
import sys
import httpx
import os

from celery import shared_task
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml_service:8001")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "mediflow-internal-secret")

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


@celery_app.task(name="tasks.retrain_task.run_weekly_retraining")
def run_weekly_retraining_task(model_name: str = "all"):
    asyncio.run(run_weekly_retraining(model_name=model_name))

async def run_weekly_retraining(model_name: str = "all"):
    """
    Triggers the ML Service to retrain its models and reload them.
    Called periodically by Celery Beat.
    """
    logger.info(f"Starting weekly model retraining for {model_name}...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/retrain",
                headers={"X-Internal-Secret": INTERNAL_SECRET},
                json={"model_name": model_name, "reason": "scheduled"},
                timeout=300.0,
            )
            if response.status_code == 200:
                logger.info("Retraining triggered successfully: %s", response.json())
            else:
                logger.error("Failed to trigger retraining: %s - %s",
                             response.status_code, response.text)
    except Exception as exc:
        logger.error("Error during retraining task: %s", exc)


if __name__ == "__main__":
    asyncio.run(run_weekly_retraining())
