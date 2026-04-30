import { motion, AnimatePresence } from "framer-motion";
import { Calendar, X, Bot, Repeat2, Mic, UserPlus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getActivity } from "@/services/opsService";

const ICONS = {
  booking: { Icon: Calendar, color: "text-info bg-info/10" },
  cancel: { Icon: X, color: "text-destructive bg-destructive/10" },
  ai: { Icon: Bot, color: "text-violet bg-violet/10" },
  reassign: { Icon: Repeat2, color: "text-warning bg-warning/10" },
  voice: { Icon: Mic, color: "text-primary bg-primary/10" },
  walkin: { Icon: UserPlus, color: "text-success bg-success/10" },
} as const;

export function ActivityFeed() {
  const { data: items = [] } = useQuery({
    queryKey: ["ops", "activity"],
    queryFn: getActivity,
    refetchInterval: 10_000,
  });

  return (
    <div className="rounded-2xl glass-card p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="font-display font-bold text-lg">Live Clinic Activity</h3>
          <p className="text-sm text-muted-foreground">
            Real-time bookings, cancellations and AI actions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-success animate-pulse" />
          <span className="text-xs text-muted-foreground">Live</span>
        </div>
      </div>

      <div className="space-y-2 max-h-[420px] overflow-y-auto scrollbar-thin pr-2">
        <AnimatePresence initial={false}>
          {items.slice(0, 16).map((item) => {
            const cfg = ICONS[item.type as keyof typeof ICONS] ?? ICONS.booking;
            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, x: -12, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 12 }}
                transition={{ type: "spring", stiffness: 320, damping: 28 }}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-muted/50 transition-colors"
              >
                <div className={`size-9 rounded-lg grid place-items-center ${cfg.color}`}>
                  <cfg.Icon className="size-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{item.text}</p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap">{item.time}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
