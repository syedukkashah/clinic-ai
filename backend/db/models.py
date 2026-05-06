import enum
import uuid

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


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

# adding booking channels for ML features - ij
class BookingChannel(str, enum.Enum):
    CHAT = "chat"
    VOICE_NOTE = "voice_note"
    WEBRTC_CALL = "webrtc_call"
    TWILIO_CALL = "twilio_call"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    preferred_lang = Column(String(5), default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    appointments = relationship("Appointment", back_populates="patient")
    notifications = relationship("Notification", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    specialty = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    avg_consult_duration = Column(Float, default=10.0)

    appointments = relationship("Appointment", back_populates="doctor")
    slots = relationship("Slot", back_populates="doctor")
    daily_load_records = relationship("DailyLoad", back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=True, index=True)

    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    date = Column(Date, nullable=True)
    time = Column(String, nullable=True)

    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    urgency = Column(Enum(UrgencyLevel), default=UrgencyLevel.ROUTINE)

    reason = Column(String, nullable=True)
    complaint = Column(String, nullable=True)
    specialty = Column(String, nullable=True)
    patient_age = Column(Integer, nullable=True)
    booking_channel = Column(Enum(BookingChannel), nullable=True)
    booking_lead_days = Column(Integer, nullable=True)

    predicted_wait_min = Column(Integer, default=0)
    is_follow_up = Column(Boolean, default=False)

    showed_up = Column(Boolean, nullable=True)
    actual_wait_minutes = Column(Float, nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    slot = relationship("Slot", back_populates="appointment")
    ml_predictions = relationship("MLPrediction", back_populates="appointment")
    notifications = relationship("Notification", back_populates="appointment")

class AnomalyPrediction(Base):
    __tablename__ = "anomaly_predictions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)
    value = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON, nullable=True)


#adding new tables -ij
class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    is_available = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="slots")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)
    
    __table_args__ = (
        UniqueConstraint("doctor_id", "start_time", name="uq_slot_doctor_time"),
    )


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    target_doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)
    target_date = Column(Date, nullable=True)
    target_hour = Column(Integer, nullable=True)
    input_features = Column(JSON, nullable=False)
    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    appointment = relationship("Appointment", back_populates="ml_predictions")


class OpsAlert(Base):
    __tablename__ = "ops_alerts"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String, nullable=False)
    severity = Column(String(20), default="warning")
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    message = Column(String, nullable=False)
    notification_type = Column(String(20), default="patient")
    is_mock = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="notifications")
    appointment = relationship("Appointment", back_populates="notifications")


class DailyLoad(Base):
    __tablename__ = "daily_load"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    specialty = Column(String, nullable=False)
    scheduled_date = Column(Date, nullable=False, index=True)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    week_of_year = Column(Integer, nullable=False)
    is_holiday = Column(Boolean, default=False)
    is_day_after_holiday = Column(Boolean, default=False)
    is_ramadan = Column(Boolean, default=False)
    season = Column(String, nullable=True)
    patient_count = Column(Integer, default=0)
    lag_1w = Column(Float, nullable=True)
    lag_2w = Column(Float, nullable=True)
    roll_4w_avg = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("doctor_id", "scheduled_date", "hour_of_day",
                         name="uq_daily_load_doctor_date_hour"),
    )

    doctor = relationship("Doctor", back_populates="daily_load_records")