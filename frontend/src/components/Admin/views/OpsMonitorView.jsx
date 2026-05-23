import { adminApi } from "@/api/adminApi";
import { getMetricValue } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import DataTable from "../shared/DataTable";
import GaugeChart from "../shared/GaugeChart";
import MiniChart from "../shared/MiniChart";
import ReActTrace from "../shared/ReActTrace";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, sampleTrace } from "./ViewHelpers";

export default function OpsMonitorView() {
  const { metrics } = useMetrics();
  const alerts = useAdminResource(() => adminApi.getOpsAlerts(20), []);
  const runs = useAdminResource(() => adminApi.getAgentRuns("ops_monitor", 10), []);
  const anomaly = getMetricValue(metrics, "mediflow_anomaly_score", 0);
  const alertRows = asArray(alerts.data);

  return (
    <div className="admin-view">
      <ViewHeader title="Ops Monitor Agent" kicker="AI Agents / AIOps Brain">
        <FieldPill tone={anomaly < -0.3 ? "red" : "green"}>{anomaly < -0.3 ? "ANOMALY RUN" : "NORMAL"}</FieldPill>
      </ViewHeader>
      <Panel className="admin-aiops-banner">
        <GaugeChart value={anomaly} label="Isolation Forest Score" />
        <div>
          <h2>Booking Volume - 5-min buckets</h2>
          <MiniChart height={120} />
        </div>
        <div>
          <h2>Trigger Sources</h2>
          <FieldPill tone="blue">Celery Beat</FieldPill>
          <p>Prometheus webhook and MLflow callback routes are not exposed yet.</p>
        </div>
      </Panel>
      {!runs.ok && !runs.loading && <ComingSoon endpoint="/api/admin/agent-runs?agent=ops_monitor" />}
      <div className="admin-grid admin-grid--split">
        <Panel title="Ops Monitor Run Detail">
          <ReActTrace steps={asArray(runs.data)[0]?.steps || sampleTrace("Gemini")} />
        </Panel>
        <Panel title="Alert History">
          <DataTable
            rows={alertRows}
            columns={[
              { key: "severity", label: "Severity", render: (row) => <FieldPill tone={row.severity === "critical" ? "red" : "amber"}>{row.severity || "info"}</FieldPill> },
              { key: "message", label: "Message", render: (row) => <span dir="auto">{row.message || "--"}</span> },
              { key: "triggered_by", label: "Triggered By", render: (row) => row.triggered_by || row.source || "ops_monitor" },
              { key: "created_at", label: "Time", render: (row) => fmtDate(row.created_at || row.timestamp) },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}
