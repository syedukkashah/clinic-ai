import { useEffect, useRef, useState } from "react";

export default function WebRTCCall({
  sessionId,
  getWsUrl,
  onFinalTurn,
  onLanguage,
  onTrace,
}) {
  const [callState, setCallState] = useState("pre");
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [turns, setTurns] = useState(0);
  const [appointmentCreated, setAppointmentCreated] = useState(false);
  const [lines, setLines] = useState([]);
  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    if (callState !== "active") return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [callState]);

  useEffect(() => () => endCall(false), []);

  const startCall = async () => {
    setCallState("active");
    setSeconds(0);
    setTurns(0);
    setAppointmentCreated(false);
    setLines([{ speaker: "MediFlow", text: "Connected. You can speak naturally now." }]);
    onTrace?.(makeCallTrace("connect", "voice_socket", "WebSocket opened"));

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ws = new WebSocket(getWsUrl({ sessionId }));
      ws.binaryType = "blob";
      wsRef.current = ws;

      ws.onopen = () => {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        const recorder = new MediaRecorder(stream, { mimeType });
        recorderRef.current = recorder;
        recorder.ondataavailable = async (event) => {
          if (event.data.size > 0 && ws.readyState === WebSocket.OPEN && !muted) {
            ws.send(await event.data.arrayBuffer());
          }
        };
        recorder.start(250);
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          const payload = JSON.parse(event.data);
          if (payload.lang || payload.detected_lang) onLanguage?.(payload.detected_lang || payload.lang);
          if (payload.type === "partial" && payload.text) {
            setLines((prev) => replaceLastPartial(prev, payload.text));
          }
          if (payload.type === "final") {
            const userText = payload.transcript || "";
            const agentText = payload.text || "";
            setTurns((value) => value + 1);
            setAppointmentCreated(Boolean(payload.appointment));
            setLines((prev) => [
              ...prev.filter((line) => !line.partial),
              ...(userText ? [{ speaker: "You", text: userText }] : []),
              ...(agentText ? [{ speaker: "MediFlow", text: agentText }] : []),
            ]);
            onFinalTurn?.({
              transcript: userText,
              responseText: agentText,
              appointment: payload.appointment,
              suggestedSlots: payload.suggestedSlots || payload.slots,
            });
            onTrace?.(normalizeTrace(payload.tool_calls || payload.agent_trace, "voice_agent"));
          }
          if (payload.type === "error") {
            setLines((prev) => [...prev, { speaker: "MediFlow", text: payload.text || "Voice call failed." }]);
          }
          return;
        }

        const audioBlob = event.data instanceof Blob ? event.data : new Blob([event.data], { type: "audio/mpeg" });
        if (audioBlob.size > 0) {
          const audioUrl = URL.createObjectURL(audioBlob);
          const audio = new Audio(audioUrl);
          audio.onended = () => URL.revokeObjectURL(audioUrl);
          await audio.play();
        }
      };
    } catch {
      setLines((prev) => [
        ...prev,
        { speaker: "MediFlow", text: "Microphone access was blocked or voice service is unavailable." },
      ]);
    }
  };

  const endCall = (showSummary = true) => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    if (showSummary) setCallState("post");
  };

  if (callState === "post") {
    return (
      <section className="call-screen">
        <div className="call-card call-card--summary">
          <h1>Call Summary</h1>
          <div className="summary-grid">
            <span>Duration</span>
            <strong>{formatTimer(seconds)}</strong>
            <span>Turns</span>
            <strong>{turns}</strong>
            <span>Appointment created</span>
            <strong>{appointmentCreated ? "Yes" : "No"}</strong>
          </div>
          <button type="button" className="start-call-button" onClick={() => setCallState("pre")}>
            Start New Call
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="call-screen">
      <div className="call-card">
        <h1>MediFlow</h1>
        <p>AI Receptionist · Available now</p>
        <div className={`call-avatar ${callState === "active" ? "call-avatar--active" : ""}`}>M</div>
        <div className="call-availability">
          <span />
          {callState === "active" ? `Connected · ${formatTimer(seconds)}` : "Available"}
        </div>

        {callState === "pre" ? (
          <>
            <button type="button" className="start-call-button" onClick={startCall}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6.6 10.8c1.4 2.8 3.8 5.2 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.3 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.8 21 3 13.2 3 3.7c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.3 1.1l-2.2 2.2Z" />
              </svg>
              Start Call
            </button>
            <div className="call-hint">Uses your browser microphone · No app needed</div>
          </>
        ) : (
          <>
            <div className="call-transcript">
              {lines.map((line, index) => (
                <div key={`${line.speaker}-${index}`} className="call-line">
                  <span>{line.speaker}:</span>
                  <p>{line.text}</p>
                </div>
              ))}
            </div>
            <div className="call-controls">
              <button
                type="button"
                className={`call-control ${muted ? "call-control--muted" : ""}`}
                onClick={() => setMuted((value) => !value)}
                aria-label="Mute call"
              >
                {muted ? "🔇" : "🎙"}
              </button>
              <button type="button" className="call-control call-control--end" onClick={() => endCall(true)} aria-label="End call">
                🔴
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function replaceLastPartial(lines, text) {
  const next = lines.filter((line) => !line.partial);
  return [...next, { speaker: "You", text, partial: true }];
}

function formatTimer(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function normalizeTrace(trace, fallbackTool) {
  if (!Array.isArray(trace) || trace.length === 0) return makeCallTrace("observe", fallbackTool, "Voice response received");
  return trace.map((step, index) => ({
    id: step.id || `voice-${index}`,
    type: step.type || (index === trace.length - 1 ? "CONCLUDE" : "ACT"),
    tool: step.tool || step.toolName || fallbackTool,
    provider: step.provider || (index % 2 ? "gemini" : "groq"),
    args: step.args || step.arguments || {},
    result: step.result || step.preview || "Completed",
    latencyMs: step.latencyMs || 700 + index * 220,
  }));
}

function makeCallTrace(type, tool, result) {
  return [
    {
      id: `call-${Date.now()}`,
      type: type === "connect" ? "ACT" : "OBSERVE",
      tool,
      provider: type === "connect" ? "groq" : "gemini",
      args: { session_id: "active" },
      result,
      latencyMs: 620,
    },
  ];
}
