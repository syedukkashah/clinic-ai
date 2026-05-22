import LanguageBadge from "./LanguageBadge.jsx";

const MODES = [
  { id: "text", icon: "💬", label: "Text Chat" },
  { id: "voice", icon: "🎙", label: "Voice Note" },
  { id: "call", icon: "📞", label: "Live Call" },
];

export default function LeftSidebar({
  mode,
  onModeChange,
  sessionId,
  lang,
  appointment,
  mobile = false,
  appointmentExpanded,
  onToggleAppointment,
}) {
  if (mobile) {
    return (
      <>
        <header className="patient-mobile-topbar">
          <div className="patient-mobile-logo">MediFlow</div>
          <div className="mobile-mode-switcher" aria-label="Interaction mode">
            {MODES.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`mobile-mode-button ${mode === item.id ? "mobile-mode-button--active" : ""}`}
                onClick={() => onModeChange(item.id)}
                aria-label={item.label}
              >
                {item.icon}
              </button>
            ))}
          </div>
          <LanguageBadge lang={lang} />
        </header>
        {appointment && (
          <button
            type="button"
            className={`mobile-appointment-banner ${appointmentExpanded ? "mobile-appointment-banner--open" : ""}`}
            onClick={onToggleAppointment}
          >
            <span>✓ Appointment Confirmed</span>
            {appointmentExpanded && <AppointmentCard appointment={appointment} />}
          </button>
        )}
      </>
    );
  }

  return (
    <aside className="left-sidebar reveal reveal-delay-0">
      <div className="sidebar-logo reveal reveal-delay-1">
        <h1>MediFlow</h1>
        <p>AI Clinic · بلنگسل</p>
      </div>
      <div className="sidebar-divider" />

      <nav className="mode-switcher reveal reveal-delay-2" aria-label="Interaction mode">
        {MODES.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={`mode-pill ${mode === item.id ? "mode-pill--active" : ""}`}
            style={{ animationDelay: `${160 + index * 80}ms` }}
            onClick={() => onModeChange(item.id)}
          >
            <span className="mode-pill__icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />

      <section className="session-block">
        <div className="sidebar-label">Session</div>
        <div className="session-id">{sessionId}</div>
        <LanguageBadge lang={lang} />
      </section>

      {appointment && <AppointmentCard appointment={appointment} />}

      <div className="sidebar-branding">Powered by Gemini · Groq · XGBoost</div>
    </aside>
  );
}

function AppointmentCard({ appointment }) {
  return (
    <section className="appointment-card">
      <div className="appointment-card__status">✓ Appointment Confirmed</div>
      <div className="appointment-card__doctor">{appointment.doctorName || "Dr. Ahmed Raza"}</div>
      <span className="appointment-card__tag">{appointment.specialty || "General Practice"}</span>
      <div className="appointment-card__time">
        {appointment.date || "Today"} · {appointment.time || "10:30 AM"}
      </div>
      <div className="appointment-card__wait">
        ~{appointment.wait ?? appointment.predictedWaitMin ?? 12} min wait
      </div>
    </section>
  );
}
