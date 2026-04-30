import { jsxs, jsx } from "react/jsx-runtime";
import { motion } from "framer-motion";
import { Brain, Activity, AlertTriangle, Zap, Sparkles, CheckCircle2 } from "lucide-react";
import { l as listAlerts, d as getSuggestions, g as getMetrics, b as getAgents, B as Button } from "./router-kWCNp4I7.js";
import { toast } from "sonner";
import { ResponsiveContainer, RadialBarChart, PolarAngleAxis, RadialBar, AreaChart, CartesianGrid, XAxis, YAxis, Tooltip, Area } from "recharts";
import { useQuery } from "@tanstack/react-query";
import "@tanstack/react-router";
import "react";
import "axios";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
const SEV_STYLES = {
  High: {
    bg: "bg-destructive/15",
    text: "text-destructive",
    border: "border-destructive/40",
    dot: "bg-destructive"
  },
  Medium: {
    bg: "bg-warning/15",
    text: "text-warning",
    border: "border-warning/40",
    dot: "bg-warning"
  },
  Low: {
    bg: "bg-success/15",
    text: "text-success",
    border: "border-success/40",
    dot: "bg-success"
  }
};
const ANOMALY_SERIES = Array.from({
  length: 24
}, (_, i) => ({
  t: `${i}h`,
  score: Math.max(0, Math.min(1, 0.2 + Math.sin(i / 3) * 0.15 + (i > 18 ? 0.4 : 0) + Math.random() * 0.1))
}));
function AIOpsPage() {
  const {
    data: alerts = []
  } = useQuery({
    queryKey: ["alerts"],
    queryFn: listAlerts,
    refetchInterval: 15e3
  });
  const {
    data: suggestions = []
  } = useQuery({
    queryKey: ["ops", "suggestions"],
    queryFn: getSuggestions,
    refetchInterval: 2e4
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
  const anomalyScore = metrics?.anomalyScore ?? 0;
  const agentsOnline = agents.filter((a) => a.state === "online").length;
  return /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-end justify-between flex-wrap gap-3", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsxs("h1", { className: "font-display font-bold text-3xl tracking-tight flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("span", { className: "size-8 rounded-lg gradient-violet grid place-items-center", children: /* @__PURE__ */ jsx(Brain, { className: "size-4 text-white" }) }),
          "AI Operations Monitor"
        ] }),
        /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Anomaly detection, model health & autonomous recommendations" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs", children: [
        /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full bg-success animate-pulse" }),
        "3 models active ·",
        " ",
        agentsOnline,
        " agents online"
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-4", children: [
      /* @__PURE__ */ jsxs(motion.div, { initial: {
        opacity: 0,
        y: 10
      }, animate: {
        opacity: 1,
        y: 0
      }, className: "rounded-2xl glass-card p-6", children: [
        /* @__PURE__ */ jsx("div", { className: "text-sm text-muted-foreground", children: "Composite Anomaly Score" }),
        /* @__PURE__ */ jsxs("div", { className: "relative h-56 mt-2", children: [
          /* @__PURE__ */ jsx(ResponsiveContainer, { width: "100%", height: "100%", children: /* @__PURE__ */ jsxs(RadialBarChart, { innerRadius: "70%", outerRadius: "100%", data: [{
            name: "score",
            value: anomalyScore * 100
          }], startAngle: 210, endAngle: -30, children: [
            /* @__PURE__ */ jsx(PolarAngleAxis, { type: "number", domain: [0, 100], tick: false }),
            /* @__PURE__ */ jsx(RadialBar, { dataKey: "value", cornerRadius: 20, fill: "url(#anomG)", background: {
              fill: "var(--color-muted)"
            } }),
            /* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsxs("linearGradient", { id: "anomG", x1: "0", y1: "0", x2: "1", y2: "1", children: [
              /* @__PURE__ */ jsx("stop", { offset: "0%", stopColor: "var(--color-warning)" }),
              /* @__PURE__ */ jsx("stop", { offset: "100%", stopColor: "var(--color-destructive)" })
            ] }) })
          ] }) }),
          /* @__PURE__ */ jsx("div", { className: "absolute inset-0 grid place-items-center text-center", children: /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "text-5xl font-display font-bold gradient-text", children: (anomalyScore * 100).toFixed(0) }),
            /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground mt-1", children: "Elevated risk" })
          ] }) })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "grid grid-cols-3 gap-2 text-center text-xs", children: [{
          l: "Surge",
          v: "0.92",
          c: "text-destructive"
        }, {
          l: "Latency",
          v: "0.61",
          c: "text-warning"
        }, {
          l: "Drift",
          v: "0.44",
          c: "text-warning"
        }].map((x) => /* @__PURE__ */ jsxs("div", { className: "rounded-lg bg-muted/50 p-2", children: [
          /* @__PURE__ */ jsx("div", { className: `font-bold ${x.c}`, children: x.v }),
          /* @__PURE__ */ jsx("div", { className: "text-muted-foreground", children: x.l })
        ] }, x.l)) })
      ] }),
      /* @__PURE__ */ jsxs(motion.div, { initial: {
        opacity: 0,
        y: 10
      }, animate: {
        opacity: 1,
        y: 0,
        transition: {
          delay: 0.05
        }
      }, className: "rounded-2xl glass-card p-6 lg:col-span-2", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between mb-2", children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "font-display font-semibold", children: "Anomaly score · last 24h" }),
            /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: "Composite of booking, latency & drift signals" })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "text-xs text-muted-foreground flex items-center gap-2", children: [
            /* @__PURE__ */ jsx(Activity, { className: "size-3.5" }),
            "Streaming"
          ] })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "h-56", children: /* @__PURE__ */ jsx(ResponsiveContainer, { width: "100%", height: "100%", children: /* @__PURE__ */ jsxs(AreaChart, { data: ANOMALY_SERIES, margin: {
          left: -20,
          right: 8,
          top: 8,
          bottom: 0
        }, children: [
          /* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsxs("linearGradient", { id: "anomA", x1: "0", y1: "0", x2: "0", y2: "1", children: [
            /* @__PURE__ */ jsx("stop", { offset: "0%", stopColor: "var(--color-violet)", stopOpacity: 0.6 }),
            /* @__PURE__ */ jsx("stop", { offset: "100%", stopColor: "var(--color-violet)", stopOpacity: 0 })
          ] }) }),
          /* @__PURE__ */ jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "var(--color-border)", vertical: false }),
          /* @__PURE__ */ jsx(XAxis, { dataKey: "t", stroke: "var(--color-muted-foreground)", fontSize: 10, tickLine: false, axisLine: false }),
          /* @__PURE__ */ jsx(YAxis, { stroke: "var(--color-muted-foreground)", fontSize: 10, tickLine: false, axisLine: false, domain: [0, 1] }),
          /* @__PURE__ */ jsx(Tooltip, { contentStyle: {
            background: "var(--color-card)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            fontSize: 12
          } }),
          /* @__PURE__ */ jsx(Area, { type: "monotone", dataKey: "score", stroke: "var(--color-violet)", strokeWidth: 2.5, fill: "url(#anomA)" })
        ] }) }) })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-4", children: [
      /* @__PURE__ */ jsxs("div", { className: "lg:col-span-2 rounded-2xl glass-card p-6", children: [
        /* @__PURE__ */ jsx("div", { className: "flex items-center justify-between mb-4", children: /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsxs("h3", { className: "font-display font-bold text-lg flex items-center gap-2", children: [
            /* @__PURE__ */ jsx(AlertTriangle, { className: "size-4 text-warning" }),
            "Active Alerts"
          ] }),
          /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground", children: "AI-generated reasoning for each event" })
        ] }) }),
        /* @__PURE__ */ jsx("div", { className: "space-y-3", children: alerts.map((a, i) => {
          const s = SEV_STYLES[a.severity];
          return /* @__PURE__ */ jsx(motion.div, { initial: {
            opacity: 0,
            x: -8
          }, animate: {
            opacity: 1,
            x: 0
          }, transition: {
            delay: i * 0.06
          }, className: `rounded-xl border ${s.border} ${s.bg} p-4`, children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-3", children: [
            /* @__PURE__ */ jsxs("div", { className: "relative shrink-0 mt-1", children: [
              /* @__PURE__ */ jsx("span", { className: `size-2.5 rounded-full block ${s.dot}` }),
              a.severity === "High" && /* @__PURE__ */ jsx("span", { className: `absolute inset-0 rounded-full ${s.dot} animate-pulse-ring` })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "flex-1 min-w-0", children: [
              /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between gap-3 flex-wrap", children: [
                /* @__PURE__ */ jsx("div", { className: "font-semibold", children: a.title }),
                /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
                  /* @__PURE__ */ jsx("span", { className: `text-[10px] font-bold px-2 py-0.5 rounded-full ${s.text} ${s.bg} border ${s.border}`, children: a.severity.toUpperCase() }),
                  /* @__PURE__ */ jsx("span", { className: "text-xs text-muted-foreground", children: a.timestamp })
                ] })
              ] }),
              /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground mt-1.5", children: a.reasoning }),
              a.trace && /* @__PURE__ */ jsxs("div", { className: "mt-3 space-y-1", children: [
                /* @__PURE__ */ jsx("div", { className: "text-[10px] font-bold text-muted-foreground uppercase tracking-wider", children: "Reasoning Trace" }),
                /* @__PURE__ */ jsx("div", { className: "rounded-lg bg-background/40 p-2 font-mono text-[10px] space-y-0.5 border border-border/40", children: a.trace.map((t, idx) => /* @__PURE__ */ jsxs("div", { className: "flex gap-2", children: [
                  /* @__PURE__ */ jsx("span", { className: "text-muted-foreground opacity-50", children: idx + 1 }),
                  /* @__PURE__ */ jsx("span", { children: t })
                ] }, idx)) })
              ] }),
              a.recommendedActions && /* @__PURE__ */ jsx("div", { className: "mt-3 flex flex-wrap gap-2", children: a.recommendedActions.map((action, idx) => /* @__PURE__ */ jsxs(Button, { size: "sm", variant: "outline", className: "h-7 text-[10px] font-bold uppercase tracking-tight bg-background/50", onClick: () => toast.success("Action initiated", {
                description: `Triggered: ${action.kind}`
              }), children: [
                /* @__PURE__ */ jsx(Zap, { className: "size-3 mr-1 text-warning" }),
                action.kind.replace(/_/g, " ")
              ] }, idx)) })
            ] })
          ] }) }, a.id);
        }) })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
        /* @__PURE__ */ jsxs("h3", { className: "font-display font-bold text-lg flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ jsx(Sparkles, { className: "size-4 text-violet" }),
          " System Suggestions"
        ] }),
        /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground mb-4", children: "Apply with one click" }),
        /* @__PURE__ */ jsx("div", { className: "space-y-3", children: suggestions.map((s, i) => /* @__PURE__ */ jsxs(motion.div, { initial: {
          opacity: 0,
          y: 8
        }, animate: {
          opacity: 1,
          y: 0,
          transition: {
            delay: i * 0.05
          }
        }, className: "rounded-xl border border-border/60 p-4 bg-background/50", children: [
          /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-2", children: [
            /* @__PURE__ */ jsx(Zap, { className: "size-4 text-warning mt-0.5" }),
            /* @__PURE__ */ jsxs("div", { className: "flex-1", children: [
              /* @__PURE__ */ jsx("div", { className: "font-medium text-sm", children: s.title }),
              /* @__PURE__ */ jsx("div", { className: "text-xs text-success mt-0.5", children: s.impact })
            ] })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between mt-3", children: [
            /* @__PURE__ */ jsxs("div", { className: "text-xs text-muted-foreground", children: [
              "Confidence ",
              (s.confidence * 100).toFixed(0),
              "%"
            ] }),
            /* @__PURE__ */ jsxs(Button, { size: "sm", className: "gradient-primary text-white border-0 h-8", onClick: () => toast.success("Action applied", {
              description: s.title
            }), children: [
              /* @__PURE__ */ jsx(CheckCircle2, { className: "size-3.5 mr-1" }),
              "Apply"
            ] })
          ] }),
          /* @__PURE__ */ jsx("div", { className: "mt-2 h-1 rounded-full bg-muted overflow-hidden", children: /* @__PURE__ */ jsx("div", { className: "h-full gradient-primary", style: {
            width: `${s.confidence * 100}%`
          } }) })
        ] }, s.id)) })
      ] })
    ] })
  ] });
}
export {
  AIOpsPage as component
};
