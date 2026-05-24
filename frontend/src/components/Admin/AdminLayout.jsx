import { useEffect, useMemo, useState } from "react";
import { MetricsProvider } from "@/context/MetricsContext";
import { adminApi } from "@/api/adminApi";
import TopNavbar from "./TopNavbar";
import LeftNav, { adminNavGroups } from "./LeftNav";
import DashboardView from "./views/DashboardView";
import AppointmentsView from "./views/AppointmentsView";
import DoctorSlotsView from "./views/DoctorSlotsView";
import NotificationsView from "./views/NotificationsView";
import BookingAgentView from "./views/BookingAgentView";
import SchedulingAgentView from "./views/SchedulingAgentView";
import OpsMonitorView from "./views/OpsMonitorView";
import WaitTimeModelView from "./views/WaitTimeModelView";
import LoadForecastView from "./views/LoadForecastView";
import MLflowRegistryView from "./views/MLflowRegistryView";
import DriftRetrainingView from "./views/DriftRetrainingView";
import LLMKeyPoolView from "./views/LLMKeyPoolView";
import VoicePipelineView from "./views/VoicePipelineView";
import AIOpsView from "./views/AIOpsView";
import DevOpsView from "./views/DevOpsView";
import SystemMetricsView from "./views/SystemMetricsView";
import OpsAlertsView from "./views/OpsAlertsView";
import PredictionsLogView from "./views/PredictionsLogView";
import AgentRunLogView from "./views/AgentRunLogView";

const viewMap = {
  dashboard: DashboardView,
  appointments: AppointmentsView,
  "doctors-slots": DoctorSlotsView,
  notifications: NotificationsView,
  "booking-agent": BookingAgentView,
  "scheduling-agent": SchedulingAgentView,
  "ops-monitor-agent": OpsMonitorView,
  "wait-time-model": WaitTimeModelView,
  "load-forecast-model": LoadForecastView,
  "mlflow-registry": MLflowRegistryView,
  "drift-retraining": DriftRetrainingView,
  "llm-key-pool": LLMKeyPoolView,
  "voice-pipeline": VoicePipelineView,
  "aiops-anomaly": AIOpsView,
  "devops-ci-cd": DevOpsView,
  "system-metrics": SystemMetricsView,
  "ops-alerts": OpsAlertsView,
  "predictions-log": PredictionsLogView,
  "agent-run-log": AgentRunLogView,
};

const validIds = new Set(adminNavGroups.flatMap((group) => group.items.map((item) => item.id)));

export default function AdminLayout() {
  return (
    <MetricsProvider>
      <AdminLayoutInner />
    </MetricsProvider>
  );
}

function AdminLayoutInner() {
  const [active, setActive] = useState(() => normalizeHash(window.location.hash));
  const [health, setHealth] = useState(null);
  const View = useMemo(() => viewMap[active] || DashboardView, [active]);

  useEffect(() => {
    const onHash = () => setActive(normalizeHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.history.replaceState(null, "", "#dashboard");
    adminApi.getHealth().then((result) => setHealth(result.ok ? result.data : null));
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (id) => {
    window.location.hash = id;
    setActive(id);
  };

  return (
    <div className="admin-root">
      <TopNavbar health={health} />
      <div className="admin-shell">
        <LeftNav active={active} onNavigate={navigate} />
        <main className="admin-main">
          <View navigate={navigate} />
        </main>
      </div>
    </div>
  );
}

function normalizeHash(hash) {
  const id = String(hash || "").replace("#", "") || "dashboard";
  return validIds.has(id) ? id : "dashboard";
}
