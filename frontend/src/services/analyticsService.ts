import { api } from "@/lib/api";

export type OverviewStats = {
  totalToday: number;
  inQueue: number;
  avgWait: number;
  health: number;
};
export type WaitSeriesPoint = { time: string; wait: number; threshold: number };
export type LoadForecastPoint = { hour: string; actual: number | null; predicted: number };

export async function getOverview() {
  const { data } = await api.get<OverviewStats>("/analytics/overview");
  return data;
}

export async function getWaitSeries() {
  const { data } = await api.get<WaitSeriesPoint[]>("/analytics/wait-series");
  return data;
}

export async function getLoadForecast() {
  const { data } = await api.get<LoadForecastPoint[]>("/analytics/load-forecast");
  return data;
}
