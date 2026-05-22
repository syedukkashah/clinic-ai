export default function SlotCard({ slot, onBook }) {
  const wait = Number(slot.wait ?? slot.predictedWaitMin ?? 0);

  return (
    <div className="slot-card">
      <div className="slot-card__top">
        <div>
          <div className="slot-card__doctor">{slot.doctorName}</div>
          <div className="slot-card__specialty">{slot.specialty}</div>
        </div>
        <div className="slot-card__meta">
          <div className="slot-card__time">{slot.time}</div>
          <div className="slot-card__wait">~{wait} min</div>
        </div>
      </div>
      <button type="button" className="slot-card__book" onClick={() => onBook(slot)}>
        Book this slot →
      </button>
    </div>
  );
}
