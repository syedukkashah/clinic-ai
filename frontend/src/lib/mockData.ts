// Realistic mock data for MediFlow

import { useSyncExternalStore, useCallback, useRef } from "react";

export type Role = "admin" | "staff";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  avatar?: string;
}

export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  avatarColor: string;
  appointmentsToday: number;
  capacity: number;
  status: "available" | "busy" | "overloaded" | "off";
  avgConsultMin: number;
}

export type AppointmentStatus = "Confirmed" | "Waiting" | "In Progress" | "Completed" | "Cancelled";

export interface Appointment {
  id: string;
  patientName: string;
  patientId: string;
  doctorId: string;
  doctorName: string;
  time: string; // HH:mm
  date: string; // YYYY-MM-DD
  status: AppointmentStatus;
  predictedWaitMin: number;
  reason: string;
  slotId?: string;
  urgency?: "low" | "medium" | "high";
}

export interface Alert {
  id: string;
  severity: "Low" | "Medium" | "High";
  title: string;
  reasoning: string;
  timestamp: string;
  type: "surge" | "latency" | "drift" | "capacity";
  trace?: string[];
  recommendedActions?: Array<
    | { kind: "open_slots"; count: number; doctorId?: string; windowLabel?: string }
    | { kind: "reassign_patients"; count: number; fromDoctorId?: string; toDoctorId?: string }
    | { kind: "trigger_retraining"; model: "wait_time_model" | "patient_load_model" }
    | { kind: "notify"; channel: "sms" | "whatsapp"; count: number }
  >;
  acknowledged?: boolean;
}

const SPECIALTIES = [
  "Cardiology",
  "Pediatrics",
  "Dermatology",
  "Orthopedics",
  "Neurology",
  "General Practice",
  "ENT",
  "Gynecology",
  "Psychiatry",
  "Endocrinology",
  "Ophthalmology",
  "Urology",
];

const FIRST = [
  "Ayesha",
  "Imran",
  "Sara",
  "Bilal",
  "Hina",
  "Usman",
  "Maria",
  "Ahmed",
  "Zara",
  "Faisal",
  "Noor",
  "Hassan",
  "Fatima",
  "Ali",
  "Komal",
  "Junaid",
];
const LAST = [
  "Khan",
  "Malik",
  "Ahmed",
  "Siddiqui",
  "Raza",
  "Hussain",
  "Iqbal",
  "Sheikh",
  "Qureshi",
  "Akhtar",
  "Chaudhry",
  "Butt",
];

const DOCTOR_COLORS = [
  "from-blue-500 to-cyan-500",
  "from-violet-500 to-fuchsia-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-indigo-500 to-blue-500",
  "from-teal-500 to-emerald-500",
  "from-fuchsia-500 to-purple-500",
  "from-sky-500 to-indigo-500",
  "from-orange-500 to-red-500",
  "from-cyan-500 to-blue-500",
  "from-purple-500 to-violet-500",
];

function rand<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

export const DOCTORS: Doctor[] = Array.from({ length: 12 }, (_, i) => {
  const apt = 8 + Math.floor(Math.random() * 18);
  const cap = 22;
  const ratio = apt / cap;
  let status: Doctor["status"] = "available";
  if (ratio > 1) status = "overloaded";
  else if (ratio > 0.75) status = "busy";
  else if (ratio < 0.1) status = "off";
  return {
    id: `doc-${i + 1}`,
    name: `Dr. ${rand(FIRST)} ${rand(LAST)}`,
    specialty: SPECIALTIES[i % SPECIALTIES.length],
    avatarColor: DOCTOR_COLORS[i % DOCTOR_COLORS.length],
    appointmentsToday: apt,
    capacity: cap,
    status,
    avgConsultMin: 8 + Math.floor(Math.random() * 18),
  };
});

const REASONS = [
  "Follow-up",
  "Consultation",
  "Annual checkup",
  "Lab review",
  "Vaccination",
  "Urgent care",
  "Prescription refill",
];
const STATUSES: AppointmentStatus[] = [
  "Confirmed",
  "Waiting",
  "In Progress",
  "Completed",
  "Confirmed",
  "Waiting",
  "Completed",
];

const today = new Date().toISOString().slice(0, 10);

export const APPOINTMENTS: Appointment[] = Array.from({ length: 220 }, (_, i) => {
  const doc = rand(DOCTORS);
  const hour = 8 + Math.floor(Math.random() * 11);
  const minute = rand([0, 15, 30, 45]);
  return {
    id: `apt-${i + 1}`,
    patientName: `${rand(FIRST)} ${rand(LAST)}`,
    patientId: `pat-${1000 + i}`,
    doctorId: doc.id,
    doctorName: doc.name,
    time: `${pad(hour)}:${pad(minute)}`,
    date: today,
    status: rand(STATUSES),
    predictedWaitMin: Math.floor(Math.random() * 55),
    reason: rand(REASONS),
    urgency: rand(["low", "medium", "high"] as const),
  };
});

// Wait time series for last 12 hours
export const WAIT_SERIES = Array.from({ length: 12 }, (_, i) => {
  const hour = 8 + i;
  const base = 12 + Math.sin(i / 2) * 8 + Math.random() * 10;
  return {
    time: `${pad(hour)}:00`,
    wait: Math.max(5, Math.round(base + (i > 6 ? 12 : 0))),
    threshold: 30,
  };
});

// Patient load forecast for the day
export const LOAD_FORECAST = Array.from({ length: 12 }, (_, i) => {
  const hour = 8 + i;
  const peak = i === 5 || i === 7;
  return {
    hour: `${pad(hour)}:00`,
    actual: i < 6 ? Math.round(20 + Math.random() * 18) : null,
    predicted: Math.round(18 + Math.sin((i - 2) / 2) * 14 + (peak ? 22 : 0) + Math.random() * 6),
  };
});

export const ALERTS: Alert[] = [
  {
    id: "alt-1",
    severity: "High",
    title: "Booking surge detected — 3 PM slot",
    reasoning:
      "Inbound bookings up 187% vs forecast. Anomaly score 0.92. Recommend opening 8 additional slots between 14:30 and 16:00 to avoid 38min wait spike.",
    timestamp: "2 min ago",
    type: "surge",
    trace: [
      "trigger=prometheus_alert booking_volume spike detected",
      "score_anomaly(window=30m) => -0.41 (anomalous)",
      "query_prometheus(p95_latency,15m) => 1.2s (within SLA)",
      "suggest_open_slots(count=8, window=14:30–16:00)",
    ],
    recommendedActions: [{ kind: "open_slots", count: 8, windowLabel: "14:30–16:00" }],
  },
  {
    id: "alt-2",
    severity: "Medium",
    title: "Voice agent latency above SLA",
    reasoning:
      "p95 STT latency = 1.4s (SLA: 800ms). Likely cause: cold-start on regional ASR pod. Auto-scaling triggered, ETA recovery 3min.",
    timestamp: "11 min ago",
    type: "latency",
    trace: [
      "trigger=prometheus_alert p95_latency >= 2s",
      "query_prometheus(p95_latency,15m) => 2.3s",
      "diagnose => STT cold start likely",
      "recommend => scale voice workers; route to fallback",
    ],
  },
  {
    id: "alt-3",
    severity: "Medium",
    title: "Wait-time model drift — Cardiology",
    reasoning:
      "Predicted vs actual MAE drifted from 4.2 → 9.1 min over last 48h. Patient mix shifted (chronic +22%). Retraining scheduled tonight.",
    timestamp: "34 min ago",
    type: "drift",
    recommendedActions: [{ kind: "trigger_retraining", model: "wait_time_model" }],
  },
  {
    id: "alt-4",
    severity: "Low",
    title: "Capacity OK across all departments",
    reasoning: "All doctors below 75% capacity. No action needed.",
    timestamp: "1 hr ago",
    type: "capacity",
  },
];

export const SUGGESTIONS = [
  { id: "s1", title: "Open 8 new slots at 15:00", impact: "−18 min avg wait", confidence: 0.92 },
  {
    id: "s2",
    title: "Reassign 4 patients from Dr. Khan → Dr. Malik",
    impact: "Balance load 91% → 74%",
    confidence: 0.86,
  },
  {
    id: "s3",
    title: "Send proactive SMS to 12 patients",
    impact: "Reduce no-shows by 23%",
    confidence: 0.78,
  },
];

// Live activity feed seed
export const ACTIVITY_SEED = [
  { type: "booking", text: "New booking — Sara Khan with Dr. Malik", time: "just now" },
  { type: "ai", text: "AI agent confirmed appointment via WhatsApp", time: "1m" },
  { type: "reassign", text: "Patient reassigned: Dr. Khan → Dr. Iqbal", time: "3m" },
  { type: "cancel", text: "Cancellation — Bilal Raza (10:30 slot)", time: "5m" },
  { type: "voice", text: "Voice booking completed in Urdu — 38s call", time: "7m" },
  { type: "booking", text: "Walk-in registered — Hassan Ahmed", time: "9m" },
  { type: "ai", text: "Model retraining triggered for wait_time_model", time: "12m" },
  { type: "ai", text: "Anomaly score surge detected (0.88)", time: "15m" },
];

// Stats
export function getOverviewStats() {
  const totalToday = APPOINTMENTS.length;
  const inQueue = APPOINTMENTS.filter(
    (a) => a.status === "Waiting" || a.status === "In Progress",
  ).length;
  const avgWait = Math.round(
    APPOINTMENTS.reduce((s, a) => s + a.predictedWaitMin, 0) / APPOINTMENTS.length,
  );
  return {
    totalToday,
    inQueue,
    avgWait,
    health: 99.2,
  };
}

export interface Slot {
  id: string;
  doctorId: string;
  doctorName: string;
  specialty: string;
  date: string; // YYYY-MM-DD
  time: string; // HH:mm
  status: "available" | "booked" | "blocked";
  predictedWaitMin: number;
}

export interface AgentStatus {
  id: "booking" | "calling" | "scheduling" | "ops_monitor";
  name: string;
  state: "online" | "degraded" | "offline";
  lastAction: string;
  lastSeenAt: number;
}

export interface SchedulingRun {
  id: string;
  startedAt: number;
  windowHoursAhead: number;
  overloadedDoctors: Array<{
    doctorId: string;
    doctorName: string;
    avgPredictedWait: number;
    peakHourLabel: string;
    peakHourPatients: number;
  }>;
  reassignments: Array<{
    appointmentId: string;
    fromDoctorId: string;
    toDoctorId: string;
    fromTime: string;
    toTime: string;
    gate: { oldWaitMin: number; newWaitMin: number; passed: boolean };
  }>;
}

export interface ClinicMetrics {
  bookingVolume30m: number;
  p95LatencyMs: number;
  apiErrorRatePct: number;
  anomalyScore: number;
  waitModelDriftKl: number;
  keyPoolAvailable: Record<"gemini" | "groq" | "together" | "openrouter", number>;
}

export interface ClinicSimState {
  now: number;
  doctors: Doctor[];
  slots: Slot[];
  appointments: Appointment[];
  waitSeries: Array<{ time: string; wait: number; threshold: number }>;
  loadForecast: Array<{ hour: string; actual: number | null; predicted: number }>;
  alerts: Alert[];
  suggestions: typeof SUGGESTIONS;
  activity: Array<{
    id: string;
    type: (typeof ACTIVITY_SEED)[number]["type"];
    text: string;
    time: string;
    at: number;
  }>;
  agents: AgentStatus[];
  metrics: ClinicMetrics;
  lastSchedulingRun?: SchedulingRun;
  overview?: {
    totalToday: number;
    inQueue: number;
    avgWait: number;
    health: number;
  };
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function minutesAgoLabel(now: number, at: number) {
  const diffMin = Math.round((now - at) / 60000);
  if (diffMin <= 0) return "just now";
  if (diffMin === 1) return "1 min ago";
  if (diffMin < 60) return `${diffMin} min ago`;
  const hr = Math.round(diffMin / 60);
  return `${hr} hr ago`;
}

function makeSlotId(doctorId: string, date: string, time: string) {
  return `slot:${doctorId}:${date}:${time}`;
}

function initialSlots(): Slot[] {
  const hours = Array.from({ length: 11 }, (_, i) => 8 + i);
  const minutes = [0, 15, 30, 45];
  const slots: Slot[] = [];
  for (const d of DOCTORS) {
    for (const h of hours) {
      for (const m of minutes) {
        const time = `${pad(h)}:${pad(m)}`;
        slots.push({
          id: makeSlotId(d.id, today, time),
          doctorId: d.id,
          doctorName: d.name,
          specialty: d.specialty,
          date: today,
          time,
          status: "available",
          predictedWaitMin: Math.floor(Math.random() * 35),
        });
      }
    }
  }
  return slots;
}

function seedBookedSlots(
  slots: Slot[],
  appointments: Appointment[],
): { slots: Slot[]; appointments: Appointment[] } {
  type SlotKey = `${string}|${string}|${string}`;
  const byKey = new Map<SlotKey, Slot>(
    slots.map((s) => [`${s.doctorId}|${s.date}|${s.time}` as SlotKey, s]),
  );
  const newAppointments = appointments.map((apt) => {
    const key = `${apt.doctorId}|${apt.date}|${apt.time}` as SlotKey;
    const slot = byKey.get(key);
    if (slot) {
      slot.status = "booked";
      slot.predictedWaitMin = apt.predictedWaitMin;
      return { ...apt, slotId: slot.id };
    }
    return apt;
  });
  return { slots, appointments: newAppointments };
}

function computeDoctorStats(doctors: Doctor[], appointments: Appointment[]): Doctor[] {
  const byDoc = new Map<string, number>();
  for (const a of appointments) {
    if (a.status !== "Cancelled") {
      byDoc.set(a.doctorId, (byDoc.get(a.doctorId) ?? 0) + 1);
    }
  }
  return doctors.map((d) => {
    const count = byDoc.get(d.id) ?? 0;
    const ratio = count / d.capacity;
    let status: Doctor["status"] = "available";
    if (ratio > 1) status = "overloaded";
    else if (ratio > 0.75) status = "busy";
    else if (ratio < 0.1) status = "off";

    if (d.appointmentsToday === count && d.status === status) return d;
    return { ...d, appointmentsToday: count, status };
  });
}

function computeOverviewStatsFrom(state: ClinicSimState) {
  const totalToday = state.appointments.length;
  const inQueue = state.appointments.filter(
    (a) => a.status === "Waiting" || a.status === "In Progress",
  ).length;
  const avgWait = totalToday
    ? Math.round(state.appointments.reduce((s, a) => s + a.predictedWaitMin, 0) / totalToday)
    : 0;
  return { totalToday, inQueue, avgWait };
}

const INITIAL_STATE: ClinicSimState = (() => {
  const baseDoctors = DOCTORS.map((d) => ({ ...d }));
  const baseAppointments = APPOINTMENTS.map((a) => ({ ...a }));
  const baseSlots = initialSlots();
  const { slots, appointments } = seedBookedSlots(baseSlots, baseAppointments);
  const doctors = computeDoctorStats(baseDoctors, appointments);
  const now = Date.now();
  const initialState: ClinicSimState = {
    now,
    doctors,
    slots,
    appointments,
    waitSeries: WAIT_SERIES.map((x) => ({ ...x })),
    loadForecast: LOAD_FORECAST.map((x) => ({ ...x })),
    alerts: ALERTS.map((a) => ({ ...a })),
    suggestions: SUGGESTIONS,
    activity: ACTIVITY_SEED.map((s, i) => ({ ...s, id: `seed-${i}`, at: now - i * 60000 })),
    agents: [
      {
        id: "booking",
        name: "Booking Agent",
        state: "online",
        lastAction: "Language detected · ready",
        lastSeenAt: now,
      },
      {
        id: "calling",
        name: "Calling Agent",
        state: "online",
        lastAction: "Voice channel idle",
        lastSeenAt: now - 22000,
      },
      {
        id: "scheduling",
        name: "Scheduling Agent",
        state: "online",
        lastAction: "Next run in 30m",
        lastSeenAt: now - 120000,
      },
      {
        id: "ops_monitor",
        name: "Ops Monitor Agent",
        state: "online",
        lastAction: "Monitoring Prometheus alerts",
        lastSeenAt: now - 15000,
      },
    ],
    metrics: {
      bookingVolume30m: 42,
      p95LatencyMs: 1200,
      apiErrorRatePct: 1.6,
      anomalyScore: 0.32,
      waitModelDriftKl: 0.06,
      keyPoolAvailable: { gemini: 11, groq: 18, together: 7, openrouter: 4 },
    },
  };
  initialState.overview = { ...computeOverviewStatsFrom(initialState), health: 100 };
  return initialState;
})();

let state: ClinicSimState = INITIAL_STATE;
const listeners = new Set<() => void>();
let simHandles: number[] = [];

function emit() {
  for (const l of listeners) l();
}

function setState(next: ClinicSimState) {
  state = next;
  emit();
}

function updateState(updater: (s: ClinicSimState) => ClinicSimState) {
  setState(updater(state));
}

function ensureSimRunning() {
  if (simHandles.length) return;

  const tick = window.setInterval(() => {
    updateState((s) => {
      const now = Date.now();
      const next: ClinicSimState = { ...s, now };

      const drift = clamp(s.metrics.waitModelDriftKl + (Math.random() - 0.5) * 0.01, 0.01, 0.22);
      const p95 = clamp(s.metrics.p95LatencyMs + (Math.random() - 0.5) * 240, 450, 3200);
      const bookingVol = clamp(
        s.metrics.bookingVolume30m + Math.round((Math.random() - 0.45) * 6),
        12,
        140,
      );
      const errRate = clamp(s.metrics.apiErrorRatePct + (Math.random() - 0.48) * 0.3, 0.2, 6);

      const surge = clamp((bookingVol - 40) / 100, 0, 1);
      const latency = clamp((p95 - 1200) / 2000, 0, 1);
      const driftNorm = clamp((drift - 0.05) / 0.15, 0, 1);
      const anomalyScore = clamp(
        0.15 + surge * 0.55 + latency * 0.2 + driftNorm * 0.25 + Math.random() * 0.05,
        0,
        1,
      );

      next.metrics = {
        ...s.metrics,
        waitModelDriftKl: drift,
        p95LatencyMs: p95,
        bookingVolume30m: bookingVol,
        apiErrorRatePct: errRate,
        anomalyScore,
        keyPoolAvailable: {
          gemini: clamp(
            s.metrics.keyPoolAvailable.gemini + Math.round((Math.random() - 0.65) * 2),
            0,
            20,
          ),
          groq: clamp(
            s.metrics.keyPoolAvailable.groq + Math.round((Math.random() - 0.55) * 3),
            0,
            30,
          ),
          together: clamp(
            s.metrics.keyPoolAvailable.together + Math.round((Math.random() - 0.6) * 2),
            0,
            14,
          ),
          openrouter: clamp(
            s.metrics.keyPoolAvailable.openrouter + Math.round((Math.random() - 0.6) * 2),
            0,
            10,
          ),
        },
      };

      next.waitSeries = s.waitSeries.slice(1).concat([
        {
          time: new Date(now).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          wait: Math.round(8 + surge * 32 + Math.random() * 10),
          threshold: 30,
        },
      ]);

      next.loadForecast = s.loadForecast.map((x, i) => ({
        ...x,
        predicted: Math.max(
          0,
          Math.round(
            x.predicted + (Math.sin((now / 60000 + i) / 4) * 2 + (Math.random() - 0.5) * 2),
          ),
        ),
      }));

      next.activity = s.activity
        .map((a) => ({ ...a, time: minutesAgoLabel(now, a.at) }))
        .slice(0, 40);

      const maybeActivity = Math.random() < 0.34;
      if (maybeActivity) {
        const pick = rand([
          {
            type: "ai" as const,
            text: "Ops Monitor evaluated anomaly score and updated recommendations",
          },
          { type: "voice" as const, text: "Voice STT pipeline processed a new utterance (EN/UR)" },
          { type: "booking" as const, text: `New booking intent detected — ${rand(SPECIALTIES)}` },
          {
            type: "reassign" as const,
            text: "Scheduling Agent prepared reassignment candidates (gate check applied)",
          },
        ]);
        next.activity = [
          { id: `evt-${now}`, ...pick, time: "just now", at: now },
          ...next.activity,
        ].slice(0, 40);
      }

      next.slots = s.slots.map((slot) => {
        if (slot.status !== "available") return slot;
        const hour = parseInt(slot.time.slice(0, 2), 10);
        const base = 8 + (hour >= 14 && hour <= 16 ? 10 : 0);
        const wait = clamp(Math.round(base + surge * 20 + Math.random() * 12), 3, 65);
        return slot.predictedWaitMin === wait ? slot : { ...slot, predictedWaitMin: wait };
      });

      next.appointments = s.appointments.map((a) => {
        if (a.status === "Cancelled" || a.status === "Completed") return a;
        const jitter = Math.round((Math.random() - 0.55) * 4);
        const pred = clamp(a.predictedWaitMin + jitter, 0, 70);
        return pred === a.predictedWaitMin ? a : { ...a, predictedWaitMin: pred };
      });

      next.doctors = computeDoctorStats(s.doctors, next.appointments);

      const alerts = [...s.alerts];
      const hasSurge = alerts.some((a) => a.type === "surge" && !a.acknowledged);
      if (!hasSurge && anomalyScore > 0.78) {
        alerts.unshift({
          id: `alt-${now}`,
          severity: "High",
          title: "Booking surge anomaly detected",
          reasoning: `Booking volume up ${Math.round(surge * 220)}% vs forecast. Composite anomaly score ${(anomalyScore * 100).toFixed(0)}. Recommend opening overflow slots and redistributing workload.`,
          timestamp: "just now",
          type: "surge",
          trace: [
            "trigger=prometheus_alert booking_volume spike detected",
            `query_booking_volume(30m) => ${bookingVol} bookings`,
            `score_anomaly() => ${(anomalyScore * -0.55).toFixed(2)}`,
            `query_prometheus(p95_latency,15m) => ${(p95 / 1000).toFixed(1)}s`,
          ],
          recommendedActions: [{ kind: "open_slots", count: 8, windowLabel: "14:30–16:00" }],
        });
        next.activity = [
          {
            id: `alert-${now}`,
            type: "ai",
            text: "Ops Monitor raised a surge alert with reasoning trace",
            time: "just now",
            at: now,
          },
          ...next.activity,
        ].slice(0, 40);
      }
      const hasLatency = alerts.some((a) => a.type === "latency" && !a.acknowledged);
      if (!hasLatency && p95 >= 2000) {
        alerts.unshift({
          id: `alt-${now}-lat`,
          severity: "Medium",
          title: "API p95 latency above SLA",
          reasoning: `p95 ${(p95 / 1000).toFixed(1)}s (> 2.0s). Ops Monitor recommends routing STT to fallback and scaling voice workers.`,
          timestamp: "just now",
          type: "latency",
          trace: [
            "trigger=prometheus_alert p95_latency >= 2s",
            `query_prometheus(p95_latency,15m) => ${(p95 / 1000).toFixed(1)}s`,
            "recommend => scale voice workers; route to fallback",
          ],
        });
      }
      const hasDrift = alerts.some((a) => a.type === "drift" && !a.acknowledged);
      if (!hasDrift && drift >= 0.12) {
        alerts.unshift({
          id: `alt-${now}-drift`,
          severity: "Medium",
          title: "Model drift detected — wait_time_model",
          reasoning: `KL drift score ${drift.toFixed(2)} (>= 0.12). Retraining recommended before patient mix impacts wait-time accuracy.`,
          timestamp: "just now",
          type: "drift",
          recommendedActions: [{ kind: "trigger_retraining", model: "wait_time_model" }],
        });
      }
      next.alerts = alerts
        .slice(0, 12)
        .map((a) => ({ ...a, timestamp: a.timestamp === "just now" ? "just now" : a.timestamp }));

      next.agents = s.agents.map((a) => {
        const jitter = Math.random() < 0.18;
        if (!jitter) return a;
        const lastSeenAt = now;
        if (a.id === "ops_monitor")
          return {
            ...a,
            lastSeenAt,
            lastAction:
              anomalyScore > 0.75
                ? "Raised surge alert · suggested open slots"
                : "Monitoring metrics & alerts",
          };
        if (a.id === "scheduling")
          return { ...a, lastSeenAt, lastAction: "Evaluated overload gates · queued candidates" };
        if (a.id === "booking")
          return { ...a, lastSeenAt, lastAction: "Generated slot options with predicted wait" };
        return { ...a, lastSeenAt, lastAction: "Voice channel warm" };
      });

      next.overview = {
        ...computeOverviewStatsFrom(next),
        health: clamp(Math.round(100 - anomalyScore * 40 + (Math.random() - 0.5) * 2), 20, 100),
      };

      return next;
    });
  }, 4000);

  const schedulingTick = window.setInterval(() => {
    runSchedulingAgent({ windowHoursAhead: 4 });
  }, 30000);

  simHandles = [tick, schedulingTick];
}

function maybeStopSim() {
  if (listeners.size > 0) return;
  for (const h of simHandles) window.clearInterval(h);
  simHandles = [];
}

export function useClinicSim<T>(selector: (s: ClinicSimState) => T): T {
  const subscribe = useCallback((onStoreChange: () => void) => {
    listeners.add(onStoreChange);
    ensureSimRunning();
    return () => {
      listeners.delete(onStoreChange);
      maybeStopSim();
    };
  }, []);

  const lastSnapshot = useRef<T>(selector(state));
  const lastState = useRef<ClinicSimState | null>(null);

  const getSnapshot = () => {
    if (state !== lastState.current) {
      const next = selector(state);

      const isObject = (val: unknown): val is Record<string, unknown> =>
        val != null && typeof val === "object";
      const isArray = Array.isArray;

      if (isArray(next) && isArray(lastSnapshot.current)) {
        const nArr = next as unknown[];
        const lArr = lastSnapshot.current as unknown[];
        const isSame = nArr.length === lArr.length && nArr.every((v, i) => v === lArr[i]);
        if (!isSame) lastSnapshot.current = next;
      } else if (
        isObject(next) &&
        isObject(lastSnapshot.current) &&
        !isArray(next) &&
        !isArray(lastSnapshot.current)
      ) {
        const nextObj = next as Record<string, unknown>;
        const lastObj = lastSnapshot.current as Record<string, unknown>;
        const keys = Object.keys(nextObj);
        const lastKeys = Object.keys(lastObj);

        const isSame =
          keys.length === lastKeys.length && keys.every((k) => nextObj[k] === lastObj[k]);

        if (!isSame) {
          lastSnapshot.current = next;
        }
      } else if (next !== lastSnapshot.current) {
        lastSnapshot.current = next;
      }
      lastState.current = state;
    }
    return lastSnapshot.current;
  };

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function getClinicSimState() {
  return state;
}

export function acknowledgeAlert(alertId: string) {
  updateState((s) => ({
    ...s,
    alerts: s.alerts.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a)),
  }));
}

export function bookAppointmentFromSlot(params: {
  slotId: string;
  patientName: string;
  patientId?: string;
  reason?: string;
  urgency?: Appointment["urgency"];
}) {
  updateState((s) => {
    const slot = s.slots.find((x) => x.id === params.slotId);
    if (!slot || slot.status !== "available") return s;
    const now = Date.now();
    const patientId = params.patientId ?? `pat-${1000 + (s.appointments.length % 9000)}`;
    const apt: Appointment = {
      id: `apt-${now}`,
      patientName: params.patientName,
      patientId,
      doctorId: slot.doctorId,
      doctorName: slot.doctorName,
      time: slot.time,
      date: slot.date,
      status: "Confirmed",
      predictedWaitMin: slot.predictedWaitMin,
      reason: params.reason ?? rand(REASONS),
      slotId: slot.id,
      urgency: params.urgency ?? "medium",
    };
    const slots: Slot[] = s.slots.map(
      (x): Slot => (x.id === slot.id ? { ...x, status: "booked" } : x),
    );
    const appointments = [apt, ...s.appointments];
    const activity = [
      {
        id: `bk-${now}`,
        type: "booking" as const,
        text: `New booking — ${apt.patientName} with ${apt.doctorName} at ${apt.time}`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);
    const agents = s.agents.map((a) =>
      a.id === "booking"
        ? { ...a, lastSeenAt: now, lastAction: `create_appointment(slot=${slot.time}) · confirmed` }
        : a,
    );
    const doctors = computeDoctorStats(
      s.doctors.map((d) =>
        d.id === slot.doctorId ? { ...d, appointmentsToday: d.appointmentsToday + 1 } : d,
      ),
      appointments,
    );
    return { ...s, slots, appointments, activity, agents, doctors };
  });
}

export function cancelAppointment(appointmentId: string) {
  updateState((s) => {
    const apt = s.appointments.find((a) => a.id === appointmentId);
    if (!apt || apt.status === "Cancelled") return s;
    const now = Date.now();
    const appointments: Appointment[] = s.appointments.map(
      (a): Appointment => (a.id === appointmentId ? { ...a, status: "Cancelled" } : a),
    );
    const slots: Slot[] = apt.slotId
      ? s.slots.map((x): Slot => (x.id === apt.slotId ? { ...x, status: "available" } : x))
      : s.slots;
    const activity = [
      {
        id: `cx-${now}`,
        type: "cancel" as const,
        text: `Cancellation — ${apt.patientName} (${apt.time} slot)`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);
    const doctors = computeDoctorStats(
      s.doctors.map((d) =>
        d.id === apt.doctorId
          ? { ...d, appointmentsToday: Math.max(0, d.appointmentsToday - 1) }
          : d,
      ),
      appointments,
    );
    return { ...s, appointments, slots, activity, doctors };
  });
}

export function updateAppointment(
  appointmentId: string,
  patch: Partial<Pick<Appointment, "patientName" | "doctorId" | "doctorName" | "time" | "status">>,
) {
  updateState((s) => {
    const current = s.appointments.find((a) => a.id === appointmentId);
    if (!current) return s;
    const now = Date.now();
    const nextApt: Appointment = { ...current, ...patch };
    let slots = s.slots;
    if (current.slotId && (patch.doctorId || patch.time)) {
      slots = slots.map((x): Slot => (x.id === current.slotId ? { ...x, status: "available" } : x));
      const key = makeSlotId(nextApt.doctorId, nextApt.date, nextApt.time);
      const newSlot = slots.find((x) => x.id === key && x.status === "available");
      if (newSlot) {
        nextApt.slotId = newSlot.id;
        nextApt.predictedWaitMin = newSlot.predictedWaitMin;
        slots = slots.map((x): Slot => (x.id === newSlot.id ? { ...x, status: "booked" } : x));
      }
    }
    const appointments: Appointment[] = s.appointments.map(
      (a): Appointment => (a.id === appointmentId ? nextApt : a),
    );
    const activity = [
      {
        id: `up-${now}`,
        type: "ai" as const,
        text: `Appointment updated — ${nextApt.patientName} moved to ${nextApt.doctorName} at ${nextApt.time}`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);
    const doctors = computeDoctorStats(
      s.doctors.map((d) => ({ ...d })),
      appointments,
    );
    return { ...s, appointments, slots, activity, doctors };
  });
}

export function runSchedulingAgent(params: { windowHoursAhead: number }) {
  updateState((s) => {
    const now = Date.now();
    const appts = s.appointments.filter(
      (a) => a.status !== "Cancelled" && a.status !== "Completed",
    );
    const byDoc = new Map<string, Appointment[]>();
    for (const a of appts) {
      const list = byDoc.get(a.doctorId) ?? [];
      list.push(a);
      byDoc.set(a.doctorId, list);
    }

    const overloadedDoctors: SchedulingRun["overloadedDoctors"] = [];
    for (const d of s.doctors) {
      const list = byDoc.get(d.id) ?? [];
      if (!list.length) continue;
      const avgPred = list.reduce((sum, a) => sum + a.predictedWaitMin, 0) / list.length;
      const peakHourPatients = Math.max(0, Math.round(list.length / 3 + Math.random() * 3));
      const peakHourLabel = `${pad(12 + Math.floor(Math.random() * 5))}:00`;
      if (avgPred > 35 || peakHourPatients > 8) {
        overloadedDoctors.push({
          doctorId: d.id,
          doctorName: d.name,
          avgPredictedWait: Math.round(avgPred),
          peakHourLabel,
          peakHourPatients,
        });
      }
    }

    const candidates = appts
      .filter((a) => a.urgency !== "high")
      .sort((a, b) => b.predictedWaitMin - a.predictedWaitMin)
      .slice(0, 8);

    const reassignments: SchedulingRun["reassignments"] = [];
    let slots = s.slots;
    let appointments = s.appointments;

    for (const apt of candidates) {
      const oldWait = apt.predictedWaitMin;
      const targetSlot = slots.find(
        (sl) =>
          sl.status === "available" &&
          sl.specialty ===
            (s.doctors.find((d) => d.id === apt.doctorId)?.specialty ?? sl.specialty) &&
          sl.predictedWaitMin < 22,
      );
      if (!targetSlot) continue;
      const gate = {
        oldWaitMin: oldWait,
        newWaitMin: targetSlot.predictedWaitMin,
        passed: oldWait > 45 && targetSlot.predictedWaitMin < 20,
      };
      reassignments.push({
        appointmentId: apt.id,
        fromDoctorId: apt.doctorId,
        toDoctorId: targetSlot.doctorId,
        fromTime: apt.time,
        toTime: targetSlot.time,
        gate,
      });
      if (!gate.passed) continue;

      slots = slots.map((x): Slot => {
        if (x.id === apt.slotId) return { ...x, status: "available" };
        if (x.id === targetSlot.id) return { ...x, status: "booked" };
        return x;
      });

      appointments = appointments.map((a): Appointment => {
        if (a.id !== apt.id) return a;
        return {
          ...a,
          doctorId: targetSlot.doctorId,
          doctorName: targetSlot.doctorName,
          time: targetSlot.time,
          slotId: targetSlot.id,
          predictedWaitMin: targetSlot.predictedWaitMin,
        };
      });
    }

    const run: SchedulingRun = {
      id: `run-${now}`,
      startedAt: now,
      windowHoursAhead: params.windowHoursAhead,
      overloadedDoctors,
      reassignments,
    };

    const shouldAlert = overloadedDoctors.length > 0;
    const schedulingAlert: Alert = {
      id: `alt-${now}-sched`,
      severity: "High",
      title: "Scheduling overload flagged",
      reasoning: `Scheduling Agent detected overload in ${overloadedDoctors.length} doctor(s). Gate-based reassignment suggested to keep predicted waits below 35m.`,
      timestamp: "just now",
      type: "capacity",
      trace: [
        "trigger=celery_beat schedule_optimizer",
        "predict_patient_load(doctors) => peak_hour_patients per doctor",
        "predict_wait_time(slots) => avg_predicted_wait",
        "flag_overload() => ops_alert created",
        "reassign_slot() gated by (old_wait>45 AND new_wait<20)",
      ],
    };
    const alerts: Alert[] = shouldAlert ? [schedulingAlert, ...s.alerts].slice(0, 12) : s.alerts;

    const activity = [
      {
        id: `sched-${now}`,
        type: "ai" as const,
        text: `Scheduling Agent ran optimization window (+${params.windowHoursAhead}h) · ${reassignments.filter((r) => r.gate.passed).length} reassignment(s) applied`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);

    const agents = s.agents.map((a) =>
      a.id === "scheduling"
        ? {
            ...a,
            lastSeenAt: now,
            lastAction: `Optimized schedule (+${params.windowHoursAhead}h) · gates enforced`,
          }
        : a,
    );
    const doctors = s.doctors.map((d) => ({ ...d }));
    computeDoctorStats(doctors, appointments);
    return { ...s, slots, appointments, lastSchedulingRun: run, alerts, activity, agents, doctors };
  });
}

export function getAvailableSlots(params: {
  specialty?: string;
  date?: string;
  preferredTime?: string;
  limit?: number;
}) {
  const s = state;
  const date = params.date ?? today;
  const limit = params.limit ?? 3;
  const prefHour = params.preferredTime ? parseInt(params.preferredTime.slice(0, 2), 10) : null;
  return s.slots
    .filter((sl) => sl.status === "available" && sl.date === date)
    .filter((sl) =>
      params.specialty ? sl.specialty.toLowerCase().includes(params.specialty.toLowerCase()) : true,
    )
    .sort((a, b) => {
      const aH = parseInt(a.time.slice(0, 2), 10);
      const bH = parseInt(b.time.slice(0, 2), 10);
      const prefA = prefHour == null ? 0 : Math.abs(aH - prefHour);
      const prefB = prefHour == null ? 0 : Math.abs(bH - prefHour);
      return prefA - prefB || a.predictedWaitMin - b.predictedWaitMin;
    })
    .slice(0, limit);
}

export function openOverflowSlots(params: { count: number; doctorId?: string; date?: string }) {
  updateState((s) => {
    const now = Date.now();
    const date = params.date ?? today;
    const doctor =
      (params.doctorId && s.doctors.find((d) => d.id === params.doctorId)) ??
      [...s.doctors].sort((a, b) => b.appointmentsToday - a.appointmentsToday)[0];
    if (!doctor) return s;

    const existing = new Set(
      s.slots.filter((x) => x.doctorId === doctor.id && x.date === date).map((x) => x.time),
    );
    const candidates = ["18:30", "19:00", "19:30", "20:00", "20:30", "21:00"];
    const toCreate = candidates.filter((t) => !existing.has(t)).slice(0, params.count);
    if (!toCreate.length) return s;

    const newSlots: Slot[] = toCreate.map((time) => ({
      id: makeSlotId(doctor.id, date, time),
      doctorId: doctor.id,
      doctorName: doctor.name,
      specialty: doctor.specialty,
      date,
      time,
      status: "available",
      predictedWaitMin: clamp(Math.round(8 + Math.random() * 14), 3, 40),
    }));

    const activity = [
      {
        id: `open-${now}`,
        type: "ai" as const,
        text: `Opened ${newSlots.length} overflow slot(s) for ${doctor.name} (${doctor.specialty})`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);

    const agents = s.agents.map((a) =>
      a.id === "ops_monitor"
        ? {
            ...a,
            lastSeenAt: now,
            lastAction: `suggest_open_slots(count=${newSlots.length}) · completed`,
          }
        : a,
    );

    const metrics: ClinicMetrics = {
      ...s.metrics,
      bookingVolume30m: clamp(s.metrics.bookingVolume30m - Math.round(newSlots.length * 2), 0, 180),
      anomalyScore: clamp(s.metrics.anomalyScore - 0.08, 0, 1),
    };

    return { ...s, slots: [...newSlots, ...s.slots], activity, agents, metrics };
  });
}

export function triggerRetraining(model: "wait_time_model" | "patient_load_model") {
  updateState((s) => {
    const now = Date.now();
    const activity = [
      {
        id: `rt-${now}`,
        type: "ai" as const,
        text: `Retraining triggered for ${model} (champion/challenger pipeline)`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);

    const agents = s.agents.map((a) =>
      a.id === "ops_monitor"
        ? { ...a, lastSeenAt: now, lastAction: `trigger_retraining(model=${model})` }
        : a,
    );

    const metrics: ClinicMetrics =
      model === "wait_time_model"
        ? {
            ...s.metrics,
            waitModelDriftKl: clamp(s.metrics.waitModelDriftKl - 0.06, 0.01, 0.22),
            anomalyScore: clamp(s.metrics.anomalyScore - 0.05, 0, 1),
          }
        : { ...s.metrics, anomalyScore: clamp(s.metrics.anomalyScore - 0.03, 0, 1) };

    return { ...s, activity, agents, metrics };
  });
}

export function sendNotifications(params: { channel: "sms" | "whatsapp"; count: number }) {
  updateState((s) => {
    const now = Date.now();
    const activity = [
      {
        id: `nt-${now}`,
        type: "ai" as const,
        text: `Sent ${params.count} ${params.channel.toUpperCase()} notification(s) to patients`,
        time: "just now",
        at: now,
      },
      ...s.activity,
    ].slice(0, 40);
    return { ...s, activity };
  });
}
