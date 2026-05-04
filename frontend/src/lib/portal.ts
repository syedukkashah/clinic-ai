export type Portal = "admin" | "patient" | "full";

export function getPortal(): Portal {
  const mode = import.meta.env.MODE;
  if (mode === "admin") return "admin";
  if (mode === "patient") return "patient";
  return "full";
}

export function getAdminPortalUrl(): string {
  return import.meta.env.VITE_ADMIN_PORTAL_URL || "/login";
}

export function getPatientPortalUrl(): string {
  return import.meta.env.VITE_PATIENT_PORTAL_URL || "/patient";
}
