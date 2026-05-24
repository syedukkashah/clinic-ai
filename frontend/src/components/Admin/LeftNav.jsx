import { useEffect, useState } from "react";
import { adminApi } from "@/api/adminApi";
import StatusPill from "./shared/StatusPill";

export const adminNavGroups = [
  { label: "Overview", items: [{ id: "dashboard", label: "Dashboard" }] },
  {
    label: "Clinic Ops",
    items: [
      { id: "appointments", label: "Appointments" },
      { id: "doctors-slots", label: "Doctors & Slots" },
      { id: "notifications", label: "Notifications" },
    ],
  },
  {
    label: "AI Agents",
    items: [
      { id: "booking-agent", label: "Booking Agent" },
      { id: "scheduling-agent", label: "Scheduling Agent" },
      { id: "ops-monitor-agent", label: "Ops Monitor Agent" },
    ],
  },
  {
    label: "ML Models",
    items: [
      { id: "wait-time-model", label: "Wait Time Model" },
      { id: "load-forecast-model", label: "Load Forecast Model" },
      { id: "mlflow-registry", label: "MLflow Registry" },
      { id: "drift-retraining", label: "Drift & Retraining" },
    ],
  },
  {
    label: "Infrastructure",
    items: [
      { id: "llm-key-pool", label: "LLM Key Pool" },
      { id: "voice-pipeline", label: "Voice Pipeline" },
      { id: "aiops-anomaly", label: "AIOps & Anomaly" },
      { id: "devops-ci-cd", label: "DevOps / CI-CD" },
      { id: "system-metrics", label: "System Metrics" },
    ],
  },
  {
    label: "Logs",
    items: [
      { id: "ops-alerts", label: "Ops Alerts" },
      { id: "predictions-log", label: "Predictions Log" },
      { id: "agent-run-log", label: "Agent Run Log" },
    ],
  },
];

export default function LeftNav({ active, onNavigate }) {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let mounted = true;
    adminApi.getDbHealth().then((result) => {
      if (mounted) setHealth(result.ok ? result.data : null);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <aside className="admin-leftnav">
      <nav>
        {adminNavGroups.map((group) => (
          <section key={group.label}>
            <h3>{group.label}</h3>
            {group.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={active === item.id ? "is-active" : ""}
                onClick={() => onNavigate(item.id)}
              >
                <i />
                {item.label}
              </button>
            ))}
          </section>
        ))}
      </nav>
      <div className="admin-leftnav__health">
        <HealthRow label="API" ok={Boolean(health)} />
        <HealthRow label="DB" ok={Boolean(health?.database)} />
        <HealthRow label="Redis" ok={false} unknown />
      </div>
    </aside>
  );
}

function HealthRow({ label, ok, unknown }) {
  return (
    <div>
      <span>{label}</span>
      <StatusPill tone={unknown ? "amber" : ok ? "green" : "red"}>{unknown ? "UNKNOWN" : ok ? "HEALTHY" : "DOWN"}</StatusPill>
    </div>
  );
}
