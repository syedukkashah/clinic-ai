import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Bar,
  Line,
  ComposedChart,
} from "recharts";
import type { TooltipProps } from "recharts";
import { useQuery } from "@tanstack/react-query";
import { getLoadForecast, getWaitSeries } from "@/services/analyticsService";

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg glass-card px-3 py-2 text-xs shadow-elevated">
      <div className="font-medium mb-1">{label}</div>
      {payload.map((p) => (
        <div key={String(p.dataKey ?? p.name ?? "")} className="flex items-center gap-2">
          <span className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{String(p.name ?? "")}:</span>
          <span className="font-semibold">{String(p.value ?? "")}</span>
        </div>
      ))}
    </div>
  );
}

export function WaitTimeChart() {
  const { data = [] } = useQuery({ queryKey: ["analytics", "waitSeries"], queryFn: getWaitSeries });
  return (
    <div className="rounded-2xl glass-card p-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="font-display font-bold text-lg">Predicted Wait Times</h3>
          <p className="text-sm text-muted-foreground">ML forecast vs critical thresholds</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-primary" />
            Predicted
          </div>
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-destructive" />
            Critical 30m
          </div>
        </div>
      </div>
      <div className="h-64 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="waitG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="var(--color-muted-foreground)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="var(--color-muted-foreground)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <ReferenceLine
              y={30}
              stroke="var(--color-destructive)"
              strokeDasharray="4 4"
              label={{
                value: "30m",
                position: "right",
                fill: "var(--color-destructive)",
                fontSize: 10,
              }}
            />
            <ReferenceLine y={45} stroke="var(--color-warning)" strokeDasharray="4 4" />
            <Area
              type="monotone"
              dataKey="wait"
              name="Wait (min)"
              stroke="var(--color-primary)"
              strokeWidth={2.5}
              fill="url(#waitG)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function LoadForecastChart() {
  const { data = [] } = useQuery({
    queryKey: ["analytics", "loadForecast"],
    queryFn: getLoadForecast,
  });
  return (
    <div className="rounded-2xl glass-card p-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="font-display font-bold text-lg">Patient Load Forecast</h3>
          <p className="text-sm text-muted-foreground">Hourly forecast — peak at 13:00 & 15:00</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded bg-teal" />
            Actual
          </div>
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded bg-violet" />
            Predicted
          </div>
        </div>
      </div>
      <div className="h-64 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="actG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-teal)" stopOpacity={0.9} />
                <stop offset="100%" stopColor="var(--color-teal)" stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis
              dataKey="hour"
              stroke="var(--color-muted-foreground)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="var(--color-muted-foreground)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="actual" name="Actual" fill="url(#actG)" radius={[6, 6, 0, 0]} />
            <Line
              type="monotone"
              dataKey="predicted"
              name="Predicted"
              stroke="var(--color-violet)"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "var(--color-violet)" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-warning/10 text-warning text-xs">
        <span className="font-semibold">Insight:</span>
        <span>
          High load expected at 15:00 — consider opening overflow slots or sending appointment
          confirmations early.
        </span>
      </div>
    </div>
  );
}
