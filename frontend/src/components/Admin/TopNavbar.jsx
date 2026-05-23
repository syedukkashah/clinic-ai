import { useEffect, useState } from "react";
import { getMetricValue } from "@/api/prometheusParser";
import { useMetrics } from "@/context/MetricsContext";
import StatusPill from "./shared/StatusPill";
import { formatAge } from "./shared/hooks";

export default function TopNavbar({ health }) {
  const { metrics, live, setLive, lastUpdated, refresh } = useMetrics();
  const [now, setNow] = useState(() => new Date());
  const anomaly = getMetricValue(metrics, "mediflow_anomaly_score", 0);
  const driftSamples = metrics?.get("mediflow_model_drift_score")?.samples || [];
  const maxDrift = driftSamples.reduce((max, sample) => Math.max(max, Number(sample.value) || 0), 0);
  const apiStatus = health?.status === "ok" || health?.status === "healthy" ? "HEALTHY" : health ? "DEGRADED" : "UNKNOWN";

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <header className="admin-topbar">
      <div className="admin-brand">
        <strong>MediFlow</strong>
        <span>Admin Console</span>
      </div>
      <div className="admin-topbar__status">
        <StatusPill tone={apiStatus === "HEALTHY" ? "green" : "amber"}>{apiStatus}</StatusPill>
        <StatusPill tone={anomaly < -0.3 ? "red" : "green"}>
          {anomaly < -0.3 ? "ANOMALY DETECTED" : "ANOMALY NORMAL"}
        </StatusPill>
        <StatusPill tone={maxDrift >= 0.1 ? "amber" : "green"}>
          {maxDrift >= 0.1 ? "DRIFT WARNING" : "DRIFT OK"}
        </StatusPill>
      </div>
      <div className="admin-topbar__right">
        <button type="button" className={`admin-live ${live ? "is-live" : ""}`} onClick={() => setLive(!live)}>
          <i />
          LIVE
        </button>
        <button type="button" className="admin-ghost" onClick={refresh}>
          Updated {formatAge(lastUpdated)}
        </button>
        <span className="admin-separator" />
        <time>{now.toISOString().slice(11, 19)} UTC</time>
      </div>
    </header>
  );
}
