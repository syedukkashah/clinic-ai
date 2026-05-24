import { useMemo, useState } from "react";
import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import HeatmapGrid from "../shared/HeatmapGrid";
import MiniChart from "../shared/MiniChart";
import SkeletonLoader from "../shared/SkeletonLoader";
import { useAdminResource } from "../shared/hooks";
import { FieldPill, Panel, ViewHeader, asArray, valueTone } from "./ViewHelpers";

export default function DoctorSlotsView() {
  const doctors = useAdminResource(() => adminApi.getDoctors(), []);
  const rows = asArray(doctors.data);
  const [selectedId, setSelectedId] = useState(null);
  const selected = rows.find((doctor) => doctor.id === selectedId) || rows[0];
  const today = new Date().toISOString().slice(0, 10);
  const availability = useAdminResource(
    () => (selected?.id ? adminApi.getSlots(selected.id, today) : Promise.resolve({ ok: true, data: [] })),
    [selected?.id],
  );

  const slotRows = useMemo(() => asArray(availability.data?.items || availability.data?.slots || availability.data), [availability.data]);

  return (
    <div className="admin-view">
      <ViewHeader title="Doctors & Slots" kicker="Clinic Ops / Capacity Control" />
      <div className="admin-doctor-layout">
        <Panel title="Doctors" className="admin-doctor-list-panel">
          {doctors.loading ? (
            <SkeletonLoader rows={8} />
          ) : (
            rows.map((doctor) => (
              <button
                key={doctor.id}
                className={`admin-doctor-card ${selected?.id === doctor.id ? "is-active" : ""}`}
                onClick={() => setSelectedId(doctor.id)}
              >
                <strong>{doctor.name}</strong>
                <FieldPill tone="blue">{doctor.specialty || "general"}</FieldPill>
                <span>EN / UR</span>
                <div style={{ "--load": `${Math.min(100, Number(doctor.peak_hour_patients || 4) * 8)}%` }} />
              </button>
            ))
          )}
        </Panel>
        <Panel title={`${selected?.name || "Select doctor"} - Today's Schedule`}>
          <MiniChart type="bar" data={forecastBars(selected)} height={140} />
          <div className="admin-spacer" />
          <HeatmapGrid rows={selected ? [{ name: selected.name, values: forecastValues(selected) }] : []} />
          <div className="admin-spacer" />
          <DataTable
            rows={slotRows}
            pageSize={10}
            columns={[
              { key: "time", label: "Time", render: (row) => row.time || row.start_time || row.slot_time || "--" },
              { key: "patient", label: "Patient", render: (row) => row.patient_name || <em>Available</em> },
              { key: "predicted_wait", label: "Pred. Wait", render: (row) => <span className={`admin-text-${valueTone(row.predicted_wait_minutes)}`}>{row.predicted_wait_minutes || "--"} min</span> },
              { key: "actual_wait", label: "Actual Wait", render: (row) => row.actual_wait_minutes || "pending" },
              { key: "status", label: "Status", render: (row) => <FieldPill tone={row.status === "booked" ? "green" : "blue"}>{row.status || "available"}</FieldPill> },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

function forecastValues(doctor) {
  const base = Number(doctor?.peak_hour_patients || 4);
  return Array.from({ length: 13 }).map((_, index) => Math.max(0, Math.round(base + Math.sin(index / 2) * 2)));
}

function forecastBars(doctor) {
  return forecastValues(doctor).map((value, index) => ({ name: `${8 + index}:00`, value }));
}
