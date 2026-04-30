import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { Appointment } from "@/lib/mockData";
import { Sparkles, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listAppointments,
  updateAppointment as apiUpdateAppointment,
} from "@/services/appointmentsService";
import { listDoctors } from "@/services/doctorsService";

export const Route = createFileRoute("/scheduling")({
  component: SchedulingPage,
});

const HOURS = Array.from({ length: 11 }, (_, i) => 8 + i); // 08..18

function SchedulingPage() {
  const qc = useQueryClient();
  const { data: appointments = [] } = useQuery({
    queryKey: ["appointments"],
    queryFn: listAppointments,
  });
  const { data: doctors = [] } = useQuery({ queryKey: ["doctors"], queryFn: listDoctors });

  const updateMut = useMutation({
    mutationFn: (params: { id: string; patch: Partial<Appointment> }) =>
      apiUpdateAppointment(params.id, params.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });

  const grid = useMemo(() => {
    const map = new Map<string, typeof appointments>();
    appointments.forEach((a) => {
      const hr = parseInt(a.time.split(":")[0]);
      const key = `${a.doctorId}-${hr}`;
      const arr = map.get(key) ?? [];
      arr.push(a);
      map.set(key, arr);
    });
    return map;
  }, [appointments]);

  const [drag, setDrag] = useState<{ id: string; from: string } | null>(null);

  const drop = (toDoctorId: string, toHour: number) => {
    if (!drag) return;
    const apt = appointments.find((a) => a.id === drag.id);
    if (!apt) return;

    const toDoctor = doctors.find((d) => d.id === toDoctorId);
    if (!toDoctor) return;

    const time = `${String(toHour).padStart(2, "0")}:00`;

    updateMut.mutate({
      id: apt.id,
      patch: { doctorId: toDoctorId, doctorName: toDoctor.name, time },
    });

    toast.success("Appointment moved", {
      description: `${apt.patientName} → ${toDoctor.name} at ${time}`,
    });
    setDrag(null);
  };

  const suggestions = useMemo(() => {
    return doctors.slice(0, 4).map((d, i) => ({
      doc: d,
      hour: 9 + i * 2,
      reason: "Lower load + matching specialty",
    }));
  }, [doctors]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-3xl tracking-tight">Smart Scheduling</h1>
          <p className="text-muted-foreground">
            Drag any appointment to reschedule. Overloaded slots are highlighted.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="size-3 rounded bg-success/40 border border-success/60" />
            Light
          </div>
          <div className="flex items-center gap-1.5">
            <span className="size-3 rounded bg-warning/40 border border-warning/60" />
            Busy
          </div>
          <div className="flex items-center gap-1.5">
            <span className="size-3 rounded bg-destructive/50 border border-destructive/70" />
            Overloaded
          </div>
        </div>
      </div>

      <div className="rounded-2xl glass-card p-4 overflow-x-auto scrollbar-thin">
        <div className="min-w-[900px]">
          <div
            className="grid"
            style={{ gridTemplateColumns: `180px repeat(${HOURS.length}, 1fr)` }}
          >
            <div className="text-xs uppercase tracking-wider text-muted-foreground p-2">Doctor</div>
            {HOURS.map((h) => (
              <div
                key={h}
                className="text-xs uppercase tracking-wider text-muted-foreground p-2 text-center"
              >
                {String(h).padStart(2, "0")}:00
              </div>
            ))}

            {doctors.slice(0, 8).map((d) => (
              <div key={d.id} className="contents">
                <div className="p-2 border-t border-border/40 flex items-center gap-2">
                  <div
                    className={`size-8 rounded-full bg-gradient-to-br ${d.avatarColor} grid place-items-center text-white text-xs font-bold`}
                  >
                    {d.name.split(" ")[1]?.[0] ?? "D"}
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium truncate">{d.name}</div>
                    <div className="text-[10px] text-muted-foreground truncate">{d.specialty}</div>
                  </div>
                </div>
                {HOURS.map((h) => {
                  const key = `${d.id}-${h}`;
                  const items = grid.get(key) ?? [];
                  const load = items.length;
                  const tone =
                    load >= 4
                      ? "bg-destructive/20 border-destructive/40"
                      : load >= 2
                        ? "bg-warning/15 border-warning/30"
                        : load >= 1
                          ? "bg-success/10 border-success/20"
                          : "bg-background/40 border-border/40";
                  return (
                    <div
                      key={key}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => drop(d.id, h)}
                      className={`m-1 min-h-20 rounded-lg border ${tone} p-1.5 space-y-1 transition-colors`}
                    >
                      {items.slice(0, 3).map((a) => (
                        <motion.div
                          key={a.id}
                          layout
                          draggable
                          onDragStart={() => setDrag({ id: a.id, from: key })}
                          whileHover={{ scale: 1.02 }}
                          className="cursor-grab active:cursor-grabbing rounded-md bg-card border border-border/60 px-2 py-1 text-[11px] shadow-soft truncate flex items-center justify-between"
                          title={`${a.patientName} — ${a.reason}`}
                        >
                          <span className="truncate">{a.patientName}</span>
                          {a.urgency === "high" && (
                            <span className="size-1.5 rounded-full bg-destructive shrink-0 ml-1 animate-pulse" />
                          )}
                        </motion.div>
                      ))}
                      {items.length > 3 && (
                        <div className="text-[10px] text-muted-foreground text-center">
                          +{items.length - 3} more
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl glass-card p-6">
        <h3 className="font-display font-bold text-lg flex items-center gap-2 mb-4">
          <Sparkles className="size-4 text-violet" /> Suggested better slots
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {suggestions.map((s) => (
            <div key={s.doc.id} className="rounded-xl border border-border/60 p-4 bg-background/50">
              <div className="text-xs text-muted-foreground">Suggested slot</div>
              <div className="font-display font-bold text-lg mt-1">
                {String(s.hour).padStart(2, "0")}:00
              </div>
              <div className="text-sm mt-1">{s.doc.name}</div>
              <div className="text-xs text-muted-foreground">{s.reason}</div>
              <button className="mt-3 text-xs font-medium gradient-text inline-flex items-center gap-1">
                Apply <ArrowRight className="size-3" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
