import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from db.session import AsyncSessionLocal
from db.models import MLPrediction, OpsAlert
from db import crud
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.ops_task.run_daily_drift_checks")
def run_daily_drift_checks_task():
    asyncio.run(run_daily_drift_checks())

async def run_daily_drift_checks():
    """
    Calculates model drift (Mean Absolute Error) for the last 24 hours.
    If drift is high, creates an operational alert.
    """
    logger.info("Starting daily model drift checks...")
    
    async with AsyncSessionLocal() as db:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Calculate MAE for wait_time_model
        stmt = select(
            func.avg(func.abs(MLPrediction.predicted_value - MLPrediction.actual_value))
        ).where(
            MLPrediction.model_name == "wait_time_model",
            MLPrediction.actual_value != None,
            MLPrediction.predicted_at >= yesterday
        )
        
        result = await db.execute(stmt)
        mae = result.scalar()
        
        if mae is not None and mae > 10.0: # 10 minute threshold
            logger.warning(f"High drift detected for wait_time_model: MAE={mae:.2f}")
            
            await crud.create_ops_alert(db, {
                "severity": "Medium",
                "title": "ML Model Drift Detected",
                "reasoning": f"Wait time model MAE is {mae:.2f} mins (threshold: 10.0).",
                "type": "drift",
                "trace": [f"mae={mae:.2f}", "threshold=10.0"],
                "recommendedActions": [{"kind": "trigger_retraining", "model": "wait_time_model"}]
            })
            await db.commit()
            
    logger.info("Drift checks completed.")

if __name__ == "__main__":
    asyncio.run(run_daily_drift_checks())
