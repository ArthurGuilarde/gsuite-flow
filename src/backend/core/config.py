import os
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
FRONTEND_DIR = BASE_DIR / "src/frontend"


def is_loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ip_address(host or "").is_loopback
    except ValueError:
        return False


def safe_public_address(public_url: str) -> str:
    """Return the configured origin without userinfo, query parameters, or fragments."""
    parsed = urlparse(public_url)
    host = parsed.hostname or "unknown"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        port = ""
    return f"{parsed.scheme}://{host}{port}"


class Settings(BaseSettings):
    APP_PROFILE: Literal["dev", "integrated", "production", "direct"] = "direct"
    PROJECT_NAME: str = "Guilarde Suite"
    APP_ID: str = "suite-example"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["development", "production"] = "development"
    AUTH_MODE: Literal["oidc", "local"] = "oidc"
    HOST: str = "127.0.0.1"
    PORT: int = Field(default=8000, ge=1, le=65535)
    DEBUG: bool = False
    PUBLIC_URL: str = "http://127.0.0.1:8000"
    DATABASE_URL: str = "sqlite:///./.local/dev.sqlite3"
    MIGRATION_DATABASE_URL: str | None = None
    OIDC_ISSUER: str = "https://auth.guilarde.com/application/o/suite-example/"
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_AUDIENCE: str = "suite-example"
    CORE_URL: str = "https://core.guilarde.com"
    SESSION_ENCRYPTION_KEY: str = ""
    SESSION_COOKIE: str = "guilarde_session"
    SESSION_TTL_SECONDS: int = Field(default=28800, ge=300, le=86400)
    COOKIE_SECURE: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_API_PER_MINUTE: int = 120
    MAX_REQUEST_SIZE_BYTES: int = 2 * 1024 * 1024
    model_config = SettingsConfigDict(
        env_file=os.environ.get("APP_ENV_FILE", ".env"), case_sensitive=True, extra="ignore", env_file_encoding="utf-8"
    )

    @model_validator(mode="after")
    def validate_config(self):
        postgres = self.DATABASE_URL.startswith("postgresql+psycopg://")
        sqlite = self.DATABASE_URL.startswith(("sqlite:///", "sqlite+pysqlite:///"))
        if not (postgres or sqlite):
            raise ValueError("Use SQLite in development or PostgreSQL with psycopg")
        if self.MIGRATION_DATABASE_URL:
            migration_postgres = self.MIGRATION_DATABASE_URL.startswith("postgresql+psycopg://")
            migration_sqlite = self.MIGRATION_DATABASE_URL.startswith(("sqlite:///", "sqlite+pysqlite:///"))
            if (postgres and not migration_postgres) or (sqlite and not migration_sqlite):
                raise ValueError("Migration and runtime databases must use the same backend")
        if self.AUTH_MODE == "local":
            if not sqlite:
                raise ValueError("Local authentication requires a SQLite development database")
            if self.ENVIRONMENT != "development":
                raise ValueError("Local authentication is development-only")
            url = urlparse(self.PUBLIC_URL)
            if not is_loopback(self.HOST) or not is_loopback(url.hostname) or url.scheme != "http":
                raise ValueError("Local authentication requires an HTTP loopback address")
        if self.ENVIRONMENT == "production":
            if not postgres or self.AUTH_MODE != "oidc":
                raise ValueError("Production requires PostgreSQL and OIDC")
            if self.DEBUG:
                raise ValueError("Production cannot enable debug/reload")
            for endpoint in [self.PUBLIC_URL, self.OIDC_ISSUER, self.CORE_URL]:
                if urlparse(endpoint).scheme != "https":
                    raise ValueError("Production endpoints require HTTPS")
            if not self.COOKIE_SECURE or not self.OIDC_CLIENT_ID or not self.OIDC_CLIENT_SECRET:
                raise ValueError("Production requires secure cookies and OIDC credentials")
            if not self.SESSION_ENCRYPTION_KEY:
                raise ValueError("Production requires a persistent session encryption key")
        if self.SESSION_ENCRYPTION_KEY:
            Fernet(self.SESSION_ENCRYPTION_KEY.encode())
        return self


settings = Settings()
