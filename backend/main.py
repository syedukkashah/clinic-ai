from fastapi import FastAPI
from backend.api.routes import triage, doctors, appointments, metrics
from backend.core.cors import setup_cors
from backend.core.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Clinic AI DevOps Project")

# Setup CORS
setup_cors(app)

# Include routers
app.include_router(triage.router, prefix="/triage", tags=["Triage"])
app.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
app.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])


@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")

@app.get("/")
def root():
    return {"message": "Clinic AI backend is running"}
