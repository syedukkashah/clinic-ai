import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from db.session import AsyncSessionLocal
from db.models import MLPrediction, Appointment, AppointmentStatus
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.resolve_predictions.resolve_completed_appointments")
def resolve_completed_appointments():
    """
    Hourly task: fills actual_value in ml_predictions for completed appointments.
    Runs every hour via Celery beat.
    """
    return asyncio.run(run_hourly_resolution())

async def run_hourly_resolution():
    logger.info("Starting hourly prediction resolution...")
    
    async with AsyncSessionLocal() as db:
        # Find predictions that don't have an actual value yet
        stmt = select(MLPrediction).where(MLPrediction.actual_value == None)
        result = await db.execute(stmt)
        pending_preds = result.scalars().all()
        
        resolved_count = 0
        for pred in pending_preds:
            if not pred.appointment_id:
                continue
                
            # Check if appointment is completed
            appt_stmt = select(Appointment).where(Appointment.id == pred.appointment_id)
            appt_result = await db.execute(appt_stmt)
            appt = appt_result.scalar_one_or_none()
            
            if appt and appt.status == AppointmentStatus.COMPLETED and appt.actual_wait_minutes is not None:
                pred.actual_value = appt.actual_wait_minutes
                pred.resolved_at = datetime.now(timezone.utc)
                resolved_count += 1
        
        await db.commit()
        logger.info(f"Resolved {resolved_count} predictions out of {len(pending_preds)} pending.")

if __name__ == "__main__":
    asyncio.run(run_hourly_resolution())
