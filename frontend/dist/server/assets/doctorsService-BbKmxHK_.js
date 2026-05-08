import { a as api } from "./router-kWCNp4I7.js";
async function listDoctors() {
  const { data } = await api.get("/doctors");
  return data;
}
export {
  listDoctors as l
};
