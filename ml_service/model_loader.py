"""
model_loader.py — MLflow model loading utilities for MediFlow ML service.

Loads production-stage models from the MLflow model registry and provides
version introspection. All functions are designed to fail gracefully when
MLflow is unreachable — they log warnings and return None / "unknown" instead
of raising exceptions.
"""

import logging
import os

import mlflow
from mlflow.exceptions import MlflowException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MLflow tracking URI — configured at import time
# ---------------------------------------------------------------------------
ML_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
MLFLOW_TRACKING_URI: str = os.environ.get(
    "MLFLOW_TRACKING_URI", f"sqlite:///{ML_SERVICE_DIR}/mlflow.db"
)
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


def load_production_model(model_name: str):
    """Load a Production-stage model from the MLflow model registry.

    Args:
        model_name: The registered model name in MLflow (e.g. "wait_time_model").

    Returns:
        A ``mlflow.pyfunc.PyFuncModel`` instance, or ``None`` if the model
        could not be loaded (e.g. MLflow is unreachable or no Production
        stage model exists).
    """
    model_uri = f"models:/{model_name}/Production"
    try:
        model = mlflow.pyfunc.load_model(model_uri)
        logger.info("Loaded model '%s' from %s", model_name, model_uri)
        return model
    except (MlflowException, Exception) as exc:
        logger.warning(
            "Failed to load model '%s' from MLflow (%s): %s",
            model_name,
            MLFLOW_TRACKING_URI,
            exc,
        )
        return None


def get_current_model_version(model_name: str) -> str:
    """Query the MLflow registry for the current Production version number.

    Returns:
        The version string (e.g. ``"3"``), or ``"unknown"`` if the registry
        is unreachable or no Production model exists.
    """
    try:
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if versions:
            return versions[0].version
        logger.warning(
            "No Production version found for model '%s'", model_name
        )
        return "unknown"
    except (MlflowException, Exception) as exc:
        logger.warning(
            "Failed to query model version for '%s': %s", model_name, exc
        )
        return "unknown"
