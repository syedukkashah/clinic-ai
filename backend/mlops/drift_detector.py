# backend/mlops/drift_detector.py
import numpy as np
import logging
import os
from pathlib import Path
from scipy.stats import entropy
from sqlalchemy import create_engine, text
from celery import shared_task

logger = logging.getLogger(__name__)

DRIFT_THRESHOLD = 0.1
MIN_SAMPLES = 200
BASELINE_DIR = Path(__file__).parent / "baselines"
BASELINE_DIR.mkdir(exist_ok=True)

MODELS = ["wait_time_model", "patient_load_model"]


# ── Utility functions ────────────────────────────────────────────

def compute_kl_divergence(p_samples: list, q_samples: list, bins: int = 20) -> float:
    """KL divergence between two distributions of prediction values."""
    range_min = min(min(p_samples), min(q_samples))
    range_max = max(max(p_samples), max(q_samples))
    bin_range = (range_min, range_max)

    p, _ = np.histogram(p_samples, bins=bins, range=bin_range, density=True)
    q, _ = np.histogram(q_samples, bins=bins, range=bin_range, density=True)

    # Smooth to avoid log(0)
    p = p + 1e-10
    q = q + 1e-10

    return float(entropy(p, q))


def save_baseline(model_name: str, predictions: list):
    """Call once to save baseline distribution from synthetic data."""
    path = BASELINE_DIR / f"baseline_{model_name}.npy"
    np.save(str(path), np.array(predictions))
    logger.info(f"Saved baseline for {model_name}: {len(predictions)} samples → {path}")


def load_baseline(model_name: str) -> list:
    path = BASELINE_DIR / f"baseline_{model_name}.npy"
    if not path.exists():
        raise FileNotFoundError(
            f"No baseline found for {model_name}. "
            f"Run generate_baselines() first."
        )
    return np.load(str(path)).tolist()


def get_recent_predictions(model_name: str, hours: int = 24) -> list:
    """Fetch last N hours of resolved predictions for drift comparison."""
    from core.config import settings
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT predicted_value FROM ml_predictions
            WHERE model_name = :name
              AND predicted_at > NOW() - INTERVAL ':hours hours'
              AND actual_value IS NOT NULL
        """), {"name": model_name, "hours": hours}).fetchall()
    return [float(r[0]) for r in rows]


def log_drift_result(model_name: str, kl: float | None, status: str, n: int):
    """Persist drift check result for audit trail / dashboard."""
    from core.config import settings
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO drift_check_logs
                (model_name, kl_divergence, status, sample_count, checked_at)
            VALUES (:model, :kl, :status, :n, NOW())
        """), {"model": model_name, "kl": kl, "status": status, "n": n})
        conn.commit()


# ── Main drift check task ────────────────────────────────────────

@shared_task(name="mlops.drift_detector.run_daily_drift_check")
def run_daily_drift_check():
    """
    Daily task: compares recent predictions to baseline.
    Triggers retraining if KL divergence > DRIFT_THRESHOLD.
    """
    logger.info("Starting daily drift check...")

    for model_name in MODELS:
        try:
            recent_preds = get_recent_predictions(model_name, hours=24)
            n = len(recent_preds)

            if n < MIN_SAMPLES:
                logger.warning(f"{model_name}: only {n} samples — need {MIN_SAMPLES}. Skipping.")
                log_drift_result(model_name, kl=None, status="insufficient_data", n=n)
                continue

            baseline = load_baseline(model_name)
            kl = compute_kl_divergence(recent_preds, baseline)

            logger.info(f"{model_name}: KL divergence = {kl:.4f} (threshold={DRIFT_THRESHOLD})")

            if kl > DRIFT_THRESHOLD:
                logger.warning(f"{model_name}: DRIFT DETECTED (KL={kl:.4f}) — triggering retrain")
                log_drift_result(model_name, kl=kl, status="drift_detected", n=n)
                trigger_retraining.delay(model_name, reason=f"drift_kl_{kl:.4f}")
            else:
                logger.info(f"{model_name}: No drift. All good.")
                log_drift_result(model_name, kl=kl, status="ok", n=n)

        except FileNotFoundError as e:
            logger.error(str(e))
        except Exception as e:
            logger.error(f"Drift check failed for {model_name}: {e}")


@shared_task(name="mlops.drift_detector.trigger_retraining")
def trigger_retraining(model_name: str, reason: str = "manual"):
    """Stub for now — wire to your actual retrain task when MLflow is ready."""
    logger.info(f"[RETRAIN TRIGGERED] model={model_name} reason={reason}")
    # TODO: call your MLflow retrain task here once MLflow server is up
    # from tasks.retrain import retrain_model
    # retrain_model.delay(model_name)


# ── One-time baseline generation ─────────────────────────────────

def generate_baselines():
    """
    Run this ONCE after backfill to create baseline .npy files.
    Uses the backfilled synthetic predictions as ground truth baseline.
    """
    from core.config import settings
    engine = create_engine(settings.DATABASE_URL)

    for model_name in MODELS:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT predicted_value FROM ml_predictions
                WHERE model_name = :name
                  AND model_version = 'v1_backfill'
                  AND actual_value IS NOT NULL
                LIMIT 500
            """), {"name": model_name}).fetchall()

        preds = [float(r[0]) for r in rows]

        if not preds:
            logger.warning(f"No backfilled data for {model_name} — run backfill_predictions.py first")
            continue

        save_baseline(model_name, preds)
        print(f"✅ Baseline saved for {model_name} ({len(preds)} samples)")


if __name__ == "__main__":
    generate_baselines()