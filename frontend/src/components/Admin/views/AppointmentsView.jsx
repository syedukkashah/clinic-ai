import { useMemo, useState } from "react";
import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import SkeletonLoader from "../shared/SkeletonLoader";
import { useAdminResource } from "../shared/hooks";
import { FieldPill, Panel, ViewHeader, asArray, fmtDate, valueTone } from "./ViewHelpers";

export default function AppointmentsView() {
  const [status, setStatus] = useState("all");
  const appointments = useAdminResource(() => adminApi.getAppointments({ limit: 100 }), []);
  const doctors = useAdminResource(() => adminApi.getDoctors(), []);
  const rows = useMemo(() => {
    const all = asArray(appointments.data);
    return status === "all" ? all : all.filter((row) => String(row.status || "").toLowerCase() === status);
  }, [appointments.data, status]);

  const summary = {
    total: rows.length,
    confirmed: rows.filter((row) => row.status === "confirmed").length,
    rescheduled: rows.filter((row) => row.status === "rescheduled").length,
    cancelled: rows.filter((row) => row.status === "cancelled").length,
  };

  return (
    <div className="admin-view">
      <ViewHeader title="Appointments" kicker="Clinic Ops / Live Booking Ledger">
        <select className="admin-input" aria-label="Doctor filter">
          <option>All doctors</option>
          {asArray(doctors.data).map((doctor) => (
            <option key={doctor.id}>{doctor.name}</option>
          ))}
        </select>
      </ViewHeader>

      <Panel>
        <div className="admin-filter-row">
          <input className="admin-input" type="date" defaultValue={new Date().toISOString().slice(0, 10)} />
          {["all", "confirmed", "rescheduled", "cancelled"].map((item) => (
            <button key={item} className={status === item ? "is-active" : ""} onClick={() => setStatus(item)}>
              {item}
            </button>
          ))}
          <input className="admin-input" placeholder="Search patient or appointment ID" />
        </div>
        <div className="admin-summary-strip">
          <span>Total: {summary.total}</span>
          <span>Confirmed: {summary.confirmed}</span>
          <span>Rescheduled: {summary.rescheduled}</span>
          <span>Cancelled: {summary.cancelled}</span>
        </div>
      </Panel>

      <Panel title="Appointment Table">
        {appointments.loading ? (
          <SkeletonLoader rows={8} />
        ) : (
          <DataTable
            rows={rows}
            columns={[
              { key: "id", label: "ID", render: (row) => <code>{String(row.id || row.appointment_id || "--").slice(0, 8)}</code> },
              { key: "patient", label: "Patient", render: (row) => row.patient_name || row.patient?.name || row.patient_id || "--" },
              { key: "doctor", label: "Doctor", render: (row) => row.doctor_name || row.doctor?.name || row.doctor_id || "--" },
              { key: "specialty", label: "Specialty", render: (row) => <FieldPill tone="blue">{row.specialty || row.doctor?.specialty || "general"}</FieldPill> },
              { key: "time", label: "Time", render: (row) => fmtDate(row.scheduled_at || row.appointment_time || row.time) },
              { key: "predicted_wait", label: "Pred. Wait", render: (row) => <span className={`admin-text-${valueTone(row.predicted_wait_minutes || row.predicted_wait)}`}>{row.predicted_wait_minutes || row.predicted_wait || "--"} min</span> },
              { key: "actual_wait", label: "Actual Wait", render: (row) => row.actual_wait_minutes ? `${row.actual_wait_minutes} min` : "pending" },
              { key: "channel", label: "Channel", render: (row) => row.booking_channel || row.channel || "chat" },
              { key: "status", label: "Status", render: (row) => <FieldPill tone={row.status === "cancelled" ? "red" : row.status === "rescheduled" ? "amber" : "green"}>{row.status || "pending"}</FieldPill> },
            ]}
          />
        )}
      </Panel>
    </div>
  );
}
