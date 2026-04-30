import { jsxs, jsx } from "react/jsx-runtime";
import { useState, useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { B as Button } from "./router-kWCNp4I7.js";
import { I as Input, L as Label } from "./label-Bp8Ivt_c.js";
import { S as Select, f as SelectTrigger, g as SelectValue, h as SelectContent, i as SelectItem, D as Dialog, a as DialogContent, b as DialogHeader, c as DialogTitle, e as DialogFooter } from "./select-C9cCNatX.js";
import { Search, Filter, Calendar, Repeat2, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { l as listAppointments, u as updateAppointment } from "./appointmentsService-MokiHzFH.js";
import { l as listDoctors } from "./doctorsService-BbKmxHK_.js";
import "@tanstack/react-router";
import "axios";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-label";
import "@radix-ui/react-dialog";
import "@radix-ui/react-select";
const STATUS_STYLES = {
  Confirmed: "bg-info/15 text-info border-info/30",
  Waiting: "bg-warning/15 text-warning border-warning/30",
  "In Progress": "bg-primary/15 text-primary border-primary/30",
  Completed: "bg-success/15 text-success border-success/30",
  Cancelled: "bg-destructive/15 text-destructive border-destructive/30"
};
function AppointmentsPage() {
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
  const [q, setQ] = useState("");
  const [doctor, setDoctor] = useState("all");
  const [status, setStatus] = useState("all");
  const [editing, setEditing] = useState(null);
  const updateMut = useMutation({
    mutationFn: (params) => updateAppointment(params.id, params.patch),
    onSuccess: () => qc.invalidateQueries({
      queryKey: ["appointments"]
    })
  });
  const filtered = useMemo(() => {
    return appointments.filter((a) => {
      if (doctor !== "all" && a.doctorId !== doctor) return false;
      if (status !== "all" && a.status !== status) return false;
      if (q && !a.patientName.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [appointments, q, doctor, status]);
  const cancel = (id) => {
    updateMut.mutate({
      id,
      patch: {
        status: "Cancelled"
      }
    });
    toast.error("Appointment cancelled", {
      description: "Patient will be notified via SMS & WhatsApp."
    });
  };
  const reassign = (id) => {
    const apt = appointments.find((a) => a.id === id);
    if (!apt) return;
    const others = doctors.filter((d) => d.id !== apt.doctorId);
    const newDoc = others[Math.floor(Math.random() * others.length)];
    if (!newDoc) return;
    updateMut.mutate({
      id,
      patch: {
        doctorId: newDoc.id,
        doctorName: newDoc.name
      }
    });
    toast.success("Patient reassigned", {
      description: `Now with ${newDoc.name}`
    });
  };
  const saveEdit = (apt) => {
    updateMut.mutate({
      id: apt.id,
      patch: {
        patientName: apt.patientName,
        doctorId: apt.doctorId,
        doctorName: apt.doctorName,
        time: apt.time,
        status: apt.status
      }
    });
    setEditing(null);
    toast.success("Appointment updated");
  };
  return /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ jsx("div", { className: "flex items-end justify-between flex-wrap gap-3", children: /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("h1", { className: "font-display font-bold text-3xl tracking-tight", children: "Appointments" }),
      /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground", children: [
        filtered.length,
        " of ",
        appointments.length,
        " appointments today"
      ] })
    ] }) }),
    /* @__PURE__ */ jsx("div", { className: "rounded-2xl glass-card p-4", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap gap-3 items-center", children: [
      /* @__PURE__ */ jsxs("div", { className: "relative flex-1 min-w-[220px]", children: [
        /* @__PURE__ */ jsx(Search, { className: "absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" }),
        /* @__PURE__ */ jsx(Input, { placeholder: "Search patient...", value: q, onChange: (e) => setQ(e.target.value), className: "pl-9" })
      ] }),
      /* @__PURE__ */ jsxs(Select, { value: doctor, onValueChange: setDoctor, children: [
        /* @__PURE__ */ jsx(SelectTrigger, { className: "w-[200px]", children: /* @__PURE__ */ jsx(SelectValue, { placeholder: "Doctor" }) }),
        /* @__PURE__ */ jsxs(SelectContent, { children: [
          /* @__PURE__ */ jsx(SelectItem, { value: "all", children: "All doctors" }),
          doctors.map((d) => /* @__PURE__ */ jsx(SelectItem, { value: d.id, children: d.name }, d.id))
        ] })
      ] }),
      /* @__PURE__ */ jsxs(Select, { value: status, onValueChange: setStatus, children: [
        /* @__PURE__ */ jsx(SelectTrigger, { className: "w-[180px]", children: /* @__PURE__ */ jsx(SelectValue, { placeholder: "Status" }) }),
        /* @__PURE__ */ jsxs(SelectContent, { children: [
          /* @__PURE__ */ jsx(SelectItem, { value: "all", children: "All statuses" }),
          ["Confirmed", "Waiting", "In Progress", "Completed", "Cancelled"].map((s) => /* @__PURE__ */ jsx(SelectItem, { value: s, children: s }, s))
        ] })
      ] }),
      /* @__PURE__ */ jsxs(Button, { variant: "outline", children: [
        /* @__PURE__ */ jsx(Filter, { className: "size-4 mr-2" }),
        "More filters"
      ] })
    ] }) }),
    /* @__PURE__ */ jsx("div", { className: "rounded-2xl glass-card overflow-hidden", children: /* @__PURE__ */ jsx("div", { className: "overflow-x-auto", children: /* @__PURE__ */ jsxs("table", { className: "w-full text-sm", children: [
      /* @__PURE__ */ jsx("thead", { className: "text-xs uppercase tracking-wider text-muted-foreground border-b border-border/60", children: /* @__PURE__ */ jsxs("tr", { children: [
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Patient" }),
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Doctor" }),
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Time" }),
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Reason" }),
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Wait (pred)" }),
        /* @__PURE__ */ jsx("th", { className: "text-left font-medium px-5 py-3", children: "Status" }),
        /* @__PURE__ */ jsx("th", { className: "text-right font-medium px-5 py-3", children: "Actions" })
      ] }) }),
      /* @__PURE__ */ jsx("tbody", { children: /* @__PURE__ */ jsx(AnimatePresence, { initial: false, children: filtered.slice(0, 60).map((a, i) => /* @__PURE__ */ jsxs(motion.tr, { initial: {
        opacity: 0
      }, animate: {
        opacity: 1
      }, exit: {
        opacity: 0
      }, transition: {
        delay: Math.min(i * 0.01, 0.3)
      }, className: "border-b border-border/40 hover:bg-muted/40 transition-colors", children: [
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3", children: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ jsx("div", { className: "size-8 rounded-full gradient-violet grid place-items-center text-white text-xs font-semibold", children: a.patientName[0] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "font-medium", children: a.patientName }),
            /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: a.patientId })
          ] })
        ] }) }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3", children: a.doctorName }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3 font-medium", children: a.time }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3 text-muted-foreground", children: a.reason }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3", children: /* @__PURE__ */ jsxs("span", { className: `font-semibold ${a.predictedWaitMin > 30 ? "text-destructive" : a.predictedWaitMin > 15 ? "text-warning" : "text-success"}`, children: [
          a.predictedWaitMin,
          "m"
        ] }) }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3", children: /* @__PURE__ */ jsx("span", { className: `inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_STYLES[a.status]}`, children: a.status }) }),
        /* @__PURE__ */ jsx("td", { className: "px-5 py-3", children: /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-end gap-1", children: [
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "icon", onClick: () => setEditing(a), title: "Reschedule", children: /* @__PURE__ */ jsx(Calendar, { className: "size-4" }) }),
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "icon", onClick: () => reassign(a.id), title: "Reassign", children: /* @__PURE__ */ jsx(Repeat2, { className: "size-4" }) }),
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "icon", onClick: () => cancel(a.id), title: "Cancel", children: /* @__PURE__ */ jsx(X, { className: "size-4" }) })
        ] }) })
      ] }, a.id)) }) })
    ] }) }) }),
    /* @__PURE__ */ jsx(Dialog, { open: !!editing, onOpenChange: (o) => !o && setEditing(null), children: /* @__PURE__ */ jsxs(DialogContent, { className: "sm:max-w-[480px]", children: [
      /* @__PURE__ */ jsx(DialogHeader, { children: /* @__PURE__ */ jsx(DialogTitle, { children: "Reschedule appointment" }) }),
      editing && /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { children: "Patient" }),
          /* @__PURE__ */ jsx(Input, { value: editing.patientName, onChange: (e) => setEditing({
            ...editing,
            patientName: e.target.value
          }) })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-2 gap-3", children: [
          /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
            /* @__PURE__ */ jsx(Label, { children: "Time" }),
            /* @__PURE__ */ jsx(Input, { type: "time", value: editing.time, onChange: (e) => setEditing({
              ...editing,
              time: e.target.value
            }) })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
            /* @__PURE__ */ jsx(Label, { children: "Status" }),
            /* @__PURE__ */ jsxs(Select, { value: editing.status, onValueChange: (v) => setEditing({
              ...editing,
              status: v
            }), children: [
              /* @__PURE__ */ jsx(SelectTrigger, { children: /* @__PURE__ */ jsx(SelectValue, {}) }),
              /* @__PURE__ */ jsx(SelectContent, { children: ["Confirmed", "Waiting", "In Progress", "Completed", "Cancelled"].map((s) => /* @__PURE__ */ jsx(SelectItem, { value: s, children: s }, s)) })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { children: "Doctor" }),
          /* @__PURE__ */ jsxs(Select, { value: editing.doctorId, onValueChange: (v) => setEditing({
            ...editing,
            doctorId: v,
            doctorName: doctors.find((d) => d.id === v)?.name ?? ""
          }), children: [
            /* @__PURE__ */ jsx(SelectTrigger, { className: "w-full", children: /* @__PURE__ */ jsx(SelectValue, {}) }),
            /* @__PURE__ */ jsx(SelectContent, { children: doctors.map((d) => /* @__PURE__ */ jsx(SelectItem, { value: d.id, children: d.name }, d.id)) })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "rounded-lg bg-info/10 text-info text-xs p-3", children: [
          "AI suggestion: 14:15 with ",
          doctors[0]?.name ?? "Staff",
          " reduces predicted wait by 12 min."
        ] })
      ] }),
      /* @__PURE__ */ jsxs(DialogFooter, { children: [
        /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => setEditing(null), children: "Cancel" }),
        /* @__PURE__ */ jsx(Button, { className: "gradient-primary text-white border-0", onClick: () => editing && saveEdit(editing), children: "Save changes" })
      ] })
    ] }) })
  ] });
}
export {
  AppointmentsPage as component
};
