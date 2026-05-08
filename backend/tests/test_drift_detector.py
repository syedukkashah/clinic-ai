import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from mlops.drift_detector import _calculate_kl_divergence, _check_model_drift

class TestDriftDetectionLogic:

    def test_kl_divergence_identical_distributions(self):
        """KL Divergence between identical distributions should be zero."""
        p = np.array([0.1, 0.2, 0.7, 0.5])
        q = np.array([0.1, 0.2, 0.7, 0.5])
        kl = _calculate_kl_divergence(p, q)
        assert kl == pytest.approx(0.0, abs=1e-5)

    def test_kl_divergence_shifted_distribution(self):
        """KL Divergence should be positive for shifted distributions."""
        p = np.array([1, 2, 3, 4, 5])
        q = np.array([10, 20, 30, 40, 50])
        kl = _calculate_kl_divergence(p, q)
        assert kl > 0.5  # Significant shift

    @pytest.mark.asyncio
    @patch("mlops.drift_detector._load_baseline")
    @patch("mlops.drift_detector._get_recent_predictions")
    async def test_check_drift_insufficient_samples(self, mock_get_preds, mock_load_baseline):
        """Should skip check if we don't have enough live samples."""
        mock_load_baseline.return_value = np.array([1, 2, 3])
        mock_get_preds.return_value = np.array([1.0] * 50)  # Only 50 samples
        
        result = await _check_model_drift("wait_time_model")
        
        assert result["status"] == "insufficient_data"
        assert result["sample_count"] == 50

    @pytest.mark.asyncio
    @patch("mlops.drift_detector._load_baseline")
    @patch("mlops.drift_detector._get_recent_predictions")
    @patch("mlops.drift_detector._trigger_retraining")
    @patch("mlops.drift_detector._create_drift_alert")
    async def test_check_drift_triggers_retraining_on_high_kl(self, 
        mock_alert, mock_retrain, mock_get_preds, mock_load_baseline):
        """When KL Divergence > 0.1, it must trigger retraining and create an alert."""
        
        # Reference distribution
        mock_load_baseline.return_value = np.array([10, 11, 12, 13, 14] * 100) 
        # Live distribution (heavily shifted)
        mock_get_preds.return_value = np.array([100.0] * 300) 
        
        result = await _check_model_drift("wait_time_model")
        
        assert result["status"] == "drift_detected"
        assert result["action"] == "retrain_triggered"
        assert mock_retrain.called
        assert mock_alert.called

    @pytest.mark.asyncio
    @patch("mlops.drift_detector._load_baseline")
    async def test_check_drift_missing_baseline_file(self, mock_load_baseline):
        """Should handle missing .npy baseline files gracefully."""
        mock_load_baseline.return_value = None
        
        result = await _check_model_drift("wait_time_model")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "no_baseline_file"
