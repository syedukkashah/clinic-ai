from fastapi import APIRouter
from services.doctor_data import DOCTORS

router = APIRouter()


@router.get("/")
def get_doctors():
    return {"doctors": DOCTORS}