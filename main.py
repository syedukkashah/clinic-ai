import time
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from metrics import (
    record_booking,
    record_llm_call,
    set_key_pool
)

app = FastAPI(title="MediFlow API")

Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
async def startup_event():
    set_key_pool("OpenAI", 5)
    set_key_pool("Anthropic", 3)
    set_key_pool("Azure", 10)

class BookingRequest(BaseModel):
    clinic_id: str
    status: str

@app.post("/bookings")
async def create_booking(booking: BookingRequest):
    record_booking(booking.clinic_id, booking.status)
    return {"message": "Booking recorded"}

class LLMRequest(BaseModel):
    provider: str
    prompt: str

@app.post("/llm/generate")
async def generate_llm(req: LLMRequest):
    start_time = time.time()
    # Simulate processing
    time.sleep(0.2)
    duration = time.time() - start_time
    record_llm_call(req.provider, "success", duration)
    return {"response": "Generated text"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
