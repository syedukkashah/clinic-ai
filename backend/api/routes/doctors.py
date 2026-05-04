from fastapi import APIRouter
from backend.services.doctor_data import DOCTORS

router = APIRouter()


@router.get("/")
def get_doctors():
    return {"doctors": DOCTORS}