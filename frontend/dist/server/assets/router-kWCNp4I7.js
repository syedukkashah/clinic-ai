import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useLocation, useNavigate, Link, createRootRoute, redirect, Outlet, HeadContent, Scripts, createFileRoute, lazyRouteComponent, createRouter, useRouter } from "@tanstack/react-router";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";
import { useState, useCallback, useEffect, createContext, useContext } from "react";
import axios from "axios";
import { Toaster as Toaster$1 } from "sonner";
import { AnimatePresence, motion } from "framer-motion";
import { X, Menu, Stethoscope, Bell, LayoutDashboard, CalendarRange, Bot, CalendarDays, Activity, Sun, Moon, LogOut } from "lucide-react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
const API_BASE_URL = typeof window !== "undefined" ? `http://${window.location.hostname}:8000/api` : "http://localhost:8000/api";
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json"
  }
});
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const auth = window.localStorage.getItem("mediflow.auth");
      if (auth) {
        const parsed = JSON.parse(auth);
        const token = parsed?.token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem("mediflow.auth");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
async function loginAccessToken(params) {
  const body = new URLSearchParams();
  body.set("username", params.username);
  body.set("password", params.password);
  const { data } = await api.post(
    "/auth/login/access-token",
    body,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );
  return data;
}
const AuthContext = createContext(null);
const STORAGE_KEY = "mediflow.auth";
function AuthProvider({ children }) {
  const [session, setSession] = useState(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const user = session?.user ?? null;
  const token = session?.token ?? null;
  const setSessionSafe = useCallback((s) => {
    setSession((prev) => {
      if (!prev && !s) return null;
      if (prev && s && prev.token === s.token && prev.user.id === s.user.id) return prev;
      return s;
    });
  }, []);
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === STORAGE_KEY) {
        try {
          const next = e.newValue ? JSON.parse(e.newValue) : null;
          setSessionSafe(next);
        } catch {
          return;
        }
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [setSessionSafe]);
  const login = async (email, role, password) => {
    const tokenRes = await loginAccessToken({ username: email, password });
    const name = email.split("@")[0].replace(/[._-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const u = {
      id: "u-" + Math.random().toString(36).slice(2, 8),
      name: name || (role === "admin" ? "Admin User" : "Staff User"),
      email,
      role
    };
    const next = { user: u, token: tokenRes.accessToken, tokenType: tokenRes.tokenType };
    setSessionSafe(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  };
  const logout = () => {
    setSessionSafe(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  };
  return /* @__PURE__ */ jsx(AuthContext.Provider, { value: { user, token, login, logout }, children });
}
function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
const ThemeCtx = createContext(null);
function ThemeProvider({ children }) {
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("mediflow.theme") || "dark";
    setTheme(saved);
  }, []);
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("dark", theme === "dark");
    if (typeof window !== "undefined") {
      window.localStorage.setItem("mediflow.theme", theme);
    }
  }, [theme]);
  return /* @__PURE__ */ jsx(
    ThemeCtx.Provider,
    {
      value: { theme, toggle: () => setTheme((t) => t === "dark" ? "light" : "dark") },
      children
    }
  );
}
function useTheme() {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
const Toaster = ({ ...props }) => {
  return /* @__PURE__ */ jsx(
    Toaster$1,
    {
      className: "toaster group",
      toastOptions: {
        classNames: {
          toast: "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground"
        }
      },
      ...props
    }
  );
};
function cn(...inputs) {
  return twMerge(clsx(inputs));
}
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline"
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);
const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return /* @__PURE__ */ jsx(Comp, { className: cn(buttonVariants({ variant, size, className })), ref, ...props });
  }
);
Button.displayName = "Button";
async function listAlerts() {
  const { data } = await api.get("/alerts");
  return data;
}
async function getSuggestions() {
  const { data } = await api.get("/ops/suggestions");
  return data;
}
async function getActivity() {
  const { data } = await api.get("/ops/activity");
  return data;
}
async function getAgents() {
  const { data } = await api.get("/ops/agents");
  return data;
}
async function getMetrics() {
  const { data } = await api.get("/ops/metrics");
  return data;
}
const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/appointments", label: "Appointments", icon: CalendarRange },
  { to: "/ai-ops", label: "AI Ops", icon: Bot },
  { to: "/scheduling", label: "Scheduling", icon: CalendarDays },
  { to: "/activity", label: "Live Activity", icon: Activity }
];
function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { data: alerts = [] } = useQuery({
    queryKey: ["alerts"],
    queryFn: listAlerts,
    refetchInterval: 15e3
  });
  const { data: metrics } = useQuery({
    queryKey: ["ops", "metrics"],
    queryFn: getMetrics,
    refetchInterval: 1e4
  });
  const alertsCount = alerts.filter((a) => !a.acknowledged).length;
  const degraded = (metrics?.p95LatencyMs ?? 0) >= 2e3 || (metrics?.apiErrorRatePct ?? 0) >= 5 || (metrics?.anomalyScore ?? 0) >= 0.78;
  const statusLabel = degraded ? "Degraded · investigating" : "All systems operational";
  const dotClass = degraded ? "bg-warning" : "bg-success";
  const loc = useLocation();
  const navigate = useNavigate();
  return /* @__PURE__ */ jsxs("div", { className: "flex min-h-screen", children: [
    /* @__PURE__ */ jsx("aside", { className: "hidden lg:flex w-64 flex-col border-r border-sidebar-border bg-sidebar/80 backdrop-blur-xl sticky top-0 h-screen", children: /* @__PURE__ */ jsx(
      SidebarContent,
      {
        user,
        logout,
        theme,
        toggle,
        loc,
        navigate
      }
    ) }),
    /* @__PURE__ */ jsx(AnimatePresence, { children: mobileMenuOpen && /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(
        motion.div,
        {
          initial: { opacity: 0 },
          animate: { opacity: 1 },
          exit: { opacity: 0 },
          onClick: () => setMobileMenuOpen(false),
          className: "fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
        }
      ),
      /* @__PURE__ */ jsxs(
        motion.aside,
        {
          initial: { x: "-100%" },
          animate: { x: 0 },
          exit: { x: "-100%" },
          transition: { type: "spring", damping: 25, stiffness: 200 },
          className: "fixed inset-y-0 left-0 w-72 bg-sidebar z-50 lg:hidden flex flex-col border-r border-sidebar-border",
          children: [
            /* @__PURE__ */ jsx("div", { className: "flex justify-end p-4", children: /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "icon", onClick: () => setMobileMenuOpen(false), children: /* @__PURE__ */ jsx(X, { className: "size-5" }) }) }),
            /* @__PURE__ */ jsx(
              SidebarContent,
              {
                user,
                logout,
                theme,
                toggle,
                loc,
                navigate,
                onNav: () => setMobileMenuOpen(false)
              }
            )
          ]
        }
      )
    ] }) }),
    /* @__PURE__ */ jsxs("div", { className: "flex-1 min-w-0", children: [
      /* @__PURE__ */ jsx("header", { className: "sticky top-0 z-30 glass border-b border-border/60", children: /* @__PURE__ */ jsxs("div", { className: "h-16 px-4 lg:px-8 flex items-center justify-between", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "icon",
              className: "lg:hidden",
              onClick: () => setMobileMenuOpen(true),
              children: /* @__PURE__ */ jsx(Menu, { className: "size-5" })
            }
          ),
          /* @__PURE__ */ jsx("div", { className: "lg:hidden size-9 rounded-xl gradient-primary grid place-items-center", children: /* @__PURE__ */ jsx(Stethoscope, { className: "size-4 text-white" }) }),
          /* @__PURE__ */ jsxs("div", { className: "hidden md:flex items-center gap-2 text-sm", children: [
            /* @__PURE__ */ jsx("span", { className: `size-2 rounded-full ${dotClass} animate-pulse` }),
            /* @__PURE__ */ jsx("span", { className: "text-muted-foreground", children: statusLabel })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsxs(Button, { variant: "ghost", size: "icon", className: "relative", children: [
            /* @__PURE__ */ jsx(Bell, { className: "size-4" }),
            alertsCount > 0 && /* @__PURE__ */ jsx("span", { className: "absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] grid place-items-center", children: Math.min(99, alertsCount) })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "hidden sm:block text-right", children: [
            /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: "Today" }),
            /* @__PURE__ */ jsx("div", { className: "text-sm font-medium", children: (/* @__PURE__ */ new Date()).toLocaleDateString(void 0, {
              weekday: "short",
              month: "short",
              day: "numeric"
            }) })
          ] })
        ] })
      ] }) }),
      /* @__PURE__ */ jsx("main", { className: "p-4 lg:p-8", children })
    ] })
  ] });
}
function SidebarContent({
  user,
  logout,
  theme,
  toggle,
  loc,
  navigate,
  onNav
}) {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs("div", { className: "p-6 flex items-center gap-3", children: [
      /* @__PURE__ */ jsx("div", { className: "size-10 rounded-xl gradient-primary grid place-items-center shadow-glow", children: /* @__PURE__ */ jsx(Stethoscope, { className: "size-5 text-white" }) }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("div", { className: "font-display font-bold text-lg leading-none", children: "MediFlow" }),
        /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground mt-1", children: "AI Clinic OS" })
      ] })
    ] }),
    /* @__PURE__ */ jsx("nav", { className: "flex-1 px-3 space-y-1", children: NAV.map((item) => {
      const active = loc.pathname.startsWith(item.to);
      const Icon = item.icon;
      return /* @__PURE__ */ jsxs(
        Link,
        {
          to: item.to,
          onClick: onNav,
          className: `group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${active ? "text-primary-foreground" : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"}`,
          children: [
            active && /* @__PURE__ */ jsx(
              motion.div,
              {
                layoutId: "nav-active",
                className: "absolute inset-0 rounded-lg gradient-primary shadow-glow",
                transition: { type: "spring", stiffness: 400, damping: 30 }
              }
            ),
            /* @__PURE__ */ jsx(Icon, { className: "size-4 relative z-10" }),
            /* @__PURE__ */ jsx("span", { className: "relative z-10", children: item.label })
          ]
        },
        item.to
      );
    }) }),
    /* @__PURE__ */ jsxs("div", { className: "p-4 border-t border-sidebar-border", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 mb-3", children: [
        /* @__PURE__ */ jsx("div", { className: "size-9 rounded-full gradient-violet grid place-items-center text-white text-sm font-semibold", children: user?.name?.[0] ?? "A" }),
        /* @__PURE__ */ jsxs("div", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ jsx("div", { className: "text-sm font-medium truncate", children: user?.name }),
          /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground capitalize", children: user?.role })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex gap-2", children: [
        /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", className: "flex-1", onClick: toggle, children: theme === "dark" ? /* @__PURE__ */ jsx(Sun, { className: "size-4" }) : /* @__PURE__ */ jsx(Moon, { className: "size-4" }) }),
        /* @__PURE__ */ jsx(
          Button,
          {
            size: "sm",
            variant: "outline",
            className: "flex-1",
            onClick: () => {
              logout();
              navigate({ to: "/login" });
              onNav?.();
            },
            children: /* @__PURE__ */ jsx(LogOut, { className: "size-4" })
          }
        )
      ] })
    ] })
  ] });
}
const appCss = "/assets/styles-Sz6ZtQmD.css";
const Route$9 = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "MediFlow — AI Clinic Operations" },
      {
        name: "description",
        content: "AI-powered clinic operations platform with smart scheduling, voice booking, and real-time ops monitoring."
      },
      { property: "og:title", content: "MediFlow — AI Clinic Operations" },
      { property: "og:description", content: "AI-powered clinic operations platform." },
      { property: "og:type", content: "website" }
    ],
    links: [{ rel: "stylesheet", href: appCss }]
  }),
  shellComponent: RootShell,
  component: RootComponent,
  beforeLoad: ({ location }) => {
    if (typeof window === "undefined") return;
    const auth = localStorage.getItem("mediflow.auth");
    let session = null;
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
    const isAuthed = typeof session === "object" && session !== null && "user" in session && "token" in session && typeof session.token === "string";
    if (isRoot) {
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
  notFoundComponent: () => /* @__PURE__ */ jsx("div", { className: "min-h-screen grid place-items-center p-6 text-center", children: /* @__PURE__ */ jsxs("div", { children: [
    /* @__PURE__ */ jsx("div", { className: "text-6xl font-display font-bold gradient-text", children: "404" }),
    /* @__PURE__ */ jsx("p", { className: "mt-2 text-muted-foreground", children: "This page doesn't exist." }),
    /* @__PURE__ */ jsx(
      "a",
      {
        href: "/",
        className: "mt-6 inline-block px-4 py-2 rounded-lg gradient-primary text-white text-sm font-medium",
        children: "Go home"
      }
    )
  ] }) })
});
function RootShell({ children }) {
  return /* @__PURE__ */ jsxs("html", { lang: "en", children: [
    /* @__PURE__ */ jsxs("head", { children: [
      /* @__PURE__ */ jsx(HeadContent, {}),
      /* @__PURE__ */ jsx("link", { rel: "preconnect", href: "https://fonts.googleapis.com" }),
      /* @__PURE__ */ jsx("link", { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "" }),
      /* @__PURE__ */ jsx(
        "link",
        {
          href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap",
          rel: "stylesheet"
        }
      )
    ] }),
    /* @__PURE__ */ jsxs("body", { children: [
      children,
      /* @__PURE__ */ jsx(Scripts, {})
    ] })
  ] });
}
function Gate({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  const [isClient, setIsClient] = useState(false);
  useEffect(() => {
    setIsClient(true);
  }, []);
  if (!isClient) {
    return /* @__PURE__ */ jsx("div", { className: "min-h-screen grid place-items-center", children: /* @__PURE__ */ jsx("div", { className: "size-10 rounded-full border-2 border-primary/30 border-t-primary animate-spin" }) });
  }
  const isLoginPage = location.pathname === "/login";
  const isPatientSite = location.pathname === "/patient" || location.pathname.startsWith("/patient/");
  if (user && !isLoginPage && !isPatientSite) {
    return /* @__PURE__ */ jsx(AppShell, { children });
  }
  return /* @__PURE__ */ jsx(Fragment, { children });
}
function RootComponent() {
  const [queryClient] = useState(
    () => new QueryClient({
      defaultOptions: {
        queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 15e3 }
      }
    })
  );
  return /* @__PURE__ */ jsx(ThemeProvider, { children: /* @__PURE__ */ jsx(QueryClientProvider, { client: queryClient, children: /* @__PURE__ */ jsxs(AuthProvider, { children: [
    /* @__PURE__ */ jsx(Gate, { children: /* @__PURE__ */ jsx(Outlet, {}) }),
    /* @__PURE__ */ jsx(Toaster, {})
  ] }) }) });
}
const $$splitComponentImporter$8 = () => import("./scheduling-BopJPmap.js");
const Route$8 = createFileRoute("/scheduling")({
  component: lazyRouteComponent($$splitComponentImporter$8, "component")
});
const $$splitComponentImporter$7 = () => import("./patient-I_6BpXWR.js");
const Route$7 = createFileRoute("/patient")({
  component: lazyRouteComponent($$splitComponentImporter$7, "component")
});
const $$splitComponentImporter$6 = () => import("./login-WoERuwwM.js");
const Route$6 = createFileRoute("/login")({
  component: lazyRouteComponent($$splitComponentImporter$6, "component")
});
const $$splitComponentImporter$5 = () => import("./dashboard-xuytBLqj.js");
const Route$5 = createFileRoute("/dashboard")({
  component: lazyRouteComponent($$splitComponentImporter$5, "component")
});
const $$splitComponentImporter$4 = () => import("./chat-TNC_kVzt.js");
const Route$4 = createFileRoute("/chat")({
  beforeLoad: () => {
    throw redirect({
      to: "/patient",
      replace: true
    });
  },
  component: lazyRouteComponent($$splitComponentImporter$4, "component")
});
const $$splitComponentImporter$3 = () => import("./appointments-CKogwEvH.js");
const Route$3 = createFileRoute("/appointments")({
  component: lazyRouteComponent($$splitComponentImporter$3, "component")
});
const $$splitComponentImporter$2 = () => import("./ai-ops-DaMGPJeQ.js");
const Route$2 = createFileRoute("/ai-ops")({
  component: lazyRouteComponent($$splitComponentImporter$2, "component")
});
const $$splitComponentImporter$1 = () => import("./activity-lny7dcPA.js");
const Route$1 = createFileRoute("/activity")({
  component: lazyRouteComponent($$splitComponentImporter$1, "component")
});
const $$splitComponentImporter = () => import("./index-C873HOjY.js");
const Route = createFileRoute("/")({
  beforeLoad: () => {
    if (typeof window === "undefined") {
      throw redirect({
        to: "/patient",
        replace: true
      });
    }
    const auth = localStorage.getItem("mediflow.auth");
    let session = null;
    try {
      session = auth ? JSON.parse(auth) : null;
    } catch {
      localStorage.removeItem("mediflow.auth");
    }
    const isAuthed = typeof session === "object" && session !== null && "user" in session && "token" in session && typeof session.token === "string";
    throw redirect({
      to: isAuthed ? "/dashboard" : "/patient",
      replace: true
    });
  },
  component: lazyRouteComponent($$splitComponentImporter, "component")
});
const SchedulingRoute = Route$8.update({
  id: "/scheduling",
  path: "/scheduling",
  getParentRoute: () => Route$9
});
const PatientRoute = Route$7.update({
  id: "/patient",
  path: "/patient",
  getParentRoute: () => Route$9
});
const LoginRoute = Route$6.update({
  id: "/login",
  path: "/login",
  getParentRoute: () => Route$9
});
const DashboardRoute = Route$5.update({
  id: "/dashboard",
  path: "/dashboard",
  getParentRoute: () => Route$9
});
const ChatRoute = Route$4.update({
  id: "/chat",
  path: "/chat",
  getParentRoute: () => Route$9
});
const AppointmentsRoute = Route$3.update({
  id: "/appointments",
  path: "/appointments",
  getParentRoute: () => Route$9
});
const AiOpsRoute = Route$2.update({
  id: "/ai-ops",
  path: "/ai-ops",
  getParentRoute: () => Route$9
});
const ActivityRoute = Route$1.update({
  id: "/activity",
  path: "/activity",
  getParentRoute: () => Route$9
});
const IndexRoute = Route.update({
  id: "/",
  path: "/",
  getParentRoute: () => Route$9
});
const rootRouteChildren = {
  IndexRoute,
  ActivityRoute,
  AiOpsRoute,
  AppointmentsRoute,
  ChatRoute,
  DashboardRoute,
  LoginRoute,
  PatientRoute,
  SchedulingRoute
};
const routeTree = Route$9._addFileChildren(rootRouteChildren)._addFileTypes();
function DefaultErrorComponent({ error, reset }) {
  const router2 = useRouter();
  return /* @__PURE__ */ jsx("div", { className: "flex min-h-screen items-center justify-center bg-background px-4", children: /* @__PURE__ */ jsxs("div", { className: "max-w-md text-center", children: [
    /* @__PURE__ */ jsx("div", { className: "mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10", children: /* @__PURE__ */ jsx(
      "svg",
      {
        xmlns: "http://www.w3.org/2000/svg",
        className: "h-8 w-8 text-destructive",
        fill: "none",
        viewBox: "0 0 24 24",
        stroke: "currentColor",
        strokeWidth: 2,
        children: /* @__PURE__ */ jsx(
          "path",
          {
            strokeLinecap: "round",
            strokeLinejoin: "round",
            d: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          }
        )
      }
    ) }),
    /* @__PURE__ */ jsx("h1", { className: "text-2xl font-bold tracking-tight text-foreground", children: "Something went wrong" }),
    /* @__PURE__ */ jsx("p", { className: "mt-2 text-sm text-muted-foreground", children: "An unexpected error occurred. Please try again." }),
    false,
    /* @__PURE__ */ jsxs("div", { className: "mt-6 flex items-center justify-center gap-3", children: [
      /* @__PURE__ */ jsx(
        "button",
        {
          onClick: () => {
            router2.invalidate();
            reset();
          },
          className: "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
          children: "Try again"
        }
      ),
      /* @__PURE__ */ jsx(
        "a",
        {
          href: "/",
          className: "inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent",
          children: "Go home"
        }
      )
    ] })
  ] }) });
}
const getRouter = () => {
  const router2 = createRouter({
    routeTree,
    context: {},
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
    defaultErrorComponent: DefaultErrorComponent
  });
  return router2;
};
const router = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  getRouter
}, Symbol.toStringTag, { value: "Module" }));
export {
  Button as B,
  api as a,
  getAgents as b,
  cn as c,
  getSuggestions as d,
  getActivity as e,
  getMetrics as g,
  listAlerts as l,
  router as r,
  useAuth as u
};
