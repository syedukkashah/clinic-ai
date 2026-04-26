from pydantic import BaseModel


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialty: str
    current_load: int
    available_times: list[str]