export default function AgentTrace({
  open,
  onToggle,
  steps = [],
  active = false,
  mobileSheetOpen = false,
  onMobileToggle,
}) {
  const providerCounts = steps.reduce((acc, step) => {
    if (step.provider) acc[step.provider] = (acc[step.provider] || 0) + 1;
    return acc;
  }, {});
  const providerSummary = Object.entries(providerCounts)
    .map(([provider, count]) => `${capitalize(provider)}(${count})`)
    .join(" + ");
  const totalLatency = steps.reduce((sum, step) => sum + Number(step.latencyMs || 0), 0);

  const content = (
    <>
      <div className="trace-header">
        <div>
          <div className="trace-kicker">Agent Trace</div>
          <h2>Agent Reasoning</h2>
          <p>Live tool calls · ReAct loop</p>
        </div>
        <div className="trace-status">
          <span className={active ? "trace-status__dot trace-status__dot--active" : "trace-status__dot"} />
          <span>{active ? "Active" : "Idle"}</span>
          <code>{steps.length} steps · {(totalLatency / 1000).toFixed(1)}s</code>
        </div>
      </div>

      <div className="trace-list">
        {steps.length === 0 ? (
          <div className="trace-idle">
            <div className="idle-dots">
              <i />
              <i />
              <i />
            </div>
            <p>Waiting for next message...</p>
          </div>
        ) : (
          <>
            {steps.map((step, index) => (
              <TraceStep key={step.id || `${step.type}-${index}`} step={step} index={index} />
            ))}
            <div className="trace-run-divider">
              —— Run complete · {steps.length} steps · {totalLatency || 1800}ms ——
            </div>
            <div className="trace-token-summary">
              ↩ {steps.length} steps · {providerSummary || "Groq(1) + Gemini(1)"} ·{" "}
              {((totalLatency || 2100) / 1000).toFixed(1)}s total
            </div>
          </>
        )}
      </div>
    </>
  );

  return (
    <>
      <aside className={`agent-trace ${open ? "agent-trace--open" : "agent-trace--closed"} reveal reveal-delay-6`}>
        <button type="button" className="trace-tab" onClick={onToggle}>
          Agent Trace
        </button>
        {open && content}
      </aside>

      <button type="button" className="trace-floating-button" onClick={onMobileToggle} aria-label="Open agent trace">
        ⚡
      </button>
      <div className={`trace-bottom-sheet ${mobileSheetOpen ? "trace-bottom-sheet--open" : ""}`}>
        <button type="button" className="trace-sheet-close" onClick={onMobileToggle} aria-label="Close agent trace">
          ×
        </button>
        {content}
      </div>
    </>
  );
}

function TraceStep({ step, index }) {
  const type = (step.type || "ACT").toUpperCase();
  return (
    <article
      className={`trace-step trace-step--${type.toLowerCase()}`}
      style={{ animationDelay: `${index * 150}ms` }}
    >
      <div className="trace-step__badge">{index + 1}</div>
      <div className="trace-step__body">
        <div className="trace-step__top">
          <span className={`trace-pill trace-pill--${type.toLowerCase()}`}>{type}</span>
          <span className="trace-step__latency">{formatLatency(step.latencyMs)}</span>
        </div>
        <div className="trace-step__tool">{step.tool || step.toolName || "booking_agent"}</div>
        <div className="trace-step__provider">via {capitalize(step.provider || "groq")}</div>
        {step.args && <div className="trace-step__args">{stringify(step.args)}</div>}
        {step.result && <div className="trace-step__result">{stringify(step.result)}</div>}
      </div>
    </article>
  );
}

function stringify(value) {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatLatency(value) {
  if (!value) return "0.8s";
  return `${(Number(value) / 1000).toFixed(1)}s`;
}

function capitalize(value) {
  return String(value || "").slice(0, 1).toUpperCase() + String(value || "").slice(1);
}
