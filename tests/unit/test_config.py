"""Unit tests for application configuration."""

import pytest

from app.infrastructure.config import Settings


def test_settings_defaults() -> None:
    """Settings loads with sensible defaults when no env vars are set."""
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"


def test_settings_env_override() -> None:
    """Settings reads from environment variables."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("APP_ENV", "staging")
        mp.setenv("LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.app_env == "staging"
        assert settings.log_level == "DEBUG"
