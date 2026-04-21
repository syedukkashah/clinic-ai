from pydantic import BaseModel

class PatientIntakeRequest(BaseModel):
    name: str
    age: int
    symptoms: str
    preferred_time: str

class PatientIntakeResponse(BaseModel):
    extracted_symptoms: str
    urgency: str
    suggested_specialty: str