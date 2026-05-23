import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, valueTone } from "./ViewHelpers";

export default function WaitTimeModelView() {
  const status = useAdminResource(() => adminApi.getModelStatus("wait_time_model"), []);
  const predictions = useAdminResource(() => adminApi.getPredictionsWaitTime({ doctor_id: 1, hour: new Date().getHours(), queue_depth: 3 }), []);
  const rows = asArray(status.data?.predictions);

  return (
    <div className="admin-view">
      <ViewHeader title="Wait Time Model" kicker="ML Models / XGBoost Wait Prediction" />
      {!status.ok && !status.loading && <ComingSoon endpoint="/api/admin/ml/model-status?name=wait_time_model" />}
      <Panel title="Model Status">
        <div className="admin-model-hero">
          <div>
            <h2>wait_time_model</h2>
            <FieldPill tone="green">Production</FieldPill>
            <strong>{predictions.data?.predicted_wait_minutes || "--"} min</strong>
            <span>latest live prediction</span>
          </div>
          <div className="admin-feature-pills">
            {["doctor_id", "specialty", "day_of_week", "hour_of_day", "queue_depth", "appointments_before"].map((feature) => (
              <FieldPill key={feature} tone="purple">{feature}</FieldPill>
            ))}
          </div>
        </div>
      </Panel>
      <div className="admin-grid admin-grid--split">
        <Panel title="Predicted vs Actual Wait">
          <MiniChart type="line" height={220} />
        </Panel>
        <Panel title="Prediction Error Distribution">
          <MiniChart type="bar" height={220} />
        </Panel>
      </div>
      <Panel title="Recent Predictions">
        <DataTable
          rows={rows}
          columns={[
            { key: "appointment_id", label: "Appointment ID" },
            { key: "doctor", label: "Doctor" },
            { key: "predicted", label: "Predicted Wait", render: (row) => `${row.predicted_wait_minutes || row.predicted || "--"} min` },
            { key: "actual", label: "Actual Wait", render: (row) => row.actual_wait_minutes || "pending" },
            { key: "error", label: "Error", render: (row) => <span className={`admin-text-${valueTone(Math.abs(row.error || 0), 5, 15)}`}>{row.error ?? "--"}</span> },
            { key: "resolved_at", label: "Resolved At", render: (row) => fmtDate(row.resolved_at) },
          ]}
        />
      </Panel>
    </div>
  );
}
