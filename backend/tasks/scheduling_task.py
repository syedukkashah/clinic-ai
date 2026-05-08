import asyncio
from celery import shared_task
from db.session import SessionLocal
from services.scheduling_agent import run_proactive_scheduling
from core.logging import get_logger

logger = get_logger(__name__)

@shared_task(name="tasks.scheduling_task.check_schedule_and_reassign")
def check_schedule_and_reassign():
    """
    Celery task to run the proactive scheduling agent.
    """
    logger.info("Celery task 'check_schedule_and_reassign' triggered.")
    db = SessionLocal()
    try:
        # Run the async function in a sync context (Celery task)
        result = asyncio.run(run_proactive_scheduling(db))
        logger.info(f"Proactive scheduling run completed with result: {result}")
    except Exception as e:
        logger.error(f"An error occurred during the scheduling task: {e}", exc_info=True)
    finally:
        db.close()
