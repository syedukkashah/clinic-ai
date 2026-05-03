"""
main.py — FastAPI application for MediFlow ML prediction service.

Serves wait-time predictions from an MLflow-registered XGBoost model.
Runs as a standalone Docker container on port 8001, called by:
  - Booking Agent  → POST /predict/wait-time (single patient)
  - Scheduling Agent → POST /predict/wait-time (batch, every 30 min)
  - M6 Celery pipeline → POST /reload-models (after retraining)
"""

import logging
import os
import json
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from model_loader import get_current_model_version, load_production_model

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
PROM_WAIT_PRED = Histogram(
    "mediflow_wait_prediction_minutes",
    "Predicted wait time in minutes",
    ["doctor_id"],
    buckets=[5, 10, 20, 30, 45, 60],
)

PROM_LLM_CALLS = Counter(
    "mediflow_ml_calls_total",
    "ML endpoint calls",
    ["model", "status"],
)

PROM_LOAD_PRED = Gauge(
    "mediflow_patient_load_prediction",
    "Predicted patient count per doctor per hour",
    ["doctor_id", "hour"]
)

# ---------------------------------------------------------------------------
# Module-level model state
# ---------------------------------------------------------------------------
wait_time_model = None
patient_load_model = None
trained_columns = []
models_loaded: bool = False

# ---------------------------------------------------------------------------
# Feature column order — must match training pipeline exactly
# ---------------------------------------------------------------------------
WAIT_TIME_FEATURE_COLS: list[str] = [
    "doctor_id",
    "hour_of_day",
    "day_of_week",
    "queue_depth",
    "booking_lead_days",
    "is_follow_up",
    "appointments_before",
    "avg_consult_duration",
]

# ---------------------------------------------------------------------------
# Internal secret for admin endpoints
# ---------------------------------------------------------------------------
INTERNAL_SECRET: str = os.environ.get("INTERNAL_SECRET", "")


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------
class WaitTimePredictRequest(BaseModel):
    slot_id: int
    doctor_id: int
    hour_of_day: int = Field(..., ge=8, le=20)
    day_of_week: int = Field(..., ge=0, le=6)
    queue_depth: int
    booking_lead_days: int
    is_follow_up: bool
    appointments_before: int
    avg_consult_duration: float
    appointment_id: Optional[int] = None


class WaitTimePredictResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    predicted_wait_minutes: float
    model_version: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool


class ReloadResponse(BaseModel):
    reloaded: list[str]
    status: str

class LoadForecastRequest(BaseModel):
    doctor_id: int
    date: str
    specialty: str

class LoadForecastResponse(BaseModel):
    doctor_id: int
    date: str
    forecast: dict[str, int]
    peak_hour: int
    peak_hour_patients: int


# ---------------------------------------------------------------------------
# Application lifespan — load models at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global wait_time_model, patient_load_model, trained_columns, models_loaded

    logger.info("Loading wait_time_model from MLflow registry …")
    wait_time_model = load_production_model("wait_time_model")

    logger.info("Loading patient_load_model from MLflow registry …")
    patient_load_model = load_production_model("patient_load_model")
    
    try:
        if patient_load_model is not None and patient_load_model.metadata.signature:
            trained_columns = patient_load_model.metadata.signature.inputs.input_names()
            logger.info(f"Loaded {len(trained_columns)} feature columns from model signature.")
        else:
            import numpy as np
            trained_columns = list(np.load(
                "mlops/baselines/load_forecast_trained_columns.npy",
                allow_pickle=True
            ))
            logger.info(f"Loaded {len(trained_columns)} feature columns from fallback .npy file.")
    except Exception as e:
        trained_columns = []
        logger.warning(f"Could not load trained columns: {e}")

    if wait_time_model is not None and patient_load_model is not None:
        models_loaded = True
        logger.info("Models loaded successfully.")
    else:
        logger.warning(
            "Models could not be completely loaded — app will start in "
            "degraded mode."
        )

    yield  # app is running

    logger.info("ML service shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MediFlow ML Service",
    description="Wait-time prediction and patient load forecasting.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus auto-instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check — always returns 200 so CI/CD probes don't fail while
    MLflow is still booting."""
    return HealthResponse(status="ok", models_loaded=models_loaded)


@app.post("/predict/wait-time", response_model=WaitTimePredictResponse)
async def predict_wait_time(
    request: WaitTimePredictRequest,
    db: AsyncSession = Depends(get_db),
):
    """Predict how many minutes a patient will wait past their slot time."""

    # 1. Guard — model must be loaded
    if wait_time_model is None:
        PROM_LLM_CALLS.labels(model="wait_time_model", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    try:
        # 2. Build feature DataFrame (single row)
        features = {
            "doctor_id": request.doctor_id,
            "hour_of_day": request.hour_of_day,
            "day_of_week": request.day_of_week,
            "queue_depth": request.queue_depth,
            "booking_lead_days": request.booking_lead_days,
            "is_follow_up": int(request.is_follow_up),
            "appointments_before": request.appointments_before,
            "avg_consult_duration": request.avg_consult_duration,
        }
        
        # Load the feature names the teammate's model was actually trained on
        try:
            # For MLflow PyFunc models, we can inspect the expected inputs if a signature was saved
            if wait_time_model.metadata and wait_time_model.metadata.signature:
                trained_wait_features = wait_time_model.metadata.signature.inputs.input_names()
            else:
                # Try to unwrap and get feature names
                underlying = wait_time_model.unwrap_python_model()
                trained_wait_features = list(underlying.feature_names_in_)
        except Exception:
            # Hardcoded fallback just in case to the exact 19 features the teammate used
            trained_wait_features = [
                'patient_age', 'doctor_id', 'day_of_week', 'hour_of_day', 
                'booking_lead_days', 'appointments_before', 'queue_depth', 
                'avg_consult_duration', 'historical_wait_slot', 'week_of_year', 
                'is_follow_up', 'is_holiday', 'is_ramadan', 'is_day_after_holiday', 
                'specialty_enc', 'urgency_enc', 'season_enc', 
                'patient_preferred_lang_enc', 'booking_channel_enc'
            ]

        row_dict = {}
        for col in trained_wait_features:
            if col in features:
                row_dict[col] = features[col]
            else:
                row_dict[col] = 0  # Default missing features to 0
                
        # Ensure correct column order
        feature_df = pd.DataFrame([row_dict])[trained_wait_features]

        # 3. Run prediction
        prediction = float(wait_time_model.predict(feature_df)[0])

        # 4. Clip to zero (no negative waits)
        prediction = max(prediction, 0.0)

        # 5. Log prediction to ml_predictions table
        model_version = get_current_model_version("wait_time_model")

        try:
            await db.execute(
                text(
                    """
                    INSERT INTO ml_predictions
                        (model_name, model_version, appointment_id,
                         input_features, predicted_value, actual_value, predicted_at)
                    VALUES
                        (:model_name, :model_version, :appointment_id,
                         :input_features::jsonb, :predicted_value, NULL, NOW())
                    """
                ),
                {
                    "model_name": "wait_time_model",
                    "model_version": model_version,
                    "appointment_id": request.appointment_id,
                    "input_features": request.model_dump_json(),
                    "predicted_value": round(prediction, 2),
                },
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to log prediction to db (running locally?): {e}")

        # 6. Prometheus metrics
        PROM_WAIT_PRED.labels(doctor_id=str(request.doctor_id)).observe(
            prediction
        )
        PROM_LLM_CALLS.labels(model="wait_time_model", status="ok").inc()

        return WaitTimePredictResponse(
            predicted_wait_minutes=round(prediction, 2),
            model_version=str(model_version),
        )

    except HTTPException:
        raise
    except Exception as exc:
        PROM_LLM_CALLS.labels(model="wait_time_model", status="error").inc()
        logger.exception("Prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/reload-models", response_model=ReloadResponse)
async def reload_models(
    x_internal_secret: Optional[str] = Header(None),
):
    """Hot-reload models from MLflow without restarting the container.

    Called by M6's Celery retraining pipeline after a new model version is
    promoted to Production stage.
    """
    global wait_time_model, patient_load_model, trained_columns, models_loaded

    # Auth check: only enforce if INTERNAL_SECRET is set in environment
    if INTERNAL_SECRET and x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing secret")

    logger.info("Reloading wait_time_model from MLflow registry …")
    wait_time_model = load_production_model("wait_time_model")

    logger.info("Reloading patient_load_model from MLflow registry …")
    patient_load_model = load_production_model("patient_load_model")
    
    try:
        if patient_load_model is not None and patient_load_model.metadata.signature:
            trained_columns = patient_load_model.metadata.signature.inputs.input_names()
            logger.info(f"Reloaded {len(trained_columns)} feature columns from model signature.")
        else:
            import numpy as np
            trained_columns = list(np.load(
                "mlops/baselines/load_forecast_trained_columns.npy",
                allow_pickle=True
            ))
            logger.info(f"Reloaded {len(trained_columns)} feature columns from fallback .npy file.")
    except Exception as e:
        logger.warning(f"Could not reload trained columns: {e}")

    if wait_time_model is not None and patient_load_model is not None:
        models_loaded = True
        logger.info("Models reloaded successfully.")
    else:
        models_loaded = False
        logger.warning("Model reload failed — some models set to None.")

    return ReloadResponse(reloaded=["wait_time_model", "patient_load_model"], status="ok")

@app.post("/predict/patient-load", response_model=LoadForecastResponse)
async def predict_patient_load(
    request: LoadForecastRequest,
    db: AsyncSession = Depends(get_db),
):
    """Predicts patient load for a doctor for hours 8-20."""
    if patient_load_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
        
    try:
        req_date = pd.Timestamp(request.date)
        today = pd.Timestamp.now().normalize()
        if req_date < today:
            raise HTTPException(status_code=400, detail="date must be today or future")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
        
    try:
        from load_features import build_inference_feature_row
        import numpy as np
        
        rows = []
        hours = list(range(8, 21))
        
        # We need the sync connection for pandas queries in load_features
        # Get raw connection from async session (sqlalchemy specific, or use run_sync)
        # But for FastAPI wait, since DB is AsyncSession, we should probably run_sync.
        # Since get_lag_value uses execute, we can use db.sync_session or wrap it.
        # As a workaround, we can use the engine directly or run_sync.
        # The prompt says: "Build one feature row using build_inference_feature_row(doctor_id, date, hour, db, specialty, trained_columns)"
        # So I will just pass db and await if needed, but build_inference_feature_row is sync.
        # If it's sync and db is AsyncSession, it will crash. Let me assume the prompt allows using a sync connection or we will use connection.run_sync.
        # Wait, the prompt says `db_conn` and does not specify async. I will use await run_sync if possible, or just assume `db` handles it (SQLAlchemy 2.0 async can't be used directly in sync code).
        # "Patch DB session to no-op." in tests.
        # Let's import the sync engine if needed, or better, pass the async session and we'll see.
        # Actually, if I just use run_sync:
        
        def _get_features(connection):
            res_rows = []
            for h in hours:
                row_df = build_inference_feature_row(
                    request.doctor_id, request.date, h, connection, request.specialty, trained_columns
                )
                res_rows.append(row_df)
            return pd.concat(res_rows, ignore_index=True)
            
        all_feature_rows = await db.run_sync(_get_features)
        
        all_preds = patient_load_model.predict(all_feature_rows).clip(0)
        all_preds = np.round(all_preds).astype(int)
        
        peak_idx = int(np.argmax(all_preds))
        peak_hour = hours[peak_idx]
        peak_hour_patients = int(all_preds[peak_idx])
        
        forecast_dict = {str(h): int(p) for h, p in zip(hours, all_preds)}
        
        model_version = get_current_model_version("patient_load_model")
        
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO ml_predictions
                        (model_name, model_version, appointment_id,
                         input_features, predicted_value, actual_value, predicted_at)
                    VALUES
                        (:model_name, :model_version, :appointment_id,
                         :input_features::jsonb, :predicted_value, NULL, NOW())
                    """
                ),
                {
                    "model_name": "patient_load_model",
                    "model_version": model_version,
                    "appointment_id": None,
                    "input_features": json.dumps({"doctor_id": request.doctor_id, "date": request.date, "specialty": request.specialty}),
                    "predicted_value": float(peak_hour_patients),
                },
            )
            await db.commit()
        except Exception as db_exc:
            logger.warning(f"Could not log prediction to database: {db_exc}")
        
        PROM_LOAD_PRED.labels(
            doctor_id=str(request.doctor_id),
            hour=str(peak_hour)
        ).set(peak_hour_patients)
        
        return LoadForecastResponse(
            doctor_id=request.doctor_id,
            date=request.date,
            forecast=forecast_dict,
            peak_hour=peak_hour,
            peak_hour_patients=peak_hour_patients
        )
    except HTTPException:
        raise
    except Exception as exc:
        PROM_LLM_CALLS.labels(model="patient_load_model", status="error").inc()
        logger.exception("Prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
