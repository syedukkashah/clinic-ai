import axios from "axios";
import { DOCTORS, APPOINTMENTS, ALERTS, WAIT_SERIES, LOAD_FORECAST, SUGGESTIONS, getOverviewStats, ACTIVITY_SEED } from "./mockData";
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000/api`
    : "http://localhost:8000/api");

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add a request interceptor to add the JWT token to the headers
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const auth = window.localStorage.getItem("mediflow.auth");
      if (auth) {
        const parsed = JSON.parse(auth);
        const token = parsed?.token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Add a response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (typeof window === "undefined") {
      const url = error.config?.url || "";
      let mockData: any = {};
      
      if (url.includes('/doctors')) mockData = DOCTORS;
      else if (url.includes('/appointments')) mockData = APPOINTMENTS;
      else if (url.includes('/analytics/overview')) mockData = getOverviewStats();
      else if (url.includes('/analytics/wait-times')) mockData = WAIT_SERIES;
      else if (url.includes('/analytics/load-forecast')) mockData = LOAD_FORECAST;
      else if (url.includes('/ops/alerts')) mockData = ALERTS;
      else if (url.includes('/ops/suggestions')) mockData = SUGGESTIONS;
      else if (url.includes('/ops/activity')) mockData = ACTIVITY_SEED;
      else if (url.includes('/ops/agents')) mockData = [];
      else if (url.includes('/ops/metrics')) mockData = {
        bookingVolume30m: 0, p95LatencyMs: 0, apiErrorRatePct: 0, anomalyScore: 0, waitModelDriftKl: 0,
        keyPoolAvailable: { gemini: 0, groq: 0, together: 0, openrouter: 0 }
      };

      // During SSR / prerendering, return mock data so the build does not crash
      return Promise.resolve({ data: mockData });
    }

    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem("mediflow.auth");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
