import { createFileRoute } from "@tanstack/react-router";
import PatientPortal from "@/components/PatientPortal.jsx";

export const Route = createFileRoute("/patient")({
  component: PatientPage,
});

function PatientPage() {
  return <PatientPortal />;
}
