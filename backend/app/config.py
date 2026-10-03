from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Student Assessment & Analytics Platform"
    environment: str = "development"  # development | production | test

    # MySQL in production, e.g. mysql+pymysql://user:pass@host:3306/saap?charset=utf8mb4
    database_url: str = f"sqlite:///{BASE_DIR / 'saap.db'}"

    jwt_secret: str = "change-me-in-production-use-a-64-char-random-string"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # comma-separated in the environment, e.g. CORS_ORIGINS=https://saap.college.edu,https://admin.college.edu
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Login throttling: max failed attempts per (email, ip) inside the window
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    model_dir: Path = BASE_DIR / "ml_models"
    max_upload_bytes: int = 5 * 1024 * 1024

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_db_url(cls, v):
        # Render / Heroku style URLs -> SQLAlchemy psycopg3 driver
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return "postgresql+psycopg://" + v[len("postgres://"):]
            if v.startswith("postgresql://"):
                return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.strip("[]").replace('"', "").split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.jwt_secret.startswith("change-me"):
        raise RuntimeError("JWT_SECRET must be set to a strong random value in production")
    s.model_dir.mkdir(parents=True, exist_ok=True)
    return s
