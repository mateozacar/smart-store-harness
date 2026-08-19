"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/smart_store"

    @property
    def async_database_url(self) -> str:
        """Normalize the DATABASE_URL to always use the psycopg (v3) async driver."""
        url = self.database_url
        for old in ("postgresql://", "postgres://", "postgresql+psycopg2://"):
            if url.startswith(old):
                return url.replace(old, "postgresql+psycopg://", 1)
        return url
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = ""


settings = Settings()
