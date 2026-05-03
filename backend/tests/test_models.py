import pytest
from datetime import datetime, timezone, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import (
    Base, Patient, Doctor, Slot, Appointment, Prediction,
    MLPrediction, OpsAlert, Notification, DailyLoad,
    AppointmentStatus, UrgencyLevel, BookingChannel
)

# --- Test database setup ---
# Uses in-memory SQLite so no real PostgreSQL needed
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


# --- Enum tests ---

def test_urgency_level_values():
    assert UrgencyLevel.ROUTINE == "routine"
    assert UrgencyLevel.MODERATE == "moderate"
    assert UrgencyLevel.URGENT == "urgent"


def test_appointment_status_values():
    assert AppointmentStatus.PENDING == "Pending"
    assert AppointmentStatus.CONFIRMED == "Confirmed"
    assert AppointmentStatus.COMPLETED == "Completed"
    assert AppointmentStatus.CANCELLED == "Cancelled"


def test_booking_channel_values():
    assert BookingChannel.CHAT == "chat"
    assert BookingChannel.VOICE_NOTE == "voice_note"
    assert BookingChannel.WEBRTC_CALL == "webrtc_call"
    assert BookingChannel.TWILIO_CALL == "twilio_call"


# --- Table creation tests ---

def test_all_tables_exist():
    table_names = Base.metadata.tables.keys()
    assert "patients" in table_names
    assert "doctors" in table_names
    assert "slots" in table_names
    assert "appointments" in table_names
    assert "predictions" in table_names
    assert "ml_predictions" in table_names
    assert "ops_alerts" in table_names
    assert "notifications" in table_names
    assert "daily_load" in table_names


# --- Patient tests ---

def test_create_patient(db):
    patient = Patient(
        id="pat-001",
        name="Ahmed Khan",
        email="ahmed@test.com",
        phone="03001234567",
        preferred_lang="ur"
    )
    db.add(patient)
    db.commit()

    result = db.query(Patient).filter_by(id="pat-001").first()
    assert result is not None
    assert result.name == "Ahmed Khan"
    assert result.preferred_lang == "ur"


def test_patient_email_unique(db):
    db.add(Patient(id="pat-002", name="Sara", email="unique@test.com"))
    db.commit()

    from sqlalchemy.exc import IntegrityError
    db.add(Patient(id="pat-003", name="Ali", email="unique@test.com"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- Doctor tests ---

def test_create_doctor(db):
    doctor = Doctor(
        id=1,
        name="Dr. Ahmed Raza",
        specialty="general",
        is_available=True,
        avg_consult_duration=9.0
    )
    db.add(doctor)
    db.commit()

    result = db.query(Doctor).filter_by(id=1).first()
    assert result is not None
    assert result.specialty == "general"
    assert result.avg_consult_duration == 9.0


def test_doctor_id_is_integer(db):
    doctor = db.query(Doctor).filter_by(id=1).first()
    assert isinstance(doctor.id, int)


# --- Slot tests ---

def test_create_slot(db):
    slot = Slot(
        doctor_id=1,
        start_time=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
        is_available=True
    )
    db.add(slot)
    db.commit()

    result = db.query(Slot).first()
    assert result is not None
    assert result.doctor_id == 1
    assert result.is_available is True


def test_slot_doctor_relationship(db):
    slot = db.query(Slot).first()
    assert slot.doctor is not None
    assert slot.doctor.name == "Dr. Ahmed Raza"


# --- Appointment tests ---

def test_create_appointment(db):
    apt = Appointment(
        id="apt-001",
        patient_id="pat-001",
        doctor_id=1,
        scheduled_at=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.CONFIRMED,
        urgency=UrgencyLevel.ROUTINE,
        specialty="general",
        complaint="fever and cough",
        booking_channel=BookingChannel.CHAT,
        is_follow_up=False,
        patient_age=30,
        booking_lead_days=2
    )
    db.add(apt)
    db.commit()

    result = db.query(Appointment).filter_by(id="apt-001").first()
    assert result is not None
    assert result.urgency == UrgencyLevel.ROUTINE
    assert result.booking_channel == BookingChannel.CHAT
    assert result.status == AppointmentStatus.CONFIRMED


def test_appointment_patient_relationship(db):
    apt = db.query(Appointment).filter_by(id="apt-001").first()
    assert apt.patient is not None
    assert apt.patient.name == "Ahmed Khan"


def test_appointment_doctor_relationship(db):
    apt = db.query(Appointment).filter_by(id="apt-001").first()
    assert apt.doctor is not None
    assert apt.doctor.specialty == "general"


def test_appointment_ml_columns_nullable(db):
    apt = db.query(Appointment).filter_by(id="apt-001").first()
    assert apt.showed_up is None
    assert apt.actual_wait_minutes is None
    assert apt.actual_start is None
    assert apt.actual_end is None


def test_appointment_defaults(db):
    apt = db.query(Appointment).filter_by(id="apt-001").first()
    assert apt.predicted_wait_min == 0
    assert apt.is_follow_up is False


# --- MLPrediction tests ---

def test_create_ml_prediction(db):
    pred = MLPrediction(
        model_name="wait_time_model",
        model_version="1.0",
        appointment_id="apt-001",
        input_features={"doctor_id": 1, "hour_of_day": 9},
        predicted_value=15.5
    )
    db.add(pred)
    db.commit()

    result = db.query(MLPrediction).first()
    assert result is not None
    assert result.model_name == "wait_time_model"
    assert result.actual_value is None
    assert result.predicted_value == 15.5


def test_ml_prediction_appointment_relationship(db):
    pred = db.query(MLPrediction).first()
    assert pred.appointment is not None
    assert pred.appointment.id == "apt-001"


# --- OpsAlert tests ---

def test_create_ops_alert(db):
    alert = OpsAlert(
        message="Booking surge detected",
        severity="warning"
    )
    db.add(alert)
    db.commit()

    result = db.query(OpsAlert).first()
    assert result is not None
    assert result.severity == "warning"
    assert result.message == "Booking surge detected"


# --- Notification tests ---

def test_create_notification(db):
    notif = Notification(
        patient_id="pat-001",
        appointment_id="apt-001",
        message="Your appointment has been rescheduled",
        notification_type="patient",
        is_mock=True
    )
    db.add(notif)
    db.commit()

    result = db.query(Notification).first()
    assert result is not None
    assert result.notification_type == "patient"
    assert result.is_mock is True


def test_notification_relationships(db):
    notif = db.query(Notification).first()
    assert notif.patient is not None
    assert notif.appointment is not None


# --- DailyLoad tests ---

def test_create_daily_load(db):
    row = DailyLoad(
        doctor_id=1,
        specialty="general",
        scheduled_date=date(2024, 6, 1),  # ← was "2024-06-01"
        hour_of_day=9,
        day_of_week=5,
        week_of_year=22,
        patient_count=4,
        season="normal"
    )
    db.add(row)
    db.commit()

    result = db.query(DailyLoad).first()
    assert result is not None
    assert result.patient_count == 4
    assert result.season == "normal"


def test_daily_load_unique_constraint(db):
    db.add(DailyLoad(
        doctor_id=1,
        specialty="general",
        scheduled_date=date(2024, 6, 1),  # ← was "2024-06-01"
        hour_of_day=9,
        day_of_week=5,
        week_of_year=22,
        patient_count=3
    ))
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_daily_load_doctor_relationship(db):
    row = db.query(DailyLoad).first()
    assert row.doctor is not None
    assert row.doctor.id == 1