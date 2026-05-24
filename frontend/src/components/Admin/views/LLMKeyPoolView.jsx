import { getMetricSamples } from "@/api/prometheusParser";
import { adminApi } from "@/api/adminApi";
import { useMetrics } from "@/context/MetricsContext";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import { FieldPill, Panel, ViewHeader, asArray } from "./ViewHelpers";
import { useAdminResource } from "../shared/hooks";

const providers = [
  { id: "gemini", name: "Gemini", role: "Primary Reasoning", tone: "teal", tier: 1 },
  { id: "groq", name: "Groq", role: "Fast Extraction", tone: "blue", tier: 2 },
  { id: "together", name: "Together", role: "Overflow", tone: "amber", tier: 3 },
  { id: "openrouter", name: "OpenRouter", role: "Last Resort", tone: "purple", tier: 4 },
];

export default function LLMKeyPoolView() {
  const { metrics } = useMetrics();
  const keySamples = getMetricSamples(metrics, "mediflow_key_pool_available");
  const callSamples = getMetricSamples(metrics, "mediflow_llm_calls_total");
  const keyEvents = useAdminResource(() => adminApi.getKeyEvents(), []);

  return (
    <div className="admin-view">
      <ViewHeader title="LLM Key Pool" kicker="Infrastructure / DevOps Fallback Router" />
      <div className="admin-provider-grid">
        {providers.map((provider) => {
          const available = Number(keySamples.find((sample) => sample.labels?.provider?.toLowerCase() === provider.id)?.value ?? 0);
          const calls = callSamples
            .filter((sample) => sample.labels?.provider?.toLowerCase() === provider.id)
            .reduce((sum, sample) => sum + Number(sample.value || 0), 0);
          return (
            <Panel key={provider.id} className={`admin-provider-card ${available === 0 ? "is-limited" : ""}`}>
              {available === 0 && <div className="admin-rate-banner">ALL KEYS RATE LIMITED</div>}
              <h2>{provider.name}</h2>
              <FieldPill tone={provider.tone}>{provider.role}</FieldPill>
              <strong>{available} / 6 keys available</strong>
              <div className="admin-key-row">
                {Array.from({ length: 6 }).map((_, index) => (
                  <span key={index} className={index < available ? "is-on" : ""}>K</span>
                ))}
              </div>
              <p>{calls} calls observed</p>
              <FieldPill tone="blue">Tier {provider.tier}</FieldPill>
            </Panel>
          );
        })}
      </div>
      <Panel title="Fallback Chain - Live Load Distribution">
        <div className="admin-flow">
          {["Request", "Gemini?", "Groq?", "Together?", "OpenRouter"].map((node) => (
            <span key={node}>{node}</span>
          ))}
        </div>
        <MiniChart type="bar" data={[providerTotals(callSamples)]} keys={["gemini", "groq", "together", "openrouter"]} height={240} />
      </Panel>
      <Panel title="Per-Key Rate Limit Event Log">
        <DataTable
          rows={asArray(keyEvents.data)}
          columns={[
            { key: "key", label: "Key" },
            { key: "provider", label: "Provider", render: (row) => <FieldPill tone="amber">{row.provider}</FieldPill> },
            { key: "rate_limited_at", label: "Rate Limited At" },
            { key: "unblocked_at", label: "Unblocked At" },
            { key: "duration_seconds", label: "Duration", render: (row) => `${row.duration_seconds || 0}s` },
          ]}
        />
      </Panel>
    </div>
  );
}

function providerTotals(samples) {
  const totals = { name: "now", gemini: 0, groq: 0, together: 0, openrouter: 0 };
  samples.forEach((sample) => {
    const key = sample.labels?.provider?.toLowerCase();
    if (key in totals) totals[key] += Number(sample.value || 0);
  });
  return totals;
}
