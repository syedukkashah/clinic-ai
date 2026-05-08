from prometheus_client import Counter, Histogram, Gauge

PROM_BOOKINGS = Counter(
    "mediflow_appointments_booked_total",
    "Total bookings created"
)
PROM_LLM_CALLS = Counter(
    "mediflow_llm_calls_total",
    "LLM API calls",
    ["provider", "status"]
)
PROM_LLM_LAT = Histogram(
    "mediflow_llm_latency_seconds",
    "LLM call latency",
    ["provider"],
    buckets=[.2, .5, 1, 2, 5]
)
PROM_STT_CALLS = Counter(
    "mediflow_stt_calls_total",
    "STT calls",
    ["provider", "lang"]
)
PROM_DRIFT_SCORE = Gauge(
    "mediflow_model_drift_score",
    "KL divergence",
    ["model"]
)
PROM_KEY_POOL = Gauge(
    "mediflow_key_pool_available",
    "Available API keys",
    ["provider"]
)
PROM_AGENT_STEPS = Counter(
    "mediflow_agent_steps_total",
    "Agent tool calls",
    ["agent", "tool"]
)
PROM_ANOMALY_SCORE = Gauge(
    "mediflow_anomaly_score",
    "Isolation Forest score"
)
PROM_REASSIGN = Counter(
    "mediflow_reassignments_total",
    "Slot reassignments"
)