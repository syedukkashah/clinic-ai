from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, analytics, appointments, auth, chat, doctors, ops, predictions, scheduling

app = FastAPI(title="MediFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(doctors.router, prefix="/api/doctors", tags=["Doctors"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat & Voice"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Ops Monitor"])
app.include_router(ops.router, prefix="/api/ops", tags=["Ops"])
app.include_router(scheduling.router, prefix="/api/schedule", tags=["Scheduling"])


@app.get("/", include_in_schema=False)
def root():
    return {"name": "MediFlow API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}
