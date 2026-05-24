export default function TimelineBar({ items = [], nextLabel = "Next run pending" }) {
  const safeItems = items.length
    ? items
    : Array.from({ length: 12 }).map((_, index) => ({
        label: `${index * 30}m`,
        tone: index % 5 === 0 ? "amber" : "green",
        title: "Scheduled check",
      }));

  return (
    <div className="admin-timeline">
      <div className="admin-timeline__line" />
      <div className="admin-timeline__items">
        {safeItems.map((item, index) => (
          <span
            key={item.id || `${item.label}-${index}`}
            className={`admin-timeline__dot admin-timeline__dot--${item.tone || "green"}`}
            title={item.title || item.label}
          >
            <small>{item.label}</small>
          </span>
        ))}
      </div>
      <div className="admin-timeline__next">{nextLabel}</div>
    </div>
  );
}
