from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
<<<<<<< HEAD
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from api.routes import alerts, analytics, appointments, auth, chat, doctors, ops, predictions, scheduling

app = FastAPI(title="MediFlow API", version="1.0.0", docs_url=None, redoc_url=None)
=======

from api.routes import alerts, analytics, appointments, auth, chat, doctors, ops, predictions, scheduling

app = FastAPI(title="MediFlow API", version="1.0.0")
>>>>>>> origin/dev

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


<<<<<<< HEAD
@app.get("/docs", include_in_schema=False)
def docs_landing():
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MediFlow API</title>
  </head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; line-height: 1.5;">
    <h1 style="margin: 0 0 8px;">MediFlow API</h1>
    <p style="margin: 0 0 16px;">API links:</p>
    <ul>
      <li><a href="/api/health">Health</a></li>
      <li><a href="/openapi.json">OpenAPI JSON</a></li>
      <li><a href="/swagger">Swagger UI</a></li>
    </ul>
  </body>
</html>
""".strip()
    )


@app.get("/swagger", include_in_schema=False)
def swagger_ui():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI")


=======
>>>>>>> origin/dev
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}
