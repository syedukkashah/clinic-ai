import { jsxs, jsx } from "react/jsx-runtime";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, AlertTriangle, CalendarCheck2, Users, Clock, HeartPulse } from "lucide-react";
import { A as ActivityFeed } from "./ActivityFeed-CUnDqJ3N.js";
import { useQuery } from "@tanstack/react-query";
import { l as listDoctors } from "./doctorsService-BbKmxHK_.js";
import { ResponsiveContainer, AreaChart, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Area, ComposedChart, Bar, Line } from "recharts";
import { a as api, g as getMetrics, b as getAgents, B as Button } from "./router-kWCNp4I7.js";
import "@tanstack/react-router";
import "react";
import "axios";
import "sonner";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
function StatCard({ label, value, delta, icon: Icon, gradient = "primary", suffix }) {
  const grad = `gradient-${gradient}`;
  const positive = (delta ?? 0) >= 0;
  return /* @__PURE__ */ jsxs(
    motion.div,
    {
      initial: { opacity: 0, y: 12 },
      animate: { opacity: 1, y: 0 },
      whileHover: { y: -4 },
      transition: { type: "spring", stiffness: 300, damping: 24 },
      className: "relative overflow-hidden rounded-2xl glass-card p-6",
      children: [
        /* @__PURE__ */ jsx(
          "div",
          {
            className: `absolute -top-12 -right-12 size-40 rounded-full opacity-20 blur-2xl ${grad}`
          }
        ),
        /* @__PURE__ */ jsxs("div", { className: "relative", children: [
          /* @__PURE__ */ jsxs("div", { className: "flex items-start justify-between mb-4", children: [
            /* @__PURE__ */ jsx("div", { className: `size-11 rounded-xl ${grad} grid place-items-center shadow-glow`, children: /* @__PURE__ */ jsx(Icon, { className: "size-5 text-white" }) }),
            typeof delta === "number" && /* @__PURE__ */ jsxs(
              "div",
              {
                className: `flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${positive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`,
                children: [
                  positive ? /* @__PURE__ */ jsx(TrendingUp, { className: "size-3" }) : /* @__PURE__ */ jsx(TrendingDown, { className: "size-3" }),
                  Math.abs(delta),
                  "%"
                ]
              }
            )
          ] }),
          /* @__PURE__ */ jsx("div", { className: "text-sm text-muted-foreground font-medium", children: label }),
          /* @__PURE__ */ jsxs("div", { className: "mt-1 flex items-baseline gap-1", children: [
            /* @__PURE__ */ jsx("span", { className: "text-3xl font-display font-bold tracking-tight", children: value }),
            suffix && /* @__PURE__ */ jsx("span", { className: "text-sm text-muted-foreground", children: suffix })
          ] })
        ] })
      ]
    }
  );
}
const STATUS_STYLES = {
  available: { dot: "bg-success", chip: "bg-success/10 text-success", label: "Available" },
  busy: { dot: "bg-warning", chip: "bg-warning/10 text-warning", label: "Busy" },
  overloaded: {
    dot: "bg-destructive",
    chip: "bg-destructive/10 text-destructive",
    label: "Overload"
  },
  off: { dot: "bg-muted-foreground", chip: "bg-muted text-muted-foreground", label: "Off" }
};
function DoctorWorkload() {
  const { data: doctors = [] } = useQuery({
    queryKey: ["doctors"],
    queryFn: listDoctors,
    refetchInterval: 15e3
  });
  return /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
    /* @__PURE__ */ jsx("div", { className: "flex items-center justify-between mb-5", children: /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("h3", { className: "font-display font-bold text-lg", children: "Doctor Workload" }),
      /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground", children: "Real-time capacity & overload prediction" })
    ] }) }),
    /* @__PURE__ */ jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3", children: doctors.map((d, i) => {
      const ratio = Math.min(1.2, d.appointmentsToday / d.capacity);
      const pct = Math.round(ratio * 100);
      const s = STATUS_STYLES[d.status];
      return /* @__PURE__ */ jsxs(
        motion.div,
        {
          initial: { opacity: 0, y: 12 },
          animate: { opacity: 1, y: 0 },
          transition: { delay: i * 0.03 },
          whileHover: { y: -2 },
          className: "rounded-xl border border-border/60 bg-background/50 p-4 hover:shadow-soft transition-all",
          children: [
            /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 mb-3", children: [
              /* @__PURE__ */ jsx(
                "div",
                {
                  className: `size-10 rounded-full bg-gradient-to-br ${d.avatarColor} grid place-items-center text-white text-sm font-bold shrink-0`,
                  children: d.name.split(" ")[1]?.[0] ?? "D"
                }
              ),
              /* @__PURE__ */ jsxs("div", { className: "flex-1 min-w-0", children: [
                /* @__PURE__ */ jsx("div", { className: "font-medium text-sm truncate", children: d.name }),
                /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground truncate", children: d.specialty })
              ] }),
              /* @__PURE__ */ jsx("span", { className: `text-[10px] font-semibold px-2 py-0.5 rounded-full ${s.chip}`, children: s.label })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between text-xs mb-1.5", children: [
              /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground", children: [
                d.appointmentsToday,
                " / ",
                d.capacity,
                " appts"
              ] }),
              /* @__PURE__ */ jsxs(
                "span",
                {
                  className: `font-semibold ${pct > 100 ? "text-destructive" : pct > 75 ? "text-warning" : "text-foreground"}`,
                  children: [
                    pct,
                    "%"
                  ]
                }
              )
            ] }),
            /* @__PURE__ */ jsx("div", { className: "h-2 rounded-full bg-muted overflow-hidden", children: /* @__PURE__ */ jsx(
              motion.div,
              {
                initial: { width: 0 },
                animate: { width: `${Math.min(100, pct)}%` },
                transition: { duration: 0.8, ease: "easeOut", delay: i * 0.03 },
                className: `h-full rounded-full ${pct > 100 ? "bg-gradient-to-r from-destructive to-warning" : pct > 75 ? "bg-gradient-to-r from-warning to-destructive" : "gradient-primary"}`
              }
            ) }),
            d.status === "overloaded" && /* @__PURE__ */ jsxs("div", { className: "mt-3 flex items-center gap-1.5 text-[11px] text-destructive", children: [
              /* @__PURE__ */ jsx(AlertTriangle, { className: "size-3" }),
              "Predicted overload — reassign suggested"
            ] })
          ]
        },
        d.id
      );
    }) })
  ] });
}
async function getOverview() {
  const { data } = await api.get("/analytics/overview");
  return data;
}
async function getWaitSeries() {
  const { data } = await api.get("/analytics/wait-series");
  return data;
}
async function getLoadForecast() {
  const { data } = await api.get("/analytics/load-forecast");
  return data;
}
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return /* @__PURE__ */ jsxs("div", { className: "rounded-lg glass-card px-3 py-2 text-xs shadow-elevated", children: [
    /* @__PURE__ */ jsx("div", { className: "font-medium mb-1", children: label }),
    payload.map((p) => /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full", style: { background: p.color } }),
      /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground", children: [
        String(p.name ?? ""),
        ":"
      ] }),
      /* @__PURE__ */ jsx("span", { className: "font-semibold", children: String(p.value ?? "") })
    ] }, String(p.dataKey ?? p.name ?? "")))
  ] });
}
function WaitTimeChart() {
  const { data = [] } = useQuery({ queryKey: ["analytics", "waitSeries"], queryFn: getWaitSeries });
  return /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between mb-2", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { className: "font-display font-bold text-lg", children: "Predicted Wait Times" }),
        /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground", children: "ML forecast vs critical thresholds" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 text-xs", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full bg-primary" }),
          "Predicted"
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full bg-destructive" }),
          "Critical 30m"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "h-64 mt-4", children: /* @__PURE__ */ jsx(ResponsiveContainer, { width: "100%", height: "100%", children: /* @__PURE__ */ jsxs(AreaChart, { data, margin: { left: -20, right: 8, top: 8, bottom: 0 }, children: [
      /* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsxs("linearGradient", { id: "waitG", x1: "0", y1: "0", x2: "0", y2: "1", children: [
        /* @__PURE__ */ jsx("stop", { offset: "0%", stopColor: "var(--color-primary)", stopOpacity: 0.5 }),
        /* @__PURE__ */ jsx("stop", { offset: "100%", stopColor: "var(--color-primary)", stopOpacity: 0 })
      ] }) }),
      /* @__PURE__ */ jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "var(--color-border)", vertical: false }),
      /* @__PURE__ */ jsx(
        XAxis,
        {
          dataKey: "time",
          stroke: "var(--color-muted-foreground)",
          fontSize: 11,
          tickLine: false,
          axisLine: false
        }
      ),
      /* @__PURE__ */ jsx(
        YAxis,
        {
          stroke: "var(--color-muted-foreground)",
          fontSize: 11,
          tickLine: false,
          axisLine: false
        }
      ),
      /* @__PURE__ */ jsx(Tooltip, { content: /* @__PURE__ */ jsx(ChartTooltip, {}) }),
      /* @__PURE__ */ jsx(
        ReferenceLine,
        {
          y: 30,
          stroke: "var(--color-destructive)",
          strokeDasharray: "4 4",
          label: {
            value: "30m",
            position: "right",
            fill: "var(--color-destructive)",
            fontSize: 10
          }
        }
      ),
      /* @__PURE__ */ jsx(ReferenceLine, { y: 45, stroke: "var(--color-warning)", strokeDasharray: "4 4" }),
      /* @__PURE__ */ jsx(
        Area,
        {
          type: "monotone",
          dataKey: "wait",
          name: "Wait (min)",
          stroke: "var(--color-primary)",
          strokeWidth: 2.5,
          fill: "url(#waitG)"
        }
      )
    ] }) }) })
  ] });
}
function LoadForecastChart() {
  const { data = [] } = useQuery({
    queryKey: ["analytics", "loadForecast"],
    queryFn: getLoadForecast
  });
  return /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between mb-2", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { className: "font-display font-bold text-lg", children: "Patient Load Forecast" }),
        /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground", children: "Hourly forecast — peak at 13:00 & 15:00" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 text-xs", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-2 rounded bg-teal" }),
          "Actual"
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-2 rounded bg-violet" }),
          "Predicted"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "h-64 mt-4", children: /* @__PURE__ */ jsx(ResponsiveContainer, { width: "100%", height: "100%", children: /* @__PURE__ */ jsxs(ComposedChart, { data, margin: { left: -20, right: 8, top: 8, bottom: 0 }, children: [
      /* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsxs("linearGradient", { id: "actG", x1: "0", y1: "0", x2: "0", y2: "1", children: [
        /* @__PURE__ */ jsx("stop", { offset: "0%", stopColor: "var(--color-teal)", stopOpacity: 0.9 }),
        /* @__PURE__ */ jsx("stop", { offset: "100%", stopColor: "var(--color-teal)", stopOpacity: 0.4 })
      ] }) }),
      /* @__PURE__ */ jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "var(--color-border)", vertical: false }),
      /* @__PURE__ */ jsx(
        XAxis,
        {
          dataKey: "hour",
          stroke: "var(--color-muted-foreground)",
          fontSize: 11,
          tickLine: false,
          axisLine: false
        }
      ),
      /* @__PURE__ */ jsx(
        YAxis,
        {
          stroke: "var(--color-muted-foreground)",
          fontSize: 11,
          tickLine: false,
          axisLine: false
        }
      ),
      /* @__PURE__ */ jsx(Tooltip, { content: /* @__PURE__ */ jsx(ChartTooltip, {}) }),
      /* @__PURE__ */ jsx(Bar, { dataKey: "actual", name: "Actual", fill: "url(#actG)", radius: [6, 6, 0, 0] }),
      /* @__PURE__ */ jsx(
        Line,
        {
          type: "monotone",
          dataKey: "predicted",
          name: "Predicted",
          stroke: "var(--color-violet)",
          strokeWidth: 2.5,
          dot: { r: 3, fill: "var(--color-violet)" }
        }
      )
    ] }) }) }),
    /* @__PURE__ */ jsxs("div", { className: "mt-3 flex items-start gap-2 p-3 rounded-lg bg-warning/10 text-warning text-xs", children: [
      /* @__PURE__ */ jsx("span", { className: "font-semibold", children: "Insight:" }),
      /* @__PURE__ */ jsx("span", { children: "High load expected at 15:00 — consider opening overflow slots or sending appointment confirmations early." })
    ] })
  ] });
}
function Dashboard() {
  const {
    data: overview
  } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: getOverview,
    refetchInterval: 15e3
  });
  const {
    data: metrics
  } = useQuery({
    queryKey: ["ops", "metrics"],
    queryFn: getMetrics,
    refetchInterval: 1e4
  });
  const {
    data: agents = []
  } = useQuery({
    queryKey: ["ops", "agents"],
    queryFn: getAgents,
    refetchInterval: 1e4
  });
  const totalToday = overview?.totalToday ?? 0;
  const inQueue = overview?.inQueue ?? 0;
  const avgWait = overview?.avgWait ?? 0;
  const health = overview?.health ?? 100;
  const agentsOnline = agents.filter((a) => a.state === "online").length;
  const driftKl = metrics?.waitModelDriftKl ?? 0;
  return /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ jsxs(motion.div, { initial: {
      opacity: 0,
      y: 8
    }, animate: {
      opacity: 1,
      y: 0
    }, className: "flex items-end justify-between flex-wrap gap-3", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h1", { className: "font-display font-bold text-3xl tracking-tight", children: "Operations Overview" }),
        /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "AI-driven insights across your clinic, updated every few seconds." })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs", children: [
        /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full bg-success animate-pulse" }),
        /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground", children: [
          "Models active · drift ",
          driftKl.toFixed(2),
          " · ",
          agentsOnline,
          " agents online"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4", children: [
      /* @__PURE__ */ jsx(StatCard, { label: "Appointments today", value: totalToday, delta: 12, icon: CalendarCheck2, gradient: "primary" }),
      /* @__PURE__ */ jsx(StatCard, { label: "Active in queue", value: inQueue, delta: 4, icon: Users, gradient: "violet" }),
      /* @__PURE__ */ jsx(StatCard, { label: "Avg predicted wait", value: avgWait, suffix: "min", delta: -8, icon: Clock, gradient: "warm" }),
      /* @__PURE__ */ jsx(StatCard, { label: "System health", value: health, suffix: "%", delta: 1, icon: HeartPulse, gradient: "success" })
    ] }),
    driftKl > 0.12 && /* @__PURE__ */ jsxs(motion.div, { initial: {
      opacity: 0,
      scale: 0.95
    }, animate: {
      opacity: 1,
      scale: 1
    }, className: "p-4 rounded-xl border border-warning/40 bg-warning/10 text-warning flex items-center justify-between", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ jsx(AlertTriangle, { className: "size-5" }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("div", { className: "font-bold text-sm", children: "Model Drift Warning" }),
          /* @__PURE__ */ jsxs("div", { className: "text-xs opacity-90", children: [
            "Wait time prediction model (MAE) has drifted beyond threshold (KL:",
            " ",
            driftKl.toFixed(2),
            ")."
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", className: "h-8 text-xs border-warning/40 hover:bg-warning/20", children: "Retrain Model" })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 xl:grid-cols-2 gap-4", children: [
      /* @__PURE__ */ jsx(WaitTimeChart, {}),
      /* @__PURE__ */ jsx(LoadForecastChart, {})
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 xl:grid-cols-3 gap-4", children: [
      /* @__PURE__ */ jsx("div", { className: "xl:col-span-2", children: /* @__PURE__ */ jsx(DoctorWorkload, {}) }),
      /* @__PURE__ */ jsx(ActivityFeed, {})
    ] })
  ] });
}
export {
  Dashboard as component
};
