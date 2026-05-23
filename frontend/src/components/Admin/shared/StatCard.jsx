import { useCountUp } from "./hooks";

export default function StatCard({ label, value = 0, unit = "", subtext = "", tone = "teal" }) {
  const animated = useCountUp(Number(value) || 0);
  const display = Number.isInteger(Number(value)) ? Math.round(animated) : animated.toFixed(2);

  return (
    <article className={`admin-stat admin-stat--${tone}`}>
      <div className="admin-stat__label">{label}</div>
      <div className="admin-stat__value">
        {display}
        {unit && <span>{unit}</span>}
      </div>
      <div className="admin-stat__subtext">{subtext || "Live system value"}</div>
    </article>
  );
}
