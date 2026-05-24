import SlotCard from "./SlotCard.jsx";

export const isUrdu = (text = "") => /[\u0600-\u06FF]/.test(text);

export default function MessageBubble({ message, onBookSlot }) {
  if (message.type === "system") {
    return (
      <div className="system-message">
        <span />
        <p>{message.text}</p>
        <span />
      </div>
    );
  }

  if (message.type === "typing") {
    return (
      <div className="message-row message-row--agent">
        <div className="agent-avatar">M</div>
        <div>
          <div className="message-bubble message-bubble--agent typing-bubble">
            <div className="typing-dots" aria-label="MediFlow is thinking">
              <i />
              <i />
              <i />
            </div>
            <div className="typing-label">MediFlow is thinking...</div>
          </div>
        </div>
      </div>
    );
  }

  const sender = message.sender || message.from;
  const patient = sender === "patient" || sender === "user";
  const urdu = !message.forceLtr && isUrdu(message.text);
  const slots = message.slots || [];
  const hasLongWait = slots.some((slot) => Number(slot.wait ?? slot.predictedWaitMin ?? 0) > 30);

  return (
    <div className={`message-row ${patient ? "message-row--patient" : "message-row--agent"}`}>
      {!patient && <div className="agent-avatar">M</div>}
      <div className={`message-stack ${patient ? "message-stack--patient" : ""}`}>
        <div
          className={[
            "message-bubble",
            patient ? "message-bubble--patient" : "message-bubble--agent",
            urdu ? "urdu-text" : "",
          ].join(" ")}
          dir={urdu ? "rtl" : "auto"}
        >
          <p>{message.text}</p>
          {!patient && hasLongWait && (
            <div className="wait-warning">
              ⚠ Estimated wait is {Math.max(...slots.map((slot) => Number(slot.wait ?? 0)))} min.
              Consider these alternatives:
            </div>
          )}
          {!patient && slots.length > 0 && (
            <div className="slot-list">
              {slots.map((slot) => (
                <SlotCard key={slot.id} slot={slot} onBook={onBookSlot} />
              ))}
            </div>
          )}
        </div>
        <div className={`message-time ${patient ? "message-time--patient" : ""}`}>
          {message.time || "now"}
        </div>
      </div>
    </div>
  );
}
