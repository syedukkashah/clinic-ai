import { adminApi } from "@/api/adminApi";
import { getMetricSamples } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import StatCard from "../shared/StatCard";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, isUrdu } from "./ViewHelpers";

export default function VoicePipelineView() {
  const { metrics } = useMetrics();
  const sessions = useAdminResource(() => adminApi.getVoiceSessions(20), []);
  const stt = getMetricSamples(metrics, "mediflow_stt_calls_total");
  const total = stt.reduce((sum, sample) => sum + Number(sample.value || 0), 0);
  const urdu = stt.filter((sample) => /ur|urdu/i.test(sample.labels?.lang || "")).reduce((sum, sample) => sum + Number(sample.value || 0), 0);

  return (
    <div className="admin-view">
      <ViewHeader title="Voice Pipeline" kicker="Infrastructure / STT, WebRTC, Twilio" />
      <div className="admin-kpi-grid admin-kpi-grid--five">
        <StatCard label="Voice Sessions" value={total} tone="blue" />
        <StatCard label="Groq Whisper Calls" value={providerTotal(stt, "groq")} tone="teal" />
        <StatCard label="Local Fallback Calls" value={providerTotal(stt, "local")} tone="amber" />
        <StatCard label="Urdu Sessions" value={urdu} tone="purple" />
        <StatCard label="English Sessions" value={Math.max(0, total - urdu)} tone="green" />
      </div>
      <div className="admin-grid admin-grid--split">
        <Panel title="Booking Channel Distribution">
          <MiniChart type="bar" height={220} />
        </Panel>
        <Panel title="STT Latency Distribution">
          <MiniChart type="bar" height={220} />
        </Panel>
      </div>
      {!sessions.ok && !sessions.loading && <ComingSoon endpoint="/api/admin/voice-sessions" />}
      <Panel title="Voice Session Log">
        <DataTable
          rows={asArray(sessions.data)}
          columns={[
            { key: "session_id", label: "Session ID", render: (row) => <code>{row.session_id || row.id || "--"}</code> },
            { key: "mode", label: "Mode", render: (row) => <FieldPill tone="blue">{row.mode || "VoiceNote"}</FieldPill> },
            { key: "language", label: "Language" },
            { key: "provider", label: "STT Provider" },
            { key: "transcript", label: "Transcript", render: (row) => <span dir="auto" className={isUrdu(row.transcript) ? "admin-urdu" : ""}>{row.transcript || "--"}</span> },
            { key: "outcome", label: "Outcome" },
          ]}
        />
      </Panel>
    </div>
  );
}

function providerTotal(samples, provider) {
  return samples
    .filter((sample) => String(sample.labels?.provider || "").toLowerCase().includes(provider))
    .reduce((sum, sample) => sum + Number(sample.value || 0), 0);
}
