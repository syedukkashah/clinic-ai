import pytest
from unittest.mock import MagicMock, patch
from training.model_registry import get_production_model_mae, promote_to_production

class TestMLflowRegistryLogic:

    @patch("mlflow.tracking.MlflowClient")
    def test_get_production_mae_returns_inf_if_no_version(self, mock_client_class):
        """If no production model exists, it should return infinity so any new model beats it."""
        mock_client = mock_client_class.return_value
        mock_client.get_latest_versions.return_value = []
        
        mae = get_production_model_mae("test_model")
        assert mae == float("inf")

    @patch("mlflow.tracking.MlflowClient")
    def test_get_production_mae_fetches_metric_correctly(self, mock_client_class):
        """Verify it pulls the 'mae' metric from the production run."""
        mock_client = mock_client_class.return_value
        
        # Mock version
        mock_version = MagicMock()
        mock_version.run_id = "run_123"
        mock_client.get_latest_versions.return_value = [mock_version]
        
        # Mock run data
        mock_run = MagicMock()
        mock_run.data.metrics = {"mae": 0.45}
        mock_client.get_run.return_value = mock_run
        
        mae = get_production_model_mae("test_model")
        assert mae == 0.45

    @patch("mlflow.tracking.MlflowClient")
    def test_promote_to_production_archives_old_versions(self, mock_client_class):
        """Promotion must archive existing production models first."""
        mock_client = mock_client_class.return_value
        
        # Existing production v1
        old_v = MagicMock()
        old_v.version = "1"
        mock_client.get_latest_versions.side_effect = [
            [old_v],           # First call: find current production
            [MagicMock()]      # Second call: find new candidate
        ]
        
        promote_to_production("test_model")
        
        # Verify v1 was archived
        mock_client.transition_model_version_stage.assert_any_call(
            "test_model", "1", "Archived"
        )

    @patch("mlflow.tracking.MlflowClient")
    def test_promote_to_production_successfully_promotes_newest(self, mock_client_class):
        """Verify the latest 'None' stage model becomes 'Production'."""
        mock_client = mock_client_class.return_value
        
        mock_client.get_latest_versions.side_effect = [
            [], # No current production
            [MagicMock(version="2")] # New candidate v2
        ]
        
        promote_to_production("test_model")
        
        mock_client.transition_model_version_stage.assert_called_with(
            "test_model", "2", "Production"
        )
