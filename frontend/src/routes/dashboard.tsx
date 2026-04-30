import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { CalendarCheck2, Users, Clock, HeartPulse, AlertTriangle } from "lucide-react";
import { StatCard } from "@/components/StatCard";
import { ActivityFeed } from "@/components/ActivityFeed";
import { DoctorWorkload } from "@/components/DoctorWorkload";
import { WaitTimeChart, LoadForecastChart } from "@/components/Charts";
import { Button } from "@/components/ui/button";
import { useQuery } from "@tanstack/react-query";
import { getOverview } from "@/services/analyticsService";
import { getAgents, getMetrics } from "@/services/opsService";

export const Route = createFileRoute("/dashboard")({
  component: Dashboard,
});

function Dashboard() {
  const { data: overview } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: getOverview,
    refetchInterval: 15_000,
  });
  const { data: metrics } = useQuery({
    queryKey: ["ops", "metrics"],
    queryFn: getMetrics,
    refetchInterval: 10_000,
  });
  const { data: agents = [] } = useQuery({
    queryKey: ["ops", "agents"],
    queryFn: getAgents,
    refetchInterval: 10_000,
  });

  const totalToday = overview?.totalToday ?? 0;
  const inQueue = overview?.inQueue ?? 0;
  const avgWait = overview?.avgWait ?? 0;
  const health = overview?.health ?? 100;
  const agentsOnline = agents.filter((a) => a.state === "online").length;
  const driftKl = metrics?.waitModelDriftKl ?? 0;
  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-end justify-between flex-wrap gap-3"
      >
        <div>
          <h1 className="font-display font-bold text-3xl tracking-tight">Operations Overview</h1>
          <p className="text-muted-foreground">
            AI-driven insights across your clinic, updated every few seconds.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs">
          <span className="size-2 rounded-full bg-success animate-pulse" />
          <span className="text-muted-foreground">
            Models active · drift {driftKl.toFixed(2)} · {agentsOnline} agents online
          </span>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Appointments today"
          value={totalToday}
          delta={12}
          icon={CalendarCheck2}
          gradient="primary"
        />
        <StatCard
          label="Active in queue"
          value={inQueue}
          delta={4}
          icon={Users}
          gradient="violet"
        />
        <StatCard
          label="Avg predicted wait"
          value={avgWait}
          suffix="min"
          delta={-8}
          icon={Clock}
          gradient="warm"
        />
        <StatCard
          label="System health"
          value={health}
          suffix="%"
          delta={1}
          icon={HeartPulse}
          gradient="success"
        />
      </div>

      {driftKl > 0.12 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-4 rounded-xl border border-warning/40 bg-warning/10 text-warning flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="size-5" />
            <div>
              <div className="font-bold text-sm">Model Drift Warning</div>
              <div className="text-xs opacity-90">
                Wait time prediction model (MAE) has drifted beyond threshold (KL:{" "}
                {driftKl.toFixed(2)}).
              </div>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs border-warning/40 hover:bg-warning/20"
          >
            Retrain Model
          </Button>
        </motion.div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <WaitTimeChart />
        <LoadForecastChart />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <DoctorWorkload />
        </div>
        <ActivityFeed />
      </div>
    </div>
  );
}
