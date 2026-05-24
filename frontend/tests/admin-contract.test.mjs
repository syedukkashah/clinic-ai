import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parsePrometheusText } from "../src/api/prometheusParser.js";

const root = resolve(import.meta.dirname, "..");

describe("admin console contract", () => {
  it("parses Prometheus exposition metrics with labels and histogram children", () => {
    const metrics = parsePrometheusText(`
# HELP mediflow_llm_calls_total LLM calls
# TYPE mediflow_llm_calls_total counter
mediflow_llm_calls_total{provider="groq",status="ok"} 7
# HELP mediflow_request_duration_seconds request latency
# TYPE mediflow_request_duration_seconds histogram
mediflow_request_duration_seconds_bucket{endpoint="/api/chat",le="0.5"} 2
mediflow_request_duration_seconds_sum{endpoint="/api/chat"} 1.3
mediflow_request_duration_seconds_count{endpoint="/api/chat"} 3
`);

    assert.equal(metrics.get("mediflow_llm_calls_total").type, "counter");
    assert.equal(metrics.get("mediflow_llm_calls_total").samples[0].labels.provider, "groq");
    assert.equal(metrics.get("mediflow_request_duration_seconds").type, "histogram");
    assert.equal(metrics.get("mediflow_request_duration_seconds").samples.length, 3);
  });

  it("keeps the required admin file structure in place", () => {
    const required = [
      "src/components/Admin/AdminLayout.jsx",
      "src/components/Admin/TopNavbar.jsx",
      "src/components/Admin/LeftNav.jsx",
      "src/components/Admin/views/DashboardView.jsx",
      "src/components/Admin/views/LLMKeyPoolView.jsx",
      "src/components/Admin/views/OpsMonitorView.jsx",
      "src/components/Admin/views/SystemMetricsView.jsx",
      "src/context/MetricsContext.jsx",
      "src/api/adminApi.js",
      "src/api/mlflowApi.js",
      "src/api/prometheusParser.js",
      "src/styles/admin-globals.css",
      "src/styles/admin-animations.css",
    ];

    for (const file of required) {
      assert.equal(existsSync(resolve(root, file)), true, `${file} should exist`);
    }
  });

  it("renders the full pre-production navigation surface", () => {
    const leftNav = readFileSync(resolve(root, "src/components/Admin/LeftNav.jsx"), "utf8");
    [
      "Dashboard",
      "Appointments",
      "Doctors & Slots",
      "Notifications",
      "Booking Agent",
      "Scheduling Agent",
      "Ops Monitor Agent",
      "Wait Time Model",
      "Load Forecast Model",
      "MLflow Registry",
      "Drift & Retraining",
      "LLM Key Pool",
      "Voice Pipeline",
      "AIOps & Anomaly",
      "DevOps / CI-CD",
      "System Metrics",
      "Ops Alerts",
      "Predictions Log",
      "Agent Run Log",
    ].forEach((label) => assert.match(leftNav, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))));
  });

  it("keeps high-signal demo widgets wired to metrics and traces", () => {
    const topNavbar = readFileSync(resolve(root, "src/components/Admin/TopNavbar.jsx"), "utf8");
    const llmKeyPool = readFileSync(resolve(root, "src/components/Admin/views/LLMKeyPoolView.jsx"), "utf8");
    const trace = readFileSync(resolve(root, "src/components/Admin/shared/ReActTrace.jsx"), "utf8");

    assert.match(topNavbar, /mediflow_anomaly_score/);
    assert.match(topNavbar, /ANOMALY/);
    assert.match(llmKeyPool, /ALL KEYS RATE LIMITED/);
    assert.match(llmKeyPool, /mediflow_key_pool_available/);
    assert.match(trace, /ACT/);
    assert.match(trace, /OBSERVE/);
    assert.match(trace, /CONCLUDE/);
  });

  it("uses real current backend routes and explicit unavailable fallbacks", () => {
    const api = readFileSync(resolve(root, "src/api/adminApi.js"), "utf8");
    assert.match(api, /getAppointments:\s*\(query = \{\}\) => request\(`\/api\/appointments\/\?/);
    assert.match(api, /getDoctors:\s*\(\) => request\("\/api\/doctors\/"\)/);
    assert.match(api, /getMetricsText:\s*\(\) => requestText\("\/metrics"\)/);
    assert.match(api, /getNotifications:.*\/api\/admin\/notifications/);
    assert.match(api, /getPredictions:.*\/api\/admin\/ml\/predictions/);
    assert.match(api, /getModelStatus:.*\/api\/admin\/ml\/model-status/);
    assert.match(api, /getAgentRuns:.*\/api\/admin\/agent-runs/);
    assert.match(api, /getSlots:.*\/api\/slots/);
    assert.match(api, /getReassignments:.*\/api\/admin\/reassignments/);
    assert.match(api, /getCiRuns:.*\/api\/admin\/ci\/runs/);
    assert.match(api, /getKeyEvents:.*\/api\/admin\/llm\/key-events/);

    const mlflow = readFileSync(resolve(root, "src/api/mlflowApi.js"), "utf8");
    assert.match(mlflow, /\/api\/admin\/mlflow\/experiments\/list/);
    assert.match(mlflow, /\/api\/admin\/mlflow\/runs\/search/);
    assert.match(mlflow, /\/api\/admin\/mlflow\/registered-models\/list/);
  });

  it("keeps demo admin login usable when the backend auth service is unavailable", () => {
    const auth = readFileSync(resolve(root, "src/lib/auth.tsx"), "utf8");
    assert.match(auth, /VITE_ALLOW_DEMO_AUTH/);
    assert.match(auth, /admin@mediflow\.io/);
    assert.match(auth, /password === "demo"/);
    assert.match(auth, /demo-\$\{role\}-/);
  });
});
