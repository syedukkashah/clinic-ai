import { useMemo } from "react";
import { useMetrics } from "@/context/MetricsContext";
import { Panel, ViewHeader } from "./ViewHelpers";

const expected = [
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
  "mediflow_requests_total",
  "mediflow_request_duration_seconds",
];

export default function SystemMetricsView() {
  const { metrics, rawText } = useMetrics();
  const rows = useMemo(() => expected.map((name) => metrics?.get(name) || { name, type: "missing", value: 0, samples: [] }), [metrics]);

  return (
    <div className="admin-view">
      <ViewHeader title="System Metrics" kicker="Infrastructure / Prometheus Exposition" />
      <div className="admin-metrics-grid">
        {rows.map((metric) => (
          <article key={metric.name} className={metric.type === "missing" ? "is-missing" : ""}>
            <h2>{metric.name}</h2>
            <span>{metric.type}</span>
            <strong>{formatMetric(metric.value)}</strong>
            <div>
              {Object.keys(metric.samples?.[0]?.labels || {}).map((label) => (
                <small key={label}>{label}</small>
              ))}
            </div>
          </article>
        ))}
      </div>
      <Panel title="Raw Prometheus exposition format (/metrics)">
        <pre className="admin-raw-metrics">{rawText || "No /metrics response loaded yet."}</pre>
      </Panel>
    </div>
  );
}

function formatMetric(value) {
  const numeric = Number(value || 0);
  return Math.abs(numeric) >= 1000 ? Math.round(numeric).toLocaleString() : numeric.toFixed(3);
}
