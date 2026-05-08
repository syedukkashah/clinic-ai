"""
drift_detector.py — Daily drift detection for MediFlow ML models.

Celery beat calls: mlops.drift_detector.run_daily_drift_check

Compares recent resolved predictions against baseline distributions
using KL divergence. Triggers retraining when drift exceeds threshold.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select

from db.models import MLPrediction
from db.session import AsyncSessionLocal
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DRIFT_THRESHOLD = 0.1       # KL divergence threshold to trigger retraining
MIN_SAMPLES = 200           # Minimum resolved predictions needed to run check
LOOKBACK_DAYS = 7           # How far back to look for resolved predictions
MODELS_TO_CHECK = ["wait_time_model", "patient_load_model"]


# ---------------------------------------------------------------------------
# Statistical Logic
# ---------------------------------------------------------------------------
def _calculate_kl_divergence(p_samples: np.ndarray, q_samples: np.ndarray, bins: int = 20) -> float:
    """KL(P || Q) where P=baseline, Q=recent."""
    import scipy.stats

    min_val = min(p_samples.min(), q_samples.min())
    max_val = max(p_samples.max(), q_samples.max())
    edges = np.linspace(min_val, max_val, bins + 1)

    p_hist, _ = np.histogram(p_samples, bins=edges, density=True)
    q_hist, _ = np.histogram(q_samples, bins=edges, density=True)

    epsilon = 1e-10
    p_hist = p_hist + epsilon
    q_hist = q_hist + epsilon
    p_hist = p_hist / p_hist.sum()
    q_hist = q_hist / q_hist.sum()

    return float(scipy.stats.entropy(p_hist, q_hist))


# ---------------------------------------------------------------------------
# Data Fetching (Extracted for Mocking in Tests)
# ---------------------------------------------------------------------------
def _load_baseline(model_name: str) -> np.ndarray | None:
    """Load the baseline prediction distribution saved during training."""
    candidates = [
        f"mlops/baselines/{model_name}_baseline.npy",
        f"../ml_service/mlops/baselines/{model_name}_baseline.npy",
        f"/ml_service/data/{model_name}_baseline.npy",
    ]
    if model_name == "wait_time_model":
        candidates.insert(0, "mlops/baselines/wait_time_baseline_dist.npy")

    for path in candidates:
        if os.path.exists(path):
            return np.load(path, allow_pickle=True)
    return None


async def _get_recent_predictions(model_name: str) -> np.ndarray:
    """Fetch resolved predictions from DB for the lookback window."""
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(MLPrediction.predicted_value)
            .where(
                MLPrediction.model_name == model_name,
                MLPrediction.actual_value.isnot(None),
                MLPrediction.predicted_at >= since,
            )
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
    return np.array(rows, dtype=float)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def _trigger_retraining(model_name: str):
    """Trigger retraining via Celery task."""
    try:
        from tasks.retrain_task import retrain_model
        retrain_model.delay(model_name=model_name, reason="drift_detected")
        return True
    except Exception as e:
        logger.error(f"Failed to enqueue retraining for {model_name}: {e}")
        return False


async def _create_drift_alert(model_name: str, kl_div: float, sample_count: int):
    """Create ops alert in the database."""
    try:
        from db import crud
        async with AsyncSessionLocal() as db:
            await crud.create_ops_alert(db, {
                "severity": "Medium",
                "title": f"ML Model Drift: {model_name}",
                "reasoning": f"KL divergence = {kl_div:.4f} exceeds threshold {DRIFT_THRESHOLD}.",
                "type": "drift",
                "trace": [f"kl_div={kl_div:.4f}", f"samples={sample_count}"],
                "recommendedActions": [{"kind": "trigger_retraining", "model": model_name}],
            })
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to create drift alert for {model_name}: {e}")


async def _check_model_drift(model_name: str) -> dict:
    baseline = _load_baseline(model_name)
    if baseline is None:
        return {"model_name": model_name, "status": "skipped", "reason": "no_baseline_file"}

    recent = await _get_recent_predictions(model_name)
    sample_count = len(recent)

    if sample_count < MIN_SAMPLES:
        return {
            "model_name": model_name,
            "status": "insufficient_data",
            "sample_count": sample_count,
            "action": "none"
        }

    kl_div = _calculate_kl_divergence(baseline, recent)
    status = "ok"
    action = "none"

    if kl_div > DRIFT_THRESHOLD:
        status = "drift_detected"
        action = "retrain_triggered"
        await _trigger_retraining(model_name)
        await _create_drift_alert(model_name, kl_div, sample_count)

    return {
        "model_name": model_name,
        "status": status,
        "kl_divergence": round(kl_div, 6),
        "sample_count": sample_count,
        "action": action,
    }


@celery_app.task(name="mlops.drift_detector.run_daily_drift_check")
def run_daily_drift_check():
    return asyncio.run(_run_all_drift_checks())


async def _run_all_drift_checks() -> list[dict]:
    results = []
    for model_name in MODELS_TO_CHECK:
        try:
            result = await _check_model_drift(model_name)
            results.append(result)
        except Exception as e:
            logger.exception(f"Drift check failed for {model_name}: {e}")
            results.append({"model_name": model_name, "status": "error", "reason": str(e)})
    return results

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(asyncio.run(_run_all_drift_checks()), indent=2))
