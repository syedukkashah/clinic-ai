import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, isUrdu } from "./ViewHelpers";

export default function NotificationsView() {
  const notifications = useAdminResource(() => adminApi.getNotifications(50), []);
  const rows = asArray(notifications.data);

  return (
    <div className="admin-view">
      <ViewHeader title="Notifications" kicker="Clinic Ops / Patient and Doctor Messaging">
        <FieldPill tone="amber">MOCK MODE - No real SMS/email sent</FieldPill>
      </ViewHeader>
      {!notifications.ok && !notifications.loading && <ComingSoon endpoint="/api/admin/notifications" />}
      <Panel title="Notification Ledger">
        <DataTable
          rows={rows}
          columns={[
            { key: "id", label: "ID", render: (row) => <code>{row.id || "--"}</code> },
            { key: "type", label: "Type", render: (row) => <FieldPill tone={row.type === "doctor" ? "blue" : "teal"}>{row.type || "patient"}</FieldPill> },
            { key: "recipient", label: "Recipient", render: (row) => row.recipient || "--" },
            { key: "message", label: "Message", render: (row) => <span dir="auto" className={isUrdu(row.message) ? "admin-urdu" : ""}>{row.message || "--"}</span> },
            { key: "language", label: "Language", render: (row) => row.language || "--" },
            { key: "created_at", label: "Sent At", render: (row) => fmtDate(row.created_at) },
          ]}
        />
      </Panel>
    </div>
  );
}
