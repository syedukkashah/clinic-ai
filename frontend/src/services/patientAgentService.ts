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

export interface VoiceCallSocketConfig {
  sessionId: string;
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

import { api } from "@/lib/api";

export function getVoiceCallWsUrl({ sessionId }: VoiceCallSocketConfig) {
  const explicit = import.meta.env.VITE_VOICE_WS_URL;
  if (explicit) {
    return explicit.replace("{sessionId}", encodeURIComponent(sessionId));
  }

  const apiBase = api.defaults.baseURL || "/api";
  if (apiBase.startsWith("http")) {
    const url = new URL(apiBase);
    const protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${url.host}/ws/voice/${encodeURIComponent(sessionId)}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/voice/${encodeURIComponent(sessionId)}`;
}

export async function sendPatientMessage(
  input: SendPatientMessageInput,
): Promise<SendPatientMessageResult> {
  try {
    const response = await api.post("/chat/message", {
      userId: input.userId || "anonymous",
      message: input.message,
      lang: input.lang,
    });
    return { responseText: response.data.responseText || response.data.response };
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
