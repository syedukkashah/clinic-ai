"""
MediFlow — Wait Time Prediction Model (ML Model 1)
Multi-model comparison with MLflow champion/challenger promotion.

File location:  ml_service/training/train_wait_time.py
CSV location:   ml_service/data/appointments.csv

Run from inside ml_service/:
    python -m training.train_wait_time

Why multiple models?
    - Ridge Regression: fast baseline, interpretable, shows linear relationships
    - Random Forest:    handles non-linearity, robust, good out-of-box performance
    - XGBoost:         best accuracy, industry standard for tabular data (spec requirement)
    The champion/challenger system picks the best automatically.

Why NO PCA?
    - Only 19 features — PCA is for 100s of correlated features
    - XGBoost handles correlated features natively
    - PCA destroys interpretability (we need to say "queue_depth drives wait time")
    - Spec explicitly requires feature importance logging — impossible after PCA

What this produces (all inside ml_service/data/):
    - MLflow experiment: "wait_time_model_training" with all 3 model runs
    - Registered model:  "wait_time_model" — best model auto-promoted to Production
    - wait_time_baseline_dist.npy   -> M6 for drift detection
    - wait_time_features.json       -> M4 for /predict/wait-time endpoint
    - wait_time_label_encoders.pkl  -> M4 for inference encoding
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
TRAINING_DIR   = os.path.dirname(os.path.abspath(__file__))  # ml_service/training/
ML_SERVICE_DIR = os.path.dirname(TRAINING_DIR)               # ml_service/
DATA_DIR       = os.path.join(ML_SERVICE_DIR, "data")        # ml_service/data/
CSV_PATH       = os.path.join(DATA_DIR, "appointments.csv")

# ── MLflow ─────────────────────────────────────────────────────────────────────
import warnings
import logging as _logging
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

# Suppress MLflow deprecation noise and pickle warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="mlflow")
warnings.filterwarnings("ignore", message=".*pickle.*", module="mlflow")
_logging.getLogger("mlflow").setLevel(_logging.ERROR)

MLFLOW_URI      = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ML_SERVICE_DIR}/mlflow.db")
MODEL_NAME      = "wait_time_model"
EXPERIMENT_NAME = "wait_time_model_training"

mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment(EXPERIMENT_NAME)

# ── Features ───────────────────────────────────────────────────────────────────
NUMERIC_FEATURES = [
    "patient_age", "doctor_id", "day_of_week", "hour_of_day",
    "booking_lead_days", "appointments_before", "queue_depth",
    "avg_consult_duration", "historical_wait_slot", "week_of_year",
]
BOOL_FEATURES = [
    "is_follow_up", "is_holiday", "is_ramadan", "is_day_after_holiday",
]
CATEGORICAL_FEATURES = [
    "specialty", "urgency", "season", "patient_preferred_lang", "booking_channel",
]
TARGET = "actual_wait_minutes"

# ── Model definitions ──────────────────────────────────────────────────────────
# Three models trained and compared. Best val RMSE wins and gets promoted.
def get_models():
    models = {
        "ridge_regression": {
            "model": Ridge(alpha=1.0),
            "params": {"model_type": "Ridge", "alpha": 1.0},
            "note": "Linear baseline — fast, interpretable, shows if relationship is linear",
        },
        "random_forest": {
            "model": RandomForestRegressor(
                n_estimators=200, max_depth=12,
                min_samples_leaf=5, random_state=42, n_jobs=-1
            ),
            "params": {"model_type": "RandomForest", "n_estimators": 200, "max_depth": 12},
            "note": "Ensemble baseline — handles non-linearity, no hyperparameter sensitivity",
        },
        "xgboost": {
            "model": None,   # built separately to handle xgboost import
            "params": {
                "model_type": "XGBoost", "n_estimators": 500, "max_depth": 6,
                "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8,
                "early_stopping_rounds": 30,
            },
            "note": "Primary model per spec — best accuracy on tabular data",
        },
    }
    return models


# ── Champion / challenger ──────────────────────────────────────────────────────

def get_production_model_rmse(model_name: str) -> float:
    client = MlflowClient()
    try:
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if not versions:
            logger.info("No Production model yet — first winner will be auto-promoted")
            return float("inf")
        rmse = client.get_run(versions[0].run_id).data.metrics.get("val_rmse", float("inf"))
        logger.info("Current Production model val_RMSE = %.3f", rmse)
        return rmse
    except Exception as e:
        logger.warning("Could not fetch production RMSE: %s — defaulting to inf", e)
        return float("inf")


def promote_to_production(model_name: str) -> None:
    client = MlflowClient()
    for v in client.get_latest_versions(model_name, stages=["Production"]):
        logger.info("Archiving old Production model v%s", v.version)
        client.transition_model_version_stage(model_name, v.version, "Archived")
    candidates = client.get_latest_versions(model_name, stages=["None"])
    if not candidates:
        logger.error("No candidate model found to promote")
        return
    client.transition_model_version_stage(model_name, candidates[0].version, "Production")
    logger.info("Promoted model v%s to Production", candidates[0].version)


# ── Feature engineering ────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame, encoders: dict = None, fit: bool = True):
    df = df.copy()
    for col in BOOL_FEATURES:
        df[col] = df[col].astype(int)
    if encoders is None:
        encoders = {}
    for col in CATEGORICAL_FEATURES:
        if fit:
            le = LabelEncoder()
            df[col + "_enc"] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            le = encoders[col]
            df[col + "_enc"] = df[col].astype(str).apply(
                lambda x: le.transform([x])[0] if x in le.classes_ else 0
            )
    feature_cols = NUMERIC_FEATURES + BOOL_FEATURES + [c + "_enc" for c in CATEGORICAL_FEATURES]
    return df[feature_cols].copy(), encoders, feature_cols


# ── Evaluate one model ─────────────────────────────────────────────────────────

def evaluate(model, X_train, y_train, X_val, y_val):
    train_pred = model.predict(X_train).clip(0)
    val_pred   = model.predict(X_val).clip(0)
    return {
        "train_rmse":    float(np.sqrt(mean_squared_error(y_train, train_pred))),
        "train_mae":     float(mean_absolute_error(y_train, train_pred)),
        "val_rmse":      float(np.sqrt(mean_squared_error(y_val, val_pred))),
        "val_mae":       float(mean_absolute_error(y_val, val_pred)),
        "val_pred":      val_pred,
    }


# ── Training ───────────────────────────────────────────────────────────────────

def train() -> None:
    logger.info("Loading data from %s", CSV_PATH)
    df = pd.read_csv(CSV_PATH)
    logger.info("Raw dataset: %d rows, %d columns", *df.shape)

    df = df[df["showed_up"] == True].dropna(subset=[TARGET]).copy()
    logger.info("After filtering showed_up=True: %d rows", len(df))

    # TIME-BASED SPLIT — mandatory
    df = df.sort_values("scheduled_at").reset_index(drop=True)
    split_idx = int(len(df) * 0.85)
    train_df  = df.iloc[:split_idx].copy()
    val_df    = df.iloc[split_idx:].copy()
    logger.info("Train: %d rows | Val: %d rows  (85/15 time-based split)", len(train_df), len(val_df))

    X_train, encoders, feature_cols = build_features(train_df, fit=True)
    y_train = train_df[TARGET].values
    X_val, _, _ = build_features(val_df, encoders=encoders, fit=False)
    y_val = val_df[TARGET].values

    baseline_rmse = float(np.sqrt(mean_squared_error(y_val, np.full_like(y_val, y_train.mean()))))
    logger.info("Baseline RMSE (predict mean): %.3f", baseline_rmse)

    # ── Train all models and log each as a separate MLflow run ────────────────
    results = {}
    model_definitions = get_models()

    logger.info("\n%s", "=" * 68)
    logger.info("  %-22s %12s %10s %9s %8s", "Model", "Train RMSE", "Val RMSE", "Val MAE", "Overfit")
    logger.info("  %s", "-" * 65)
    logger.info("  %-22s %12s %10.3f %9s %8s", "Baseline (mean)", "—", baseline_rmse, "—", "—")

    for model_key, model_def in model_definitions.items():
        with mlflow.start_run(run_name=model_key):
            mlflow.log_params({**model_def["params"], "features": len(feature_cols)})
            mlflow.log_param("note", model_def["note"])

            # Build model
            if model_key == "xgboost":
                try:
                    import xgboost as xgb
                    model = xgb.XGBRegressor(
                        n_estimators=500, max_depth=6, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                        gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
                        objective="reg:squarederror",
                        early_stopping_rounds=30,
                        random_state=42, n_jobs=-1,
                    )
                    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                except ImportError:
                    logger.warning("XGBoost not available — skipping XGBoost run")
                    continue
            else:
                model = model_def["model"]
                model.fit(X_train, y_train)

            # Evaluate
            metrics = evaluate(model, X_train, y_train, X_val, y_val)
            overfit = metrics["val_rmse"] / metrics["train_rmse"]

            mlflow.log_metrics({
                "train_rmse":     metrics["train_rmse"],
                "train_mae":      metrics["train_mae"],
                "val_rmse":       metrics["val_rmse"],
                "val_mae":        metrics["val_mae"],
                "baseline_rmse":  baseline_rmse,
                "overfit_ratio":  overfit,
                "improvement_pct": round((1 - metrics["val_rmse"] / baseline_rmse) * 100, 2),
            })

            # Feature importance (tree models only)
            try:
                importances = dict(zip(feature_cols, model.feature_importances_))
                for feat, imp in sorted(importances.items(), key=lambda x: -x[1])[:10]:
                    mlflow.log_metric(f"fi_{feat[:35]}", round(float(imp), 6))
            except AttributeError:
                pass  # Ridge has coef_ not feature_importances_

            # Register in MLflow model registry
            mlflow.sklearn.log_model(model, "model", registered_model_name=MODEL_NAME)

            results[model_key] = {
                "model":      model,
                "val_rmse":   metrics["val_rmse"],
                "val_pred":   metrics["val_pred"],
                "train_rmse": metrics["train_rmse"],
                "val_mae":    metrics["val_mae"],
            }

            logger.info("  %-22s %12.3f %10.3f %9.3f %7.2fx  %s",
                        model_key,
                        metrics["train_rmse"],
                        metrics["val_rmse"],
                        metrics["val_mae"],
                        overfit,
                        "(OK)" if overfit < 1.5 else "(WARNING: overfitting)")

    logger.info("  %s", "=" * 65)

    if not results:
        logger.error("No models trained successfully")
        return

    # ── Pick best model ────────────────────────────────────────────────────────
    best_key = min(results, key=lambda k: results[k]["val_rmse"])
    best     = results[best_key]
    logger.info("\nBest model: %s  (val RMSE=%.3f)", best_key, best["val_rmse"])

    # ── Champion / challenger ─────────────────────────────────────────────────
    prod_rmse = get_production_model_rmse(MODEL_NAME)
    if best["val_rmse"] < prod_rmse:
        promote_to_production(MODEL_NAME)
        logger.info("NEW CHAMPION: %s  RMSE=%.3f  (beat %.3f)", best_key, best["val_rmse"], prod_rmse)
    else:
        logger.info("Challenger loses: %.3f vs Production %.3f", best["val_rmse"], prod_rmse)

    # ── Save artifacts ─────────────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)

    # Drift baseline for M6
    np.save(os.path.join(DATA_DIR, "wait_time_baseline_dist.npy"), best["val_pred"])
    logger.info("Drift baseline saved  -> ml_service/data/wait_time_baseline_dist.npy")

    # Encoders for M4 inference
    joblib.dump(encoders, os.path.join(DATA_DIR, "wait_time_label_encoders.pkl"))
    logger.info("Label encoders saved  -> ml_service/data/wait_time_label_encoders.pkl")

    # Feature list for M4
    with open(os.path.join(DATA_DIR, "wait_time_features.json"), "w") as f:
        json.dump(feature_cols, f, indent=2)
    logger.info("Feature list saved    -> ml_service/data/wait_time_features.json")

    logger.info("Training complete.")


if __name__ == "__main__":
    train()