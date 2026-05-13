import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Headphones,
  Mail,
  Mic,
  PhoneCall,
  Send,
  Square,
  Stethoscope,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  contactAgent,
  getVoiceCallWsUrl,
  processPatientVoice,
  sendPatientMessage,
  type ContactChannel,
  type PatientLang,
} from "@/services/patientAgentService";
import { getAdminPortalUrl, getPortal } from "@/lib/portal";
import { publishPortalEvent } from "@/lib/portalBus";
import { api } from "@/lib/api";

export const Route = createFileRoute("/patient")({
  component: PatientPage,
});

interface Msg {
  id: string;
  from: "user" | "ai";
  text: string;
  time: string;
}

const QUICK: Record<PatientLang, string[]> = {
  en: ["Book an appointment", "Reschedule", "Clinic hours", "Talk to an agent"],
  ur: ["اپوائنٹمنٹ بک کریں", "اپوائنٹمنٹ تبدیل کریں", "کلینک اوقات", "ایجنٹ سے بات"],
};

function getPatientSessionId() {
  if (typeof window === "undefined") return "patient-ssr";
  const key = "mediflow_patient_session_id";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const generated =
    typeof window.crypto?.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `patient-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.localStorage.setItem(key, generated);
  return generated;
}

function PatientPage() {
  const portal = getPortal();
  const sessionIdRef = useRef(getPatientSessionId());
  const [lang, setLang] = useState<PatientLang>("en");
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      id: "m0",
      from: "ai",
      text: "Hi! I'm MediFlow's assistant. How can I help you today?",
      time: "now",
    },
  ]);
  const [input, setInput] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const [callOpen, setCallOpen] = useState(false);
  const [callState, setCallState] = useState<{
    status: "idle" | "connecting" | "connected";
    greeting?: string;
    callId?: string;
  }>({ status: "idle" });
  const [callTranscript, setCallTranscript] = useState("");
  const [callReply, setCallReply] = useState("");
  const [callError, setCallError] = useState("");
  const [callWsUrl, setCallWsUrl] = useState("");
  const callWsRef = useRef<WebSocket | null>(null);
  const callRecorderRef = useRef<MediaRecorder | null>(null);
  const callStreamRef = useRef<MediaStream | null>(null);

  const [contactOpen, setContactOpen] = useState(false);
  const [contactChannel, setContactChannel] = useState<ContactChannel>("email");
  const [contactMessage, setContactMessage] = useState("");
  const [contactSending, setContactSending] = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const resetWelcome = (l: PatientLang) => {
    setMsgs([
      {
        id: "m0",
        from: "ai",
        text:
          l === "en"
            ? "Hi! I'm MediFlow's assistant. How can I help you today?"
            : "السلام علیکم! میں آپ کی کیا مدد کر سکتا ہوں؟",
        time: "now",
      },
    ]);
  };

  const sendUser = async (text: string) => {
    if (!text.trim()) return;
    if (text === "Talk to an agent" || text === "ایجنٹ سے بات") {
      setContactOpen(true);
      setContactMessage("");
      return;
    }
    const userMsg: Msg = { id: `u${Date.now()}`, from: "user", text, time: "now" };
    setMsgs((p) => [...p, userMsg]);
    setInput("");
    try {
      setSending(true);
      const res = await sendPatientMessage({ userId: sessionIdRef.current, lang, message: text });
      setMsgs((p) => [
        ...p,
        { id: `a${Date.now()}`, from: "ai", text: res.responseText, time: "now" },
      ]);
    } catch {
      toast.error(lang === "ur" ? "پیغام نہیں بھیجا جا سکا" : "Message failed");
    } finally {
      setSending(false);
    }
  };

  const currentQuick = QUICK[lang];

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        await handleVoiceSubmit(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setRecording(true);
      setTranscript(lang === "en" ? "Listening..." : "سن رہا ہوں...");
    } catch (err) {
      toast.error(lang === "ur" ? "مائیکروفون تک رسائی نہیں ہے" : "Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const handleVoiceSubmit = async (audioBlob: Blob) => {
    try {
      setSending(true);
      const data = await processPatientVoice({
        userId: sessionIdRef.current,
        lang,
        audioData: audioBlob,
      });

      setMsgs((p) => [
        ...p,
        { id: `u${Date.now()}`, from: "user", text: data.transcript, time: "now" },
        { id: `a${Date.now() + 1}`, from: "ai", text: data.responseText, time: "now" },
      ]);

      if (data.audioUrl) {
        const baseUrl = api.defaults.baseURL?.replace("/api", "") || "";
        const audio = new Audio(`${baseUrl}${data.audioUrl}`);
        void audio.play();
      }
    } catch {
      toast.error(lang === "ur" ? "وائس ناکام ہو گئی" : "Voice processing failed");
    } finally {
      setSending(false);
      setTranscript("");
    }
  };

  const endVoiceCall = (closeDialog = true, clearDetails = true) => {
    if (callRecorderRef.current && callRecorderRef.current.state !== "inactive") {
      callRecorderRef.current.stop();
    }
    callRecorderRef.current = null;
    callStreamRef.current?.getTracks().forEach((track) => track.stop());
    callStreamRef.current = null;
    callWsRef.current?.close();
    callWsRef.current = null;
    setCallState({ status: "idle" });
    if (clearDetails) {
      setCallTranscript("");
      setCallReply("");
      setCallError("");
      setCallWsUrl("");
    }
    if (closeDialog) setCallOpen(false);
  };

  const startVoiceCall = async () => {
    if (callWsRef.current) return;

    setCallOpen(true);
    setCallState({ status: "connecting" });
    setCallTranscript("");
    setCallReply("");
    setCallError("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      callStreamRef.current = stream;

      const wsUrl = getVoiceCallWsUrl({ sessionId: sessionIdRef.current });
      setCallWsUrl(wsUrl);
      const ws = new WebSocket(wsUrl);
      callWsRef.current = ws;
      ws.binaryType = "blob";

      ws.onopen = () => {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        const recorder = new MediaRecorder(stream, { mimeType });
        callRecorderRef.current = recorder;

        recorder.ondataavailable = async (event) => {
          if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(await event.data.arrayBuffer());
          }
        };

        recorder.start(250);
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          const payload = JSON.parse(event.data);
          if (payload.type === "status" && payload.text === "connected") {
            setCallState({
              status: "connected",
              callId: sessionIdRef.current,
              greeting:
                lang === "ur"
                  ? "Call connected. Please speak now."
                  : "Call connected. You can speak naturally now.",
            });
          }
          if (payload.type === "partial") {
            setCallTranscript(payload.text || "");
          }
          if (payload.type === "final") {
            const userText = payload.transcript || "";
            const aiText = payload.text || "";
            setCallTranscript(userText);
            setCallReply(aiText);
            setMsgs((prev) => [
              ...prev,
              ...(userText ? [{ id: `cu${Date.now()}`, from: "user" as const, text: userText, time: "now" }] : []),
              ...(aiText ? [{ id: `ca${Date.now() + 1}`, from: "ai" as const, text: aiText, time: "now" }] : []),
            ]);
          }
          if (payload.type === "error") {
            const message = payload.text || "Voice call failed";
            setCallError(message);
            toast.error(message);
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

      ws.onerror = () => {
        const message = "Call connection failed. Check the voice WebSocket URL, HTTPS, and backend logs.";
        setCallError(message);
        toast.error(message);
        endVoiceCall(false, false);
      };

      ws.onclose = () => {
        callWsRef.current = null;
        if (callRecorderRef.current && callRecorderRef.current.state !== "inactive") {
          callRecorderRef.current.stop();
        }
        callRecorderRef.current = null;
        callStreamRef.current?.getTracks().forEach((track) => track.stop());
        callStreamRef.current = null;
      };
    } catch {
      const message = "Microphone access denied or unsupported in this browser.";
      endVoiceCall(false, false);
      setCallError(message);
      setCallOpen(false);
      toast.error(lang === "ur" ? message : message);
    }
  };

  useEffect(() => () => endVoiceCall(false), []);

  const submitContact = async () => {
    if (!contactMessage.trim()) {
      toast.error(lang === "ur" ? "پیغام لکھیں" : "Enter a message");
      return;
    }
    setContactSending(true);
    try {
      const res = await contactAgent({
        lang,
        channel: contactChannel,
        message: contactMessage,
      });
      publishPortalEvent({
        type: "patient:contact",
        ticketId: res.ticketId,
        channel: contactChannel,
        message: contactMessage,
      });
      toast.success(lang === "ur" ? "بھیج دیا گیا" : "Sent", {
        description: `${res.confirmationText} (${res.ticketId})`,
      });
      setContactMessage("");
      setContactOpen(false);
    } catch {
      toast.error(lang === "ur" ? "بھیجنے میں ناکامی" : "Failed to send");
    } finally {
      setContactSending(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 glass border-b border-border/60">
        <div className="h-16 px-4 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl gradient-primary grid place-items-center shadow-glow">
              <Stethoscope className="size-4 text-white" />
            </div>
            <div>
              <div className="font-display font-bold leading-none">MediFlow</div>
              <div className="text-xs text-muted-foreground">Patient Support</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              {portal === "patient" ? (
                <a href={getAdminPortalUrl()}>Admin login</a>
              ) : (
                <Link to="/login">Admin login</Link>
              )}
            </Button>
          </div>
        </div>
      </header>

      <main className="p-4 lg:p-8">
        <div className="space-y-6">
          <div className="flex items-end justify-between flex-wrap gap-3">
            <div>
              <h1 className="font-display font-bold text-3xl tracking-tight">Chat with MediFlow</h1>
              <p className="text-muted-foreground">Smart AI assistant for chat and voice triage</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex p-1 rounded-xl bg-muted">
                {(["en", "ur"] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => {
                      setLang(l);
                      resetWelcome(l);
                    }}
                    className={`relative px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      lang === l ? "text-primary-foreground" : "text-muted-foreground"
                    }`}
                  >
                    {lang === l && (
                      <motion.div
                        layoutId="lang-active-patient"
                        className="absolute inset-0 rounded-lg gradient-primary"
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                      />
                    )}
                    <span className="relative">{l === "en" ? "English" : "اردو"}</span>
                  </button>
                ))}
              </div>

              <Button
                variant="outline"
                onClick={() => void startVoiceCall()}
                className="gap-2"
                disabled={sending}
              >
                <PhoneCall className="size-4" />
                Call Agent
              </Button>
              <Button
                variant="outline"
                onClick={() => setContactOpen(true)}
                className="gap-2"
                disabled={sending}
              >
                <Mail className="size-4" />
                Contact Agent
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 rounded-2xl glass-card overflow-hidden flex flex-col h-[640px]">
              <div className="px-5 py-4 border-b border-border/60 flex items-center gap-3">
                <div className="size-10 rounded-full gradient-primary grid place-items-center shadow-glow">
                  <Bot className="size-5 text-white" />
                </div>
                <div>
                  <div className="font-semibold">MediFlow AI Assistant</div>
                  <div className="text-xs text-success flex items-center gap-1.5">
                    <span className="size-1.5 rounded-full bg-success animate-pulse" />
                    Online
                  </div>
                </div>
              </div>

              <div
                className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-3"
                dir={lang === "ur" ? "rtl" : "ltr"}
              >
                <AnimatePresence initial={false}>
                  {msgs.map((m) => (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 8, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      className={`flex gap-2 ${m.from === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {m.from === "ai" && (
                        <div className="size-7 rounded-full gradient-primary grid place-items-center shrink-0 mt-1">
                          <Bot className="size-3.5 text-white" />
                        </div>
                      )}
                      <div
                        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${
                          m.from === "user"
                            ? "gradient-primary text-white rounded-br-sm"
                            : "bg-muted rounded-bl-sm"
                        }`}
                      >
                        <div>{m.text}</div>
                      </div>
                      {m.from === "user" && (
                        <div className="size-7 rounded-full bg-violet/20 grid place-items-center shrink-0 mt-1">
                          <User className="size-3.5 text-violet" />
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
                <div ref={endRef} />
              </div>

              <div className="px-5 pb-2 flex flex-wrap gap-2" dir={lang === "ur" ? "rtl" : "ltr"}>
                {currentQuick.map((q) => (
                  <button
                    key={q}
                    disabled={sending}
                    onClick={() => void sendUser(q)}
                    className="text-xs px-3 py-1.5 rounded-full border border-border bg-background/60 hover:bg-accent transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendUser(input);
                }}
                className="p-4 border-t border-border/60 flex gap-2"
                dir={lang === "ur" ? "rtl" : "ltr"}
              >
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={lang === "en" ? "Type your message..." : "اپنا پیغام لکھیں..."}
                  className="flex-1"
                />
                <Button
                  type="submit"
                  disabled={sending}
                  className="gradient-primary text-white border-0"
                >
                  <Send className="size-4" />
                </Button>
              </form>
            </div>

            <div className="rounded-2xl glass-card p-6 flex flex-col">
              <div className="flex items-center gap-2 mb-1">
                <Headphones className="size-4 text-violet" />
                <h3 className="font-display font-bold text-lg">Voice Assistant</h3>
              </div>
              <p className="text-sm text-muted-foreground mb-6">
                Tap the mic to speak
              </p>

              <div className="flex-1 flex flex-col items-center justify-center gap-6">
                <div className="relative">
                  {recording && (
                    <>
                      <span className="absolute inset-0 rounded-full bg-destructive/30 animate-pulse-ring" />
                      <span
                        className="absolute inset-0 rounded-full bg-destructive/20 animate-pulse-ring"
                        style={{ animationDelay: "0.4s" }}
                      />
                    </>
                  )}
                  <button
                    onClick={() => {
                      if (recording) stopRecording();
                      else void startRecording();
                    }}
                    className={`relative size-24 rounded-full grid place-items-center shadow-glow transition-all ${
                      recording ? "bg-destructive text-white" : "gradient-primary text-white"
                    }`}
                  >
                    {recording ? (
                      <Square className="size-8 fill-current" />
                    ) : (
                      <Mic className="size-9" />
                    )}
                  </button>
                </div>

                <div className="text-center">
                  <div className="text-sm font-medium">
                    {recording
                      ? lang === "en"
                        ? "Stop recording"
                        : "ریکارڈنگ روکیں"
                      : lang === "en"
                        ? "Tap to speak"
                        : "بولنے کے لیے ٹیپ کریں"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {recording
                      ? "Streaming to AI pipeline..."
                      : "Powered by MediFlow Voice"}
                  </div>
                </div>

                <div className="w-full">
                  <div className="text-xs text-muted-foreground mb-2">Live transcription</div>
                  <div
                    className={`min-h-20 rounded-xl border border-border/60 bg-background/50 p-3 text-sm ${
                      transcript ? "" : "text-muted-foreground"
                    }`}
                    dir={lang === "ur" ? "rtl" : "ltr"}
                  >
                    {transcript ||
                      (lang === "en"
                        ? "Your speech will appear here..."
                        : "آپ کی آواز یہاں ظاہر ہوگی...")}
                    {recording && (
                      <span className="inline-block w-1 h-4 bg-primary ml-1 animate-pulse align-middle" />
                    )}
                  </div>
                </div>

                <div className="w-full flex items-end justify-center gap-1 h-12">
                  {Array.from({ length: 28 }).map((_, i) => (
                    <motion.span
                      key={i}
                      className="w-1 rounded-full gradient-primary"
                      animate={{ height: recording ? [4, 8 + Math.random() * 32, 4] : 4 }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.04 }}
                      style={{ height: 4 }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Dialog
        open={callOpen}
        onOpenChange={(open) => {
          if (open) {
            void startVoiceCall();
          } else {
            endVoiceCall(true);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{lang === "ur" ? "ایجنٹ کو کال کریں" : "Call Agent"}</DialogTitle>
            <DialogDescription>
              {lang === "ur"
                ? "یہ فیچر فی الحال موک ہے۔ بعد میں حقیقی ایجنٹ جوڑا جا سکتا ہے۔"
                : "Live voice assistant connected through your microphone."}
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-xl border border-border/60 bg-muted/40 p-4 space-y-3">
            <div className="text-sm font-medium">
              {callState.status === "connecting"
                ? lang === "ur"
                  ? "کنیکٹ ہو رہا ہے..."
                  : "Connecting..."
                : callState.status === "connected"
                  ? lang === "ur"
                    ? "کنیکٹ ہو گیا"
                    : "Connected"
                  : lang === "ur"
                    ? "تیار"
                    : "Ready"}
            </div>
            {callState.greeting && (
              <div className="text-sm text-muted-foreground">{callState.greeting}</div>
            )}
            {callState.callId && (
              <div className="text-xs text-muted-foreground">{callState.callId}</div>
            )}
            {callError && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {callError}
              </div>
            )}
            {callWsUrl && (
              <div className="break-all text-[11px] text-muted-foreground">
                {callWsUrl}
              </div>
            )}
            <div className="space-y-1.5">
              <div className="text-xs text-muted-foreground">You said</div>
              <div className="min-h-14 rounded-lg border border-border/60 bg-background/60 p-3 text-sm">
                {callTranscript || "Listening for your voice..."}
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="text-xs text-muted-foreground">MediFlow said</div>
              <div className="min-h-14 rounded-lg border border-border/60 bg-background/60 p-3 text-sm">
                {callReply || "The assistant response will appear here and play automatically."}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => endVoiceCall(true)}>
              {lang === "ur" ? "کال ختم کریں" : "End call"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={contactOpen} onOpenChange={setContactOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{lang === "ur" ? "ایجنٹ سے رابطہ کریں" : "Contact Agent"}</DialogTitle>
            <DialogDescription>
              {lang === "ur"
                ? "اپنا پیغام درج کریں۔ یہ ایک موک سبمٹ ہے۔"
                : "Type your message here..."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>{lang === "ur" ? "طریقہ" : "Channel"}</Label>
              <Select
                value={contactChannel}
                onValueChange={(v) => setContactChannel(v as ContactChannel)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="sms">SMS</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="contactMessage">{lang === "ur" ? "پیغام" : "Message"}</Label>
              <Textarea
                id="contactMessage"
                value={contactMessage}
                onChange={(e) => setContactMessage(e.target.value)}
                placeholder={
                  lang === "ur"
                    ? "مثال: مجھے اپوائنٹمنٹ کے بارے میں مدد چاہیے"
                    : "Example: I need help booking an appointment"
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setContactOpen(false)}
              disabled={contactSending}
            >
              {lang === "ur" ? "منسوخ" : "Cancel"}
            </Button>
            <Button onClick={() => void submitContact()} disabled={contactSending}>
              {contactSending ? (lang === "ur" ? "بھیجا جا رہا ہے..." : "Sending...") : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
