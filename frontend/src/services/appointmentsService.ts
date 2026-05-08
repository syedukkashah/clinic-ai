import { api } from "@/lib/api";
import type { Appointment } from "@/lib/mockData";
import { publishPortalEvent } from "@/lib/portalBus";

export interface PaginatedAppointments {
  items: Appointment[];
  total: number;
  limit: number;
  offset: number;
}

export async function listAppointments(params: {
  limit?: number;
  offset?: number;
  search?: string;
  doctor_id?: string;
  status?: string;
  date?: string;
} = {}) {
  const { limit = 50, offset = 0, search, doctor_id, status, date } = params;
  let url = `appointments/?limit=${limit}&offset=${offset}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (doctor_id && doctor_id !== "all") url += `&doctor_id=${doctor_id}`;
  if (status && status !== "all") url += `&status=${status}`;
  if (date) url += `&date=${date}`;
  
  const { data } = await api.get<PaginatedAppointments>(url);
  return data;
}

export async function createAppointment(payload: Omit<Appointment, "id">) {
  const { data } = await api.post<Appointment>("appointments/", payload);
  publishPortalEvent({ type: "appointments:changed" });
  return data;
}

export async function updateAppointment(id: string, patch: Partial<Appointment>) {
  const { data } = await api.put<Appointment>(`appointments/${id}`, patch);
  publishPortalEvent({ type: "appointments:changed" });
  return data;
}

export async function deleteAppointment(id: string) {
  const { data } = await api.delete<{ success: boolean }>(`appointments/${id}`);
  publishPortalEvent({ type: "appointments:changed" });
  return data;
}
