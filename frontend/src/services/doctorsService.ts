import { api } from "@/lib/api";
import type { Doctor } from "@/lib/mockData";

export async function listDoctors() {
  const { data } = await api.get<Doctor[]>("/doctors");
  return data;
}

export async function getDoctor(id: string) {
  const { data } = await api.get<Doctor>(`/doctors/${id}`);
  return data;
}
