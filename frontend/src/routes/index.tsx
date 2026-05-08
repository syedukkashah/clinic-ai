import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    if (typeof window === "undefined") {
      return;
    }

    const auth = localStorage.getItem("mediflow.auth");
    let session: unknown = null;
    try {
      session = auth ? JSON.parse(auth) : null;
    } catch {
      localStorage.removeItem("mediflow.auth");
    }

    const isAuthed =
      typeof session === "object" &&
      session !== null &&
      "user" in session &&
      "token" in session &&
      typeof (session as { token?: unknown }).token === "string";

    throw redirect({ to: isAuthed ? "/dashboard" : "/patient", replace: true });
  },
  component: () => (
    <div className="min-h-screen grid place-items-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold">MediFlow</h1>
        <p className="text-muted-foreground">Redirecting...</p>
      </div>
    </div>
  ),
});
