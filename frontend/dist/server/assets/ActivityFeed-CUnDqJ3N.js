import { jsxs, jsx } from "react/jsx-runtime";
import { AnimatePresence, motion } from "framer-motion";
import { UserPlus, Mic, Repeat2, Bot, X, Calendar } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { e as getActivity } from "./router-kWCNp4I7.js";
const ICONS = {
  booking: { Icon: Calendar, color: "text-info bg-info/10" },
  cancel: { Icon: X, color: "text-destructive bg-destructive/10" },
  ai: { Icon: Bot, color: "text-violet bg-violet/10" },
  reassign: { Icon: Repeat2, color: "text-warning bg-warning/10" },
  voice: { Icon: Mic, color: "text-primary bg-primary/10" },
  walkin: { Icon: UserPlus, color: "text-success bg-success/10" }
};
function ActivityFeed() {
  const { data: items = [] } = useQuery({
    queryKey: ["ops", "activity"],
    queryFn: getActivity,
    refetchInterval: 1e4
  });
  return /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between mb-5", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { className: "font-display font-bold text-lg", children: "Live Clinic Activity" }),
        /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground", children: "Real-time bookings, cancellations and AI actions" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ jsx("span", { className: "size-2 rounded-full bg-success animate-pulse" }),
        /* @__PURE__ */ jsx("span", { className: "text-xs text-muted-foreground", children: "Live" })
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "space-y-2 max-h-[420px] overflow-y-auto scrollbar-thin pr-2", children: /* @__PURE__ */ jsx(AnimatePresence, { initial: false, children: items.slice(0, 16).map((item) => {
      const cfg = ICONS[item.type] ?? ICONS.booking;
      return /* @__PURE__ */ jsxs(
        motion.div,
        {
          layout: true,
          initial: { opacity: 0, x: -12, scale: 0.96 },
          animate: { opacity: 1, x: 0, scale: 1 },
          exit: { opacity: 0, x: 12 },
          transition: { type: "spring", stiffness: 320, damping: 28 },
          className: "flex items-center gap-3 p-3 rounded-xl hover:bg-muted/50 transition-colors",
          children: [
            /* @__PURE__ */ jsx("div", { className: `size-9 rounded-lg grid place-items-center ${cfg.color}`, children: /* @__PURE__ */ jsx(cfg.Icon, { className: "size-4" }) }),
            /* @__PURE__ */ jsx("div", { className: "flex-1 min-w-0", children: /* @__PURE__ */ jsx("p", { className: "text-sm truncate", children: item.text }) }),
            /* @__PURE__ */ jsx("span", { className: "text-xs text-muted-foreground whitespace-nowrap", children: item.time })
          ]
        },
        item.id
      );
    }) }) })
  ] });
}
export {
  ActivityFeed as A
};
