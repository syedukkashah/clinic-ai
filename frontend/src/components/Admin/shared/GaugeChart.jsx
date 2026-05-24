export default function GaugeChart({
  value = 0,
  min = -1,
  max = 1,
  label = "Score",
  size = 220,
}) {
  const numeric = Number.isFinite(Number(value)) ? Number(value) : 0;
  const ratio = Math.max(0, Math.min(1, (numeric - min) / (max - min)));
  const angle = -180 + ratio * 180;
  const tone = numeric < -0.3 ? "red" : numeric < 0.1 ? "amber" : "green";
  const radius = 82;
  const cx = 110;
  const cy = 110;
  const needleLength = 72;
  const needleX = cx + Math.cos((angle * Math.PI) / 180) * needleLength;
  const needleY = cy + Math.sin((angle * Math.PI) / 180) * needleLength;

  return (
    <div className="admin-gauge" style={{ width: size }}>
      <svg viewBox="0 0 220 140" role="img" aria-label={`${label}: ${numeric.toFixed(2)}`}>
        <defs>
          <linearGradient id="admin-gauge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--accent-red)" />
            <stop offset="50%" stopColor="var(--accent-amber)" />
            <stop offset="100%" stopColor="var(--accent-green)" />
          </linearGradient>
        </defs>
        <path
          d="M 28 110 A 82 82 0 0 1 192 110"
          fill="none"
          stroke="var(--bg-elevated)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 28 110 A 82 82 0 0 1 192 110"
          fill="none"
          stroke="url(#admin-gauge-gradient)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <line x1="86" y1="70" x2="96" y2="80" stroke="var(--accent-red)" strokeDasharray="3 3" />
        <text x="70" y="62" fill="var(--text-muted)" fontSize="8" fontFamily="JetBrains Mono">
          -0.3
        </text>
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke={`var(--accent-${tone})`}
          strokeWidth="3"
          strokeLinecap="round"
          className="admin-gauge__needle"
        />
        <circle cx={cx} cy={cy} r="5" fill={`var(--accent-${tone})`} />
      </svg>
      <strong className={`admin-gauge__value admin-text-${tone}`}>{numeric.toFixed(2)}</strong>
      <span>{label}</span>
    </div>
  );
}
