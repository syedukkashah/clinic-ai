import { jsxs, jsx } from "react/jsx-runtime";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { l as listAppointments, u as updateAppointment } from "./appointmentsService-MokiHzFH.js";
import { l as listDoctors } from "./doctorsService-BbKmxHK_.js";
import "./router-kWCNp4I7.js";
import "@tanstack/react-router";
import "axios";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
const HOURS = Array.from({
  length: 11
}, (_, i) => 8 + i);
function SchedulingPage() {
  const qc = useQueryClient();
  const {
    data: appointments = []
  } = useQuery({
    queryKey: ["appointments"],
    queryFn: listAppointments
  });
  const {
    data: doctors = []
  } = useQuery({
    queryKey: ["doctors"],
    queryFn: listDoctors
  });
  const updateMut = useMutation({
    mutationFn: (params) => updateAppointment(params.id, params.patch),
    onSuccess: () => qc.invalidateQueries({
      queryKey: ["appointments"]
    })
  });
  const grid = useMemo(() => {
    const map = /* @__PURE__ */ new Map();
    appointments.forEach((a) => {
      const hr = parseInt(a.time.split(":")[0]);
      const key = `${a.doctorId}-${hr}`;
      const arr = map.get(key) ?? [];
      arr.push(a);
      map.set(key, arr);
    });
    return map;
  }, [appointments]);
  const [drag, setDrag] = useState(null);
  const drop = (toDoctorId, toHour) => {
    if (!drag) return;
    const apt = appointments.find((a) => a.id === drag.id);
    if (!apt) return;
    const toDoctor = doctors.find((d) => d.id === toDoctorId);
    if (!toDoctor) return;
    const time = `${String(toHour).padStart(2, "0")}:00`;
    updateMut.mutate({
      id: apt.id,
      patch: {
        doctorId: toDoctorId,
        doctorName: toDoctor.name,
        time
      }
    });
    toast.success("Appointment moved", {
      description: `${apt.patientName} → ${toDoctor.name} at ${time}`
    });
    setDrag(null);
  };
  const suggestions = useMemo(() => {
    return doctors.slice(0, 4).map((d, i) => ({
      doc: d,
      hour: 9 + i * 2,
      reason: "Lower load + matching specialty"
    }));
  }, [doctors]);
  return /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-end justify-between flex-wrap gap-3", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h1", { className: "font-display font-bold text-3xl tracking-tight", children: "Smart Scheduling" }),
        /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Drag any appointment to reschedule. Overloaded slots are highlighted." })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 text-xs", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-3 rounded bg-success/40 border border-success/60" }),
          "Light"
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-3 rounded bg-warning/40 border border-warning/60" }),
          "Busy"
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "size-3 rounded bg-destructive/50 border border-destructive/70" }),
          "Overloaded"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "rounded-2xl glass-card p-4 overflow-x-auto scrollbar-thin", children: /* @__PURE__ */ jsx("div", { className: "min-w-[900px]", children: /* @__PURE__ */ jsxs("div", { className: "grid", style: {
      gridTemplateColumns: `180px repeat(${HOURS.length}, 1fr)`
    }, children: [
      /* @__PURE__ */ jsx("div", { className: "text-xs uppercase tracking-wider text-muted-foreground p-2", children: "Doctor" }),
      HOURS.map((h) => /* @__PURE__ */ jsxs("div", { className: "text-xs uppercase tracking-wider text-muted-foreground p-2 text-center", children: [
        String(h).padStart(2, "0"),
        ":00"
      ] }, h)),
      doctors.slice(0, 8).map((d) => /* @__PURE__ */ jsxs("div", { className: "contents", children: [
        /* @__PURE__ */ jsxs("div", { className: "p-2 border-t border-border/40 flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("div", { className: `size-8 rounded-full bg-gradient-to-br ${d.avatarColor} grid place-items-center text-white text-xs font-bold`, children: d.name.split(" ")[1]?.[0] ?? "D" }),
          /* @__PURE__ */ jsxs("div", { className: "min-w-0", children: [
            /* @__PURE__ */ jsx("div", { className: "text-xs font-medium truncate", children: d.name }),
            /* @__PURE__ */ jsx("div", { className: "text-[10px] text-muted-foreground truncate", children: d.specialty })
          ] })
        ] }),
        HOURS.map((h) => {
          const key = `${d.id}-${h}`;
          const items = grid.get(key) ?? [];
          const load = items.length;
          const tone = load >= 4 ? "bg-destructive/20 border-destructive/40" : load >= 2 ? "bg-warning/15 border-warning/30" : load >= 1 ? "bg-success/10 border-success/20" : "bg-background/40 border-border/40";
          return /* @__PURE__ */ jsxs("div", { onDragOver: (e) => e.preventDefault(), onDrop: () => drop(d.id, h), className: `m-1 min-h-20 rounded-lg border ${tone} p-1.5 space-y-1 transition-colors`, children: [
            items.slice(0, 3).map((a) => /* @__PURE__ */ jsxs(motion.div, { layout: true, draggable: true, onDragStart: () => setDrag({
              id: a.id,
              from: key
            }), whileHover: {
              scale: 1.02
            }, className: "cursor-grab active:cursor-grabbing rounded-md bg-card border border-border/60 px-2 py-1 text-[11px] shadow-soft truncate flex items-center justify-between", title: `${a.patientName} — ${a.reason}`, children: [
              /* @__PURE__ */ jsx("span", { className: "truncate", children: a.patientName }),
              a.urgency === "high" && /* @__PURE__ */ jsx("span", { className: "size-1.5 rounded-full bg-destructive shrink-0 ml-1 animate-pulse" })
            ] }, a.id)),
            items.length > 3 && /* @__PURE__ */ jsxs("div", { className: "text-[10px] text-muted-foreground text-center", children: [
              "+",
              items.length - 3,
              " more"
            ] })
          ] }, key);
        })
      ] }, d.id))
    ] }) }) }),
    /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6", children: [
      /* @__PURE__ */ jsxs("h3", { className: "font-display font-bold text-lg flex items-center gap-2 mb-4", children: [
        /* @__PURE__ */ jsx(Sparkles, { className: "size-4 text-violet" }),
        " Suggested better slots"
      ] }),
      /* @__PURE__ */ jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3", children: suggestions.map((s) => /* @__PURE__ */ jsxs("div", { className: "rounded-xl border border-border/60 p-4 bg-background/50", children: [
        /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: "Suggested slot" }),
        /* @__PURE__ */ jsxs("div", { className: "font-display font-bold text-lg mt-1", children: [
          String(s.hour).padStart(2, "0"),
          ":00"
        ] }),
        /* @__PURE__ */ jsx("div", { className: "text-sm mt-1", children: s.doc.name }),
        /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: s.reason }),
        /* @__PURE__ */ jsxs("button", { className: "mt-3 text-xs font-medium gradient-text inline-flex items-center gap-1", children: [
          "Apply ",
          /* @__PURE__ */ jsx(ArrowRight, { className: "size-3" })
        ] })
      ] }, s.doc.id)) })
    ] })
  ] });
}
export {
  SchedulingPage as component
};
