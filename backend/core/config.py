from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediFlow"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "change-me"
    JWT_SECRET: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = "postgresql+psycopg2://mediflow:mediflow123@localhost:5432/mediflow"
    TEST_DATABASE_URL: str = "sqlite:///./test.db"
    ASYNC_TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    POSTGRES_PASSWORD: str = "mediflow123"
    REDIS_URL: str = "redis://localhost:6379"

    GEMINI_API_KEYS: str = ""
    GROQ_API_KEYS: str = ""
    MISTRAL_API_KEYS: str = ""
    DEEPGRAM_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
