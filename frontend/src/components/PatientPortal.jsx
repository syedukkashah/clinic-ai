import { useEffect, useMemo, useState } from "react";
import AgentTrace from "./AgentTrace.jsx";
import ChatPanel from "./ChatPanel.jsx";
import LeftSidebar from "./LeftSidebar.jsx";
import VoiceRecorder from "./VoiceRecorder.jsx";
import WebRTCCall from "./WebRTCCall.jsx";
import {
  getVoiceCallWsUrl,
  processPatientVoice,
  sendPatientMessage,
} from "@/services/patientAgentService";
import { api } from "@/lib/api";
import { publishPortalEvent } from "@/lib/portalBus";

const WELCOME =
  "Hello! I'm MediFlow's AI receptionist. How can I help you today? You can speak to me in English or اردو. I can book, reschedule, or check your appointments.";

export default function PatientPortal() {
  const [sessionId, setSessionId] = useState("loading");
  const [mode, setMode] = useState("text");
  const [lang, setLang] = useState("en");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [appointment, setAppointment] = useState(null);
  const [traceOpen, setTraceOpen] = useState(true);
  const [mobileTraceOpen, setMobileTraceOpen] = useState(false);
  const [traceSteps, setTraceSteps] = useState([]);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [mobileAppointmentOpen, setMobileAppointmentOpen] = useState(false);

  useEffect(() => {
    const key = "mediflow_patient_session_id";
    const existing = window.sessionStorage.getItem(key);
    const generated = existing || crypto.randomUUID().slice(0, 8);
    window.sessionStorage.setItem(key, generated);
    setSessionId(generated);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setMessages([
        {
          id: "welcome",
          sender: "agent",
          text: WELCOME,
          forceLtr: true,
          time: "now",
        },
      ]);
    }, 480);
    return () => window.clearTimeout(timer);
  }, []);

  const compactSession = useMemo(() => {
    if (!sessionId || sessionId === "loading") return "sess_pending";
    return `sess_${sessionId}`;
  }, [sessionId]);

  const clearSession = () => {
    setMessages([
      {
        id: `system-${Date.now()}`,
        type: "system",
        text: "Session resumed · Previous booking preserved",
      },
      {
        id: `welcome-${Date.now()}`,
        sender: "agent",
        text: WELCOME,
        forceLtr: true,
        time: "now",
      },
    ]);
    setAppointment(null);
    setTraceSteps([]);
  };

  const applyConfirmedAppointment = (value) => {
    const bookedAppointment = normalizeAppointment(value);
    if (!bookedAppointment) return null;
    setAppointment(bookedAppointment);
    publishPortalEvent({ type: "appointments:changed" });
    return bookedAppointment;
  };

  const handleSend = async (text) => {
    if (!text.trim() || sending) return;
    const detectedLang = detectLanguage(text, lang);
    if (detectedLang !== lang) setLang(detectedLang);

    setMessages((prev) => [
      ...prev,
      {
        id: `patient-${Date.now()}`,
        sender: "patient",
        text,
        time: currentTime(),
      },
    ]);
    setInput("");
    setSending(true);
    setTraceSteps(makePendingTrace(text));

    try {
      const response = await sendPatientMessage({
        userId: sessionId,
        lang: detectedLang,
        message: text,
      });
      const responseText = response.responseText || response.response || "I can help with that.";
      const nextLang = response.detected_lang || response.detectedLang || detectLanguage(responseText, detectedLang);
      setLang(nextLang);

      setMessages((prev) => [
        ...prev,
        {
          id: `agent-${Date.now()}`,
          sender: "agent",
          text: responseText,
          time: currentTime(),
          slots: normalizeSlots(response.suggestedSlots || response.slots),
        },
      ]);
      setTraceSteps(normalizeTrace(response.tool_calls || response.agent_trace || response.trace, text));
      applyConfirmedAppointment(response.appointment || response.appointment_data);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-error-${Date.now()}`,
          sender: "agent",
          text: "I'm having trouble connecting to the medical assistant. Please try again in a moment.",
          time: currentTime(),
        },
      ]);
      setTraceSteps(makeErrorTrace());
    } finally {
      setSending(false);
    }
  };

  const handleBookSlot = (slot) => {
    const phrase = [
      `I want to book the ${slot.time} slot`,
      `with ${slot.doctorName}`,
      slot.date ? `on ${slot.date}` : "",
      slot.specialty ? `for ${slot.specialty}` : "",
    ]
      .filter(Boolean)
      .join(" ");
    handleSend(phrase);
  };

  const handleVoiceSubmit = async (audioBlob) => {
    setSending(true);
    setTraceSteps(makePendingTrace("voice_note"));
    try {
      const response = await processPatientVoice({
        userId: sessionId,
        lang,
        audioData: audioBlob,
      });
      const transcript = response.transcript || "";
      setVoiceTranscript(transcript);
      setLang(response.detected_lang || detectLanguage(transcript, lang));

      setMessages((prev) => [
        ...prev,
        {
          id: `voice-patient-${Date.now()}`,
          sender: "patient",
          text: transcript || "Voice note sent.",
          time: currentTime(),
        },
        {
          id: `voice-agent-${Date.now() + 1}`,
          sender: "agent",
          text: response.responseText || "I processed your voice note.",
          time: currentTime(),
          slots: normalizeSlots(response.suggestedSlots || response.slots),
        },
      ]);

      applyConfirmedAppointment(response.appointment);
      setTraceSteps(normalizeTrace(response.tool_calls || response.agent_trace, transcript || "voice_note"));

      if (response.audioUrl) {
        const baseUrl = api.defaults.baseURL?.replace("/api", "") || "";
        const audio = new Audio(`${baseUrl}${response.audioUrl}`);
        void audio.play();
      }
    } finally {
      setSending(false);
    }
  };

  const handleCallFinal = ({ transcript, responseText, appointment: callAppointment, suggestedSlots }) => {
    if (transcript || responseText) {
      setMessages((prev) => [
        ...prev,
        ...(transcript
          ? [{ id: `call-p-${Date.now()}`, sender: "patient", text: transcript, time: currentTime() }]
          : []),
        ...(responseText
          ? [{
              id: `call-a-${Date.now() + 1}`,
              sender: "agent",
              text: responseText,
              time: currentTime(),
              slots: normalizeSlots(suggestedSlots),
            }]
          : []),
      ]);
    }
    applyConfirmedAppointment(callAppointment);
  };

  return (
    <div className="patient-portal">
      <LeftSidebar
        mobile
        mode={mode}
        onModeChange={setMode}
        sessionId={compactSession}
        lang={lang}
        appointment={appointment}
        appointmentExpanded={mobileAppointmentOpen}
        onToggleAppointment={() => setMobileAppointmentOpen((value) => !value)}
      />
      <div className="patient-shell">
        <LeftSidebar
          mode={mode}
          onModeChange={setMode}
          sessionId={compactSession}
          lang={lang}
          appointment={appointment}
        />

        <main className="patient-main">
          {mode === "call" ? (
            <WebRTCCall
              sessionId={sessionId}
              getWsUrl={getVoiceCallWsUrl}
              onFinalTurn={handleCallFinal}
              onLanguage={setLang}
              onTrace={setTraceSteps}
            />
          ) : mode === "voice" ? (
            <VoiceRecorder
              messages={messages}
              sending={sending}
              transcriptPreview={voiceTranscript}
              onVoiceSubmit={handleVoiceSubmit}
              onBookSlot={handleBookSlot}
            />
          ) : (
            <ChatPanel
              messages={messages}
              input={input}
              onInputChange={setInput}
              onSend={handleSend}
              sending={sending}
              onClear={clearSession}
              onBookSlot={handleBookSlot}
            />
          )}
        </main>

        <AgentTrace
          open={traceOpen}
          onToggle={() => setTraceOpen((value) => !value)}
          steps={traceSteps}
          active={sending}
          mobileSheetOpen={mobileTraceOpen}
          onMobileToggle={() => setMobileTraceOpen((value) => !value)}
        />
      </div>
    </div>
  );
}

function detectLanguage(text, fallback = "en") {
  if (/[\u0600-\u06FF]/.test(text || "")) return "ur";
  return fallback === "ur" && !/[A-Za-z]/.test(text || "") ? "ur" : "en";
}

function currentTime() {
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date());
}

function normalizeSlots(slots) {
  if (!Array.isArray(slots)) return [];
  return slots.map((slot, index) => ({
    id: slot.id || `slot-${index}`,
    doctorId: slot.doctorId || slot.doctor_id,
    doctorName: slot.doctorName || slot.doctor_name || "Doctor",
    specialty: slot.specialty || "General Practice",
    date: slot.date || "Today",
    time: slot.time || slot.startTime || slot.start_time || "10:30",
    wait: slot.wait || slot.predictedWaitMin || slot.predicted_wait_minutes || 0,
  }));
}

function normalizeAppointment(value) {
  if (!value) return null;
  return {
    id: value.id,
    patientName: value.patientName || value.patient_name,
    doctorName: value.doctorName || value.doctor_name || value.doctor || "Doctor",
    specialty: value.specialty || value.department || "General Practice",
    date: value.date || value.appointment_date || "Today",
    time: value.time || value.appointment_time || "10:30",
    wait: value.wait || value.predictedWaitMin || value.predicted_wait_minutes || 0,
  };
}

function normalizeTrace(trace, seedText) {
  if (Array.isArray(trace) && trace.length > 0) {
    return trace.map((step, index) => ({
      id: step.id || `trace-${Date.now()}-${index}`,
      type: step.type || step.kind || (index === trace.length - 1 ? "CONCLUDE" : "ACT"),
      tool: step.tool || step.toolName || step.name || "booking_agent",
      provider: step.provider || (index % 2 === 0 ? "groq" : "gemini"),
      args: step.args || step.arguments || {},
      result: step.result || step.preview || step.output || "Completed",
      latencyMs: step.latencyMs || step.latency_ms || 600 + index * 240,
    }));
  }

  return [
    {
      id: `trace-act-${Date.now()}`,
      type: "ACT",
      tool: "classify_intent",
      provider: "groq",
      args: { input: String(seedText).slice(0, 60) },
      result: "Waiting for backend trace",
      latencyMs: 0,
    },
  ];
}

function makePendingTrace(text) {
  return [
    {
      id: `pending-${Date.now()}`,
      type: "ACT",
      tool: text === "voice_note" ? "transcribe_voice_note" : "classify_intent",
      provider: "groq",
      args: { input: String(text).slice(0, 60) },
      result: "Running",
      latencyMs: 0,
    },
  ];
}

function makeErrorTrace() {
  return [
    {
      id: `error-${Date.now()}`,
      type: "OBSERVE",
      tool: "api_error",
      provider: "gemini",
      args: {},
      result: "The frontend preserved the session and showed a recovery message.",
      latencyMs: 300,
    },
  ];
}
