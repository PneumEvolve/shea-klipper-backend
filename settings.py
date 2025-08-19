# settings.py  (Pydantic v2)
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # env
    ENV: str = Field(default="dev")
    DEBUG: bool = True
    SAFE_MODE: bool = False

    # DB
    DATABASE_URL: str

    # feature flags
    ENABLE_STRIPE: bool = False
    ENABLE_TRANSCRIBE: bool = False
    ENABLE_SUMMARY: bool = False

    # misc keys (add any others you actually use)
    OPENAI_API_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    BREVO_API_KEY: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    EMAIL_HOST: str = "smtp-relay.brevo.com"
    EMAIL_PORT: int = 587
    EMAIL_USER: Optional[str] = None
    EMAIL_PASS: Optional[str] = None
    FRONTEND_URL: Optional[str] = None
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None
    NGROK_OLLAMA_URL: Optional[str] = None
    RECAPTCHA_SECRET: Optional[str] = None  # <-- you had this in env

    # pydantic-settings config
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).with_name(".env")),
        case_sensitive=True,
        extra="ignore",               # <-- tolerate unknown env vars
    )

settings = Settings()