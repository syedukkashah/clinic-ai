import asyncio
from backend.tasks.celery_app import celery_app
from backend.db.session import SessionLocal
from backend.services.scheduling_agent import run_proactive_scheduling
from backend.core.logging import get_logger

logger = get_logger(__name__)

@celery_app.task(name="tasks.check_schedule_and_reassign")
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

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Sets up the periodic task to run every 30 minutes.
    """
    sender.add_periodic_task(
        1800.0,  # 30 minutes in seconds
        check_schedule_and_reassign.s(),
        name='check schedule every 30 minutes'
    )
