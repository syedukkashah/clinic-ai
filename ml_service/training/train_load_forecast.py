import os
import json
import logging
from datetime import datetime
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import mlflow
import mlflow.xgboost

# Make sure imports resolve if run as module
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_features import load_daily_load_csv
from training.model_registry import (
    get_production_model_mae,
    promote_to_production,
    setup_experiment,
    LOAD_FORECAST_MODEL,
    MLFLOW_TRACKING_URI
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

def train_load_forecast_model(data_path: str = "data/daily_load.csv") -> dict:
    """Trains the XGBoost model for patient load forecasting with hyperparameter tuning."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    setup_experiment("load_forecast_training")
    mlflow.set_experiment("load_forecast_training")
    
    # a. Load data
    logger.info("Loading and generating dense feature grid...")
    features_df = load_daily_load_csv(data_path)
    
    if features_df.empty:
        logger.error("No features generated. Check data.")
        return {"mae": float("inf"), "promoted": False, "run_id": None}
    
    # b. TIME-BASED SPLIT
    sorted_dates = sorted(features_df["scheduled_date"].unique())
    split_date = sorted_dates[int(len(sorted_dates) * 0.85)]
    
    # c. One-hot encode first on combined dataframe
    encoded_df = pd.get_dummies(features_df, columns=["doctor_id", "specialty", "season"], drop_first=False)
    
    # Now split
    train = encoded_df[encoded_df["scheduled_date"] < split_date]
    val = encoded_df[encoded_df["scheduled_date"] >= split_date]
    
    # Drop scheduled_date
    X_train = train.drop(columns=["scheduled_date", "patient_count"])
    y_train = train["patient_count"]
    X_val = val.drop(columns=["scheduled_date", "patient_count"])
    y_val = val["patient_count"]
    
    trained_columns = list(X_train.columns)
    
    os.makedirs("mlops/baselines", exist_ok=True)
    np.save("mlops/baselines/load_forecast_trained_columns.npy", np.array(trained_columns))
    
    # d. BASELINE RUNS
    with mlflow.start_run(run_name="baselines") as baseline_run:
        train_unencoded = features_df[features_df["scheduled_date"] < split_date]
        val_unencoded = features_df[features_df["scheduled_date"] >= split_date]
        
        # 1. Group mean baseline
        baseline_means = train_unencoded.groupby(["doctor_id", "day_of_week", "hour_of_day"])["patient_count"].mean().reset_index()
        baseline_means.rename(columns={"patient_count": "mean_pred"}, inplace=True)
        
        val_with_baseline = val_unencoded.merge(baseline_means, on=["doctor_id", "day_of_week", "hour_of_day"], how="left")
        val_with_baseline["mean_pred"] = val_with_baseline["mean_pred"].fillna(train_unencoded["patient_count"].mean())
        
        mean_baseline_mae = mean_absolute_error(val_unencoded["patient_count"], val_with_baseline["mean_pred"])
        
        # 2. Seasonal lag baseline (last week same slot)
        val_with_baseline["lag_pred"] = val_with_baseline["lag_1w"].fillna(val_with_baseline["mean_pred"])
        
        lag_baseline_mae = mean_absolute_error(val_unencoded["patient_count"], val_with_baseline["lag_pred"])
        
        mlflow.set_tag("model_type", "baseline")
        mlflow.log_metrics({
            "mean_baseline_mae": mean_baseline_mae,
            "lag_baseline_mae": lag_baseline_mae
        })
        logger.info(f"Group Mean Baseline MAE: {mean_baseline_mae:.3f}")
        logger.info(f"Seasonal Lag Baseline MAE: {lag_baseline_mae:.3f}")
        
        baseline_mae = min(mean_baseline_mae, lag_baseline_mae)

    # e. XGBOOST RUN with Simple Grid Search (proven effective neighborhood)
    with mlflow.start_run(run_name="xgboost_load_forecast_final") as active_run:
        param_grid = {
            'max_depth': [3, 5, 7],
            'learning_rate': [0.01, 0.05, 0.1],
            'n_estimators': [200, 400],
            'subsample': [0.8, 1.0],
            'colsample_bytree': [0.8, 1.0]
        }
        
        logger.info("Starting final grid search...")
        xgb_model = xgb.XGBRegressor(objective="count:poisson", random_state=42)
        
        tscv = TimeSeriesSplit(n_splits=3)
        
        grid_search = GridSearchCV(
            estimator=xgb_model,
            param_grid=param_grid,
            cv=tscv,
            scoring='neg_mean_poisson_deviance',
            verbose=1,
            n_jobs=-1
        )
        
        grid_search.fit(X_train, y_train)
        
        best_params = grid_search.best_params_
        model = grid_search.best_estimator_
        
        logger.info(f"Best parameters: {best_params}")
        
        val_predictions = model.predict(X_val).clip(0)
        
        mae = mean_absolute_error(y_val, val_predictions)
        rmse = np.sqrt(mean_squared_error(y_val, val_predictions))
        improvement_pct = (baseline_mae - mae) / baseline_mae * 100
        
        mlflow.log_params(best_params)
        mlflow.log_metrics({
            "mae": mae,
            "rmse": rmse,
            "improvement_over_baseline_pct": improvement_pct,
            "train_rows": len(X_train),
            "val_rows": len(X_val)
        })
        mlflow.log_param("split_date", split_date)
        mlflow.set_tag("model_type", "xgboost_load_forecast_final")
        
        importances = {k: float(v) for k, v in zip(X_train.columns, model.feature_importances_)}
        top_features = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True)[:15])
        mlflow.log_dict(top_features, "feature_importance.json")
        
        # f. Register model
        mlflow.xgboost.log_model(
            model, "model",
            registered_model_name=LOAD_FORECAST_MODEL
        )
        
        # g. Champion/challenger
        current_mae = get_production_model_mae(LOAD_FORECAST_MODEL)
        if mae < current_mae:
            promote_to_production(LOAD_FORECAST_MODEL)
            promoted = True
            print(f"New champion promoted. MAE={mae:.3f} beats {current_mae:.3f}")
        else:
            promoted = False
            print(f"Challenger lost. MAE={mae:.3f} did not beat {current_mae:.3f}")
            
        # h. ALWAYS save drift baseline
        np.save(f"mlops/baselines/{LOAD_FORECAST_MODEL}_baseline.npy", val_predictions)
        stats = {
            "mean": float(val_predictions.mean()),
            "std": float(val_predictions.std()),
            "p10": float(np.percentile(val_predictions, 10)),
            "p50": float(np.percentile(val_predictions, 50)),
            "p90": float(np.percentile(val_predictions, 90)),
            "n_samples": len(val_predictions),
            "saved_at": datetime.utcnow().isoformat()
        }
        with open(f"mlops/baselines/{LOAD_FORECAST_MODEL}_stats.json", "w") as f:
            json.dump(stats, f)
            
        return {"mae": mae, "promoted": promoted, "run_id": active_run.info.run_id}

if __name__ == "__main__":
    result = train_load_forecast_model()
    print(result)
