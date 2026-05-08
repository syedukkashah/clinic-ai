import { a as api } from "./router-kWCNp4I7.js";
async function listAppointments() {
  const { data } = await api.get("/appointments");
  return data;
}
async function updateAppointment(id, patch) {
  const { data } = await api.put(`/appointments/${id}`, patch);
  return data;
}
export {
  listAppointments as l,
  updateAppointment as u
};
