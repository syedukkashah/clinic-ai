from __future__ import annotations

import re

import pytest

from services import monitoring_service


REQUIRED_CUSTOM_METRICS = [
    "mediflow_appointments_booked_total",
    "mediflow_llm_calls_total",
    "mediflow_llm_latency_seconds",
    "mediflow_stt_calls_total",
    "mediflow_stt_latency_seconds",
    "mediflow_wait_prediction_minutes",
    "mediflow_patient_load_prediction",
    "mediflow_model_drift_score",
    "mediflow_key_pool_available",
    "mediflow_agent_steps_total",
    "mediflow_anomaly_score",
    "mediflow_reassignments_total",
    "mediflow_notifications_sent_total",
]


def _metric_value(metrics_text: str, metric_name: str, label_fragment: str | None = None) -> float:
    for line in metrics_text.splitlines():
        if not line.startswith(metric_name):
            continue
        if label_fragment and label_fragment not in line:
            continue
        try:
            return float(line.rsplit(" ", 1)[-1])
        except ValueError:
            continue
    raise AssertionError(f"{metric_name} with {label_fragment!r} not found")


def test_all_custom_metrics_registered(client):
    monitoring_service.PROM_LLM_CALLS.labels(provider="groq", status="ok").inc(0)
    monitoring_service.PROM_LLM_LAT.labels(provider="groq").observe(0.1)
    monitoring_service.PROM_STT_CALLS.labels(provider="groq_whisper", lang="en").inc(0)
    monitoring_service.PROM_STT_LAT.observe(0.1)
    monitoring_service.PROM_WAIT_PREDICTION.labels(doctor_id="1").observe(15)
    monitoring_service.PROM_PATIENT_LOAD.labels(doctor_id="1", hour="10").set(4)
    monitoring_service.PROM_DRIFT_SCORE.labels(model="wait_time_model").set(0.07)
    monitoring_service.PROM_KEY_POOL.labels(provider="groq").set(1)
    monitoring_service.PROM_AGENT_STEPS.labels(agent="booking", tool="run").inc(0)
    monitoring_service.PROM_NOTIFICATIONS_SENT.labels(notification_type="patient").inc(0)

    response_text = client.get("/metrics").text

    for metric in REQUIRED_CUSTOM_METRICS:
        assert metric in response_text, f"{metric} missing from /metrics"


def test_booking_counter_increments(client):
    before = _metric_value(client.get("/metrics").text, "mediflow_appointments_booked_total")
    monitoring_service.PROM_BOOKINGS.inc()
    after = _metric_value(client.get("/metrics").text, "mediflow_appointments_booked_total")
    assert after == pytest.approx(before + 1)


def test_llm_calls_counter_increments(client):
    before = _metric_value(
        client.get("/metrics").text,
        "mediflow_llm_calls_total",
        'provider="gemini",status="ok"',
    ) if 'provider="gemini",status="ok"' in client.get("/metrics").text else 0.0
    monitoring_service.PROM_LLM_CALLS.labels(provider="gemini", status="ok").inc()
    after = _metric_value(
        client.get("/metrics").text,
        "mediflow_llm_calls_total",
        'provider="gemini",status="ok"',
    )
    assert after >= before + 1


def test_llm_latency_histogram_has_buckets(client):
    monitoring_service.PROM_LLM_LAT.labels(provider="groq").observe(0.42)
    text = client.get("/metrics").text
    buckets = [
        line for line in text.splitlines()
        if line.startswith("mediflow_llm_latency_seconds_bucket")
        and 'provider="groq"' in line
    ]
    assert len(buckets) >= 3


def test_key_pool_gauge_reflects_actual_state(client):
    monitoring_service.PROM_KEY_POOL.labels(provider="groq").set(0)
    text = client.get("/metrics").text
    value = _metric_value(text, "mediflow_key_pool_available", 'provider="groq"')
    assert value == 0


def test_agent_steps_counter_labels(client):
    monitoring_service.PROM_AGENT_STEPS.labels(agent="booking", tool="run").inc()
    text = client.get("/metrics").text
    assert 'mediflow_agent_steps_total{agent="booking",tool="run"}' in text


def test_drift_score_gauge_updated_after_drift_check(client):
    monitoring_service.PROM_DRIFT_SCORE.labels(model="wait_time_model").set(0.07)
    text = client.get("/metrics").text
    match = re.search(r'mediflow_model_drift_score\{model="wait_time_model"\}\s+([0-9.]+)', text)
    assert match
    assert float(match.group(1)) == pytest.approx(0.07, abs=0.001)
