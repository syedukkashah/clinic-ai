import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";

const QUICK_ACTIONS = [
  { label: "🗓 Book appointment", value: "I would like to book an appointment" },
  { label: "❌ Cancel booking", value: "I want to cancel my appointment" },
  { label: "ℹ️ My appointments", value: "Please check my appointments" },
];

export default function ChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  sending,
  onClear,
  onBookSlot,
}) {
  const endRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 140)}px`;
  }, [input]);

  const submit = () => {
    if (!input.trim() || sending) return;
    onSend(input);
  };

  return (
    <section className="center-panel">
      <div className="center-topbar reveal reveal-delay-3">
        <span>Patient Portal / Text Booking</span>
        <button type="button" className="ghost-button" onClick={onClear}>
          Clear session
        </button>
      </div>

      <div className="message-list reveal reveal-delay-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onBookSlot={onBookSlot} />
        ))}
        {sending && <MessageBubble message={{ id: "typing", type: "typing" }} />}
        <div ref={endRef} />
      </div>

      <div className="text-input-bar reveal reveal-delay-5">
        <div className="text-input-row">
          <textarea
            ref={textareaRef}
            dir="auto"
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="Type in English or اردو میں لکھیں..."
            className="chat-textarea"
            rows={1}
          />
          <button
            type="button"
            className={`send-button ${input.trim() ? "send-button--ready" : ""}`}
            disabled={!input.trim() || sending}
            onClick={submit}
            aria-label="Send message"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3.4 20.3 21.2 12 3.4 3.7 5.1 10.9 14.4 12l-9.3 1.1-1.7 7.2Z" />
            </svg>
          </button>
        </div>
        <div className="quick-chip-row">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              type="button"
              className="quick-chip"
              onClick={() => onInputChange(action.value)}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
