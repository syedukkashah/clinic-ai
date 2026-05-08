from celery.schedules import crontab

timezone = "UTC"

beat_schedule = {
    "weekly-retraining": {
        "task": "tasks.retrain_task.run_weekly_retraining",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "daily-drift-checks": {
        "task": "tasks.ops_task.run_daily_drift_checks",
        "schedule": crontab(hour=0, minute=0),
    },
    "hourly-prediction-resolution": {
        "task": "tasks.resolve_predictions.run_hourly_resolution",
        "schedule": crontab(minute=0),
    },
}
