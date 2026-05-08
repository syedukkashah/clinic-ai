# backend/scripts/backfill_predictions.py
"""
One-time script: backfills 500 resolved predictions from synthetic data
so drift detection has enough samples on day 1 of demo.

Run from backend/ directory:
    python scripts/backfill_predictions.py
"""
import sys
import os
from pathlib import Path

# Make sure backend/ is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from core.config import settings

DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
engine = create_engine(DATABASE_URL)

TARGET_ROWS = 500
MODEL_VERSION = "v1_backfill"

MODELS = ["wait_time_model", "patient_load_model"]


def backfill_model(conn, model_name: str):
    # Check if already backfilled for this model
    existing = conn.execute(
        text("SELECT COUNT(*) FROM ml_predictions WHERE model_version = :v AND model_name = :m"),
        {"v": MODEL_VERSION, "m": model_name}
    ).scalar()

    if existing >= TARGET_ROWS:
        print(f"Already have {existing} backfilled rows for {model_name} — skipping.")
        return

    # Pull synthetic appointments that completed (have actual_start)
    rows = conn.execute(text("""
        SELECT id, doctor_id, scheduled_at, actual_start,
               EXTRACT(HOUR FROM scheduled_at) AS hour_of_day,
               EXTRACT(EPOCH FROM (actual_start - scheduled_at)) / 60 AS actual_wait
        FROM appointments
        WHERE actual_start IS NOT NULL
          AND showed_up = TRUE
        ORDER BY RANDOM()
        LIMIT :limit
    """), {"limit": TARGET_ROWS}).fetchall()

    if not rows:
        print("No completed appointments found in DB. Make sure synthetic data is loaded.")
        return

    inserted = 0
    for row in rows:
        actual_wait = float(row.actual_wait) if row.actual_wait else 15.0

        # Simulate model prediction with small realistic noise
        predicted_wait = max(0, actual_wait + np.random.normal(0, 3))

        # Spread predicted_at over last 7 days for realistic drift window
        fake_predicted_at = datetime.now() - timedelta(
            days=np.random.randint(1, 7),
            hours=np.random.randint(0, 23)
        )

        conn.execute(text("""
            INSERT INTO ml_predictions
                (model_name, model_version, appointment_id,
                 input_features, predicted_value, actual_value,
                 predicted_at, resolved_at)
            VALUES
                (:model_name, :model_version, :appt_id,
                 CAST(:features AS jsonb), :predicted, :actual,
                 :predicted_at, NOW())
        """), {
            "model_name": model_name,
            "model_version": MODEL_VERSION,
            "appt_id": row.id,
            "features": f'{{"doctor_id": {row.doctor_id}, "hour_of_day": {int(row.hour_of_day)}}}',
            "predicted": round(predicted_wait, 2),
            "actual": round(actual_wait, 2),
            "predicted_at": fake_predicted_at,
        })
        inserted += 1

    conn.commit()
    print(f"✅ Backfilled {inserted} resolved predictions for {model_name}.")


def backfill():
    with engine.connect() as conn:
        for model_name in MODELS:
            backfill_model(conn, model_name)

    print("Drift detection will now have enough data to run immediately.")


if __name__ == "__main__":
    backfill()