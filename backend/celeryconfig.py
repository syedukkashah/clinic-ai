from celery.schedules import crontab

beat_schedule = {
    "check-schedule-every-30-min": {
        "task": "tasks.check_schedule_and_reassign",
        "schedule": 1800.0,
    },
    "resolve-predictions-hourly": {
        "task": "tasks.resolve_predictions.resolve_completed_appointments",
        "schedule": crontab(minute=0),
    },
    "daily-drift-check": {
        "task": "mlops.drift_detector.run_daily_drift_check",
        "schedule": crontab(hour=1, minute=0),
    },
}
broker_connection_retry_on_startup = True