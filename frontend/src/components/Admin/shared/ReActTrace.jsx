import StatusPill from "./StatusPill";

export default function ReActTrace({ steps = [], empty = "Select a run to inspect its ReAct trace" }) {
  if (!steps.length) {
    return <div className="admin-trace-empty">{empty}</div>;
  }

  const providers = [...new Set(steps.map((step) => step.provider).filter(Boolean))].join(" + ");
  const total = steps.reduce((sum, step) => sum + Number(step.latencyMs || step.duration_ms || 0), 0);

  return (
    <div className="admin-react-trace">
      {steps.map((step, index) => {
        const type = String(step.type || "ACT").toUpperCase();
        return (
          <article
            key={step.id || `${type}-${index}`}
            className={`admin-trace-step admin-trace-step--${type.toLowerCase()}`}
            style={{ animationDelay: `${index * 150}ms` }}
          >
            <div className="admin-trace-step__num">{index + 1}</div>
            <div className="admin-trace-step__body">
              <div className="admin-trace-step__top">
                <StatusPill tone={type === "CONCLUDE" ? "amber" : type === "OBSERVE" ? "blue" : "teal"} dot={false}>
                  {type}
                </StatusPill>
                <span>{formatLatency(step.latencyMs || step.duration_ms)}</span>
              </div>
              <h4>{step.tool || step.toolName || "agent_step"}</h4>
              <p className={`admin-provider admin-provider--${String(step.provider || "groq").toLowerCase()}`}>
                via {capitalize(step.provider || "groq")}
              </p>
              <pre>{JSON.stringify(step.args || step.arguments || {}, null, 2)}</pre>
              <pre>{typeof step.result === "string" ? step.result : JSON.stringify(step.result || "Completed", null, 2)}</pre>
            </div>
          </article>
        );
      })}
      <div className="admin-trace-footer">
        Return {steps.length} steps - {providers || "Groq"} - {total}ms
      </div>
    </div>
  );
}

function formatLatency(value) {
  const ms = Number(value || 0);
  return ms ? `${(ms / 1000).toFixed(1)}s` : "0.0s";
}

function capitalize(value) {
  return String(value).slice(0, 1).toUpperCase() + String(value).slice(1);
}
