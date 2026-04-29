import { api } from "@/lib/api";
import type { Appointment } from "@/lib/mockData";

export async function listAppointments() {
  const { data } = await api.get<Appointment[]>("/appointments");
  return data;
}

export async function createAppointment(payload: Omit<Appointment, "id">) {
  const { data } = await api.post<Appointment>("/appointments", payload);
  return data;
}

export async function updateAppointment(id: string, patch: Partial<Appointment>) {
  const { data } = await api.put<Appointment>(`/appointments/${id}`, patch);
  return data;
}

export async function deleteAppointment(id: string) {
  const { data } = await api.delete<{ success: boolean }>(`/appointments/${id}`);
  return data;
}
