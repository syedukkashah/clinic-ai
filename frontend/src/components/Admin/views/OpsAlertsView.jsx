import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import { useAdminResource } from "../shared/hooks";
import { FieldPill, Panel, ViewHeader, asArray, fmtDate } from "./ViewHelpers";

export default function OpsAlertsView() {
  const alerts = useAdminResource(() => adminApi.getOpsAlerts(100), []);
  const rows = asArray(alerts.data);
  const stats = {
    total: rows.length,
    critical: rows.filter((row) => row.severity === "critical").length,
    warning: rows.filter((row) => row.severity === "warning").length,
    info: rows.filter((row) => row.severity === "info").length,
    unacked: rows.filter((row) => !row.acknowledged).length,
  };

  return (
    <div className="admin-view">
      <ViewHeader title="Ops Alerts" kicker="Logs / AIOps Reasoning Output" />
      <Panel>
        <div className="admin-summary-strip">
          <span>Total: {stats.total}</span>
          <span>Critical: {stats.critical}</span>
          <span>Warning: {stats.warning}</span>
          <span>Info: {stats.info}</span>
          <span>Unacknowledged: {stats.unacked}</span>
        </div>
      </Panel>
      <Panel title="Alert Log">
        <DataTable
          rows={rows}
          columns={[
            { key: "id", label: "#", render: (row) => <code>{row.id}</code> },
            { key: "severity", label: "Severity", render: (row) => <FieldPill tone={row.severity === "critical" ? "red" : row.severity === "warning" ? "amber" : "blue"}>{row.severity || "info"}</FieldPill> },
            { key: "message", label: "Message", render: (row) => <span dir="auto">{row.message || row.title}</span> },
            { key: "triggered_by", label: "Triggered By", render: (row) => row.triggered_by || row.source || "ops_monitor" },
            { key: "steps_taken", label: "Steps Taken", render: (row) => row.steps_taken || row.recommendation || "--" },
            { key: "created_at", label: "Created At", render: (row) => fmtDate(row.created_at || row.timestamp) },
            { key: "acknowledged", label: "Acknowledged", render: (row) => row.acknowledged ? "yes" : "no" },
          ]}
        />
      </Panel>
    </div>
  );
}
