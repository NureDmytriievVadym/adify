from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADIFY_", extra="ignore")

    app_name: str = "Adify API"
    debug: bool = False
    database_url: str = "postgresql+psycopg://adify:adify-local-only@localhost:5432/adify"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Local development only; every deployed environment must set its own secret.
    jwt_secret: str = "adify-local-only-jwt-secret-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    refresh_cookie_secure: bool = False
    # Local disk for listing attachments; a deployment should mount durable storage here.
    storage_dir: str = "storage"
    max_attachment_bytes: int = 10 * 1024 * 1024
    max_attachments: int = 5
    # FR-019: a listing stops taking orders this many days after it is published.
    listing_lifetime_days: int = 30
    # The demo-data CLI is opt-in so it cannot accidentally run against a shared database.
    allow_seed: bool = False
    # Mail goes to a local Mailpit by default; Gmail is smtp.gmail.com:587 with STARTTLS
    # and a Google Workspace app password (SW-002).
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_starttls: bool = False
    smtp_username: str | None = None
    smtp_password: str | None = None
    mail_from: str = "Adify <no-reply@adify.local>"
    web_base_url: str = "http://localhost:5173"
    verification_code_minutes: int = 15
    verification_max_attempts: int = 5
    verification_resend_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
