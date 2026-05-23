import UnavailableBanner from "../shared/UnavailableBanner";

export function ViewHeader({ title, kicker, children }) {
  return (
    <div className="admin-view-header admin-panel-reveal">
      <div>
        <p>{kicker}</p>
        <h1>{title}</h1>
      </div>
      {children}
    </div>
  );
}

export function Panel({ title, action, children, className = "" }) {
  return (
    <section className={`admin-panel admin-panel-reveal ${className}`}>
      {(title || action) && (
        <header className="admin-panel__header">
          <h2>{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function ComingSoon({ endpoint, children }) {
  return (
    <div className="admin-coming-soon-wrap">
      <UnavailableBanner message="Not yet implemented - Coming soon" />
      {endpoint && <code>{endpoint}</code>}
      {children}
    </div>
  );
}

export function FieldPill({ tone = "teal", children }) {
  return <span className={`admin-field-pill admin-field-pill--${tone}`}>{children}</span>;
}

export function valueTone(value, warn = 20, critical = 35) {
  const numeric = Number(value) || 0;
  if (numeric >= critical) return "red";
  if (numeric >= warn) return "amber";
  return "green";
}

export function isUrdu(text = "") {
  return /[\u0600-\u06FF]/.test(String(text));
}

export function asArray(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

export function fmtDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function sampleTrace(provider = "Groq") {
  return [
    {
      type: "ACT",
      tool: "inspect_operational_state",
      provider,
      latencyMs: 420,
      args: { source: "live_backend" },
      result: "Route exists; waiting for persisted run traces.",
    },
    {
      type: "CONCLUDE",
      tool: "render_admin_surface",
      provider: "Gemini",
      latencyMs: 680,
      args: { mode: "graceful_degradation" },
      result: "Dashboard shows real metrics where available and clear coming-soon states elsewhere.",
    },
  ];
}
