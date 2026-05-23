import { adminApi } from "@/api/adminApi";
import { getMetricSamples } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray } from "./ViewHelpers";

export default function DriftRetrainingView() {
  const { metrics } = useMetrics();
  const driftHistory = useAdminResource(() => adminApi.getDriftHistory(), []);
  const taskHistory = useAdminResource(() => adminApi.getCeleryTasks("retrain", 10), []);
  const driftSamples = getMetricSamples(metrics, "mediflow_model_drift_score");

  return (
    <div className="admin-view">
      <ViewHeader title="Drift & Retraining" kicker="MLOps / Model Governance" />
      {!driftHistory.ok && !driftHistory.loading && <ComingSoon endpoint="/api/admin/ml/drift-history" />}
      <div className="admin-grid admin-grid--split">
        {["wait_time_model", "patient_load_model"].map((name) => {
          const value = Number(driftSamples.find((sample) => sample.labels?.model_name === name)?.value || 0);
          return (
            <Panel key={name} title={name}>
              <div className="admin-drift-card" style={{ "--drift": `${Math.min(100, value * 500)}%` }}>
                <strong className={`admin-text-${value >= 0.1 ? "red" : value >= 0.05 ? "amber" : "green"}`}>{value.toFixed(3)}</strong>
                <FieldPill tone={value >= 0.1 ? "red" : "green"}>{value >= 0.1 ? "DRIFT WARNING" : "DRIFT OK"}</FieldPill>
                <div />
                <p>Insufficient samples (min 200 required) is shown by backend when the guard trips.</p>
              </div>
            </Panel>
          );
        })}
      </div>
      <Panel title="Drift History">
        <MiniChart type="line" keys={["value", "p95"]} height={220} />
      </Panel>
      <Panel title="Retraining Pipeline Runs">
        {!taskHistory.ok && !taskHistory.loading && <ComingSoon endpoint="/api/admin/celery/task-history?task=retrain" />}
        <DataTable rows={asArray(taskHistory.data)} columns={["run_time", "model", "trigger", "old_metric", "new_metric", "outcome"].map((key) => ({ key, label: key }))} />
      </Panel>
    </div>
  );
}
