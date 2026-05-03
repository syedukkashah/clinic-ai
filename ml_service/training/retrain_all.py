import logging
from datetime import datetime
from training.train_load_forecast import train_load_forecast_model

logger = logging.getLogger(__name__)

def retrain_load_forecast_model(reason: str = "scheduled") -> dict:
    """Retrains the load forecast model."""
    import mlflow
    try:
        # train_load_forecast_model creates its own run, so we don't start one here,
        # but the prompt says: "Logs reason as MLflow run tag"
        # We can pass reason to the function or let it add it.
        # Wait, if we set the tag after it runs, we need the run_id.
        result = train_load_forecast_model()
        if result.get("run_id"):
            client = mlflow.tracking.MlflowClient()
            client.set_tag(result["run_id"], "reason", reason)
        result["reason"] = reason
        return result
    except Exception as e:
        logger.exception(f"Failed to retrain load forecast model: {e}")
        return {"mae": float("inf"), "promoted": False, "run_id": None, "reason": reason, "error": str(e)}

def retrain_all_models() -> dict:
    """Retrains all models and returns combined results."""
    # Note: If there were other models like wait_time, we'd call them here too.
    # We'll just call load_forecast as requested.
    load_forecast_res = retrain_load_forecast_model(reason="scheduled")
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "load_forecast": load_forecast_res
    }
