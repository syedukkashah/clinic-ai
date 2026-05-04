import { getPortal, type Portal } from "@/lib/portal";

export type PortalBusEvent =
  | { type: "presence"; portal: Portal }
  | { type: "appointments:changed" }
  | { type: "patient:contact"; ticketId: string; channel: string; message: string };

type Envelope = {
  id: string;
  ts: number;
  from: Portal;
  event: PortalBusEvent;
};

const CHANNEL = "mediflow:portal";
const STORAGE_KEY = "mediflow.portal.bus";

let bc: BroadcastChannel | null = null;
let storageListenerInstalled = false;
let ws: WebSocket | null = null;
let wsQueue: string[] = [];
let wsReconnectTimer: number | null = null;

function getId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function ensureChannel() {
  if (bc) return bc;
  if (typeof window === "undefined") return null;
  if (!("BroadcastChannel" in window)) return null;
  bc = new BroadcastChannel(CHANNEL);
  return bc;
}

function getWebSocketUrl() {
  if (typeof window === "undefined") return null;
  if (!("WebSocket" in window)) return null;

  const portal = getPortal();
  const raw = import.meta.env.VITE_PORTAL_WS_URL as string | undefined;
  if (raw) {
    if (raw.includes("{portal}")) return raw.replace("{portal}", portal);
    const sep = raw.includes("?") ? "&" : "?";
    return `${raw}${sep}portal=${encodeURIComponent(portal)}`;
  }

  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.hostname}:8000/ws/portal?portal=${encodeURIComponent(portal)}`;
}

type Handler = (event: PortalBusEvent, envelope: Envelope) => void;
const handlers = new Set<Handler>();

function dispatch(envelope: Envelope) {
  for (const h of handlers) h(envelope.event, envelope);
}

function ensureWebSocket() {
  if (ws) return ws;
  const url = getWebSocketUrl();
  if (!url) return null;

  try {
    ws = new WebSocket(url);
  } catch {
    ws = null;
    return null;
  }

  ws.addEventListener("open", () => {
    const q = wsQueue;
    wsQueue = [];
    for (const msg of q) {
      try {
        ws?.send(msg);
      } catch { }
    }
  });

  ws.addEventListener("message", (e) => {
    try {
      const envelope = JSON.parse(String(e.data)) as Envelope;
      dispatch(envelope);
    } catch { }
  });

  ws.addEventListener("close", () => {
    ws = null;
    if (typeof window === "undefined") return;
    if (wsReconnectTimer != null) return;
    wsReconnectTimer = window.setTimeout(() => {
      wsReconnectTimer = null;
      ensureWebSocket();
    }, 5000);
  });

  ws.addEventListener("error", () => { });

  return ws;
}

function installStorageFallback() {
  if (typeof window === "undefined") return;
  if (storageListenerInstalled) return;
  storageListenerInstalled = true;
  window.addEventListener("storage", (e) => {
    if (e.key !== STORAGE_KEY || !e.newValue) return;
    try {
      const envelope = JSON.parse(e.newValue) as Envelope;
      dispatch(envelope);
    } catch { }
  });
}

export function publishPortalEvent(event: PortalBusEvent) {
  if (typeof window === "undefined") return;
  const envelope: Envelope = { id: getId(), ts: Date.now(), from: getPortal(), event };
  const text = JSON.stringify(envelope);
  const socket = ensureWebSocket();
  if (socket) {
    if (socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(text);
      } catch {
        wsQueue.push(text);
      }
    } else {
      wsQueue.push(text);
    }
  } else {
    const channel = ensureChannel();
    if (channel) {
      channel.postMessage(envelope);
    } else {
      installStorageFallback();
      try {
        localStorage.setItem(STORAGE_KEY, text);
      } catch { }
    }
  }
  dispatch(envelope);
}

export function subscribePortalEvents(handler: Handler) {
  handlers.add(handler);
  ensureWebSocket();

  const channel = ensureChannel();
  if (channel) {
    const onMessage = (e: MessageEvent) => {
      const envelope = e.data as Envelope;
      dispatch(envelope);
    };
    channel.addEventListener("message", onMessage);
    return () => {
      handlers.delete(handler);
      channel.removeEventListener("message", onMessage);
    };
  }

  installStorageFallback();
  return () => {
    handlers.delete(handler);
  };
}

export function startPortalPresence(intervalMs = 5000) {
  if (typeof window === "undefined") return () => { };
  publishPortalEvent({ type: "presence", portal: getPortal() });
  const t = window.setInterval(() => {
    publishPortalEvent({ type: "presence", portal: getPortal() });
  }, intervalMs);
  return () => window.clearInterval(t);
}
