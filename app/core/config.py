# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Centralized application configuration.
    Validates environment variables on startup using Pydantic.
    """

    # --- Database Configuration ---
    # Primary database connection string (PostgreSQL)
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # --- Security & Encryption ---
    # Used for AES-GCM encryption of sensitive database fields.
    ENCRYPTION_KEY: str

    # --- Celery Configuration ---
    # Points to the 'redis' service defined in docker-compose
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    
    # --- Redis ---
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # --- Authentication (JWT) ---
    # Used to sign and verify JWT tokens for user login.
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- WhatsApp Integration ---
    # Credentials for the Meta Graph API.
    WHATSAPP_APP_SECRET: str
    WHATSAPP_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    # SECURITY: Required token for webhook verification. No default allowed.
    WHATSAPP_VERIFY_TOKEN: str

    # --- Email Integration (SendGrid) ---
    # Optional: If not provided, email features will be disabled or log-only.
    SENDGRID_API_KEY: Optional[str] = None
    DEFAULT_SENDER_EMAIL: str = "noreply@example.com"

    # --- AI Services (OpenAI) ---
    # Required for RAG (Embeddings). Replaces Cohere.
    OPENAI_API_KEY: Optional[str] = None

    # --- Observability ---
    SENTRY_DSN: Optional[str] = None

    # --- CORS Configuration ---
    # SECURITY: Whitelist of allowed origins. Defaults to empty list (fail-closed).
    # Example: ["https://app.example.com", "https://admin.example.com"]
    BACKEND_CORS_ORIGINS: list[str] = []

    # --- Config Loading ---
    # Load settings from the .env file if available.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

# Instantiate the settings object to be imported by other modules
settings = Settings()