import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { Link } from "@tanstack/react-router";
import * as React from "react";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Stethoscope, PhoneCall, Mail, Bot, User, Send, Headphones, Square, Mic } from "lucide-react";
import { toast } from "sonner";
import { c as cn, B as Button } from "./router-kWCNp4I7.js";
import { I as Input, L as Label } from "./label-Bp8Ivt_c.js";
import { D as Dialog, a as DialogContent, b as DialogHeader, c as DialogTitle, d as DialogDescription, e as DialogFooter, S as Select, f as SelectTrigger, g as SelectValue, h as SelectContent, i as SelectItem } from "./select-C9cCNatX.js";
import "@tanstack/react-query";
import "axios";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-label";
import "@radix-ui/react-dialog";
import "@radix-ui/react-select";
const Textarea = React.forwardRef(
  ({ className, ...props }, ref) => {
    return /* @__PURE__ */ jsx(
      "textarea",
      {
        className: cn(
          "flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
          className
        ),
        ref,
        ...props
      }
    );
  }
);
Textarea.displayName = "Textarea";
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
function safeLower(s) {
  return s.trim().toLowerCase();
}
function isLikelyUrdu(s) {
  return /[\u0600-\u06FF]/.test(s);
}
function buildMockReply(lang, message) {
  const m = safeLower(message);
  const wantsAppointment = m.includes("appointment") || m.includes("book") || m.includes("schedule") || m.includes("reschedule") || isLikelyUrdu(message);
  if (lang === "ur") {
    if (wantsAppointment) {
      return "بالکل—براہِ کرم بتائیں آپ کس دن اور کس وقت اپوائنٹمنٹ چاہتے ہیں، اور کس ڈاکٹر/ڈیپارٹمنٹ کے لیے؟";
    }
    if (m.includes("hours") || m.includes("timing") || m.includes("open")) {
      return "کلینک کے اوقات: پیر تا جمعہ صبح 9 بجے سے شام 5 بجے تک۔";
    }
    return "میں مدد کے لیے حاضر ہوں۔ براہِ کرم اپنی مسئلے کی مختصر تفصیل بتائیں۔";
  }
  if (wantsAppointment) {
    return "Sure — tell me your preferred day/time and which doctor or department you want to see.";
  }
  if (m.includes("hours") || m.includes("timing") || m.includes("open")) {
    return "Clinic hours (mock): Mon–Fri, 9:00 AM to 5:00 PM.";
  }
  if (m.includes("billing") || m.includes("payment")) {
    return "For billing questions (mock), I can connect you to support. What’s your invoice number (if any)?";
  }
  return "I can help with appointments, rescheduling, clinic hours, and general questions. What do you need today?";
}
async function sendPatientMessage(input) {
  const lang = input.lang === "ur" ? "ur" : "en";
  await sleep(450);
  return { responseText: buildMockReply(lang, input.message) };
}
async function processPatientVoice(input) {
  const lang = input.lang === "ur" ? "ur" : "en";
  await sleep(700);
  const transcript = lang === "ur" ? "مجھے اپوائنٹمنٹ بُک کرنی ہے" : "I want to book an appointment";
  return {
    transcript,
    responseText: buildMockReply(lang, transcript)
  };
}
async function callAgent(input) {
  const callId = `call_${Math.random().toString(36).slice(2, 10)}`;
  await sleep(600);
  return {
    callId,
    status: "connected",
    greeting: input.lang === "ur" ? "ہیلو! یہ ایک موک کال ہے۔ آپ بتائیں میں آپ کی کیا مدد کر سکتا ہوں؟" : "Hello! This is a mock call. How can I help you?"
  };
}
async function contactAgent(input) {
  const ticketId = `tkt_${Math.random().toString(36).slice(2, 10)}`;
  await sleep(500);
  return {
    ticketId,
    channel: input.channel,
    confirmationText: input.lang === "ur" ? "آپ کا پیغام موصول ہو گیا ہے۔ ہماری ٹیم جلد آپ سے رابطہ کرے گی۔" : "Your message has been received. Our team will contact you shortly."
  };
}
const QUICK = {
  en: ["Book an appointment", "Reschedule", "Clinic hours", "Talk to an agent"],
  ur: ["مجھے اپوائنٹمنٹ بُک کرنی ہے", "اپوائنٹمنٹ تبدیل کریں", "کلینک اوقات", "ایجنٹ سے بات"]
};
function PatientPage() {
  const [lang, setLang] = useState("en");
  const [msgs, setMsgs] = useState([{
    id: "m0",
    from: "ai",
    text: "Hi! I’m MediFlow’s assistant. How can I help you today?",
    time: "now"
  }]);
  const [input, setInput] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);
  const [callOpen, setCallOpen] = useState(false);
  const [callState, setCallState] = useState({
    status: "idle"
  });
  const [contactOpen, setContactOpen] = useState(false);
  const [contactChannel, setContactChannel] = useState("email");
  const [contactMessage, setContactMessage] = useState("");
  const [contactSending, setContactSending] = useState(false);
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: "smooth"
    });
  }, [msgs]);
  const resetWelcome = (l) => {
    setMsgs([{
      id: "m0",
      from: "ai",
      text: l === "en" ? "Hi! I’m MediFlow’s assistant. How can I help you today?" : "السلام علیکم! میں آپ کی کیا مدد کر سکتا ہوں؟",
      time: "now"
    }]);
  };
  const sendUser = async (text) => {
    if (!text.trim()) return;
    const userMsg = {
      id: `u${Date.now()}`,
      from: "user",
      text,
      time: "now"
    };
    setMsgs((p) => [...p, userMsg]);
    setInput("");
    try {
      setSending(true);
      const res = await sendPatientMessage({
        userId: "anon",
        lang,
        message: text
      });
      setMsgs((p) => [...p, {
        id: `a${Date.now()}`,
        from: "ai",
        text: res.responseText,
        time: "now"
      }]);
    } catch {
      toast.error(lang === "ur" ? "پیغام نہیں بھیجا جا سکا" : "Message failed");
    } finally {
      setSending(false);
    }
  };
  const currentQuick = QUICK[lang];
  useEffect(() => {
    if (!recording) return;
    const phrases = lang === "en" ? ["I want", "I want to book", "I want to book an appointment", "I want to book an appointment with cardiology"] : ["مجھے", "مجھے اپوائنٹمنٹ", "مجھے اپوائنٹمنٹ بُک کرنی ہے"];
    let i = 0;
    const t = setInterval(() => {
      setTranscript(phrases[Math.min(i, phrases.length - 1)]);
      i++;
      if (i >= phrases.length + 2) {
        clearInterval(t);
        setRecording(false);
        (async () => {
          try {
            setSending(true);
            const data = await processPatientVoice({
              userId: "anon",
              lang,
              audioDataBase64: "bW9jaw=="
            });
            setMsgs((p) => [...p, {
              id: `u${Date.now()}`,
              from: "user",
              text: data.transcript,
              time: "now"
            }, {
              id: `a${Date.now() + 1}`,
              from: "ai",
              text: data.responseText,
              time: "now"
            }]);
          } catch {
            toast.error(lang === "ur" ? "وائس ناکام ہو گئی" : "Voice processing failed");
          } finally {
            setSending(false);
          }
        })();
        setTranscript("");
      }
    }, 600);
    return () => clearInterval(t);
  }, [recording, lang]);
  useEffect(() => {
    if (!callOpen) {
      setCallState({
        status: "idle"
      });
      return;
    }
    setCallState({
      status: "connecting"
    });
    (async () => {
      try {
        const res = await callAgent({
          lang
        });
        setCallState({
          status: "connected",
          greeting: res.greeting,
          callId: res.callId
        });
      } catch {
        setCallOpen(false);
        toast.error(lang === "ur" ? "کال شروع نہیں ہو سکی" : "Unable to start call");
      }
    })();
  }, [callOpen, lang]);
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
        message: contactMessage
      });
      toast.success(lang === "ur" ? "بھیج دیا گیا" : "Sent", {
        description: `${res.confirmationText} (${res.ticketId})`
      });
      setContactMessage("");
      setContactOpen(false);
    } catch {
      toast.error(lang === "ur" ? "بھیجنے میں ناکامی" : "Failed to send");
    } finally {
      setContactSending(false);
    }
  };
  return /* @__PURE__ */ jsxs("div", { className: "min-h-screen", children: [
    /* @__PURE__ */ jsx("header", { className: "sticky top-0 z-30 glass border-b border-border/60", children: /* @__PURE__ */ jsxs("div", { className: "h-16 px-4 lg:px-8 flex items-center justify-between", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ jsx("div", { className: "size-9 rounded-xl gradient-primary grid place-items-center shadow-glow", children: /* @__PURE__ */ jsx(Stethoscope, { className: "size-4 text-white" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("div", { className: "font-display font-bold leading-none", children: "MediFlow" }),
          /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: "Patient Support" })
        ] })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "flex items-center gap-2", children: /* @__PURE__ */ jsx(Button, { variant: "outline", asChild: true, children: /* @__PURE__ */ jsx(Link, { to: "/login", children: "Admin login" }) }) })
    ] }) }),
    /* @__PURE__ */ jsx("main", { className: "p-4 lg:p-8", children: /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-end justify-between flex-wrap gap-3", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h1", { className: "font-display font-bold text-3xl tracking-tight", children: "Chat with MediFlow" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Mock agent chat + mock call/contact options" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("div", { className: "flex p-1 rounded-xl bg-muted", children: ["en", "ur"].map((l) => /* @__PURE__ */ jsxs("button", { onClick: () => {
            setLang(l);
            resetWelcome(l);
          }, className: `relative px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${lang === l ? "text-primary-foreground" : "text-muted-foreground"}`, children: [
            lang === l && /* @__PURE__ */ jsx(motion.div, { layoutId: "lang-active-patient", className: "absolute inset-0 rounded-lg gradient-primary", transition: {
              type: "spring",
              stiffness: 400,
              damping: 30
            } }),
            /* @__PURE__ */ jsx("span", { className: "relative", children: l === "en" ? "English" : "اردو" })
          ] }, l)) }),
          /* @__PURE__ */ jsxs(Button, { variant: "outline", onClick: () => setCallOpen(true), className: "gap-2", disabled: sending, children: [
            /* @__PURE__ */ jsx(PhoneCall, { className: "size-4" }),
            "Call Agent"
          ] }),
          /* @__PURE__ */ jsxs(Button, { variant: "outline", onClick: () => setContactOpen(true), className: "gap-2", disabled: sending, children: [
            /* @__PURE__ */ jsx(Mail, { className: "size-4" }),
            "Contact Agent"
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [
        /* @__PURE__ */ jsxs("div", { className: "lg:col-span-2 rounded-2xl glass-card overflow-hidden flex flex-col h-[640px]", children: [
          /* @__PURE__ */ jsxs("div", { className: "px-5 py-4 border-b border-border/60 flex items-center gap-3", children: [
            /* @__PURE__ */ jsx("div", { className: "size-10 rounded-full gradient-primary grid place-items-center shadow-glow", children: /* @__PURE__ */ jsx(Bot, { className: "size-5 text-white" }) }),
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx("div", { className: "font-semibold", children: "MediFlow Agent (Mock)" }),
              /* @__PURE__ */ jsxs("div", { className: "text-xs text-success flex items-center gap-1.5", children: [
                /* @__PURE__ */ jsx("span", { className: "size-1.5 rounded-full bg-success animate-pulse" }),
                "Online"
              ] })
            ] })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "flex-1 overflow-y-auto scrollbar-thin p-5 space-y-3", dir: lang === "ur" ? "rtl" : "ltr", children: [
            /* @__PURE__ */ jsx(AnimatePresence, { initial: false, children: msgs.map((m) => /* @__PURE__ */ jsxs(motion.div, { initial: {
              opacity: 0,
              y: 8,
              scale: 0.96
            }, animate: {
              opacity: 1,
              y: 0,
              scale: 1
            }, className: `flex gap-2 ${m.from === "user" ? "justify-end" : "justify-start"}`, children: [
              m.from === "ai" && /* @__PURE__ */ jsx("div", { className: "size-7 rounded-full gradient-primary grid place-items-center shrink-0 mt-1", children: /* @__PURE__ */ jsx(Bot, { className: "size-3.5 text-white" }) }),
              /* @__PURE__ */ jsx("div", { className: `max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${m.from === "user" ? "gradient-primary text-white rounded-br-sm" : "bg-muted rounded-bl-sm"}`, children: /* @__PURE__ */ jsx("div", { children: m.text }) }),
              m.from === "user" && /* @__PURE__ */ jsx("div", { className: "size-7 rounded-full bg-violet/20 grid place-items-center shrink-0 mt-1", children: /* @__PURE__ */ jsx(User, { className: "size-3.5 text-violet" }) })
            ] }, m.id)) }),
            /* @__PURE__ */ jsx("div", { ref: endRef })
          ] }),
          /* @__PURE__ */ jsx("div", { className: "px-5 pb-2 flex flex-wrap gap-2", dir: lang === "ur" ? "rtl" : "ltr", children: currentQuick.map((q) => /* @__PURE__ */ jsx("button", { disabled: sending, onClick: () => void sendUser(q), className: "text-xs px-3 py-1.5 rounded-full border border-border bg-background/60 hover:bg-accent transition-colors", children: q }, q)) }),
          /* @__PURE__ */ jsxs("form", { onSubmit: (e) => {
            e.preventDefault();
            void sendUser(input);
          }, className: "p-4 border-t border-border/60 flex gap-2", dir: lang === "ur" ? "rtl" : "ltr", children: [
            /* @__PURE__ */ jsx(Input, { value: input, onChange: (e) => setInput(e.target.value), placeholder: lang === "en" ? "Type your message..." : "اپنا پیغام لکھیں...", className: "flex-1" }),
            /* @__PURE__ */ jsx(Button, { type: "submit", disabled: sending, className: "gradient-primary text-white border-0", children: /* @__PURE__ */ jsx(Send, { className: "size-4" }) })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "rounded-2xl glass-card p-6 flex flex-col", children: [
          /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
            /* @__PURE__ */ jsx(Headphones, { className: "size-4 text-violet" }),
            /* @__PURE__ */ jsx("h3", { className: "font-display font-bold text-lg", children: "Voice (Mock)" })
          ] }),
          /* @__PURE__ */ jsx("p", { className: "text-sm text-muted-foreground mb-6", children: "Tap the mic to simulate a call transcript" }),
          /* @__PURE__ */ jsxs("div", { className: "flex-1 flex flex-col items-center justify-center gap-6", children: [
            /* @__PURE__ */ jsxs("div", { className: "relative", children: [
              recording && /* @__PURE__ */ jsxs(Fragment, { children: [
                /* @__PURE__ */ jsx("span", { className: "absolute inset-0 rounded-full bg-destructive/30 animate-pulse-ring" }),
                /* @__PURE__ */ jsx("span", { className: "absolute inset-0 rounded-full bg-destructive/20 animate-pulse-ring", style: {
                  animationDelay: "0.4s"
                } })
              ] }),
              /* @__PURE__ */ jsx("button", { onClick: () => {
                setRecording((r) => !r);
                setTranscript("");
              }, className: `relative size-24 rounded-full grid place-items-center shadow-glow transition-all ${recording ? "bg-destructive text-white" : "gradient-primary text-white"}`, children: recording ? /* @__PURE__ */ jsx(Square, { className: "size-8 fill-current" }) : /* @__PURE__ */ jsx(Mic, { className: "size-9" }) })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "text-center", children: [
              /* @__PURE__ */ jsx("div", { className: "text-sm font-medium", children: recording ? "Listening..." : "Tap to speak" }),
              /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground mt-1", children: recording ? "Streaming to a mock pipeline" : "Powered by MediFlow Voice (Mock)" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "w-full", children: [
              /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground mb-2", children: "Live transcription" }),
              /* @__PURE__ */ jsxs("div", { className: `min-h-20 rounded-xl border border-border/60 bg-background/50 p-3 text-sm ${transcript ? "" : "text-muted-foreground"}`, dir: lang === "ur" ? "rtl" : "ltr", children: [
                transcript || (lang === "en" ? "Your speech will appear here..." : "آپ کی آواز یہاں ظاہر ہوگی..."),
                recording && /* @__PURE__ */ jsx("span", { className: "inline-block w-1 h-4 bg-primary ml-1 animate-pulse align-middle" })
              ] })
            ] }),
            /* @__PURE__ */ jsx("div", { className: "w-full flex items-end justify-center gap-1 h-12", children: Array.from({
              length: 28
            }).map((_, i) => /* @__PURE__ */ jsx(motion.span, { className: "w-1 rounded-full gradient-primary", animate: {
              height: recording ? [4, 8 + Math.random() * 32, 4] : 4
            }, transition: {
              duration: 0.6,
              repeat: Infinity,
              delay: i * 0.04
            }, style: {
              height: 4
            } }, i)) })
          ] })
        ] })
      ] })
    ] }) }),
    /* @__PURE__ */ jsx(Dialog, { open: callOpen, onOpenChange: setCallOpen, children: /* @__PURE__ */ jsxs(DialogContent, { children: [
      /* @__PURE__ */ jsxs(DialogHeader, { children: [
        /* @__PURE__ */ jsx(DialogTitle, { children: lang === "ur" ? "ایجنٹ کو کال کریں" : "Call Agent" }),
        /* @__PURE__ */ jsx(DialogDescription, { children: lang === "ur" ? "یہ فیچر فی الحال موک ہے۔ بعد میں حقیقی ایجنٹ جوڑا جا سکتا ہے۔" : "This feature is currently mocked and can be wired to a real agent later." })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "rounded-xl border border-border/60 bg-muted/40 p-4 space-y-2", children: [
        /* @__PURE__ */ jsx("div", { className: "text-sm font-medium", children: callState.status === "connecting" ? lang === "ur" ? "کنیکٹ ہو رہا ہے..." : "Connecting..." : callState.status === "connected" ? lang === "ur" ? "کنیکٹ ہو گیا" : "Connected" : lang === "ur" ? "تیار" : "Ready" }),
        callState.greeting && /* @__PURE__ */ jsx("div", { className: "text-sm text-muted-foreground", children: callState.greeting }),
        callState.callId && /* @__PURE__ */ jsx("div", { className: "text-xs text-muted-foreground", children: callState.callId })
      ] }),
      /* @__PURE__ */ jsx(DialogFooter, { children: /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => setCallOpen(false), children: lang === "ur" ? "کال ختم کریں" : "End call" }) })
    ] }) }),
    /* @__PURE__ */ jsx(Dialog, { open: contactOpen, onOpenChange: setContactOpen, children: /* @__PURE__ */ jsxs(DialogContent, { children: [
      /* @__PURE__ */ jsxs(DialogHeader, { children: [
        /* @__PURE__ */ jsx(DialogTitle, { children: lang === "ur" ? "ایجنٹ سے رابطہ کریں" : "Contact Agent" }),
        /* @__PURE__ */ jsx(DialogDescription, { children: lang === "ur" ? "اپنا پیغام درج کریں۔ یہ ایک موک سبمٹ ہے۔" : "Enter your message. This submission is mocked." })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { children: lang === "ur" ? "طریقہ" : "Channel" }),
          /* @__PURE__ */ jsxs(Select, { value: contactChannel, onValueChange: (v) => setContactChannel(v), children: [
            /* @__PURE__ */ jsx(SelectTrigger, { children: /* @__PURE__ */ jsx(SelectValue, { placeholder: "Select" }) }),
            /* @__PURE__ */ jsxs(SelectContent, { children: [
              /* @__PURE__ */ jsx(SelectItem, { value: "email", children: "Email" }),
              /* @__PURE__ */ jsx(SelectItem, { value: "sms", children: "SMS" }),
              /* @__PURE__ */ jsx(SelectItem, { value: "whatsapp", children: "WhatsApp" })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { htmlFor: "contactMessage", children: lang === "ur" ? "پیغام" : "Message" }),
          /* @__PURE__ */ jsx(Textarea, { id: "contactMessage", value: contactMessage, onChange: (e) => setContactMessage(e.target.value), placeholder: lang === "ur" ? "مثال: مجھے اپوائنٹمنٹ کے بارے میں مدد چاہیے" : "Example: I need help booking an appointment" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs(DialogFooter, { children: [
        /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => setContactOpen(false), disabled: contactSending, children: lang === "ur" ? "منسوخ" : "Cancel" }),
        /* @__PURE__ */ jsx(Button, { onClick: () => void submitContact(), disabled: contactSending, children: contactSending ? lang === "ur" ? "بھیجا جا رہا ہے..." : "Sending..." : "Send" })
      ] })
    ] }) })
  ] });
}
export {
  PatientPage as component
};
