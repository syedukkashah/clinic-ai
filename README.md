# Clinic AI (MediFlow)

A full-stack demo clinic operations + patient experience app.

- **Backend**: FastAPI (Python) exposing a REST API under `/api/*`
- **Frontend**: Vite + TanStack (React) dashboard and patient UI
- **Note**: Many features are intentionally **mocked/in-memory** to make the project easy to run locally (no external services required by default).

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

- `GET /api/health` — health check
- `POST /api/auth/login/access-token` — demo login (returns JWT)
- `GET /api/doctors/` and `GET /api/doctors/{id}/availability` — doctors data (mocked)
- `GET /api/appointments/`, `POST /api/appointments/`, `PUT /api/appointments/{id}`, `DELETE /api/appointments/{id}` — appointment CRUD (in-memory)
- `GET /api/analytics/*` — overview and charts (mocked)
- `GET /api/ops/*` — ops suggestions, activity feed, agents, metrics (mocked)
- `POST /api/chat/message` — chat agent (simple rule-based)
- `POST /api/chat/voice/process` — voice flow (mocked)

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
