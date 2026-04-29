from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr

from db.models import AppointmentStatus


class Patient(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None


class Doctor(BaseModel):
    id: str
    name: str
    specialty: str
    avatarColor: str
    appointmentsToday: int
    capacity: int
    status: Literal["available", "busy", "overloaded", "off"]
    avgConsultMin: int


class Appointment(BaseModel):
    id: str
    patientName: str
    patientId: str
    doctorId: str
    doctorName: str
    time: str
    date: str
    status: AppointmentStatus
    predictedWaitMin: int
    reason: str
    slotId: Optional[str] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None


class AppointmentCreate(BaseModel):
    patientName: str
    patientId: str
    doctorId: str
    doctorName: str
    time: str
    date: str
    reason: str
    slotId: Optional[str] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None


class AppointmentUpdate(BaseModel):
    patientName: Optional[str] = None
    patientId: Optional[str] = None
    doctorId: Optional[str] = None
    doctorName: Optional[str] = None
    time: Optional[str] = None
    date: Optional[str] = None
    status: Optional[AppointmentStatus] = None
    predictedWaitMin: Optional[int] = None
    reason: Optional[str] = None
    slotId: Optional[str] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None


class AlertActionOpenSlots(BaseModel):
    kind: Literal["open_slots"]
    count: int
    doctorId: Optional[str] = None
    windowLabel: Optional[str] = None


class AlertActionReassignPatients(BaseModel):
    kind: Literal["reassign_patients"]
    count: int
    fromDoctorId: Optional[str] = None
    toDoctorId: Optional[str] = None


class AlertActionTriggerRetraining(BaseModel):
    kind: Literal["trigger_retraining"]
    model: Literal["wait_time_model", "patient_load_model"]


class AlertActionNotify(BaseModel):
    kind: Literal["notify"]
    channel: Literal["sms", "whatsapp"]
    count: int


AlertAction = AlertActionOpenSlots | AlertActionReassignPatients | AlertActionTriggerRetraining | AlertActionNotify


class Alert(BaseModel):
    id: str
    severity: Literal["Low", "Medium", "High"]
    title: str
    reasoning: str
    timestamp: str
    type: Literal["surge", "latency", "drift", "capacity"]
    trace: Optional[List[str]] = None
    recommendedActions: Optional[List[AlertAction]] = None
    acknowledged: Optional[bool] = None


class AlertCreate(BaseModel):
    severity: Literal["Low", "Medium", "High"]
    title: str
    reasoning: str
    type: Literal["surge", "latency", "drift", "capacity"]
    trace: Optional[List[str]] = None
    recommendedActions: Optional[List[AlertAction]] = None


class Prediction(BaseModel):
    id: str
    type: Literal["wait_time", "patient_load"]
    value: float
    timestamp: datetime
    meta: Optional[Dict[str, Any]] = None


class WaitSeriesPoint(BaseModel):
    time: str
    wait: int
    threshold: int


class LoadForecastPoint(BaseModel):
    hour: str
    actual: Optional[int]
    predicted: int


class OverviewStats(BaseModel):
    totalToday: int
    inQueue: int
    avgWait: int
    health: int


class ActivityEvent(BaseModel):
    id: str
    type: Literal["ai", "voice", "booking", "reassign", "cancel", "walkin"]
    text: str
    time: str
    at: int


class Suggestion(BaseModel):
    id: str
    title: str
    impact: str
    confidence: float


class AgentStatus(BaseModel):
    id: Literal["booking", "calling", "scheduling", "ops_monitor"]
    name: str
    state: Literal["online", "degraded", "offline"]
    lastAction: str
    lastSeenAt: int


class ClinicMetrics(BaseModel):
    bookingVolume30m: int
    p95LatencyMs: int
    apiErrorRatePct: float
    anomalyScore: float
    waitModelDriftKl: float
    keyPoolAvailable: Dict[Literal["gemini", "groq", "together", "openrouter"], int]


class ChatMessage(BaseModel):
    userId: str
    message: str


class ChatResponse(BaseModel):
    response: str
    agentId: str
    intent: Optional[str] = None
    suggestedActions: Optional[List[Dict[str, Any]]] = None


class VoiceProcess(BaseModel):
    userId: str
    audioDataBase64: str


class VoiceResponse(BaseModel):
    transcript: str
    responseText: str
    responseAudioBase64: Optional[str] = None


class OptimizationRequest(BaseModel):
    windowHoursAhead: int = 4


class OptimizationResponse(BaseModel):
    success: bool
    reassignmentsCount: int
    newAvgWaitTime: float


class Token(BaseModel):
    accessToken: str
    tokenType: str
