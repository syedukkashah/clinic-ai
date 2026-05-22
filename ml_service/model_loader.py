"""
model_loader.py — MLflow model loading utilities for MediFlow ML service.

Loads production-stage models from the MLflow model registry and provides
version introspection. All functions are designed to fail gracefully when
MLflow is unreachable — they log warnings and return None / "unknown" instead
of raising exceptions.
"""

import logging
import os
import sys
import types

try:
    import mlflow
    from mlflow.exceptions import MlflowException
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light CI
    class _StubRun:
        info = types.SimpleNamespace(run_id="stub-run")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mlflow = types.ModuleType("mlflow")
    tracking = types.ModuleType("mlflow.tracking")
    sklearn = types.ModuleType("mlflow.sklearn")
    pyfunc = types.ModuleType("mlflow.pyfunc")
    tracking.MlflowClient = lambda *args, **kwargs: None
    sklearn.log_model = lambda *args, **kwargs: None
    sklearn.load_model = lambda *args, **kwargs: None
    pyfunc.load_model = lambda *args, **kwargs: None
    mlflow.tracking = tracking
    mlflow.sklearn = sklearn
    mlflow.pyfunc = pyfunc
    mlflow.set_tracking_uri = lambda *args, **kwargs: None
    mlflow.set_experiment = lambda *args, **kwargs: None
    mlflow.get_experiment_by_name = lambda *args, **kwargs: None
    mlflow.create_experiment = lambda *args, **kwargs: None
    mlflow.log_params = lambda *args, **kwargs: None
    mlflow.log_metrics = lambda *args, **kwargs: None
    mlflow.log_metric = lambda *args, **kwargs: None
    mlflow.log_param = lambda *args, **kwargs: None
    mlflow.log_dict = lambda *args, **kwargs: None
    mlflow.set_tag = lambda *args, **kwargs: None
    mlflow.active_run = lambda: None
    mlflow.start_run = lambda *args, **kwargs: _StubRun()
    sys.modules.setdefault("mlflow", mlflow)
    sys.modules.setdefault("mlflow.tracking", tracking)
    sys.modules.setdefault("mlflow.sklearn", sklearn)
    sys.modules.setdefault("mlflow.pyfunc", pyfunc)
    MlflowException = Exception

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
    if mlflow is None:
        logger.warning("MLflow is not installed; model version for '%s' is unknown", model_name)
        return "unknown"

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
