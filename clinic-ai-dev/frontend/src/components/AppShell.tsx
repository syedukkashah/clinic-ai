import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  CalendarRange,
  Activity,
  Bot,
  CalendarDays,
  Bell,
  Moon,
  Sun,
  LogOut,
  Stethoscope,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAlerts } from "@/services/alertsService";
import { getMetrics } from "@/services/opsService";
import type { User } from "@/lib/mockData";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/appointments", label: "Appointments", icon: CalendarRange },
  { to: "/ai-ops", label: "AI Ops", icon: Bot },
  { to: "/scheduling", label: "Scheduling", icon: CalendarDays },
  { to: "/activity", label: "Live Activity", icon: Activity },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { data: alerts = [] } = useQuery({
    queryKey: ["alerts"],
    queryFn: listAlerts,
    refetchInterval: 15_000,
  });
  const { data: metrics } = useQuery({
    queryKey: ["ops", "metrics"],
    queryFn: getMetrics,
    refetchInterval: 10_000,
  });
  const alertsCount = alerts.filter((a) => !a.acknowledged).length;
  const degraded =
    (metrics?.p95LatencyMs ?? 0) >= 2000 ||
    (metrics?.apiErrorRatePct ?? 0) >= 5 ||
    (metrics?.anomalyScore ?? 0) >= 0.78;
  const statusLabel = degraded ? "Degraded · investigating" : "All systems operational";
  const dotClass = degraded ? "bg-warning" : "bg-success";
  const loc = useLocation();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar - Desktop */}
      <aside className="hidden lg:flex w-64 flex-col border-r border-sidebar-border bg-sidebar/80 backdrop-blur-xl sticky top-0 h-screen">
        <SidebarContent
          user={user}
          logout={logout}
          theme={theme}
          toggle={toggle}
          loc={loc}
          navigate={navigate}
        />
      </aside>

      {/* Sidebar - Mobile */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileMenuOpen(false)}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 left-0 w-72 bg-sidebar z-50 lg:hidden flex flex-col border-r border-sidebar-border"
            >
              <div className="flex justify-end p-4">
                <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(false)}>
                  <X className="size-5" />
                </Button>
              </div>
              <SidebarContent
                user={user}
                logout={logout}
                theme={theme}
                toggle={toggle}
                loc={loc}
                navigate={navigate}
                onNav={() => setMobileMenuOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main */}
      <div className="flex-1 min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-30 glass border-b border-border/60">
          <div className="h-16 px-4 lg:px-8 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setMobileMenuOpen(true)}
              >
                <Menu className="size-5" />
              </Button>
              <div className="lg:hidden size-9 rounded-xl gradient-primary grid place-items-center">
                <Stethoscope className="size-4 text-white" />
              </div>
              <div className="hidden md:flex items-center gap-2 text-sm">
                <span className={`size-2 rounded-full ${dotClass} animate-pulse`} />
                <span className="text-muted-foreground">{statusLabel}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="relative">
                <Bell className="size-4" />
                {alertsCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] grid place-items-center">
                    {Math.min(99, alertsCount)}
                  </span>
                )}
              </Button>
              <div className="hidden sm:block text-right">
                <div className="text-xs text-muted-foreground">Today</div>
                <div className="text-sm font-medium">
                  {new Date().toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({
  user,
  logout,
  theme,
  toggle,
  loc,
  navigate,
  onNav,
}: {
  user: User | null;
  logout: () => void;
  theme: string;
  toggle: () => void;
  loc: ReturnType<typeof useLocation>;
  navigate: ReturnType<typeof useNavigate>;
  onNav?: () => void;
}) {
  return (
    <>
      <div className="p-6 flex items-center gap-3">
        <div className="size-10 rounded-xl gradient-primary grid place-items-center shadow-glow">
          <Stethoscope className="size-5 text-white" />
        </div>
        <div>
          <div className="font-display font-bold text-lg leading-none">MediFlow</div>
          <div className="text-xs text-muted-foreground mt-1">AI Clinic OS</div>
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {NAV.map((item) => {
          const active = loc.pathname.startsWith(item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNav}
              className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? "text-primary-foreground"
                  : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
              }`}
            >
              {active && (
                <motion.div
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg gradient-primary shadow-glow"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <Icon className="size-4 relative z-10" />
              <span className="relative z-10">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3 mb-3">
          <div className="size-9 rounded-full gradient-violet grid place-items-center text-white text-sm font-semibold">
            {user?.name?.[0] ?? "A"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user?.name}</div>
            <div className="text-xs text-muted-foreground capitalize">{user?.role}</div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="flex-1" onClick={toggle}>
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => {
              logout();
              navigate({ to: "/login" });
              onNav?.();
            }}
          >
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </>
  );
}
