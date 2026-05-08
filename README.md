# Clinic AI (MediFlow) - Production Integration

A full-stack, AI-driven clinic operations and patient experience platform.

- **Backend**: FastAPI (Python 3.12+) with integrated AI Agents and WebSocket relay.
- **Frontend**: Vite + TanStack (React) featuring a high-performance Admin Dashboard and Patient Portal.
- **AI Core**: Multi-provider LLM routing (Gemini 1.5, Groq Llama 3.1, Together AI) with fallback logic.
- **Voice Stack**: Deepgram Nova-3 / Groq Whisper for STT and Deepgram Aura-2 for TTS.
- **Database**: PostgreSQL 16 with 10 tables, managed via Alembic migrations.
- **Real-time**: Redis 7 for session memory and portal-to-portal event broadcasting.

---

## 🚀 Quick Start (Docker Dev)

The recommended way to run MediFlow is via Docker Compose, which orchestrates all 8 services.

### 1. Configure Environment
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Fill in your API keys (Gemini, Groq, Together, Deepgram, Twilio).

### 2. Launch the Stack
```bash
docker compose -f docker-compose.dev.yml up -d --build
```

### 3. Access the Portals
- **Admin Dashboard**: [http://localhost:5173](http://localhost:5173) (Login: `admin@mediflow.io` / `demo`)
- **Patient Portal**: [http://localhost:5174/patient](http://localhost:5174/patient)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Advanced Operations

### Rebuilding Specific Components
If you modify frontend code:
```bash
docker compose -f docker-compose.dev.yml up -d --build frontend_admin frontend_patient
```
If you modify backend/agent logic:
```bash
docker compose -f docker-compose.dev.yml up -d --build backend
```

### Database Migrations
MediFlow uses Alembic for schema management. To apply new migrations:
```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### Testing the AI Agents
You can test the Booking Agent directly from the terminal within the container:
```bash
docker compose -f docker-compose.dev.yml exec backend python scripts/debug_agent.py
```

---

## 🔒 Security & Best Practices
- **Secrets**: Never commit `.env` files. They are ignored by `.gitignore`.
- **Docker Optimization**: `.dockerignore` ensures that local `node_modules` and virtual environments do not bloat the Docker build context.
- **LLM Fallback**: The `LLM_Router` automatically cycles through providers if rate limits (429) or failures (500) occur.

---

## 🧠 MLOps & MLflow Integration

MediFlow includes a complete, automated Machine Learning pipeline for predicting clinic wait times and patient loads.

### MLflow UI
The MLflow Tracking Server and Model Registry are accessible at:
👉 **[http://localhost:5000](http://localhost:5000)**

### Automated MLOps Lifecycle

1. **Prediction Logging**: The `ml_service` logs every prediction (features and output) to the `ml_predictions` PostgreSQL table.
2. **Resolver Task**: The `resolve_predictions` Celery beat task runs hourly, matching actual wait times from completed appointments and updating the `ml_predictions` table.
3. **Drift Detection**: The `drift_detector` Celery task runs daily, calculating KL divergence between recent actuals and a synthetic baseline.
4. **Triggered Retraining**: If KL Divergence exceeds the threshold (`> 0.1`), the backend triggers the `ml_service` via its `/retrain` endpoint.
5. **Champion / Challenger**: During retraining, models are evaluated against the current Production model's RMSE/MAE. If the challenger model beats the champion, it is automatically transitioned to the "Production" stage in MLflow.
6. **Hot Reload**: The `ml_service` `/retrain` endpoint triggers a dynamic reload of the latest Production models without dropping container traffic.

### Celery Schedules
Scheduled operations are managed via Celery Beat (defined in `backend/celeryconfig.py`):
- `check-schedule-every-30-min`: Reassigns doctors based on real-time loads.
- `resolve-predictions-hourly`: Fills in `actual_value` for predictions.
- `daily-drift-check`: Detects KL divergence.
- `weekly-retrain-wait-time` / `weekly-retrain-patient-load`: Scheduled retraining runs (Sundays at 2AM/3AM).
