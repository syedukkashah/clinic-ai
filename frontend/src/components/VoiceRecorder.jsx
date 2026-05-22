import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";

export default function VoiceRecorder({ messages, sending, transcriptPreview, onVoiceSubmit, onBookSlot }) {
  const [state, setState] = useState("idle");
  const [duration, setDuration] = useState(0);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (state !== "recording") {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
      return;
    }
    intervalRef.current = window.setInterval(() => {
      setDuration((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(intervalRef.current);
  }, [state]);

  useEffect(() => {
    return () => {
      window.clearInterval(intervalRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const startRecording = async () => {
    if (state !== "idle") return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];
    setDuration(0);

    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = async () => {
      setState("processing");
      const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      await onVoiceSubmit(audioBlob);
      setState("idle");
    };
    recorder.start();
    setState("recording");
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  };

  const processing = state === "processing" || sending;
  const recording = state === "recording";

  return (
    <section className="center-panel">
      <div className="center-topbar reveal reveal-delay-3">
        <span>Patient Portal / Voice Note</span>
      </div>
      <div className="message-list reveal reveal-delay-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onBookSlot={onBookSlot} />
        ))}
      </div>

      <div className="voice-recorder-panel reveal reveal-delay-5">
        {transcriptPreview && (
          <div className="transcript-pill">🎙 Transcript: {transcriptPreview}</div>
        )}
        <button
          type="button"
          className={[
            "voice-record-button",
            recording ? "voice-record-button--recording" : "",
            processing ? "voice-record-button--processing" : "",
          ].join(" ")}
          onClick={recording ? stopRecording : startRecording}
          disabled={processing}
          aria-label={recording ? "Stop recording" : "Start recording"}
        >
          {processing ? (
            <span className="spinner-ring" />
          ) : recording ? (
            <span className="stop-square" />
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 15a4 4 0 0 0 4-4V6a4 4 0 0 0-8 0v5a4 4 0 0 0 4 4Zm6-4a6 6 0 0 1-12 0H4a8 8 0 0 0 7 7.93V22h2v-3.07A8 8 0 0 0 20 11h-2Z" />
            </svg>
          )}
        </button>

        {recording && (
          <div className="waveform">
            {[0, 80, 160, 240, 160, 80, 0].map((delay, index) => (
              <span key={`${delay}-${index}`} style={{ animationDelay: `${delay}ms` }} />
            ))}
            <time>{formatDuration(duration)}</time>
          </div>
        )}

        <div className={`voice-label ${recording ? "voice-label--active" : ""}`}>
          {processing ? "Transcribing..." : recording ? "Recording... tap to stop" : "Tap to record"}
        </div>
        <div className="voice-hint">Speak clearly in English or صاف اردو میں بولیں</div>
      </div>
    </section>
  );
}

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
