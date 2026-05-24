export default function HeatmapGrid({ rows = [], hours = defaultHours }) {
  const safeRows = rows.length ? rows : [{ name: "No forecast data", values: hours.map(() => null) }];

  return (
    <div className="admin-heatmap">
      <div className="admin-heatmap__header">
        <span />
        {hours.map((hour) => (
          <span key={hour}>{hour}</span>
        ))}
      </div>
      {safeRows.map((row) => (
        <div className="admin-heatmap__row" key={row.id || row.name}>
          <strong>{row.name}</strong>
          {hours.map((hour, index) => {
            const value = row.values?.[index];
            return (
              <span key={`${row.name}-${hour}`} className={`admin-heatmap__cell ${toneFor(value)}`}>
                {value ?? "--"}
              </span>
            );
          })}
        </div>
      ))}
      <div className="admin-heatmap__legend">
        <span>0</span>
        <div />
        <span>10+</span>
      </div>
    </div>
  );
}

function toneFor(value) {
  if (value == null) return "admin-heatmap__cell--empty";
  if (value >= 10) return "admin-heatmap__cell--red";
  if (value >= 7) return "admin-heatmap__cell--amber";
  if (value >= 4) return "admin-heatmap__cell--blue";
  return "admin-heatmap__cell--low";
}

const defaultHours = ["8a", "9a", "10a", "11a", "12p", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p"];
