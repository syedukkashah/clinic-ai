from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agents import ops_agent


class _FakeIsolationForest:
    contamination = 0.05
    n_estimators = 100
    n_features_in_ = 7

    def __init__(self, score: float):
        self._score = score

    def decision_function(self, X):
        assert X.shape[1] == self.n_features_in_
        return np.array([self._score])


def test_normal_booking_window_scores_positive():
    with patch("agents.ops_agent.joblib.load", return_value=_FakeIsolationForest(0.22)):
        score = ops_agent.score_anomaly([3, 4, 3, 5, 4, 3, 4])
    assert score > -0.3


def test_anomalous_booking_spike_scores_negative():
    with patch("agents.ops_agent.joblib.load", return_value=_FakeIsolationForest(-0.74)):
        score = ops_agent.score_anomaly([4, 3, 5, 18, 22, 31, 28])
    assert score < -0.3


def test_anomaly_score_updates_prometheus_gauge():
    with patch("agents.ops_agent.joblib.load", return_value=_FakeIsolationForest(-0.41)):
        score = ops_agent.score_anomaly([4, 3, 5, 18, 22, 31, 28])
    samples = list(ops_agent.PROM_ANOMALY_SCORE.collect())[0].samples
    assert any(sample.name == "mediflow_anomaly_score" and sample.value == pytest.approx(score) for sample in samples)


def test_score_pads_short_vectors_to_model_width():
    model = MagicMock()
    model.n_features_in_ = 7
    model.decision_function.side_effect = [
        ValueError("wrong width"),
        np.array([0.12]),
    ]
    with patch("agents.ops_agent.joblib.load", return_value=model):
        score = ops_agent.score_anomaly([3, 4, 5])
    assert score == pytest.approx(0.12)
    assert model.decision_function.call_count == 2
    assert model.decision_function.call_args.args[0].shape == (1, 7)


def test_isolation_forest_model_parameters_are_guarded():
    model = _FakeIsolationForest(0.0)
    assert model.contamination == 0.05
    assert model.n_estimators == 100
