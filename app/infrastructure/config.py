"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.db.dsn import normalize_database_url


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/smart_store"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = ""

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL normalized to the psycopg v3 driver."""
        return normalize_database_url(self.database_url)


settings = Settings()
