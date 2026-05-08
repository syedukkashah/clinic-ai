from celery.schedules import crontab

timezone = "UTC"

beat_schedule = {
    "weekly-retrain-wait-time": {
        "task": "tasks.retrain_task.run_weekly_retraining",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
        "kwargs": {"model_name": "wait_time_model"}
    },
    "weekly-retrain-patient-load": {
        "task": "tasks.retrain_task.run_weekly_retraining",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
        "kwargs": {"model_name": "patient_load_model"}
    },
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
