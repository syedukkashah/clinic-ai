from fastapi import APIRouter, HTTPException
from app.schemas.appointment import AppointmentRequest, AppointmentResponse
from app.services.triage_agent import analyze_symptoms
from app.services.doctor_data import DOCTORS
from app.services.scheduling_agent import assign_doctor
from app.services.wait_time_model import predict_wait_time

router = APIRouter()


@router.post("/book", response_model=AppointmentResponse)
def book_appointment(data: AppointmentRequest):
    triage_result = analyze_symptoms(data.symptoms)

    assigned_doctor = assign_doctor(
        specialty=triage_result["specialty"],
        preferred_time=data.preferred_time,
        doctors=DOCTORS
    )

    if "error" in assigned_doctor:
        raise HTTPException(status_code=404, detail=assigned_doctor["error"])

    predicted_wait = predict_wait_time(assigned_doctor["current_load"])

    return AppointmentResponse(
        patient_name=data.name,
        assigned_doctor=assigned_doctor["name"],
        specialty=triage_result["specialty"],
        urgency=triage_result["urgency"],
        appointment_time=data.preferred_time,
        predicted_wait_minutes=predicted_wait
    )