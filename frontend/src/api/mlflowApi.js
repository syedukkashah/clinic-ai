const mlflowBase = import.meta.env.VITE_ADMIN_API_BASE || "";

async function mlflowRequest(path, options = {}) {
  try {
    const response = await fetch(`${mlflowBase}${path}`, options);
    if (!response.ok) return { ok: false, endpoint: path, status: response.status, data: null };
    return { ok: true, endpoint: path, status: response.status, data: await response.json() };
  } catch (error) {
    return { ok: false, endpoint: path, status: 0, data: null, error };
  }
}

export const mlflowApi = {
  listExperiments: () => mlflowRequest("/api/admin/mlflow/experiments/list"),
  searchRuns: (body) =>
    mlflowRequest("/api/admin/mlflow/runs/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  listRegisteredModels: () => mlflowRequest("/api/admin/mlflow/registered-models/list"),
};
