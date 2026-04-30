import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/chat")({
  beforeLoad: () => {
    throw redirect({ to: "/patient", replace: true });
  },
  component: () => (
    <div className="min-h-screen grid place-items-center p-6 text-center">
      <div>
        <div className="text-2xl font-display font-bold">Redirecting…</div>
        <p className="mt-2 text-muted-foreground">Taking you to the patient site.</p>
      </div>
    </div>
  ),
});
