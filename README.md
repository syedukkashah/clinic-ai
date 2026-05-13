# MediFlow

<p align="center">
  <a href="https://clinic-ai-patient.vercel.app/patient">
    <img alt="Deployed Site" src="https://img.shields.io/badge/Deployed%20Site-Visit%20MediFlow-00C7D9?style=for-the-badge&logo=vercel&logoColor=white">
  </a>
  <a href="#">
    <img alt="Demo" src="https://img.shields.io/badge/Demo-Watch%20Demo-6C63FF?style=for-the-badge&logo=youtube&logoColor=white">
  </a>
  <a href="#">
    <img alt="Pitch Deck" src="https://img.shields.io/badge/Pitch%20Deck-View%20Deck-111827?style=for-the-badge&logo=googleslides&logoColor=white">
  </a>
</p>

MediFlow is an AI-powered clinic operations platform that connects patient support, appointment booking, clinical operations, voice automation, predictive analytics, and production monitoring into one integrated system.

The project was built as a realistic end-to-end healthcare operations stack: patients can chat or speak with an AI assistant, book appointments, ask clinic questions, and contact support, while clinic staff get an operational dashboard for appointments, scheduling, analytics, alerts, model health, and automation.

## What We Built

MediFlow includes a patient-facing AI assistant and an admin-facing clinic operations dashboard backed by a production-ready FastAPI service. The assistant can answer clinic questions through RAG, guide patients through appointment booking, remember conversation context, resolve doctor and specialty intent, check availability, and create bookings in the database.

The platform supports both text and voice workflows. Voice requests use speech-to-text, agent reasoning, text-to-speech, and WebSocket streaming so the assistant can behave like a real clinic call agent rather than a static chatbot. A Twilio voice path is also included for phone-call based interactions.

On the admin side, MediFlow provides appointment visibility, scheduling intelligence, operational metrics, alerts, AI operations monitoring, and ML-backed predictions for wait time and patient load. The system is designed around real production concerns: background jobs, service health, observability, migrations, environment separation, deployment automation, and graceful failure handling.

## Core Capabilities

- AI appointment booking with structured tool execution and database verification.
- RAG-based answers for clinic policies, doctor profiles, visiting guidelines, timings, and FAQs.
- Real-time voice assistant using browser audio streaming, Deepgram STT, LLM reasoning, and TTS playback.
- Twilio voice webhook support for phone-based clinic assistance.
- Redis-backed session memory for chat, voice, and booking state.
- PostgreSQL data layer with Alembic migrations and production-oriented configuration.
- Admin dashboard for clinic activity, scheduling, analytics, alerts, and operational insight.
- ML service for wait-time and patient-load prediction.
- Automated background workers for scheduling checks, prediction resolution, drift detection, retraining, and ops monitoring.

## AI Architecture

MediFlow uses a multi-agent backend instead of a single prompt-only chatbot. The orchestrator separates informational queries from operational booking tasks, routing each request to the right path.

The booking agent uses a guarded ReAct-style workflow with explicit tools for doctor lookup, availability checks, appointment creation, and confirmation. It is designed to avoid fake booking confirmations by verifying database writes before telling the patient an appointment is booked.

The RAG service uses clinic documents indexed into ChromaDB so informational answers are grounded in clinic-specific knowledge rather than generic model output. The voice path shares the same agent logic as chat, keeping behavior consistent across channels.

## Tools And Technologies

- **Frontend:** React, Vite, TanStack Router, TypeScript, Tailwind CSS, shadcn/Radix-style UI primitives.
- **Backend:** FastAPI, SQLAlchemy, Alembic, Pydantic, async Python services.
- **Database:** PostgreSQL via Neon-compatible production configuration.
- **Realtime And Memory:** Redis, WebSockets, browser media APIs.
- **AI And Voice:** Gemini, Groq, Together/OpenRouter-style LLM routing, Deepgram Nova STT, Deepgram Aura TTS, Groq Whisper fallback, Twilio voice webhooks.
- **RAG:** ChromaDB, clinic document ingestion, deterministic fallback embeddings for constrained deployment environments.
- **Background Jobs:** Celery workers and Celery Beat.
- **ML:** scikit-learn/XGBoost-style pipelines, MLflow tracking and model registry.
- **Infrastructure:** Docker, Docker Compose, Caddy reverse proxy, AWS EC2, Vercel frontend deployment, GitHub Actions.

## DevOps

MediFlow was prepared for split free-tier deployment: frontend on Vercel, backend services on EC2, managed PostgreSQL on Neon, Redis inside the backend stack, and optional ML service deployment either alongside the backend or separately.

The backend is containerized with Docker Compose and includes separate services for the API, Redis, Celery worker, Celery beat, and optional ML workloads. GitHub Actions deploys the backend automatically on pushes to `main`, pulls the latest code on EC2, rebuilds the stack, runs migrations, refreshes RAG ingestion, and keeps the deployment reproducible.

Production hardening includes environment templates, CORS configuration for deployed frontend origins, HTTPS through Caddy, database migration automation, health checks, isolated secrets, and recovery-friendly deployment documentation.

## MLOps

The ML layer predicts operational signals such as clinic wait time and patient load. Predictions are logged, resolved against actual outcomes, monitored for drift, and used to trigger retraining workflows.

MLflow is used for experiment tracking, metric logging, model registry behavior, and champion/challenger promotion logic. Celery schedules model maintenance tasks, while retraining and reload endpoints allow the ML service to refresh production models without treating ML as an offline-only notebook workflow.

The result is a practical MLOps loop: prediction, logging, actual-value resolution, drift detection, retraining, model comparison, promotion, and service reload.

## AIOps

MediFlow includes an Ops Monitor Agent that acts as the AIOps layer for the clinic stack. It watches operational signals such as API health, Celery worker availability, model drift, booking volume, latency, STT/TTS degradation, and scheduling pressure.

The AIOps agent can reason over incidents, classify severity, trigger alerts, suggest schedule adjustments, initiate retraining flows, and detect when critical background infrastructure is down. This turns the system from a passive dashboard into an active operations assistant.

## Why It Matters

MediFlow is more than a demo chatbot. It combines AI agents, RAG, voice automation, database-backed workflows, production deployment, background automation, MLOps, and AIOps into a single healthcare operations product.

It demonstrates how modern AI systems can move from conversation to action: answering patients, booking appointments, supporting staff, monitoring themselves, and improving operational decisions over time.
