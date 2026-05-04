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
  audioDataBase64: string;
}

export interface ProcessPatientVoiceResult {
  transcript: string;
  responseText: string;
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

export async function sendPatientMessage(
  input: SendPatientMessageInput,
): Promise<SendPatientMessageResult> {
  const lang = input.lang === "ur" ? "ur" : "en";
  await sleep(450);
  return { responseText: buildMockReply(lang, input.message) };
}

export async function processPatientVoice(
  input: ProcessPatientVoiceInput,
): Promise<ProcessPatientVoiceResult> {
  const lang = input.lang === "ur" ? "ur" : "en";
  await sleep(700);

  const transcript =
    lang === "ur" ? "مجھے اپوائنٹمنٹ بُک کرنی ہے" : "I want to book an appointment";

  return {
    transcript,
    responseText: buildMockReply(lang, transcript),
  };
}

export async function callAgent(input: CallAgentInput): Promise<CallAgentResult> {
  const callId = `call_${Math.random().toString(36).slice(2, 10)}`;
  await sleep(600);
  return {
    callId,
    status: "connected",
    greeting:
      input.lang === "ur"
        ? "ہیلو! یہ ایک موک کال ہے۔ آپ بتائیں میں آپ کی کیا مدد کر سکتا ہوں؟"
        : "Hello! This is a mock call. How can I help you?",
  };
}

export async function contactAgent(input: ContactAgentInput): Promise<ContactAgentResult> {
  const ticketId = `tkt_${Math.random().toString(36).slice(2, 10)}`;
  await sleep(500);
  return {
    ticketId,
    channel: input.channel,
    confirmationText:
      input.lang === "ur"
        ? "آپ کا پیغام موصول ہو گیا ہے۔ ہماری ٹیم جلد آپ سے رابطہ کرے گی۔"
        : "Your message has been received. Our team will contact you shortly.",
  };
}
