from prometheus_client import Counter, Histogram, Gauge

mediflow_llm_calls_total = Counter(
    "mediflow_llm_calls_total",
    "Total LLM calls",
    ["provider", "status"]
)

mediflow_llm_latency_seconds = Histogram(
    "mediflow_llm_latency_seconds",
    "LLM call latency in seconds",
    ["provider"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

mediflow_stt_latency_seconds = Histogram(
    "mediflow_stt_latency_seconds",
    "STT call latency in seconds",
    ["engine"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

mediflow_bookings_total = Counter(
    "mediflow_bookings_total",
    "Total bookings",
    ["clinic_id", "status"]
)

mediflow_predicted_wait_minutes = Gauge(
    "mediflow_predicted_wait_minutes",
    "Predicted wait time in minutes",
    ["clinic_id"]
)

mediflow_model_drift_score = Gauge(
    "mediflow_model_drift_score",
    "Model drift score",
    ["model_name"]
)

mediflow_anomaly_score = Gauge(
    "mediflow_anomaly_score",
    "Anomaly score",
    ["model_name"]
)

mediflow_key_pool_available = Gauge(
    "mediflow_key_pool_available",
    "Available keys in the pool",
    ["provider"]
)

mediflow_reassignments_total = Counter(
    "mediflow_reassignments_total",
    "Total reassignments",
    ["clinic_id"]
)

mediflow_notifications_sent_total = Counter(
    "mediflow_notifications_sent_total",
    "Total notifications sent",
    ["channel"]
)

def record_llm_call(provider: str, status: str, duration_seconds: float):
    mediflow_llm_calls_total.labels(provider=provider, status=status).inc()
    mediflow_llm_latency_seconds.labels(provider=provider).observe(duration_seconds)

def record_stt_call(engine: str, duration_seconds: float):
    mediflow_stt_latency_seconds.labels(engine=engine).observe(duration_seconds)

def record_booking(clinic_id: str, status: str):
    mediflow_bookings_total.labels(clinic_id=clinic_id, status=status).inc()

def set_key_pool(provider: str, count: int):
    mediflow_key_pool_available.labels(provider=provider).set(count)

def set_drift_score(model_name: str, score: float):
    mediflow_model_drift_score.labels(model_name=model_name).set(score)

def set_anomaly_score(model_name: str, score: float):
    mediflow_anomaly_score.labels(model_name=model_name).set(score)

def set_predicted_wait(clinic_id: str, minutes: float):
    mediflow_predicted_wait_minutes.labels(clinic_id=clinic_id).set(minutes)
