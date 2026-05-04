import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from api.routes import (
    alerts,
    analytics,
    appointments,
    auth,
    chat,
    doctors,
    ops,
    predictions,
    scheduling,
)

app = FastAPI(
    title="MediFlow API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

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
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
    )


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


class PortalHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._clients: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, portal: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[websocket] = portal

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(websocket, None)

    async def broadcast(self, message: str, *, sender: WebSocket) -> None:
        async with self._lock:
            clients = list(self._clients.keys())

        for ws in clients:
            if ws is sender:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                pass


portal_hub = PortalHub()


@app.websocket("/ws/portal")
async def ws_portal(websocket: WebSocket):
    portal = websocket.query_params.get("portal", "unknown")
    await portal_hub.connect(websocket, portal)

    try:
        while True:
            msg = await websocket.receive_text()
            await portal_hub.broadcast(msg, sender=websocket)
    except WebSocketDisconnect:
        await portal_hub.disconnect(websocket)