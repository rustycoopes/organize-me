import pytest

from app.core.config import Settings


def test_settings_reads_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI has no .env.local file - DATABASE_URL must come from a real env var alone."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com:5432/postgres")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_url == "postgresql://user:pass@example.com:5432/postgres"


def test_settings_reads_jwt_secret_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com:5432/postgres")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.jwt_secret == "test-secret"
