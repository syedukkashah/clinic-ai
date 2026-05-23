const jsonHeaders = { Accept: "application/json" };

async function request(endpoint, options = {}) {
  try {
    const response = await fetch(endpoint, { headers: jsonHeaders, ...options });
    if (!response.ok) {
      return { ok: false, endpoint, status: response.status, data: null };
    }
    return { ok: true, endpoint, status: response.status, data: await response.json() };
  } catch (error) {
    return { ok: false, endpoint, status: 0, data: null, error };
  }
}

async function requestText(endpoint) {
  try {
    const response = await fetch(endpoint);
    if (!response.ok) return { ok: false, endpoint, status: response.status, data: "" };
    return { ok: true, endpoint, status: response.status, data: await response.text() };
  } catch (error) {
    return { ok: false, endpoint, status: 0, data: "", error };
  }
}

const params = (value = {}) => new URLSearchParams(
  Object.entries(value).filter(([, val]) => val !== undefined && val !== null && val !== "all" && val !== ""),
).toString();

export const adminApi = {
  getHealth: () => request("/api/health"),
  getDbHealth: () => request("/api/health/db"),
  getMetricsText: () => requestText("/metrics"),
  getOpsMetrics: () => request("/api/ops/metrics/"),
  getOverview: () => request("/api/analytics/overview/"),
  getWaitSeries: () => request("/api/analytics/wait-series/"),
  getLoadForecastSeries: () => request("/api/analytics/load-forecast/"),
  getAppointments: (query = {}) => request(`/api/appointments/?${params(query)}`),
  getDoctors: () => request("/api/doctors/"),
  getDoctorAvailability: (doctorId) => request(`/api/doctors/${doctorId}/availability`),
  getOpsAlerts: (limit = 100) => request(`/api/admin/ops-alerts?${params({ limit })}`),
  acknowledgeAlert: (id) => request(`/api/alerts/${id}/acknowledge`, { method: "POST" }),
  getActivity: () => request("/api/ops/activity/"),
  getAgents: () => request("/api/ops/agents/"),
  getSuggestions: () => request("/api/ops/suggestions/"),
  getPredictionsWaitTime: () => request("/api/predictions/wait-time"),
  getPredictionsLoad: () => request("/api/predictions/load"),
  runOpsMonitor: () => request("/api/ops/run", { method: "POST" }),

  getStats: () => request("/api/admin/stats/summary"),
  getAdminAppointments: (query = {}) => request(`/api/admin/appointments?${params(query)}`),
  getSlots: (doctorId, date) => request(`/api/slots?${params({ doctor_id: doctorId, date })}`),
  getAgentRuns: (agent, limit = 20) => request(`/api/admin/agent-runs?${params({ agent, limit })}`),
  getReassignments: (limit = 50) => request(`/api/admin/reassignments?${params({ limit })}`),
  getCiRuns: (limit = 10) => request(`/api/admin/ci/runs?${params({ limit })}`),
  getKeyEvents: () => request("/api/admin/llm/key-events"),
  getNotifications: (limit = 50) => request(`/api/admin/notifications?${params({ limit })}`),
  getPredictions: (model, limit = 50) => request(`/api/admin/ml/predictions?${params({ model, limit })}`),
  getModelStatus: (name) => request(`/api/admin/ml/model-status?${params({ name })}`),
  getDriftHistory: (limit = 30) => request(`/api/admin/ml/drift-history?${params({ limit })}`),
  getVoiceSessions: (limit = 20) => request(`/api/admin/voice-sessions?${params({ limit })}`),
  getAnomalyHistory: (limit = 48) => request(`/api/admin/anomaly-history?${params({ limit })}`),
  getCeleryTasks: (task, limit = 10) => request(`/api/admin/celery/task-history?${params({ task, limit })}`),
};

export function isAvailable(result) {
  return Boolean(result?.ok);
}
