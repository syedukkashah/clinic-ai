from fastapi import APIRouter
from schemas.patient import PatientIntakeRequest, PatientIntakeResponse
from services.triage_agent import analyze_symptoms

router = APIRouter()


@router.post("/", response_model=PatientIntakeResponse)
def triage_patient(data: PatientIntakeRequest):
    result = analyze_symptoms(data.symptoms)

    return PatientIntakeResponse(
        extracted_symptoms=data.symptoms,
        urgency=result["urgency"],
        suggested_specialty=result["specialty"]
    )