import { api } from "@/lib/api";
import type { Alert } from "@/lib/mockData";

export async function listAlerts() {
  const { data } = await api.get<Alert[]>("/alerts");
  return data;
}

export async function acknowledgeAlert(id: string) {
  const { data } = await api.post<{ success: boolean; message?: string }>(
    `/alerts/${id}/acknowledge`,
  );
  return data;
}
