"""
MediFlow — Wait Time Prediction Model (ML Model 1)
Multi-model comparison with MLflow champion/challenger promotion.

File location:  ml_service/training/train_wait_time.py
CSV location:   ml_service/data/appointments.csv

Run from inside ml_service/:
    python -m training.train_wait_time

Preprocessing — separate pipeline per model family:
    Ridge    → OneHotEncoder(handle_unknown='ignore', drop='first') + StandardScaler
               Unknown category → all-zeros row. No collision. No ordinal assumption.
    RF/XGB   → OrdinalEncoder(unknown_value=-1)
               Unknown category → -1, outside real class range. Trees handle it correctly.

No .pkl files:
    The full Pipeline (preprocessor + model) is saved inside MLflow.
    M4 loads it with mlflow.sklearn.load_model() and calls pipeline.predict(raw_df).
    No manual encoding step. No risk of encoder/model mismatch.

.gitignore for teammates:
    Add mlruns/ and mlflow.db to .gitignore — these are local experiment files.
    In production (Docker), MLFLOW_TRACKING_URI points to the shared MLflow server.
    Each teammate runs training locally against their own local DB, or against the
    shared server by setting the env var. The code works either way.
"""

import os
import sys
import warnings
import logging as _logging

# ── Silence MLflow BEFORE importing it — only reliable method ─────────────────
os.environ["GIT_PYTHON_REFRESH"]               = "quiet"
os.environ["MLFLOW_ENABLE_SYSTEM_METRICS_LOGGING"] = "false"
warnings.filterwarnings("ignore")

# Pre-silence any loggers that already exist
for _n in ["mlflow", "mlflow.tracking", "mlflow.store", "mlflow.store.db.utils",
           "mlflow.models", "mlflow.sklearn", "mlflow.utils", "mlflow.data",
           "mlflow.tracking.fluent", "mlflow.tracking.client"]:
    _l = _logging.getLogger(_n)
    _l.setLevel(_logging.CRITICAL)
    _l.propagate = False

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

# Re-silence after import (mlflow re-registers loggers on import)
for _n in list(_logging.root.manager.loggerDict):
    if "mlflow" in _n:
        _l = _logging.getLogger(_n)
        _l.setLevel(_logging.CRITICAL)
        _l.propagate = False

# ── Our logger — clean format, no timestamps ───────────────────────────────────
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger("mediflow.train")

# ── Remaining imports ──────────────────────────────────────────────────────────
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

# ── Paths ──────────────────────────────────────────────────────────────────────
TRAINING_DIR   = os.path.dirname(os.path.abspath(__file__))  # ml_service/training/
ML_SERVICE_DIR = os.path.dirname(TRAINING_DIR)               # ml_service/
DATA_DIR       = os.path.join(ML_SERVICE_DIR, "data")        # ml_service/data/
CSV_PATH       = os.path.join(DATA_DIR, "appointments.csv")

# ── MLflow ─────────────────────────────────────────────────────────────────────
MLFLOW_URI      = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ML_SERVICE_DIR}/mlflow.db")
MODEL_NAME      = "wait_time_model"
EXPERIMENT_NAME = "wait_time_model_training"

mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment(EXPERIMENT_NAME)

# ── Feature groups ─────────────────────────────────────────────────────────────
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
ALL_FEATURES = NUMERIC_FEATURES + BOOL_FEATURES + CATEGORICAL_FEATURES
TARGET = "actual_wait_minutes"


# ── Preprocessors ──────────────────────────────────────────────────────────────

def make_ohe_preprocessor():
    """For Ridge — OHE + StandardScaler. Unknown category → all-zeros (no collision)."""
    return ColumnTransformer(transformers=[
        ("num", StandardScaler(),  NUMERIC_FEATURES + BOOL_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first", sparse_output=False),
         CATEGORICAL_FEATURES),
    ], remainder="drop")


def make_ordinal_preprocessor():
    """For RF/XGBoost — passthrough numerics, OrdinalEncoder. Unknown → -1 (no collision)."""
    return ColumnTransformer(transformers=[
        ("num", "passthrough",     NUMERIC_FEATURES + BOOL_FEATURES),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_FEATURES),
    ], remainder="drop")


# ── Champion / challenger ──────────────────────────────────────────────────────

def get_production_model_rmse(model_name: str) -> float:
    client = MlflowClient()
    try:
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if not versions:
            return float("inf")
        return client.get_run(versions[0].run_id).data.metrics.get("val_rmse", float("inf"))
    except Exception:
        return float("inf")


def promote_to_production(model_name: str) -> None:
    client = MlflowClient()
    for v in client.get_latest_versions(model_name, stages=["Production"]):
        client.transition_model_version_stage(model_name, v.version, "Archived")
    candidates = client.get_latest_versions(model_name, stages=["None"])
    if candidates:
        client.transition_model_version_stage(model_name, candidates[0].version, "Production")


# ── Evaluate ───────────────────────────────────────────────────────────────────

def evaluate(pipeline, X_train, y_train, X_val, y_val):
    train_pred = pipeline.predict(X_train).clip(0)
    val_pred   = pipeline.predict(X_val).clip(0)
    return {
        "train_rmse": float(np.sqrt(mean_squared_error(y_train, train_pred))),
        "train_mae":  float(mean_absolute_error(y_train, train_pred)),
        "val_rmse":   float(np.sqrt(mean_squared_error(y_val, val_pred))),
        "val_mae":    float(mean_absolute_error(y_val, val_pred)),
        "val_pred":   val_pred,
    }


# ── Training ───────────────────────────────────────────────────────────────────

def train() -> None:
    logger.info("Loading data...")
    df = pd.read_csv(CSV_PATH)
    df = df[df["showed_up"] == True].dropna(subset=[TARGET]).copy()
    df = df.sort_values("scheduled_at").reset_index(drop=True)

    split_idx = int(len(df) * 0.85)
    train_df  = df.iloc[:split_idx].copy()
    val_df    = df.iloc[split_idx:].copy()

    X_train, y_train = train_df[ALL_FEATURES], train_df[TARGET].values
    X_val,   y_val   = val_df[ALL_FEATURES],   val_df[TARGET].values

    baseline_rmse = float(np.sqrt(mean_squared_error(y_val, np.full_like(y_val, y_train.mean()))))

    logger.info("  Rows  — train: %d  |  val: %d", len(train_df), len(val_df))
    logger.info("  Split — 85%% training (chronological), 15%% validation\n")

    # ── Table header ──────────────────────────────────────────────────────────
    W = 90
    logger.info("─" * W)
    logger.info("  %-22s %-28s %10s %10s %9s %8s",
                "Model", "Encoding", "Train RMSE", "Val RMSE", "Val MAE", "Overfit")
    logger.info("─" * W)
    logger.info("  %-22s %-28s %10s %10.3f %9s %8s",
                "Baseline (mean)", "—", "—", baseline_rmse, "—", "—")
    logger.info("─" * W)

    # ── Model definitions ─────────────────────────────────────────────────────
    models_to_train = [
        ("ridge_regression", "OneHotEncoder + StandardScaler",
         Pipeline([("pre", make_ohe_preprocessor()), ("model", Ridge(alpha=1.0))]),
         {"model_type": "Ridge", "alpha": 1.0}, False),

        ("random_forest", "OrdinalEncoder (unknown=-1)",
         Pipeline([("pre", make_ordinal_preprocessor()),
                   ("model", RandomForestRegressor(
                       n_estimators=200, max_depth=12,
                       min_samples_leaf=5, random_state=42, n_jobs=-1))]),
         {"model_type": "RandomForest", "n_estimators": 200}, False),
    ]

    try:
        import xgboost as xgb
        models_to_train.append((
            "xgboost", "OrdinalEncoder (unknown=-1)",
            Pipeline([("pre", make_ordinal_preprocessor()),
                      ("model", xgb.XGBRegressor(
                          n_estimators=500, max_depth=6, learning_rate=0.05,
                          subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                          gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
                          objective="reg:squarederror", early_stopping_rounds=30,
                          random_state=42, n_jobs=-1))]),
            {"model_type": "XGBoost", "n_estimators": 500, "learning_rate": 0.05}, True,
        ))
    except ImportError:
        logger.info("  XGBoost not installed — skipping (pip install xgboost)")

    # ── Train each model ──────────────────────────────────────────────────────
    results = {}
    for model_key, encoding_label, pipeline, params, needs_eval_set in models_to_train:
        with mlflow.start_run(run_name=model_key):
            mlflow.log_params(params)

            if needs_eval_set:
                # XGBoost early stopping — transform manually then fit estimator
                pre = pipeline.named_steps["pre"]
                pre.fit(X_train)
                Xt = pre.transform(X_train)
                Xv = pre.transform(X_val)
                pipeline.named_steps["model"].fit(
                    Xt, y_train, eval_set=[(Xv, y_val)], verbose=False)
                # Re-fit preprocessor so pipeline.predict() works end-to-end
                pre.fit(X_train)
            else:
                pipeline.fit(X_train, y_train)

            m      = evaluate(pipeline, X_train, y_train, X_val, y_val)
            overfit = m["val_rmse"] / m["train_rmse"]

            mlflow.log_metrics({
                "train_rmse":     m["train_rmse"],
                "train_mae":      m["train_mae"],
                "val_rmse":       m["val_rmse"],
                "val_mae":        m["val_mae"],
                "baseline_rmse":  baseline_rmse,
                "overfit_ratio":  overfit,
                "improvement_pct": round((1 - m["val_rmse"] / baseline_rmse) * 100, 2),
            })

            try:
                raw_model = pipeline.named_steps["model"]
                imps = dict(zip(ALL_FEATURES[:len(raw_model.feature_importances_)],
                                raw_model.feature_importances_))
                for f, i in sorted(imps.items(), key=lambda x: -x[1])[:10]:
                    mlflow.log_metric(f"fi_{f[:35]}", round(float(i), 6))
            except AttributeError:
                pass

            mlflow.sklearn.log_model(pipeline, "model", registered_model_name=MODEL_NAME)

            results[model_key] = {**m, "encoding": encoding_label}

            logger.info("  %-22s %-28s %10.3f %10.3f %9.3f %7.2fx  %s",
                        model_key, encoding_label,
                        m["train_rmse"], m["val_rmse"], m["val_mae"],
                        overfit, "✓" if overfit < 1.5 else "⚠ overfit")

    logger.info("─" * W)

    if not results:
        logger.info("No models trained.")
        return

    # ── Champion / challenger ─────────────────────────────────────────────────
    best_key = min(results, key=lambda k: results[k]["val_rmse"])
    best     = results[best_key]
    prod_rmse = get_production_model_rmse(MODEL_NAME)

    logger.info("")
    logger.info("  Best model : %s", best_key)
    logger.info("  Val RMSE   : %.3f  (baseline was %.3f — %.1f%% improvement)",
                best["val_rmse"], baseline_rmse,
                (1 - best["val_rmse"] / baseline_rmse) * 100)

    if best["val_rmse"] < prod_rmse:
        promote_to_production(MODEL_NAME)
        logger.info("  Champion   : ✓ promoted to Production (beat %.3f)", prod_rmse)
    else:
        logger.info("  Champion   : existing model retained (%.3f ≤ %.3f)",
                    best["val_rmse"], prod_rmse)

    # ── Save artifacts ────────────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)
    np.save(os.path.join(DATA_DIR, "wait_time_baseline_dist.npy"), best["val_pred"])
    with open(os.path.join(DATA_DIR, "wait_time_features.json"), "w") as f:
        json.dump(ALL_FEATURES, f, indent=2)

    logger.info("")
    logger.info("  Artifacts saved:")
    logger.info("    wait_time_baseline_dist.npy  → M6 (drift detection)")
    logger.info("    wait_time_features.json      → M4 (inference endpoint)")
    logger.info("    Pipeline (pre+model)         → MLflow registry (Production)")
    logger.info("")
    logger.info("  Done.")


if __name__ == "__main__":
    train()