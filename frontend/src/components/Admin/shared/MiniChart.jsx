import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function MiniChart({ type = "area", data = [], keys = ["value"], height = 180 }) {
  const chartData = data.length ? data : sampleData();
  const axis = {
    tick: { fill: "var(--text-muted)", fontSize: 10, fontFamily: "JetBrains Mono" },
    stroke: "var(--border)",
  };

  const common = (
    <>
      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
      <XAxis dataKey="name" {...axis} />
      <YAxis {...axis} />
      <Tooltip content={<TooltipBox />} />
    </>
  );

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {type === "bar" ? (
          <BarChart data={chartData}>
            {common}
            {keys.map((key, index) => (
              <Bar key={key} dataKey={key} fill={colors[index % colors.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        ) : type === "line" ? (
          <LineChart data={chartData}>
            {common}
            {keys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={false}
                isAnimationActive
                animationDuration={1200}
              />
            ))}
          </LineChart>
        ) : (
          <AreaChart data={chartData}>
            {common}
            <Area
              type="monotone"
              dataKey={keys[0]}
              stroke="var(--accent-teal)"
              fill="var(--accent-teal)"
              fillOpacity={0.22}
              isAnimationActive
              animationDuration={1200}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function TooltipBox({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="admin-chart-tooltip">
      <strong>{label}</strong>
      {payload.map((item) => (
        <span key={item.dataKey}>
          {item.dataKey}: {item.value}
        </span>
      ))}
    </div>
  );
}

function sampleData() {
  return Array.from({ length: 12 }).map((_, index) => ({
    name: `${index * 5}m`,
    value: Math.max(1, Math.round(4 + Math.sin(index / 2) * 3 + (index % 3))),
    p95: Math.max(1, Math.round(7 + Math.cos(index / 3) * 4)),
  }));
}

const colors = ["var(--accent-teal)", "var(--accent-blue)", "var(--accent-amber)", "var(--accent-purple)"];
