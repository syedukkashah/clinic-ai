# MediFlow Split Deployment

This deployment path is optimized for free tiers and small credits. Deploy in this order:

1. Frontend on Vercel.
2. Backend API, Redis, Celery worker, and Celery beat on an AWS EC2 instance.
3. ML service either on the same EC2 instance or later as a Hugging Face Docker Space.
4. Observability stack only after the core product is stable.

## 1. Database

Create a Postgres database on Neon or Supabase.

Backend URL format:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB?sslmode=require
```

ML service URL format:

```env
ML_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB?ssl=require
```

Run migrations from the backend container:

```bash
docker compose -f docker-compose.backend.yml run --rm api alembic upgrade head
```

Seed demo data only when needed:

```bash
docker compose -f docker-compose.backend.yml run --rm api python scripts/seed.py
```

## 2. Backend Host

On the AWS EC2 instance:

```bash
git clone <repo-url> clinic-ai
cd clinic-ai
cp .env.deploy.example .env
```

Fill `.env`, then start the backend tier:

```bash
docker compose -f docker-compose.backend.yml up -d --build redis api celery_worker celery_beat
```

Health checks:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/db
```

Expose the API through a real HTTPS domain such as `https://api.example.com`.

## 3. Frontend

Create two Vercel projects from the `frontend/` directory.

Admin project:

```text
Build Command: npm run deploy:admin
Output Directory: dist-admin/client
```

Patient project:

```text
Build Command: npm run deploy:patient
Output Directory: dist-patient/client
```

Set these env vars in both Vercel projects:

```env
VITE_API_BASE_URL=https://api.example.com/api
VITE_PORTAL_WS_URL=wss://api.example.com/ws/portal
VITE_ALLOW_DEMO_AUTH=false
```

Optional cross-links:

```env
VITE_ADMIN_PORTAL_URL=https://mediflow-admin.vercel.app/login
VITE_PATIENT_PORTAL_URL=https://mediflow-patient.vercel.app/patient
```

Add both Vercel domains to backend `ALLOWED_ORIGINS`.

## 4. ML Service

Run ML on the backend host first:

```bash
docker compose -f docker-compose.backend.yml --profile ml up -d --build ml_service
```

Set backend `.env`:

```env
ML_SERVICE_URL=http://ml_service:8001
```

If deploying to Hugging Face later, create a Docker Space from `ml_service/`, set the same ML env vars, then update backend:

```env
ML_SERVICE_URL=https://<space-subdomain>.hf.space
```

## 5. Defer Until Later

Do not deploy these on day one unless you have spare credits:

- MLflow server
- Prometheus
- Alertmanager
- Grafana

The application can run without the observability stack. ML predictions will be degraded until production models are available through MLflow or bundled fallback artifacts.
