import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { listDoctors } from "@/services/doctorsService";

const STATUS_STYLES = {
  available: { dot: "bg-success", chip: "bg-success/10 text-success", label: "Available" },
  busy: { dot: "bg-warning", chip: "bg-warning/10 text-warning", label: "Busy" },
  overloaded: {
    dot: "bg-destructive",
    chip: "bg-destructive/10 text-destructive",
    label: "Overload",
  },
  off: { dot: "bg-muted-foreground", chip: "bg-muted text-muted-foreground", label: "Off" },
} as const;

export function DoctorWorkload() {
  const { data: doctors = [] } = useQuery({
    queryKey: ["doctors"],
    queryFn: listDoctors,
    refetchInterval: 15_000,
  });
  return (
    <div className="rounded-2xl glass-card p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="font-display font-bold text-lg">Doctor Workload</h3>
          <p className="text-sm text-muted-foreground">Real-time capacity & overload prediction</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {doctors.map((d, i) => {
          const ratio = Math.min(1.2, d.appointmentsToday / d.capacity);
          const pct = Math.round(ratio * 100);
          const s = STATUS_STYLES[d.status];
          return (
            <motion.div
              key={d.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              whileHover={{ y: -2 }}
              className="rounded-xl border border-border/60 bg-background/50 p-4 hover:shadow-soft transition-all"
            >
              <div className="flex items-center gap-3 mb-3">
                <div
                  className={`size-10 rounded-full bg-gradient-to-br ${d.avatarColor} grid place-items-center text-white text-sm font-bold shrink-0`}
                >
                  {d.name.split(" ")[1]?.[0] ?? "D"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{d.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{d.specialty}</div>
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${s.chip}`}>
                  {s.label}
                </span>
              </div>

              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-muted-foreground">
                  {d.appointmentsToday} / {d.capacity} appts
                </span>
                <span
                  className={`font-semibold ${pct > 100 ? "text-destructive" : pct > 75 ? "text-warning" : "text-foreground"}`}
                >
                  {pct}%
                </span>
              </div>

              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, pct)}%` }}
                  transition={{ duration: 0.8, ease: "easeOut", delay: i * 0.03 }}
                  className={`h-full rounded-full ${
                    pct > 100
                      ? "bg-gradient-to-r from-destructive to-warning"
                      : pct > 75
                        ? "bg-gradient-to-r from-warning to-destructive"
                        : "gradient-primary"
                  }`}
                />
              </div>

              {d.status === "overloaded" && (
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-destructive">
                  <AlertTriangle className="size-3" />
                  Predicted overload — reassign suggested
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
