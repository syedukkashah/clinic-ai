from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediFlow"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "change-me"
    JWT_SECRET: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ADMIN_EMAIL: str = "admin@mediflow.io"
    ADMIN_PASSWORD: str = ""
    STAFF_EMAIL: str = "staff@mediflow.io"
    STAFF_PASSWORD: str = ""
    ALLOW_DEMO_AUTH: bool = True

    DATABASE_URL: str = "postgresql+psycopg2://mediflow:mediflow123@localhost:5432/mediflow"
    TEST_DATABASE_URL: str = "sqlite:///./test.db"
    ASYNC_TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    POSTGRES_PASSWORD: str = "mediflow123"
    REDIS_URL: str = "redis://localhost:6379"
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:5174"
    )
    PROMETHEUS_URL: str = "http://prometheus:9090"
    ALERTMANAGER_WEBHOOK_TOKEN: str = ""   # empty = no auth check (dev mode)
    INTERNAL_SECRET: str = "mediflow-internal-secret"
    EXPECTED_CELERY_WORKERS: list[str] = []  # e.g. ["celery@worker1"]

    GEMINI_API_KEYS: str = ""
    GROQ_API_KEYS: str = ""
    MISTRAL_API_KEYS: str = ""
    TOGETHER_API_KEYS: str = ""
    DEEPGRAM_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    OPENROUTER_API_KEYS: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
