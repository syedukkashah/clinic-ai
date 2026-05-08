export type PatientLang = "en" | "ur";

export type ContactChannel = "email" | "sms" | "whatsapp";

export interface SendPatientMessageInput {
  userId?: string;
  lang: PatientLang;
  message: string;
}

export interface SendPatientMessageResult {
  responseText: string;
}

export interface ProcessPatientVoiceInput {
  userId?: string;
  lang: PatientLang;
  audioData: Blob;
}

export interface ProcessPatientVoiceResult {
  transcript: string;
  responseText: string;
  audioUrl?: string;
}

export interface CallAgentInput {
  lang: PatientLang;
}

export interface CallAgentResult {
  callId: string;
  status: "connecting" | "connected" | "ended";
  greeting: string;
}

export interface ContactAgentInput {
  lang: PatientLang;
  channel: ContactChannel;
  message: string;
}

export interface ContactAgentResult {
  ticketId: string;
  channel: ContactChannel;
  confirmationText: string;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function safeLower(s: string) {
  return s.trim().toLowerCase();
}

function isLikelyUrdu(s: string) {
  return /[\u0600-\u06FF]/.test(s);
}

function buildMockReply(lang: PatientLang, message: string) {
  const m = safeLower(message);
  const wantsAppointment =
    m.includes("appointment") ||
    m.includes("book") ||
    m.includes("schedule") ||
    m.includes("reschedule") ||
    isLikelyUrdu(message);

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

import { api } from "@/lib/api";

export async function sendPatientMessage(
  input: SendPatientMessageInput,
): Promise<SendPatientMessageResult> {
  try {
    const response = await api.post("/chat/message", {
      userId: input.userId || "anonymous",
      message: input.message,
    });
    // The backend returns { response: "..." }, but frontend expects { responseText: "..." }
    return { responseText: response.data.response };
  } catch (error) {
    console.error("Failed to send patient message:", error);
    return {
      responseText: "I'm having trouble connecting to the medical assistant. Please try again later."
    };
  }
}

export async function processPatientVoice(
  input: ProcessPatientVoiceInput,
): Promise<ProcessPatientVoiceResult> {
  try {
    const formData = new FormData();
    formData.append("audio", input.audioData, "voice.webm");
    formData.append("session_id", input.userId || "anonymous");

    const response = await api.post("/voice/chat", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });

    const data = response.data;
    return {
      transcript: data.transcript,
      responseText: data.text_response,
      audioUrl: data.audio_url,
    };
  } catch (error) {
    console.error("Failed to process voice:", error);
    return {
      transcript: "Error transcribing audio.",
      responseText: "I'm sorry, I had trouble processing your voice request. Please try again.",
    };
  }
}

export async function callAgent(input: CallAgentInput): Promise<CallAgentResult> {
  const callId = `call_${Math.random().toString(36).slice(2, 10)}`;
  await sleep(800);
  return {
    callId,
    status: "connected",
    greeting:
      input.lang === "ur"
        ? "میڈی فلو اے آئی ٹرائیج میں خوش آمدید۔ میں آپ کی کیسے مدد کر سکتا ہوں؟"
        : "Welcome to MediFlow AI Triage. How can I assist you with your health inquiry today?",
  };
}

export async function contactAgent(input: ContactAgentInput): Promise<ContactAgentResult> {
  const ticketId = `tkt_${Math.random().toString(36).slice(2, 10)}`;
  try {
    // Simulate API call to ticketing system
    await sleep(1000);
    return {
      ticketId,
      channel: input.channel,
      confirmationText:
        input.lang === "ur"
          ? "آپ کی انکوائری کامیابی کے ساتھ درج کر لی گئی ہے۔ ہماری ٹیم جلد آپ سے رابطہ کرے گی۔"
          : "Your inquiry has been successfully logged. Our medical team will reach out to you via your preferred channel shortly.",
    };
  } catch (error) {
    console.error("Failed to submit contact request:", error);
    throw error;
  }
}
