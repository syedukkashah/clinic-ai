import asyncio
import logging
import httpx
import os

logger = logging.getLogger(__name__)

from tasks.celery_app import celery_app

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "mediflow-internal-secret")

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
                timeout=300.0 # Retraining can take time
            )
            
            if response.status_code == 200:
                logger.info("Retraining triggered successfully.")
                logger.info(f"Results: {response.json()}")
            else:
                logger.error(f"Failed to trigger retraining: {response.status_code} - {response.text}")
                
    except Exception as e:
        logger.error(f"Error during retraining task: {e}")

if __name__ == "__main__":
    asyncio.run(run_weekly_retraining())
