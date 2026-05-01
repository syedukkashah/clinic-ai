from pydantic import BaseModel


class AppointmentRequest(BaseModel):
    name: str
    age: int
    symptoms: str
    preferred_time: str


class AppointmentResponse(BaseModel):
    patient_name: str
    assigned_doctor: str
    specialty: str
    urgency: str
    appointment_time: str
    predicted_wait_minutes: int