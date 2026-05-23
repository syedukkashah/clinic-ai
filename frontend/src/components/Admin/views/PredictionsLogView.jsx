import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, valueTone } from "./ViewHelpers";

export default function PredictionsLogView() {
  const predictions = useAdminResource(() => adminApi.getPredictions(null, 50), []);
  const wait = useAdminResource(() => adminApi.getPredictionsWaitTime({ doctor_id: 1, hour: new Date().getHours(), queue_depth: 3 }), []);
  const load = useAdminResource(() => adminApi.getPredictionsLoad({ doctor_id: 1, hour: new Date().getHours(), day_of_week: new Date().getDay() }), []);
  const rows = asArray(predictions.data);

  return (
    <div className="admin-view">
      <ViewHeader title="Predictions Log" kicker="Logs / Ground Truth Collection" />
      {!predictions.ok && !predictions.loading && <ComingSoon endpoint="/api/admin/ml/predictions" />}
      <Panel>
        <div className="admin-summary-strip">
          <span>Latest wait prediction: {wait.data?.predicted_wait_minutes || "--"} min</span>
          <span>Latest load prediction: {load.data?.predicted_load || load.data?.patients || "--"} patients</span>
          <span>Resolver: resolve_completed_appointments</span>
        </div>
      </Panel>
      <Panel title="Prediction Ledger">
        <DataTable
          rows={rows}
          columns={[
            { key: "id", label: "ID" },
            { key: "model", label: "Model", render: (row) => <FieldPill tone="purple">{row.model || row.model_name}</FieldPill> },
            { key: "version", label: "Version" },
            { key: "appointment_id", label: "Appointment ID" },
            { key: "predicted", label: "Predicted" },
            { key: "actual", label: "Actual", render: (row) => row.actual_value ?? "--" },
            { key: "error", label: "Error", render: (row) => <span className={`admin-text-${valueTone(Math.abs(row.error || 0), 5, 15)}`}>{row.error ?? "--"}</span> },
            { key: "predicted_at", label: "Predicted At", render: (row) => fmtDate(row.predicted_at) },
            { key: "status", label: "Status", render: (row) => <FieldPill tone={row.actual_value == null ? "amber" : "green"}>{row.actual_value == null ? "PENDING" : "RESOLVED"}</FieldPill> },
          ]}
        />
      </Panel>
    </div>
  );
}
