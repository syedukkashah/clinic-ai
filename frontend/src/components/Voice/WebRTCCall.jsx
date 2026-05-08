import { useState, useRef, useCallback, useEffect } from "react";

/**
 * WebRTCCall — Real-time voice call component (v5.0)
 *
 * Opens a WebSocket to /ws/voice/{session_id}, streams 250ms audio chunks,
 * displays live partial transcripts from Deepgram, and plays back the
 * agent's TTS audio response.
 */

const API_WS_BASE =
  import.meta.env.VITE_WS_BASE_URL || `ws://${window.location.host}`;

export default function WebRTCCall({ sessionId }) {
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | connecting | connected | error

  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);

  const appendMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { role, text, ts: Date.now() }]);
  }, []);

  // --- WebSocket lifecycle ---

  const connect = useCallback(() => {
    const sid = sessionId || `web_${Date.now()}`;
    const url = `${API_WS_BASE}/ws/voice/${sid}`;

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        // Binary — audio response from TTS
        const blob = new Blob([e.data], { type: "audio/mpeg" });
        const audio = new Audio(URL.createObjectURL(blob));
        audio.play().catch(() => {});
      } else {
        // JSON message
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "partial") {
            setLiveTranscript(msg.text);
          } else if (msg.type === "final") {
            setLiveTranscript("");
            appendMessage("user", msg.transcript);
            appendMessage("assistant", msg.text);
          } else if (msg.type === "error") {
            setStatus("error");
            appendMessage("system", msg.text);
          }
        } catch {
          // ignore malformed messages
        }
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };

    ws.onclose = () => {
      setStatus("idle");
      setIsRecording(false);
    };
  }, [sessionId, appendMessage]);

  // --- MediaRecorder (250ms chunks) ---

  const startRecording = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      // Wait briefly for connection
      await new Promise((r) => setTimeout(r, 500));
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setStatus("error");
        return;
      }
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (
          e.data.size > 0 &&
          wsRef.current &&
          wsRef.current.readyState === WebSocket.OPEN
        ) {
          wsRef.current.send(e.data);
        }
      };

      recorder.start(250); // 250ms timeslice
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access denied:", err);
      setStatus("error");
    }
  }, [connect]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [stopRecording]);

  // --- UI ---

  const handleToggle = () => {
    if (isRecording) {
      stopRecording();
    } else {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
      }
      startRecording();
    }
  };

  return (
    <div className="webrtc-call">
      {/* Status indicator */}
      <div className="webrtc-status" data-status={status}>
        {status === "connecting" && "Connecting…"}
        {status === "connected" && "Connected"}
        {status === "error" && "Connection error"}
        {status === "idle" && "Ready"}
      </div>

      {/* Live transcript (partial from Deepgram) */}
      {liveTranscript && (
        <div className="live-transcript">{liveTranscript}</div>
      )}

      {/* Message history */}
      <div className="webrtc-messages">
        {messages.map((m, i) => (
          <div key={i} className={`webrtc-msg webrtc-msg--${m.role}`}>
            <span className="webrtc-msg-role">{m.role}:</span> {m.text}
          </div>
        ))}
      </div>

      {/* Mic toggle */}
      <button
        className={`webrtc-mic-btn ${isRecording ? "webrtc-mic-btn--active" : ""}`}
        onClick={handleToggle}
        aria-label={isRecording ? "Stop recording" : "Start recording"}
      >
        {isRecording ? "⏹ Stop" : "🎤 Speak"}
      </button>
    </div>
  );
}
