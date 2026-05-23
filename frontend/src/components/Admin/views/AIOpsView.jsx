import { adminApi } from "@/api/adminApi";
import { getMetricValue } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import GaugeChart from "../shared/GaugeChart";
import MiniChart from "../shared/MiniChart";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate } from "./ViewHelpers";

export default function AIOpsView() {
  const { metrics } = useMetrics();
  const history = useAdminResource(() => adminApi.getAnomalyHistory(48), []);
  const alerts = useAdminResource(() => adminApi.getOpsAlerts(5), []);
  const score = getMetricValue(metrics, "mediflow_anomaly_score", 0);

  return (
    <div className="admin-view">
      <ViewHeader title="AIOps & Anomaly" kicker="Infrastructure / Isolation Forest Detection" />
      {!history.ok && !history.loading && <ComingSoon endpoint="/api/admin/anomaly-history" />}
      <Panel className="admin-anomaly-hero">
        <GaugeChart value={score} label="Anomaly Score" size={280} />
        <div>
          <FieldPill tone={score < -0.3 ? "red" : "green"}>{score < -0.3 ? "ANOMALY DETECTED" : "NORMAL"}</FieldPill>
          <h2>Last anomaly events</h2>
          {asArray(alerts.data).slice(0, 5).map((alert) => (
            <p key={alert.id}>{fmtDate(alert.created_at)} - {alert.message}</p>
          ))}
        </div>
      </Panel>
      <Panel title="Booking Volume - Anomaly Detection Windows">
        <MiniChart height={260} />
      </Panel>
      <Panel title="Isolation Forest Model Info">
        <div className="admin-info-grid">
          <span>Training info: synthetic booking patterns</span>
          <span>Contamination: 0.05</span>
          <span>n_estimators: 100</span>
          <span>Model file: /models/anomaly_detector.pkl</span>
        </div>
      </Panel>
    </div>
  );
}
