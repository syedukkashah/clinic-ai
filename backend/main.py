from fastapi import FastAPI
from api.routes import triage, doctors, appointments, metrics

app = FastAPI(title="Clinic AI DevOps Project")

app.include_router(triage.router, prefix="/triage", tags=["Triage"])
app.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
app.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])


@app.get("/")
def root():
    return {"message": "Clinic AI backend is running"}