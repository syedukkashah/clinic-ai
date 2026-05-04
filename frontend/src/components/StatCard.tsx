import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  delta?: number;
  icon: LucideIcon;
  gradient?: "primary" | "violet" | "warm" | "success";
  suffix?: string;
}

export function StatCard({ label, value, delta, icon: Icon, gradient = "primary", suffix }: Props) {
  const grad = `gradient-${gradient}`;
  const positive = (delta ?? 0) >= 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className="relative overflow-hidden rounded-2xl glass-card p-6"
    >
      <div
        className={`absolute -top-12 -right-12 size-40 rounded-full opacity-20 blur-2xl ${grad}`}
      />
      <div className="relative">
        <div className="flex items-start justify-between mb-4">
          <div className={`size-11 rounded-xl ${grad} grid place-items-center shadow-glow`}>
            <Icon className="size-5 text-white" />
          </div>
          {typeof delta === "number" && (
            <div
              className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${
                positive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
              }`}
            >
              {positive ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
              {Math.abs(delta)}%
            </div>
          )}
        </div>
        <div className="text-sm text-muted-foreground font-medium">{label}</div>
        <div className="mt-1 flex items-baseline gap-1">
          <span className="text-3xl font-display font-bold tracking-tight">{value}</span>
          {suffix && <span className="text-sm text-muted-foreground">{suffix}</span>}
        </div>
      </div>
    </motion.div>
  );
}
