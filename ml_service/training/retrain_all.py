import logging
from datetime import datetime
from training.train_load_forecast import train_load_forecast_model
from training.train_wait_time import train_wait_time_model

logger = logging.getLogger(__name__)

def retrain_load_forecast_model(reason: str = "scheduled") -> dict:
    """Retrains the load forecast model."""
    import mlflow
    try:
        result = train_load_forecast_model()
        if result.get("run_id"):
            client = mlflow.tracking.MlflowClient()
            client.set_tag(result["run_id"], "reason", reason)
        result["reason"] = reason
        return result
    except Exception as e:
        logger.exception(f"Failed to retrain load forecast model: {e}")
        return {"mae": float("inf"), "promoted": False, "run_id": None, "reason": reason, "error": str(e)}

def retrain_wait_time_model(reason: str = "scheduled") -> dict:
    """Retrains the wait time model."""
    import mlflow
    try:
        result = train_wait_time_model(reason=reason)
        if result.get("run_id"):
            client = mlflow.tracking.MlflowClient()
            client.set_tag(result["run_id"], "reason", reason)
        return result
    except Exception as e:
        logger.exception(f"Failed to retrain wait time model: {e}")
        return {"rmse": float("inf"), "promoted": False, "run_id": None, "reason": reason, "error": str(e)}

def retrain_models(model_name: str = "all", reason: str = "scheduled") -> dict:
    """Retrains models based on model_name and returns combined results."""
    results = {"timestamp": datetime.utcnow().isoformat()}
    
    if model_name in ["patient_load_model", "all"]:
        results["patient_load_model"] = retrain_load_forecast_model(reason=reason)
        
    if model_name in ["wait_time_model", "all"]:
        results["wait_time_model"] = retrain_wait_time_model(reason=reason)
        
    return results
