import { useEffect, useRef, useState } from "react";
import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import ReActTrace from "../shared/ReActTrace";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate, sampleTrace } from "./ViewHelpers";

export default function AgentRunLogView() {
  const runs = useAdminResource(() => adminApi.getAgentRuns(null, 100), []);
  const rows = asArray(runs.data);
  const [selected, setSelected] = useState(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!selected) return undefined;
    closeRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  return (
    <div className="admin-view">
      <ViewHeader title="Agent Run Log" kicker="Logs / Unified ReAct Audit Trail" />
      {!runs.ok && !runs.loading && <ComingSoon endpoint="/api/admin/agent-runs" />}
      <Panel title="All Agent Runs">
        <DataTable
          rows={rows}
          columns={[
            { key: "run_id", label: "Run ID", render: (row) => <button className="admin-link" onClick={() => setSelected(row)}>{String(row.run_id || row.id || "--").slice(0, 12)}</button> },
            { key: "agent", label: "Agent" },
            { key: "mode", label: "Mode" },
            { key: "language", label: "Language" },
            { key: "steps", label: "Steps", render: (row) => `${row.steps?.length || row.tool_calls?.length || 0} steps` },
            { key: "providers", label: "Providers Used", render: (row) => <ProviderPills providers={row.providers || row.providers_used} /> },
            { key: "duration", label: "Duration", render: (row) => row.duration_ms ? `${Math.round(row.duration_ms / 1000)}s` : "--" },
            { key: "outcome", label: "Outcome", render: (row) => <FieldPill tone="green">{row.outcome || "--"}</FieldPill> },
            { key: "started_at", label: "Started At", render: (row) => fmtDate(row.started_at) },
          ]}
        />
      </Panel>
      {selected && (
        <aside className="admin-drawer" role="dialog" aria-modal="true">
          <header>
            <h2>{selected.run_id || selected.id}</h2>
            <button ref={closeRef} onClick={() => setSelected(null)}>Close</button>
          </header>
          <ReActTrace steps={selected.steps || selected.tool_calls || sampleTrace("Groq")} />
        </aside>
      )}
    </div>
  );
}

function ProviderPills({ providers }) {
  const list = Array.isArray(providers) ? providers : String(providers || "").split(/[,+]/).filter(Boolean);
  return (
    <span className="admin-provider-pills">
      {list.map((provider) => (
        <FieldPill key={provider} tone="blue">{String(provider).slice(0, 1).toUpperCase()}</FieldPill>
      ))}
    </span>
  );
}
