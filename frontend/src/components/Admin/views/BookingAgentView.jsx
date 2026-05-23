import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import ReActTrace from "../shared/ReActTrace";
import SkeletonLoader from "../shared/SkeletonLoader";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, sampleTrace } from "./ViewHelpers";

export default function BookingAgentView() {
  const runs = useAdminResource(() => adminApi.getAgentRuns("booking", 20), []);
  const agents = useAdminResource(() => adminApi.getAgents(), []);
  const booking = asArray(agents.data?.agents || agents.data).find((agent) => /booking/i.test(agent.name || agent.agent || ""));
  const rows = asArray(runs.data);

  return (
    <div className="admin-view">
      <ViewHeader title="Booking Agent" kicker="AI Agents / ReAct Booking Loop">
        <FieldPill tone="teal">MAX_STEPS 5 text / 3 voice</FieldPill>
      </ViewHeader>
      {!runs.ok && !runs.loading && <ComingSoon endpoint="/api/admin/agent-runs?agent=booking" />}
      <div className="admin-grid admin-grid--split">
        <Panel title="Run List">
          {runs.loading ? (
            <SkeletonLoader rows={8} />
          ) : (
            <DataTable
              rows={rows}
              columns={[
                { key: "run_id", label: "Run ID", render: (row) => <code>{String(row.run_id || row.id || "--").slice(0, 12)}</code> },
                { key: "mode", label: "Mode", render: (row) => <FieldPill tone="blue">{row.mode || "TEXT"}</FieldPill> },
                { key: "language", label: "Lang", render: (row) => row.language || "--" },
                { key: "outcome", label: "Outcome", render: (row) => <FieldPill tone="green">{row.outcome || "--"}</FieldPill> },
                { key: "started_at", label: "Started", render: (row) => fmtDate(row.started_at) },
              ]}
            />
          )}
        </Panel>
        <Panel title="Run Detail">
          <div className="admin-agent-summary">
            <span>Runs today: {booking?.runs_today || booking?.runs || 0}</span>
            <span>Status: {booking?.status || "idle"}</span>
            <span>Avg time: {booking?.avg_duration_ms ? `${Math.round(booking.avg_duration_ms / 1000)}s` : "--"}</span>
          </div>
          <ReActTrace steps={rows[0]?.tool_calls || rows[0]?.steps || sampleTrace("Groq")} />
        </Panel>
      </div>
    </div>
  );
}
