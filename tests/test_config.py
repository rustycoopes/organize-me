import pytest

from app.core.config import Settings


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.com:5432/postgres")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"
    )


def test_settings_reads_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI has no .env.local file - DATABASE_URL must come from a real env var alone."""
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_url == "postgresql://user:pass@example.com:5432/postgres"


def test_settings_reads_jwt_secret_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.jwt_secret == "test-secret"


def test_settings_reads_google_oauth_client_id_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.google_oauth_client_id == "test-client-id"
