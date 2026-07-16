from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    database_url: str
    jwt_secret: str
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str
    # Empty default (rather than a required field) so existing deployments/CI jobs that don't
    # set RESEND_API_KEY yet don't fail Settings construction; ResendEmailSender only needs a
    # real value once forgot-password is actually exercised in a live environment.
    resend_api_key: str = ""
    # Verified custom domain sender (issue #152 - Resend's shared sandbox sender previously
    # used here, onboarding@resend.dev, only delivered to the account owner's own verified
    # address). Override via EMAIL_FROM if needed.
    email_from: str = "OrganizeMe <uploads@organiseme.russcoopersoftware.com>"
    # Enables the test-only Playwright helper endpoints (app.api.v1.internal_e2e). MUST only
    # ever be true on the QA Cloud Run service, never prod - it exposes a way to mint a valid
    # password-reset token for any registered email. Defaults false so those routes return 404
    # everywhere it isn't explicitly switched on.
    e2e_test_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
