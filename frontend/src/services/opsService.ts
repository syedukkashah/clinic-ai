import { api } from "@/lib/api";
import type { AgentStatus, ClinicMetrics } from "@/lib/mockData";

export type Suggestion = { id: string; title: string; impact: string; confidence: number };
export type ActivityEvent = { id: string; type: string; text: string; time: string; at: number };

export async function getSuggestions() {
  const { data } = await api.get<Suggestion[]>("/ops/suggestions");
  return data;
}

export async function getActivity() {
  const { data } = await api.get<ActivityEvent[]>("/ops/activity");
  return data;
}

export async function getAgents() {
  const { data } = await api.get<AgentStatus[]>("/ops/agents");
  return data;
}

export async function getMetrics() {
  const { data } = await api.get<ClinicMetrics>("/ops/metrics");
  return data;
}
