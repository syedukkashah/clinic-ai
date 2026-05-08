import os
import json
import numpy as np
import scipy.stats
import logging

logger = logging.getLogger(__name__)

DRIFT_THRESHOLD = 0.1
MIN_SAMPLES = 200

def save_drift_baseline(model_name: str, predictions: np.ndarray) -> None:
    """Saves predictions and stats for M6 drift detection."""
    os.makedirs("mlops/baselines", exist_ok=True)
    np.save(f"mlops/baselines/{model_name}_baseline.npy", predictions)
    
    from datetime import datetime
    stats = {
        "mean": float(predictions.mean()),
        "std": float(predictions.std()),
        "p10": float(np.percentile(predictions, 10)),
        "p50": float(np.percentile(predictions, 50)),
        "p90": float(np.percentile(predictions, 90)),
        "n_samples": len(predictions),
        "saved_at": datetime.utcnow().isoformat()
    }
    with open(f"mlops/baselines/{model_name}_stats.json", "w") as f:
        json.dump(stats, f)

def load_baseline_distribution(model_name: str) -> np.ndarray:
    """Loads baseline numpy array. Raises FileNotFoundError if missing."""
    path = f"mlops/baselines/{model_name}_baseline.npy"
    if not os.path.exists(path):
        raise FileNotFoundError(f"Baseline distribution file missing at {path}")
    return np.load(path)

def load_baseline_stats(model_name: str) -> dict:
    """Loads baseline stats. Returns empty dict if missing."""
    path = f"mlops/baselines/{model_name}_stats.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def compute_kl_divergence(p_samples: np.ndarray, q_samples: np.ndarray, bins: int = 20) -> float:
    """Computes KL divergence between two sets of samples."""
    min_val = min(p_samples.min(), q_samples.min())
    max_val = max(p_samples.max(), q_samples.max())
    
    # Compute bin edges covering range of BOTH arrays combined
    edges = np.linspace(min_val, max_val, bins + 1)
    
    # Histogram both arrays using same edges, density=True
    p_hist, _ = np.histogram(p_samples, bins=edges, density=True)
    q_hist, _ = np.histogram(q_samples, bins=edges, density=True)
    
    # Add epsilon to both
    epsilon = 1e-10
    p_hist = p_hist + epsilon
    q_hist = q_hist + epsilon
    
    # Normalize again to ensure they sum to 1
    p_hist = p_hist / p_hist.sum()
    q_hist = q_hist / q_hist.sum()
    
    return float(scipy.stats.entropy(p_hist, q_hist))
