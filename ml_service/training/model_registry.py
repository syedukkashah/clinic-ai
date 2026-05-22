import os
import logging
import sys
import types

try:
    import mlflow
except ModuleNotFoundError:  # pragma: no cover - dependency-light test/runtime fallback
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

logger = logging.getLogger(__name__)

ML_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ML_SERVICE_DIR}/mlflow.db")
LOAD_FORECAST_MODEL = "patient_load_model"

def get_production_model_mae(model_name: str) -> float:
    """Queries MLflow registry for Production stage model of given name and returns MAE."""
    try:
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if not versions:
            return float("inf")
        run = client.get_run(versions[0].run_id)
        return float(run.data.metrics.get("mae", float("inf")))
    except Exception as e:
        logger.warning(f"Could not fetch production MAE for {model_name}: {e}")
        return float("inf")


def promote_to_production(model_name: str) -> None:
    """Archives current Production versions and promotes latest 'None' stage version."""
    try:
        client = mlflow.tracking.MlflowClient()
        for v in client.get_latest_versions(model_name, stages=["Production"]):
            client.transition_model_version_stage(model_name, v.version, "Archived")
        
        candidates = client.get_latest_versions(model_name, stages=["None"])
        if candidates:
            client.transition_model_version_stage(model_name, candidates[0].version, "Production")
            logger.info(f"Promoted {model_name} v{candidates[0].version} to Production")
    except Exception as e:
        logger.warning(f"Failed to promote {model_name}: {e}")


def setup_experiment(experiment_name: str) -> None:
    """Creates MLflow experiment if it doesn't exist."""
    try:
        mlflow.get_experiment_by_name(experiment_name)
    except Exception:
        pass
    try:
        mlflow.create_experiment(experiment_name)
    except Exception:
        pass
