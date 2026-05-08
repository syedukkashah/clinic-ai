# backend/tests/test_drift_detector.py
import pytest
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Import the functions we want to test ─────────────────────────
from mlops.drift_detector import (
    compute_kl_divergence,
    save_baseline,
    load_baseline,
    DRIFT_THRESHOLD,
    MIN_SAMPLES,
)


# ── KL Divergence tests ───────────────────────────────────────────

def test_kl_divergence_identical_distributions():
    """Same distribution → KL should be near 0."""
    samples = list(np.random.normal(10, 2, 300))
    kl = compute_kl_divergence(samples, samples)
    assert kl < 0.01, f"Identical distributions should have KL ≈ 0, got {kl}"


def test_kl_divergence_different_distributions():
    """Very different distributions → KL should exceed drift threshold."""
    baseline = list(np.random.normal(10, 1, 300))   # mean=10
    drifted  = list(np.random.normal(40, 1, 300))   # mean=40 — clearly drifted
    kl = compute_kl_divergence(drifted, baseline)
    assert kl > DRIFT_THRESHOLD, f"Drifted distributions should exceed threshold, got {kl}"


def test_kl_divergence_returns_float():
    p = list(np.random.normal(5, 1, 100))
    q = list(np.random.normal(6, 1, 100))
    result = compute_kl_divergence(p, q)
    assert isinstance(result, float)


def test_kl_divergence_is_non_negative():
    p = list(np.random.normal(5, 2, 200))
    q = list(np.random.normal(7, 2, 200))
    assert compute_kl_divergence(p, q) >= 0


def test_kl_divergence_slight_shift_below_threshold():
    """Distributions with same mean and std should have near-zero KL."""
    np.random.seed(42)
    base = list(np.random.normal(15, 2, 500))
    same = list(np.random.normal(15, 2, 500))
    kl = compute_kl_divergence(same, base)
    assert kl < DRIFT_THRESHOLD, f"Same distribution params should be below threshold, got {kl}"


# ── Baseline save/load tests ──────────────────────────────────────

def test_save_and_load_baseline():
    """Save a baseline and load it back — values should match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mlops.drift_detector.BASELINE_DIR", Path(tmpdir)):
            predictions = list(np.random.normal(10, 2, 200))
            save_baseline("test_model", predictions)
            loaded = load_baseline("test_model")
            assert len(loaded) == len(predictions)
            assert abs(np.mean(loaded) - np.mean(predictions)) < 0.001


def test_load_baseline_missing_raises():
    """Loading a non-existent baseline should raise FileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("mlops.drift_detector.BASELINE_DIR", Path(tmpdir)):
            with pytest.raises(FileNotFoundError):
                load_baseline("nonexistent_model")


def test_save_baseline_creates_npy_file():
    """save_baseline should create a .npy file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        with patch("mlops.drift_detector.BASELINE_DIR", tmppath):
            save_baseline("wait_time_model", [1.0, 2.0, 3.0])
            assert (tmppath / "baseline_wait_time_model.npy").exists()


# ── Constants sanity checks ───────────────────────────────────────

def test_drift_threshold_value():
    assert DRIFT_THRESHOLD == 0.1


def test_min_samples_value():
    assert MIN_SAMPLES == 200