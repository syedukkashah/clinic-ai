import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import ReActTrace from "../shared/ReActTrace";
import TimelineBar from "../shared/TimelineBar";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, Panel, ViewHeader, asArray, sampleTrace } from "./ViewHelpers";

export default function SchedulingAgentView() {
  const runs = useAdminResource(() => adminApi.getAgentRuns("scheduling", 10), []);
  const doctors = useAdminResource(() => adminApi.getDoctors(), []);
  const reassignments = useAdminResource(() => adminApi.getReassignments(20), []);

  return (
    <div className="admin-view">
      <ViewHeader title="Scheduling Agent" kicker="AI Agents / Celery Beat Load Balancer" />
      {!runs.ok && !runs.loading && <ComingSoon endpoint="/api/admin/agent-runs?agent=scheduling" />}
      <Panel title="Celery Beat Timeline">
        <TimelineBar nextLabel="Next run countdown requires task-history endpoint" />
      </Panel>
      <div className="admin-grid admin-grid--split">
        <Panel title="Slot Reassignments">
          {!reassignments.ok && !reassignments.loading && <ComingSoon endpoint="/api/admin/reassignments" />}
          <DataTable
            rows={asArray(reassignments.data)}
            columns={[
              { key: "appointment_id", label: "Appointment" },
              { key: "from_doctor", label: "From", render: (row) => row.from_doctor || row.from_doctor_id || "--" },
              { key: "to_doctor", label: "To", render: (row) => row.to_doctor || row.to_doctor_id || "--" },
              { key: "reason", label: "Reason" },
              {
                key: "wait",
                label: "Wait",
                render: (row) => `${row.predicted_wait_before ?? "--"} min -> ${row.predicted_wait_after ?? "pending"} min`,
              },
            ]}
          />
        </Panel>
        <Panel title="Doctor Load Summary">
          <div className="admin-load-list">
            {asArray(doctors.data).map((doctor) => {
              const load = Math.min(100, Number(doctor.peak_hour_patients || 4) * 8);
              return (
                <div key={doctor.id} style={{ "--load": `${load}%` }}>
                  <strong>{doctor.name}</strong>
                  <span>{doctor.specialty}</span>
                  <i />
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
      <Panel title="Last Run Trace">
        <ReActTrace steps={asArray(runs.data)[0]?.steps || sampleTrace("Gemini")} />
      </Panel>
    </div>
  );
}
