# Clinic AI (MediFlow)

A full-stack demo clinic operations + patient experience app.

- **Backend**: FastAPI (Python) exposing a REST API under `/api/*`
- **Frontend**: Vite + TanStack (React) dashboard and patient UI
- **Database**: PostgreSQL 16 with ~58k appointments, 11 doctors, ~7.9k patients, and ~13.5k daily-load rows
- **Note**: Core features (doctors, appointments, analytics) are **backed by real PostgreSQL data**. Some features (AI agents, ops monitoring, chat/voice) remain intentionally mocked.

---

## What You Can Do

- View doctors, appointments, analytics, ops metrics and activity
- Simulate chat + voice flows via API endpoints
- Login with demo credentials (no database needed)

---

## Repo Structure (important folders)

- `backend/` — FastAPI API server
  - `main.py` — FastAPI app + router registration
  - `main.py` — also hosts portal relay WebSocket at `/ws/portal`
  - `api/routes/` — REST endpoints
  - `agents/` + `services/` — chat/voice “agent” logic (currently mocked/simple)
  - `tests/` — backend tests
- `frontend/` — Vite/TanStack UI
  - `src/lib/api.ts` — API base URL configuration
  - `src/lib/portal.ts` — portal mode (`admin` / `patient`)
  - `src/lib/portalBus.ts` — cross-portal event bus (WebSocket/BroadcastChannel fallback)

---

## Prerequisites (install these first)

### 1) Install Python

- Install **Python 3.12+** (3.13 is fine).
- Make sure `python` works in your terminal:

```bash
python --version
```

### 2) Install Node.js

- Install **Node.js 18+** (Node 20/22 is fine).
- Make sure `node` and `npm` work:

```bash
node -v
npm -v
```

---

## Run The Project (basic step-by-step)

This project uses:

- **Backend API + Portal WebSocket** on **http://127.0.0.1:8000** (WebSocket: `ws://127.0.0.1:8000/ws/portal`)
- **Frontend Admin portal** (separate deployment)
- **Frontend Patient portal** (separate deployment)

For local development you typically run **3 processes** (backend + 2 frontends). You can still run a single combined frontend with `npm run dev`, but the recommended setup is the two-portal structure below.

### One-time setup (from scratch)

From the repo root:

#### Windows (PowerShell)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r backend\requirements.txt

cd frontend
npm ci
cd ..
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r backend/requirements.txt

cd frontend
npm ci
cd ..
```

---

## Run With Docker (dev) — Full Guide

The repo includes `docker-compose.dev.yml` which starts **all services**: Postgres, Redis, Backend, ML Service, Frontend Admin, Frontend Patient, Prometheus, and Grafana.

### Prerequisites

- **Docker Desktop** installed and running (Windows/macOS) or Docker Engine + Compose plugin (Linux)
- At least **4 GB RAM** allocated to Docker (the frontend Vite build is memory-intensive)

### Step 1 — Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and set **at minimum**:

```dotenv
POSTGRES_PASSWORD=changeme123
JWT_SECRET=some-long-random-string
```

Optional (for AI features): `GEMINI_API_KEYS`, `GROQ_API_KEYS`, `TOGETHER_API_KEYS`

### Step 2 — Build & start everything

From the **repo root**:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

> First build takes 3–5 minutes (downloads base images + npm install + Vite build).

### Step 3 — Verify services

| Service | URL |
|---------|-----|
| Backend API | http://127.0.0.1:8000/api/health |
| Backend Swagger Docs | http://127.0.0.1:8000/docs |
| ML Service | http://127.0.0.1:8001/ |
| **Admin Portal** | http://127.0.0.1:5173/ |
| **Patient Portal** | http://127.0.0.1:5174/patient |
| Prometheus | http://127.0.0.1:9090/ |
| Grafana | http://127.0.0.1:3000/ |

### Step 4 — Common operations

**View logs (follow mode):**

```bash
docker compose -f docker-compose.dev.yml logs -f --tail=200
```

**View logs for a specific service:**

```bash
docker compose -f docker-compose.dev.yml logs -f frontend_admin
```

**Stop the stack (keep data):**

```bash
docker compose -f docker-compose.dev.yml down
```

**Stop and wipe all data (Postgres/Grafana volumes):**

```bash
docker compose -f docker-compose.dev.yml down -v
```

**Check container status:**

```bash
docker compose -f docker-compose.dev.yml ps
```

### Rebuild only the frontend containers

If you change frontend code, you don't need to rebuild everything:

```bash
docker compose -f docker-compose.dev.yml up -d --build frontend_admin frontend_patient
```

### Rebuild only the backend

```bash
docker compose -f docker-compose.dev.yml up -d --build backend
```

### Clean up Docker storage

Docker images accumulate over multiple rebuilds. To free space:

```bash
# Remove unused/dangling images
docker image prune -f

# Remove ALL build cache (aggressive — forces full rebuild next time)
docker builder prune -a -f

# Nuclear option: remove everything unused (images, containers, volumes, networks)
docker system prune -a -f
```

### Frontend Docker Architecture

The frontend Dockerfile uses a **multi-stage build**:

1. **Build stage** (`node:22-alpine`):
   - Runs `npm ci` to install dependencies
   - Runs `npm run build:admin` and `npm run build:patient` (Vite builds)
   - Runs `node scripts/generate-index.mjs` to create `index.html` for each portal
   - Prerendering is **disabled** because TanStack Start's SSR server cannot reach the backend API during the Docker build phase
2. **Serve stage** (`nginx:1.27-alpine`):
   - Copies the built static files into nginx
   - The `BUILD_MODE` build arg (`admin` or `patient`) selects which dist to serve
   - nginx uses `try_files $uri $uri/ /index.html` for SPA client-side routing

Key files involved in the Docker build:

| File | Purpose |
|------|---------|
| `frontend/Dockerfile` | Multi-stage build: Node build → nginx serve |
| `frontend/nginx.conf` | SPA-friendly nginx config with gzip |
| `frontend/scripts/generate-index.mjs` | Generates `index.html` from TanStack Start manifest (needed because prerendering is disabled) |
| `frontend/vite.config.ts` | Prerendering disabled (`enabled: false`) to avoid SSR crashes during build |
| `frontend/src/lib/api.ts` | Axios interceptor returns mock data during SSR to prevent build failures |
| `frontend/.dockerignore` | Excludes `node_modules/`, `dist*/`, `.vite/` from build context |
| `backend/.dockerignore` | Excludes local caches from backend build context |
| `docker-compose.dev.yml` | Orchestrates all services with correct `BUILD_MODE` args |

---

## Database Setup (PostgreSQL + Alembic + Seed Data)

The backend uses **PostgreSQL 16** for persistent storage, **Alembic** for schema migrations, and a Python seed script to populate initial data. This section walks through setting up the database from scratch.

### Architecture overview

```
docker-compose.dev.yml
  └─ postgres (port 5432)    ← Docker container running PostgreSQL 16
       └─ database: mediflow
            └─ user: mediflow / password: from POSTGRES_PASSWORD in .env

backend/
  ├─ alembic.ini             ← Alembic config (DB connection URL)
  ├─ db/migrations/versions/ ← Migration files (schema changes)
  ├─ scripts/seed.py         ← Populates tables with CSV data
  └─ scripts/verify_db.py    ← Prints table counts + schema checks
```

### Step 1 — Start only Postgres

You don't need to start all Docker services — just Postgres:

```bash
docker compose -f docker-compose.dev.yml up -d postgres
```

Verify it's running:

```bash
docker compose -f docker-compose.dev.yml ps postgres
```

You should see `STATUS: Up` with port `5432->5432`.

### Step 2 — Create Python virtual environment

From the **repo root**:

#### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install psycopg2-binary python-dotenv pandas numpy
```

> If PowerShell blocks activation, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install psycopg2-binary python-dotenv pandas numpy
```

> **Note:** The `openai-whisper` dependency in `requirements.txt` may fail to build on some machines — this is fine. It's only needed for the voice transcription feature, not for the database setup.

### Step 3 — Configure the database URL

The backend reads `DATABASE_URL` from `backend/.env`. Create it if it doesn't exist:

```dotenv
# backend/.env
DATABASE_URL=postgresql+psycopg2://mediflow:mediflow123@localhost:5432/mediflow
POSTGRES_PASSWORD=mediflow123
JWT_SECRET=supersecretlocalkey123456789
SECRET_KEY=supersecretlocalkey123456789
```

Alembic reads its connection URL from `backend/alembic.ini` (line 4). It should match:

```ini
sqlalchemy.url = postgresql://mediflow:mediflow123@localhost:5432/mediflow
```

> Replace `mediflow123` with whatever value you set for `POSTGRES_PASSWORD` in the root `.env`.

### Step 4 — Run Alembic migrations

From `backend/`:

```bash
python -m alembic upgrade head
```

This creates all tables: `doctors`, `patients`, `appointments`, `daily_load`, `ml_predictions`, `slots`, `notifications`, `ops_alerts`, `predictions`.

### Step 5 — Seed the database

The seed script reads CSV files from `ml_service/data/` and populates the database. It is **idempotent** — running it multiple times won't duplicate data (it skips tables that already have rows).

From `backend/`:

#### Windows (PowerShell)

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts\seed.py
```

> The `PYTHONIOENCODING` setting is required on Windows because the script prints Unicode characters (⏭, ✅) that the default Windows console encoding (cp1252) cannot render.

#### macOS / Linux

```bash
python scripts/seed.py
```

### Step 6 — Verify the database

From `backend/`:

```bash
python scripts/verify_db.py
```

Expected output:

```
============================================================
  DATABASE VERIFICATION
============================================================

  Tables found: 10
    - alembic_version: 1 rows
    - appointments: 58,864 rows
    - daily_load: 13,500 rows
    - doctors: 11 rows
    - ml_predictions: 0 rows
    - notifications: 0 rows
    - ops_alerts: 0 rows
    - patients: 7,939 rows
    - predictions: 0 rows
    - slots: 0 rows

  Enum types:
    urgencylevel:
      - ROUTINE
      - MODERATE
      - URGENT

  Doctor IDs: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
  Doctor ID type: int

============================================================
  Verification complete ✅
============================================================
```

### Expected data summary

| Table | Rows | Source |
|-------|------|--------|
| doctors | 11 | Hardcoded in `seed.py` |
| patients | ~7,939 | Derived from unique `patient_id` in `appointments.csv` |
| appointments | ~58,864 | From `ml_service/data/appointments.csv` |
| daily_load | ~13,500 | From `ml_service/data/daily_load.csv` |
| ml_predictions | 0 | Populated by ML service at runtime |

### Schema rules

- **Urgency enum** (`urgencylevel`): `ROUTINE`, `MODERATE`, `URGENT`
- **Booking channel enum** (`bookingchannel`): `CHAT`, `VOICE_NOTE`, `WEBRTC_CALL`, `TWILIO_CALL`
- **Appointment status enum** (`appointmentstatus`): `PENDING`, `CONFIRMED`, `WAITING`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`
- **Doctor IDs**: Integers 1–11 (not strings)
- **Patient IDs / Appointment IDs**: UUID strings

### Reset the database (start fresh)

If you need to wipe everything and start over:

```bash
# Stop Postgres and delete its volume
docker compose -f docker-compose.dev.yml down -v

# Start Postgres fresh
docker compose -f docker-compose.dev.yml up -d postgres

# Wait ~5 seconds for Postgres to initialize, then re-run migrations + seed
cd backend
python -m alembic upgrade head
python scripts/seed.py
```

---

## Database Integration Architecture

The backend uses a clean **async CRUD layer** (`db/crud.py`) that sits between API routes and the database. All routes call CRUD functions instead of writing inline queries.

### Connection Layer

| File | Purpose |
|------|---------|
| `backend/core/config.py` | Pydantic Settings — single source of truth for `DATABASE_URL` |
| `backend/db/session.py` | Async engine (asyncpg) + sync engine (psycopg2) + session factories |
| `backend/db/models.py` | 10 SQLAlchemy ORM models with enums and relationships |
| `backend/db/crud.py` | Async data-access layer — all DB queries live here |

### Connection Pool Settings

The async engine is configured with production-grade pool settings:

```python
async_engine = create_async_engine(
    ASYNC_URL,
    pool_size=10,       # 10 persistent connections
    max_overflow=20,    # up to 20 additional on burst
    pool_pre_ping=True, # detect stale connections before use
)
```

### DB-Backed Endpoints

These endpoints query PostgreSQL via the CRUD layer:

| Endpoint | CRUD Function | Description |
|----------|--------------|-------------|
| `GET /api/health/db` | `crud.check_db()` | DB connectivity probe + table row counts |
| `GET /api/doctors/` | `crud.get_doctors()` | All doctors with computed dashboard fields |
| `GET /api/doctors/{id}/availability` | `crud.get_doctor_availability()` | Available slots for a doctor |
| `GET /api/appointments/` | `crud.get_appointments()` | Paginated appointments with joined names |
| `POST /api/appointments/` | `crud.create_appointment()` | Insert new appointment |
| `PUT /api/appointments/{id}` | `crud.update_appointment()` | Update appointment fields |
| `DELETE /api/appointments/{id}` | `crud.delete_appointment()` | Delete appointment |
| `GET /api/analytics/overview` | `crud.get_overview_stats()` | Today's totals, queue, avg wait, health |
| `GET /api/analytics/wait-series` | `crud.get_wait_series()` | Hourly average wait times |
| `GET /api/analytics/load-forecast` | `crud.get_load_forecast()` | Hourly actual vs predicted patient load |

### Computed Fields (Option A — Dynamic)

The frontend schemas expect fields like `avatarColor`, `appointmentsToday`, `capacity`, and `status` that don't exist as database columns. These are **computed dynamically** at query time:

- **`avatarColor`** — Assigned from a rotating gradient palette based on doctor ID
- **`appointmentsToday`** — COUNT of today's appointments per doctor
- **`capacity`** — Fixed at 22 (configurable constant)
- **`status`** — Derived: `off` (unavailable), `overloaded` (≥ capacity), `busy` (≥ 60% capacity), `available`

This approach keeps the existing frontend contract intact without requiring schema migrations.

### Verifying DB Connectivity

After starting the backend, hit the health endpoint:

```bash
curl http://127.0.0.1:8000/api/health/db
```

Expected response:

```json
{
  "status": "connected",
  "tables": {
    "doctors": 11,
    "patients": 7939,
    "appointments": 58864,
    "daily_load": 13500,
    "ml_predictions": 0
  }
}
```

### Still-Mocked Routes

These routes intentionally remain mocked (no corresponding DB tables with real data):

| Route File | Endpoints | Reason |
|-----------|-----------|--------|
| `ops.py` | `/api/ops/*` (suggestions, activity, agents, metrics) | AI agent features — no real data |
| `alerts.py` | `/api/alerts/*` | Ops monitoring — no real data |
| `chat.py` | `/api/chat/*` | Chat agent — rule-based stub |
| `scheduling.py` | `/api/schedule/*` | Optimization — stub |

---

### Step A — Start the Backend (FastAPI + Portal WS)

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Confirm:

- Health: http://127.0.0.1:8000/api/health
- Docs: http://127.0.0.1:8000/docs
- Swagger UI: http://127.0.0.1:8000/swagger

To stop: **Ctrl + C**.

### Step B — Start the Admin Portal (Frontend)

In a new terminal:

```bash
cd frontend
npm ci
npm run dev:admin -- --host 127.0.0.1 --port 5173
```

Open:

- Admin portal: http://127.0.0.1:5173/

### Step C — Start the Patient Portal (Frontend)

In a new terminal:

```bash
cd frontend
npm ci
npm run dev:patient -- --host 127.0.0.1 --port 5174
```

Open:

- Patient portal: http://127.0.0.1:5174/patient

To stop any frontend: **Ctrl + C**.

---

## Frontend ↔ Backend Connection (API Base URL)

The frontend uses this logic to find the backend base URL:

- If `VITE_API_BASE_URL` is set, it uses that value
- Otherwise it defaults to: `http://<your-hostname>:8000/api`

This is implemented in: `frontend/src/lib/api.ts`.

### Recommended (explicit) setup

Set:

- `VITE_API_BASE_URL=http://127.0.0.1:8000/api`

How you set it depends on your environment. Common approaches:

- In your terminal session before running the frontend (Windows PowerShell):

```bash
$env:VITE_API_BASE_URL="http://127.0.0.1:8000/api"
npm run dev:admin -- --host 127.0.0.1 --port 5173
```

If you don’t set anything, it should still work as long as your backend is running on port **8000**.

---

## Two-Portal Deployments (Admin + Patient)

The frontend supports two separate deployments via Vite mode:

- **Admin deployment**: `--mode admin`
- **Patient deployment**: `--mode patient`

In these modes, the app redirects so each deployed site stays within its portal:

- Patient mode always routes to `/patient`
- Admin mode routes to `/login` or `/dashboard` depending on auth

### Portal-to-Portal communication

When the portals are deployed on different origins, they communicate through the backend WebSocket relay:

- `ws://<backend-host>:8000/ws/portal?portal=admin|patient`

Events currently used:

- `appointments:changed` → other portal refreshes appointment lists
- `patient:contact` → admin portal shows a toast and refreshes alerts

### Build two separate frontend bundles

From `frontend/`:

```bash
npm run build:admin
npm run build:patient
```

Outputs:

- `frontend/dist-admin/`
- `frontend/dist-patient/`

### Preview locally (production build)

From `frontend/` (pick different ports):

```bash
npm run preview:admin -- --host 127.0.0.1 --port 4173
npm run preview:patient -- --host 127.0.0.1 --port 4174
```

---

## Portal Environment Variables

- `VITE_API_BASE_URL` (both portals) — API base URL, e.g. `http://127.0.0.1:8000/api`
- `VITE_PORTAL_WS_URL` (optional) — override the portal bus WebSocket URL
  - Example: `ws://127.0.0.1:8000/ws/portal?portal={portal}`
- `VITE_ADMIN_PORTAL_URL` (patient portal) — where the “Admin login” button should go (if admin is deployed elsewhere)
  - Example: `http://127.0.0.1:5173/login`
- `VITE_PATIENT_PORTAL_URL` (admin portal, optional) — patient portal URL (if you want to link out)
  - Example: `http://127.0.0.1:5174/patient`

---

## Demo Login Credentials

The backend accepts two demo accounts:

- `admin@mediflow.io` / `demo`
- `staff@mediflow.io` / `demo`

Token endpoint:

- `POST /api/auth/login/access-token` (form-encoded)

---

## API Endpoints (high-level)

You can explore the full list in Swagger:

- http://127.0.0.1:8000/docs

Main groups:

- `GET /api/health` — basic health check
- `GET /api/health/db` — database connectivity check with table counts **(DB-backed)**
- `POST /api/auth/login/access-token` — demo login (returns JWT)
- `GET /api/doctors/` — all doctors with computed dashboard fields **(DB-backed)**
- `GET /api/doctors/{id}/availability` — available time slots for a doctor **(DB-backed)**
- `GET /api/appointments/?limit=50&offset=0` — paginated appointments with joined names **(DB-backed)**
- `POST /api/appointments/` — create a new appointment **(DB-backed)**
- `PUT /api/appointments/{id}` — update appointment fields **(DB-backed)**
- `DELETE /api/appointments/{id}` — delete an appointment **(DB-backed)**
- `POST /api/appointments/book` — booking stub (returns 501 — will connect to scheduling agent)
- `GET /api/analytics/overview` — today's totals, queue size, avg wait, health score **(DB-backed)**
- `GET /api/analytics/wait-series` — hourly wait time chart data **(DB-backed)**
- `GET /api/analytics/load-forecast` — hourly actual vs predicted patient load **(DB-backed)**
- `GET /api/predictions/wait-time` — ML wait time prediction (stub model)
- `GET /api/predictions/load` — ML patient load prediction (stub model)
- `GET /api/alerts/` — list ops alerts (mocked)
- `POST /api/alerts/` — create a new alert (mocked, in-memory)
- `POST /api/alerts/{id}/acknowledge` — acknowledge an alert (mocked)
- `GET /api/ops/suggestions` — AI-generated ops suggestions (mocked)
- `GET /api/ops/activity` — real-time activity feed (mocked)
- `GET /api/ops/agents` — AI agent statuses (mocked)
- `GET /api/ops/metrics` — clinic operational metrics (mocked)
- `POST /api/schedule/optimize` — schedule optimization (stub)
- `POST /api/schedule/reassign` — patient reassignment (stub)
- `POST /api/chat/message` — chat agent (simple rule-based, mocked)
- `POST /api/chat/voice/process` — voice flow (mocked)
- `ws://127.0.0.1:8000/ws/portal?portal=admin|patient` — cross-portal WebSocket relay

---

## Test The Backend (verify endpoints)

From the `backend/` folder:

```bash
python -m pytest -q
```

This project includes a test that:

- Loads `/openapi.json`
- Calls every documented endpoint with a minimal request
- Fails if any endpoint returns a 5xx error

---

## Troubleshooting (common issues)

### 1) Frontend shows `net::ERR_ABORTED http://127.0.0.1:8000/`

This usually means:

- The backend is not running, or
- The frontend (or browser) tried to load the backend root directly

Fix:

- Make sure the backend is started and reachable:
  - http://127.0.0.1:8000/api/health
- Use the API docs for a browser view:
  - http://127.0.0.1:8000/docs

### 2) `vite` is not recognized

That means frontend dependencies are not installed.

Fix:

```bash
cd frontend
npm ci
```

### 3) PowerShell blocks venv activation

If `Activate.ps1` is blocked, run this in the same PowerShell window and try again:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4) Port already in use (8000 / 5173 / 5174)

Either stop the process using the port, or run on a different port:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

```bash
npm run dev:admin -- --host 127.0.0.1 --port 5173
npm run dev:patient -- --host 127.0.0.1 --port 5174
```

### 5) Docker build fails with `exit code: 1` on `npm run build:admin`

This was a known issue caused by TanStack Start's prerendering trying to reach the backend API during the Docker build (when no backend is available).

**Fix already applied in this repo:**

- `frontend/vite.config.ts` has `prerender: { enabled: false }`
- `frontend/scripts/generate-index.mjs` generates `index.html` post-build
- `frontend/src/lib/api.ts` returns mock data during SSR

If the error reappears after modifying these files, ensure prerendering stays disabled and the generate-index script runs after each Vite build.

### 6) Docker frontend shows `403 Forbidden` from nginx

This means nginx can't find `index.html` in its root directory.

**Fix:** The `generate-index.mjs` script must run after each build in the Dockerfile. Check that the Dockerfile has:

```dockerfile
RUN npm run build:admin  && node scripts/generate-index.mjs dist-admin
RUN npm run build:patient && node scripts/generate-index.mjs dist-patient
```

### 7) Docker build is slow / runs out of memory

- Increase Docker Desktop memory allocation to **4 GB+** (Settings → Resources)
- Use selective rebuilds instead of full rebuilds:
  ```bash
  docker compose -f docker-compose.dev.yml up -d --build frontend_admin frontend_patient
  ```
- Clean old build cache: `docker builder prune -a -f`
