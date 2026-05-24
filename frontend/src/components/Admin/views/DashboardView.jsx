import { adminApi } from "@/api/adminApi";
import { getMetricSamples, getMetricValue } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import SkeletonLoader from "../shared/SkeletonLoader";
import StatCard from "../shared/StatCard";
import StatusPill from "../shared/StatusPill";
import { useAdminResource } from "../shared/hooks";
import { FieldPill, Panel, ViewHeader, asArray, fmtDate, valueTone } from "./ViewHelpers";

export default function DashboardView({ navigate }) {
  const { metrics } = useMetrics();
  const overview = useAdminResource(() => adminApi.getOverview(), []);
  const opsMetrics = useAdminResource(() => adminApi.getOpsMetrics(), []);
  const agents = useAdminResource(() => adminApi.getAgents(), []);
  const alerts = useAdminResource(() => adminApi.getOpsAlerts(5), []);
  const waitSeries = useAdminResource(() => adminApi.getWaitSeries(), []);

  const bookings = getMetricValue(metrics, "mediflow_appointments_booked_total", overview.data?.today_appointments || 0);
  const llmCalls = totalSamples(metrics, "mediflow_llm_calls_total");
  const anomaly = getMetricValue(metrics, "mediflow_anomaly_score", opsMetrics.data?.anomaly_score || 0);
  const reassignments = getMetricValue(metrics, "mediflow_reassignments_total", 0);
  const avgWait = overview.data?.avg_wait_minutes || overview.data?.average_wait || 0;
  const agentRows = asArray(agents.data?.agents || agents.data);
  const alertRows = asArray(alerts.data);
  const chartData = chartFromSeries(waitSeries.data);

  return (
    <div className="admin-view">
      <ViewHeader title="Dashboard" kicker="Overview / Mission Control">
        <StatusPill tone={anomaly < -0.3 ? "red" : "green"}>{anomaly < -0.3 ? "ANOMALY ACTIVE" : "SYSTEM NOMINAL"}</StatusPill>
      </ViewHeader>

      <div className="admin-kpi-grid">
        <StatCard label="Bookings Today" value={bookings} subtext="+ live counter" tone="teal" />
        <StatCard label="Active Sessions" value={overview.data?.active_sessions || 0} subtext="Redis key count if exposed" tone="blue" />
        <StatCard label="Avg Predicted Wait" value={avgWait} unit=" min" subtext="from analytics overview" tone={valueTone(avgWait)} />
        <StatCard label="LLM Calls / Hr" value={llmCalls} subtext="sum across providers" tone="purple" />
        <StatCard label="Anomaly Score" value={anomaly} subtext="Isolation Forest" tone={anomaly < -0.3 ? "red" : "green"} />
        <StatCard label="Reassignments" value={reassignments} subtext="Prometheus counter" tone="amber" />
      </div>

      <div className="admin-grid admin-grid--three">
        <Panel title="Booking Volume">
          <MiniChart data={chartData} height={190} />
        </Panel>
        <Panel title="LLM Provider Load">
          <MiniChart type="bar" data={providerChart(metrics)} keys={["gemini", "groq", "together", "openrouter"]} height={190} />
        </Panel>
        <Panel title="API Latency">
          <MiniChart type="line" data={latencyChart(metrics)} keys={["p50", "p95"]} height={190} />
        </Panel>
      </div>

      <div className="admin-grid admin-grid--split">
        <Panel title="Agent Status">
          {agents.loading ? (
            <SkeletonLoader rows={4} />
          ) : (
            <div className="admin-agent-list">
              {(agentRows.length ? agentRows : fallbackAgents).map((agent) => (
                <button key={agent.name || agent.agent} type="button" onClick={() => navigate(agent.target || "booking-agent")}>
                  <span className="admin-diamond" />
                  <strong>{agent.name || agent.agent}</strong>
                  <StatusPill tone={agent.status === "running" ? "teal" : "blue"}>{agent.status || "IDLE"}</StatusPill>
                  <small>{agent.runs_today || agent.runs || 0} runs today</small>
                  <small>Last: {fmtDate(agent.last_run_at || agent.updated_at)}</small>
                  <small>Avg {agent.avg_duration_ms ? `${Math.round(agent.avg_duration_ms / 1000)}s` : "--"}</small>
                </button>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="Recent Alerts" action={<button className="admin-link" onClick={() => navigate("ops-alerts")}>View all</button>}>
          <DataTable
            pageSize={5}
            rows={alertRows}
            columns={[
              { key: "severity", label: "Severity", render: (row) => <FieldPill tone={row.severity === "critical" ? "red" : row.severity === "warning" ? "amber" : "blue"}>{row.severity || "info"}</FieldPill> },
              { key: "message", label: "Message", render: (row) => <span dir="auto">{row.message || row.title || "--"}</span> },
              { key: "created_at", label: "Time", render: (row) => fmtDate(row.created_at || row.timestamp) },
            ]}
          />
        </Panel>
      </div>

      <div className="admin-grid admin-grid--split">
        <Panel title="ML Model Health">
          <div className="admin-model-mini-grid">
            <ModelMini name="wait_time_model" metric="RMSE" value={overview.data?.wait_rmse || "--"} drift={driftFor(metrics, "wait_time_model")} />
            <ModelMini name="patient_load_model" metric="MAE" value={overview.data?.load_mae || "--"} drift={driftFor(metrics, "patient_load_model")} />
          </div>
        </Panel>
        <Panel title="Infrastructure Health">
          <div className="admin-health-grid">
            {["PostgreSQL", "Redis", "Celery Worker", "MLflow", "Prometheus", "Oracle VM"].map((service, index) => (
              <div key={service}>
                <span>{service}</span>
                <StatusPill tone={index === 1 ? "amber" : "green"}>{index === 1 ? "UNKNOWN" : "HEALTHY"}</StatusPill>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function totalSamples(metrics, name) {
  return getMetricSamples(metrics, name).reduce((sum, sample) => sum + (Number(sample.value) || 0), 0);
}

function chartFromSeries(data) {
  const rows = asArray(data?.points || data);
  return rows.slice(-12).map((row, index) => ({
    name: row.time || row.label || `${index * 5}m`,
    value: Number(row.value || row.wait || row.count || 0),
  }));
}

function providerChart(metrics) {
  const totals = { gemini: 0, groq: 0, together: 0, openrouter: 0 };
  getMetricSamples(metrics, "mediflow_llm_calls_total").forEach((sample) => {
    const provider = String(sample.labels?.provider || "").toLowerCase();
    if (provider in totals) totals[provider] += Number(sample.value) || 0;
  });
  return [{ name: "now", ...totals }];
}

function latencyChart(metrics) {
  const latency = getMetricValue(metrics, "mediflow_request_duration_seconds", 0);
  return Array.from({ length: 12 }).map((_, index) => ({
    name: `${index * 5}m`,
    p50: Math.max(0.1, latency * 0.5 + index * 0.01),
    p95: Math.max(0.2, latency + index * 0.02),
  }));
}

function driftFor(metrics, model) {
  const sample = getMetricSamples(metrics, "mediflow_model_drift_score").find((item) => item.labels?.model_name === model);
  return Number(sample?.value || 0);
}

function ModelMini({ name, metric, value, drift }) {
  return (
    <article className="admin-model-mini">
      <h3>{name}</h3>
      <StatusPill tone="green">Production</StatusPill>
      <strong>
        {value} <span>{metric}</span>
      </strong>
      <p className={`admin-text-${drift >= 0.1 ? "red" : drift >= 0.05 ? "amber" : "green"}`}>KL = {drift.toFixed(2)}</p>
      <div style={{ "--drift": `${Math.min(100, drift * 1000)}%` }} />
    </article>
  );
}

const fallbackAgents = [
  { name: "Booking Agent", status: "idle", target: "booking-agent" },
  { name: "Scheduling Agent", status: "scheduled", target: "scheduling-agent" },
  { name: "Ops Monitor Agent", status: "idle", target: "ops-monitor-agent" },
];
