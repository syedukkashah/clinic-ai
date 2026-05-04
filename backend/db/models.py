import enum
from datetime import datetime, UTC

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Enum, Float,
    ForeignKey, Integer, String, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# ---------------- ENUMS ----------------

class AppointmentStatus(str, enum.Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    WAITING = "Waiting"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class UrgencyLevel(str, enum.Enum):
    ROUTINE = "routine"
    MODERATE = "moderate"
    URGENT = "urgent"


class BookingChannel(str, enum.Enum):
    CHAT = "chat"
    VOICE_NOTE = "voice_note"
    WEBRTC_CALL = "webrtc_call"
    TWILIO_CALL = "twilio_call"


# ---------------- MODELS ----------------

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    preferred_lang = Column(String(5), default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    appointments = relationship("Appointment", back_populates="patient")
    notifications = relationship("Notification", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)

    image_url = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    avg_consult_duration = Column(Float, default=10.0)

    appointments = relationship("Appointment", back_populates="doctor")
    slots = relationship("Slot", back_populates="doctor")
    daily_load_records = relationship("DailyLoad", back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    status = Column(String, default="confirmed")

    predicted_wait_min = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    status = Column(String, default="pending")

    patient = relationship("Patient", back_populates="notifications")


class OpsAlert(Base):
    __tablename__ = "ops_alerts"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String, default="warning")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # 🔥 REQUIRED for your scheduling agent test
    details = Column(JSON)


# ---------------- OPTIONAL ML TABLES ----------------

class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    is_available = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="slots")

    __table_args__ = (
        UniqueConstraint("doctor_id", "start_time", name="uq_slot_doctor_time"),
    )


class DailyLoad(Base):
    __tablename__ = "daily_load"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    specialty = Column(String, nullable=False)
    scheduled_date = Column(Date, nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    patient_count = Column(Integer, default=0)

    doctor = relationship("Doctor", back_populates="daily_load_records")