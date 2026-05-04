import {
  Outlet,
  createRootRoute,
  HeadContent,
  Scripts,
  useLocation,
  redirect,
} from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { Toaster } from "@/components/ui/sonner";
import { AppShell } from "@/components/AppShell";
import { toast } from "sonner";
import { getPortal } from "@/lib/portal";
import { startPortalPresence, subscribePortalEvents } from "@/lib/portalBus";

import appCss from "../styles.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "MediFlow — AI Clinic Operations" },
      {
        name: "description",
        content:
          "AI-powered clinic operations platform with smart scheduling, voice booking, and real-time ops monitoring.",
      },
      { property: "og:title", content: "MediFlow — AI Clinic Operations" },
      { property: "og:description", content: "AI-powered clinic operations platform." },
      { property: "og:type", content: "website" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  beforeLoad: ({ location }) => {
    // Basic auth check for initial load/navigation
    if (typeof window === "undefined") return;

    const portal = getPortal();
    const auth = localStorage.getItem("mediflow.auth");
    let session: unknown = null;
    try {
      session = auth ? JSON.parse(auth) : null;
    } catch {
      localStorage.removeItem("mediflow.auth");
    }

    const path = location.pathname.replace(/\/$/, "") || "/";
    const isLoginPage = path === "/login";
    const isRoot = path === "/";
    const isPatientSite = path === "/patient" || path.startsWith("/patient/");
    const isLegacyChatPath = path === "/chat";
    const isAuthed =
      typeof session === "object" &&
      session !== null &&
      "user" in session &&
      "token" in session &&
      typeof (session as { token?: unknown }).token === "string";

    if (portal === "patient") {
      if (isLoginPage) {
        throw redirect({ to: "/patient", replace: true });
      }
      if (!isPatientSite) {
        throw redirect({ to: "/patient", replace: true });
      }
      if (isRoot) {
        throw redirect({ to: "/patient", replace: true });
      }
      return;
    }

    if (portal === "admin") {
      if (isPatientSite) {
        throw redirect({ to: isAuthed ? "/dashboard" : "/login", replace: true });
      }
      if (isRoot) {
        throw redirect({ to: isAuthed ? "/dashboard" : "/login", replace: true });
      }
    } else if (isRoot) {
      throw redirect({ to: isAuthed ? "/dashboard" : "/patient", replace: true });
    }

    const isPublic = isLoginPage || isPatientSite || isLegacyChatPath;

    if (!isAuthed && !isPublic) {
      throw redirect({ to: "/login", replace: true });
    }

    if (isAuthed && isLoginPage) {
      throw redirect({ to: "/dashboard", replace: true });
    }
  },
  notFoundComponent: () => (
    <div className="min-h-screen grid place-items-center p-6 text-center">
      <div>
        <div className="text-6xl font-display font-bold gradient-text">404</div>
        <p className="mt-2 text-muted-foreground">This page doesn't exist.</p>
        <a
          href="/"
          className="mt-6 inline-block px-4 py-2 rounded-lg gradient-primary text-white text-sm font-medium"
        >
          Go home
        </a>
      </div>
    </div>
  ),
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function Gate({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="size-10 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  const isLoginPage = location.pathname === "/login";
  const isPatientSite =
    location.pathname === "/patient" || location.pathname.startsWith("/patient/");
  const portal = getPortal();

  // If we are logged in and on a non-login page, use AppShell
  if (portal !== "patient" && user && !isLoginPage && !isPatientSite) {
    return <AppShell>{children}</AppShell>;
  }

  // Otherwise (login page or not logged in yet), render children directly
  return <>{children}</>;
}

function RootComponent() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 15_000 },
        },
      }),
  );

  useEffect(() => {
    const stopPresence = startPortalPresence();
    const unsub = subscribePortalEvents((event, envelope) => {
      if (envelope.from === getPortal()) return;

      if (event.type === "appointments:changed") {
        queryClient.invalidateQueries({ queryKey: ["appointments"] });
      }

      if (event.type === "patient:contact") {
        queryClient.invalidateQueries({ queryKey: ["alerts"] });
        toast.info("New patient request", {
          description: `${event.channel}: ${event.ticketId}`,
        });
      }
    });

    return () => {
      stopPresence();
      unsub();
    };
  }, [queryClient]);

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Gate>
            <Outlet />
          </Gate>
          <Toaster />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
