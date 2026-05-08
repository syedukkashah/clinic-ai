import asyncio
import logging
import os
import httpx
from celery import shared_task
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml_service:8001")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "mediflow-internal-secret")

@shared_task(name="tasks.retrain_task.retrain_model", bind=True, max_retries=1)
def retrain_model(self, model_name: str, reason: str):
    """Trigger retraining of a specific model via the ML Service API."""
    logger.info("Retraining %s — reason: %s", model_name, reason)
    try:
        response = httpx.post(
            f"{ML_SERVICE_URL}/retrain",
            headers={"X-Internal-Secret": INTERNAL_SECRET},
            json={"model_name": model_name, "reason": reason},
            timeout=600.0,
        )
        if response.status_code == 200:
            logger.info("Retrain complete for %s: %s", model_name, response.json())
            return {"model_name": model_name, "status": "completed", "reason": reason}
        else:
            raise RuntimeError(f"ML service returned {response.status_code}: {response.text}")
    except Exception as exc:
        logger.error("Retrain failed for %s: %s", model_name, exc)
        raise self.retry(exc=exc, countdown=300)

@celery_app.task(name="tasks.retrain_task.run_weekly_retraining")
def run_weekly_retraining_task(model_name: str = "all"):
    """Periodically called by Celery Beat to refresh models."""
    asyncio.run(run_weekly_retraining(model_name=model_name))

async def run_weekly_retraining(model_name: str = "all"):
    logger.info(f"Starting weekly model retraining for {model_name}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/retrain",
                headers={"X-Internal-Secret": INTERNAL_SECRET},
                json={"model_name": model_name, "reason": "scheduled_weekly"},
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
