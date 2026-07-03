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
    # Resend's shared sandbox sender - works without a verified custom domain, but Resend
    # restricts delivery to the account owner's own verified address until one is set up.
    # Swap via EMAIL_FROM once a custom domain is verified.
    email_from: str = "OrganizeMe <onboarding@resend.dev>"
    # Fernet key used to encrypt stored storage-provider credentials at rest (see
    # app.core.security). Empty default (like RESEND_API_KEY) so existing deploys/CI that don't
    # set it yet don't fail Settings construction - get_credential_cipher() raises a clear error
    # if it's actually used while unset. Must be a urlsafe-base64 32-byte key
    # (cryptography.fernet.Fernet.generate_key()); wire ENCRYPTION_KEY into QA/prod before the
    # storage-config write paths (issues #46/#47) go live.
    encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
