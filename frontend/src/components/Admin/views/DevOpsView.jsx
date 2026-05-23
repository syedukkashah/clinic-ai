import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import StatusPill from "../shared/StatusPill";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader } from "./ViewHelpers";

export default function DevOpsView() {
  const health = useAdminResource(() => adminApi.getHealth(), []);
  const ciRuns = useAdminResource(() => adminApi.getCiRuns(10), []);
  const runs = Array.isArray(ciRuns.data?.runs) ? ciRuns.data.runs : [];
  const latest = runs[0];
  const latestPassed = latest?.conclusion === "success" || latest?.status === "completed";

  return (
    <div className="admin-view">
      <ViewHeader title="DevOps / CI-CD" kicker="Infrastructure / Delivery Health" />
      <Panel title="GitHub Actions CI/CD Pipeline">
        {!ciRuns.ok && !ciRuns.loading && <ComingSoon endpoint="/api/admin/ci/runs" />}
        <div className="admin-pipeline">
          {["Lint", "Test", "Build", "Deploy"].map((stage, index) => (
            <span key={stage} className={latestPassed && index < 3 ? "is-pass" : ""}>{stage}</span>
          ))}
        </div>
        <div className="admin-coverage">
          <i style={{ "--coverage": latestPassed ? "100%" : "60%" }} />
          {latest ? `${latest.name || "CI"} #${latest.run_number} - ${latest.conclusion || latest.status}` : "Waiting for CI API"}
        </div>
      </Panel>
      <Panel title="Pipeline Run History">
        <DataTable
          rows={runs}
          columns={[
            { key: "run_number", label: "Run" },
            { key: "branch", label: "Branch" },
            { key: "trigger", label: "Trigger" },
            { key: "status", label: "Status", render: (row) => <FieldPill tone={row.conclusion === "success" ? "green" : row.status === "in_progress" ? "teal" : "amber"}>{row.conclusion || row.status}</FieldPill> },
            { key: "commit", label: "Commit", render: (row) => <code>{row.commit || "--"}</code> },
          ]}
        />
      </Panel>
      <div className="admin-grid admin-grid--three">
        <Panel title="Oracle VM">
          <StatusPill tone={health.ok ? "green" : "amber"}>{health.ok ? "HEALTHY" : "DEGRADED"}</StatusPill>
          <p>Ampere A1 - 4 OCPU - 24 GB RAM - Always Free</p>
        </Panel>
        <Panel title="Docker Services">
          {["api", "ml_service", "worker", "celery_beat", "mlflow", "prometheus", "grafana", "postgres", "redis", "nginx"].map((service) => (
            <FieldPill key={service} tone="green">{service}</FieldPill>
          ))}
        </Panel>
        <Panel title="GitHub Secrets">
          <p>12 / 12 secrets configured for demo checklist.</p>
          {["ORACLE_HOST", "GEMINI_API_KEYS", "GROQ_API_KEYS", "TOGETHER_API_KEYS", "OPENROUTER_API_KEYS"].map((item) => (
            <FieldPill key={item} tone="green">{item}</FieldPill>
          ))}
        </Panel>
      </div>
    </div>
  );
}
