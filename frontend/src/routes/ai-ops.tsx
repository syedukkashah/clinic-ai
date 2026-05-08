import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { AlertTriangle, Activity, Brain, Sparkles, CheckCircle2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Area,
  AreaChart,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { listAlerts } from "@/services/alertsService";
import { getAgents, getMetrics, getSuggestions } from "@/services/opsService";

export const Route = createFileRoute("/ai-ops")({
  component: AIOpsPage,
});

const SEV_STYLES = {
  High: {
    bg: "bg-destructive/15",
    text: "text-destructive",
    border: "border-destructive/40",
    dot: "bg-destructive",
  },
  Medium: {
    bg: "bg-warning/15",
    text: "text-warning",
    border: "border-warning/40",
    dot: "bg-warning",
  },
  Low: {
    bg: "bg-success/15",
    text: "text-success",
    border: "border-success/40",
    dot: "bg-success",
  },
} as const;

const ANOMALY_SERIES = Array.from({ length: 24 }, (_, i) => ({
  t: `${i}h`,
  score: Math.max(
    0,
    Math.min(1, 0.2 + Math.sin(i / 3) * 0.15 + (i > 18 ? 0.4 : 0) + Math.random() * 0.1),
  ),
}));

function AIOpsPage() {
  const { data: alerts = [] } = useQuery({
    queryKey: ["alerts"],
    queryFn: listAlerts,
    refetchInterval: 15_000,
  });
  const { data: suggestions = [] } = useQuery({
    queryKey: ["ops", "suggestions"],
    queryFn: getSuggestions,
    refetchInterval: 20_000,
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

  const anomalyScore = metrics?.anomalyScore ?? 0;
  const agentsOnline = agents.filter((a) => a.state === "online").length;
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-3xl tracking-tight flex items-center gap-2">
            <span className="size-8 rounded-lg gradient-violet grid place-items-center">
              <Brain className="size-4 text-white" />
            </span>
            AI Operations Monitor
          </h1>
          <p className="text-muted-foreground">
            Anomaly detection, model health & autonomous recommendations
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs">
          <span className="size-2 rounded-full bg-success animate-pulse" />3 models active ·{" "}
          {agentsOnline} agents online
        </div>
      </div>

      {/* Top: anomaly gauge + signals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl glass-card p-6"
        >
          <div className="text-sm text-muted-foreground">Composite Anomaly Score</div>
          <div className="relative h-56 mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                innerRadius="70%"
                outerRadius="100%"
                data={[{ name: "score", value: anomalyScore * 100 }]}
                startAngle={210}
                endAngle={-30}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                <RadialBar
                  dataKey="value"
                  cornerRadius={20}
                  fill="url(#anomG)"
                  background={{ fill: "var(--color-muted)" }}
                />
                <defs>
                  <linearGradient id="anomG" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="var(--color-warning)" />
                    <stop offset="100%" stopColor="var(--color-destructive)" />
                  </linearGradient>
                </defs>
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 grid place-items-center text-center">
              <div>
                <div className="text-5xl font-display font-bold gradient-text">
                  {(anomalyScore * 100).toFixed(0)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Elevated risk</div>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            {[
              { l: "Surge", v: "0.92", c: "text-destructive" },
              { l: "Latency", v: "0.61", c: "text-warning" },
              { l: "Drift", v: "0.44", c: "text-warning" },
            ].map((x) => (
              <div key={x.l} className="rounded-lg bg-muted/50 p-2">
                <div className={`font-bold ${x.c}`}>{x.v}</div>
                <div className="text-muted-foreground">{x.l}</div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.05 } }}
          className="rounded-2xl glass-card p-6 lg:col-span-2"
        >
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="font-display font-semibold">Anomaly score · last 24h</div>
              <div className="text-xs text-muted-foreground">
                Composite of booking, latency & drift signals
              </div>
            </div>
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <Activity className="size-3.5" />
              Streaming
            </div>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ANOMALY_SERIES} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="anomA" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-violet)" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="var(--color-violet)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                  vertical={false}
                />
                <XAxis
                  dataKey="t"
                  stroke="var(--color-muted-foreground)"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="var(--color-muted-foreground)"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 1]}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-card)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="var(--color-violet)"
                  strokeWidth={2.5}
                  fill="url(#anomA)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      {/* Alerts + Suggestions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-display font-bold text-lg flex items-center gap-2">
                <AlertTriangle className="size-4 text-warning" />
                Active Alerts
              </h3>
              <p className="text-sm text-muted-foreground">AI-generated reasoning for each event</p>
            </div>
          </div>
          <div className="space-y-3">
            {alerts.map((a, i) => {
              const s = SEV_STYLES[a.severity];
              return (
                <motion.div
                  key={a.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className={`rounded-xl border ${s.border} ${s.bg} p-4`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative shrink-0 mt-1">
                      <span className={`size-2.5 rounded-full block ${s.dot}`} />
                      {a.severity === "High" && (
                        <span
                          className={`absolute inset-0 rounded-full ${s.dot} animate-pulse-ring`}
                        />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="font-semibold">{a.title}</div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${s.text} ${s.bg} border ${s.border}`}
                          >
                            {a.severity.toUpperCase()}
                          </span>
                          <span className="text-xs text-muted-foreground">{a.timestamp}</span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1.5">{a.reasoning}</p>
                      {a.trace && (
                        <div className="mt-3 space-y-1">
                          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                            Reasoning Trace
                          </div>
                          <div className="rounded-lg bg-background/40 p-2 font-mono text-[10px] space-y-0.5 border border-border/40">
                            {a.trace.map((t, idx) => (
                              <div key={idx} className="flex gap-2">
                                <span className="text-muted-foreground opacity-50">{idx + 1}</span>
                                <span>{t}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {a.recommendedActions && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {a.recommendedActions.map((action, idx) => (
                            <Button
                              key={idx}
                              size="sm"
                              variant="outline"
                              className="h-7 text-[10px] font-bold uppercase tracking-tight bg-background/50"
                              onClick={() =>
                                toast.success("Action initiated", {
                                  description: `Triggered: ${action.kind}`,
                                })
                              }
                            >
                              <Zap className="size-3 mr-1 text-warning" />
                              {action.kind.replace(/_/g, " ")}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl glass-card p-6">
          <h3 className="font-display font-bold text-lg flex items-center gap-2 mb-1">
            <Sparkles className="size-4 text-violet" /> System Suggestions
          </h3>
          <p className="text-sm text-muted-foreground mb-4">Apply with one click</p>
          <div className="space-y-3">
            {suggestions.map((s, i) => (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0, transition: { delay: i * 0.05 } }}
                className="rounded-xl border border-border/60 p-4 bg-background/50"
              >
                <div className="flex items-start gap-2">
                  <Zap className="size-4 text-warning mt-0.5" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">{s.title}</div>
                    <div className="text-xs text-success mt-0.5">{s.impact}</div>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-3">
                  <div className="text-xs text-muted-foreground">
                    Confidence {(s.confidence * 100).toFixed(0)}%
                  </div>
                  <Button
                    size="sm"
                    className="gradient-primary text-white border-0 h-8"
                    onClick={() => toast.success("Action applied", { description: s.title })}
                  >
                    <CheckCircle2 className="size-3.5 mr-1" />
                    Apply
                  </Button>
                </div>
                <div className="mt-2 h-1 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full gradient-primary"
                    style={{ width: `${s.confidence * 100}%` }}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
