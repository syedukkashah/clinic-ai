# backend/tasks/resolve_predictions.py
from tasks.celery_app import celery_app 
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.resolve_predictions.resolve_completed_appointments")
def resolve_completed_appointments():
    """
    Hourly task: fills actual_value in ml_predictions for completed appointments.
    Runs every hour via Celery beat.
    """
    from db.session import SessionLocal
    db = SessionLocal()

    try:
        # --- Wait time model ---
        # actual_value = how long they actually waited (in minutes)
        wait_result = db.execute(text("""
            UPDATE ml_predictions mp
            SET actual_value = EXTRACT(EPOCH FROM (a.actual_start - a.scheduled_at)) / 60,
                resolved_at = NOW()
            FROM appointments a
            WHERE mp.appointment_id = a.id
              AND mp.model_name = 'wait_time_model'
              AND mp.actual_value IS NULL
              AND a.actual_start IS NOT NULL
              AND a.scheduled_at < NOW() - INTERVAL '1 hour'
        """))
        db.commit()
        logger.info(f"Resolved {wait_result.rowcount} wait_time_model predictions")

        # --- Patient load model ---
        # actual_value = how many patients actually showed up that hour
        load_result = db.execute(text("""
            UPDATE ml_predictions mp
            SET actual_value = (
                SELECT COUNT(*) FROM appointments a2
                WHERE a2.doctor_id = (mp.input_features->>'doctor_id')::int
                  AND DATE(a2.scheduled_at) = (mp.input_features->>'date')::date
                  AND EXTRACT(HOUR FROM a2.scheduled_at) = (mp.input_features->>'hour')::int
                  AND a2.showed_up = TRUE
            ),
            resolved_at = NOW()
            WHERE mp.model_name = 'patient_load_model'
              AND mp.actual_value IS NULL
              AND (mp.input_features->>'date')::date < CURRENT_DATE
        """))
        db.commit()
        logger.info(f"Resolved {load_result.rowcount} patient_load_model predictions")

    except Exception as e:
        db.rollback()
        logger.error(f"Resolver task failed: {e}")
        raise
    finally:
        db.close()
