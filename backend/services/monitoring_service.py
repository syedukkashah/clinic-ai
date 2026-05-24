from prometheus_client import REGISTRY, Counter, Gauge, Histogram


def _collector_name(name: str) -> str:
    if name.endswith("_total"):
        return name[:-6]
    return name


def _existing(name: str):
    names = getattr(REGISTRY, "_names_to_collectors", {})
    return names.get(name) or names.get(_collector_name(name))


def _counter(name: str, description: str, labels: list[str] | None = None):
    return _existing(name) or Counter(_collector_name(name), description, labels or [])


def _histogram(name: str, description: str, labels: list[str] | None = None, **kwargs):
    return _existing(name) or Histogram(name, description, labels or [], **kwargs)


def _gauge(name: str, description: str, labels: list[str] | None = None):
    return _existing(name) or Gauge(name, description, labels or [])

PROM_BOOKINGS = _counter(
    "mediflow_appointments_booked_total",
    "Total bookings created"
)
PROM_LLM_CALLS = _counter(
    "mediflow_llm_calls_total",
    "LLM API calls",
    ["provider", "status"]
)
PROM_LLM_LAT = _histogram(
    "mediflow_llm_latency_seconds",
    "LLM call latency",
    ["provider"],
    buckets=[.2, .5, 1, 2, 5]
)
PROM_STT_CALLS = _counter(
    "mediflow_stt_calls_total",
    "STT calls",
    ["provider", "lang"]
)
PROM_STT_LAT = _histogram(
    "mediflow_stt_latency_seconds",
    "STT transcription latency in seconds",
)
PROM_WAIT_PREDICTION = _histogram(
    "mediflow_wait_prediction_minutes",
    "Predicted wait time in minutes",
    ["doctor_id"],
    buckets=[5, 10, 15, 20, 30, 45, 60, 90],
)
PROM_PATIENT_LOAD = _gauge(
    "mediflow_patient_load_prediction",
    "Predicted patient load",
    ["doctor_id", "hour"]
)
PROM_DRIFT_SCORE = _gauge(
    "mediflow_model_drift_score",
    "KL divergence",
    ["model"]
)
PROM_KEY_POOL = _gauge(
    "mediflow_key_pool_available",
    "Available API keys",
    ["provider"]
)
PROM_AGENT_STEPS = _counter(
    "mediflow_agent_steps_total",
    "Agent tool calls",
    ["agent", "tool"]
)
PROM_ANOMALY_SCORE = _gauge(
    "mediflow_anomaly_score",
    "Isolation Forest score"
)
PROM_REASSIGN = _counter(
    "mediflow_reassignments_total",
    "Slot reassignments"
)
PROM_NOTIFICATIONS_SENT = _counter(
    "mediflow_notifications_sent_total",
    "Notifications sent",
    ["notification_type"]
)
