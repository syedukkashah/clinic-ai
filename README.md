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
  - `api/routes/` — REST endpoints
  - `agents/` + `services/` — chat/voice “agent” logic (currently mocked/simple)
  - `tests/` — backend tests
- `frontend/` — Vite/TanStack UI
  - `src/lib/api.ts` — API base URL configuration

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

You will run **two** servers:

- Backend on **http://127.0.0.1:8000**
- Frontend on **http://127.0.0.1:5173**

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

### Step A — Start the Backend (FastAPI)

1) Open a terminal and go to the backend folder (recommended):

```bash
cd backend
```

2) Install Python dependencies (skip if you did the one-time setup above):

```bash
python -m pip install -r requirements.txt
```

3) Start the API server:

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

4) Confirm it’s running:

- Root: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/api/health
- Swagger docs: http://127.0.0.1:8000/docs

To stop the backend, press **Ctrl + C** in that terminal.

#### Alternative: start backend from repo root (no `cd backend`)

```bash
python -m uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### Step B — Start the Frontend (Vite)

1) Open a second terminal and go to the frontend folder:

```bash
cd frontend
```

2) Install Node dependencies (recommended):

```bash
npm ci
```

3) Start the dev server:

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

4) Open the UI:

- http://127.0.0.1:5173/

To stop the frontend, press **Ctrl + C** in that terminal.

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
npm run dev -- --host 127.0.0.1 --port 5173
```

If you don’t set anything, it should still work as long as your backend is running on port **8000**.

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

### 4) Port already in use (8000 or 5173)

Either stop the process using the port, or run on a different port:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

```bash
npm run dev -- --host 127.0.0.1 --port 5174
```
