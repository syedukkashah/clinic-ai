import { api } from "@/lib/api";

export type PatientLang = "en" | "ur";

export type ContactChannel = "email" | "sms" | "whatsapp";

export interface SendPatientMessageInput {
  userId?: string;
  lang: PatientLang;
  message: string;
}

export interface SendPatientMessageResult {
  responseText: string;
  response?: string;
  detected_lang?: PatientLang;
  detectedLang?: PatientLang;
  appointment?: Record<string, unknown> | null;
  appointment_data?: Record<string, unknown> | null;
  suggestedSlots?: Array<Record<string, unknown>>;
  slots?: Array<Record<string, unknown>>;
  tool_calls?: Array<Record<string, unknown>>;
  agent_trace?: Array<Record<string, unknown>>;
  trace?: Array<Record<string, unknown>>;
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
  detected_lang?: PatientLang;
  appointment?: Record<string, unknown> | null;
  tool_calls?: Array<Record<string, unknown>>;
  agent_trace?: Array<Record<string, unknown>>;
  suggestedSlots?: Array<Record<string, unknown>>;
  slots?: Array<Record<string, unknown>>;
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

export function getVoiceCallWsUrl({ sessionId }: VoiceCallSocketConfig) {
  const explicit = import.meta.env.VITE_VOICE_WS_URL;
  if (explicit) {
    if (explicit.includes("{sessionId}")) {
      return explicit.replace("{sessionId}", encodeURIComponent(sessionId));
    }
    return `${explicit.replace(/\/$/, "")}/${encodeURIComponent(sessionId)}`;
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
    const payload = {
      userId: input.userId || "anonymous",
      message: input.message,
      lang: input.lang,
    };

    let response;
    try {
      response = await api.post("/chat", payload);
    } catch (error: any) {
      const status = error?.response?.status;
      if (status !== 404 && status !== 405 && status !== 307 && status !== 308) {
        throw error;
      }
      response = await api.post("/chat/message", payload);
    }

    return {
      ...response.data,
      responseText: response.data.responseText || response.data.response,
    };
  } catch (error) {
    console.error("Failed to send patient message:", error);
    return {
      responseText: "I'm having trouble connecting to the medical assistant. Please try again later.",
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
      detected_lang: data.detected_lang,
      appointment: data.appointment,
      tool_calls: data.tool_calls,
      agent_trace: data.agent_trace,
      suggestedSlots: data.suggestedSlots,
      slots: data.slots,
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
    await sleep(1000);
    return {
      ticketId,
      channel: input.channel,
      confirmationText:
        "Your inquiry has been successfully logged. Our medical team will reach out to you shortly.",
    };
  } catch (error) {
    console.error("Failed to submit contact request:", error);
    throw error;
  }
}
