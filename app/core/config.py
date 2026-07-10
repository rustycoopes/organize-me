from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    database_url: str
    jwt_secret: str
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str
    # Dropbox OAuth app credentials (Slice 8.1). Empty defaults (like the Resend/Gemini/Twilio
    # keys above) so deploys/CI that don't set them yet don't fail Settings construction -
    # get_dropbox_oauth_client() only needs real values once a user actually connects Dropbox.
    dropbox_oauth_client_id: str = ""
    dropbox_oauth_client_secret: str = ""
    # Empty default (rather than a required field) so existing deployments/CI jobs that don't
    # set RESEND_API_KEY yet don't fail Settings construction; ResendEmailSender only needs a
    # real value once forgot-password is actually exercised in a live environment.
    resend_api_key: str = ""
    # Resend's shared sandbox sender - works without a verified custom domain, but Resend
    # restricts delivery to the account owner's own verified address until one is set up.
    # Swap via EMAIL_FROM once a custom domain is verified.
    email_from: str = "OrganizeMe <onboarding@resend.dev>"
    # Enables the test-only Playwright helper endpoints (app.api.v1.internal_e2e). MUST only
    # ever be true on the QA Cloud Run service, never prod - it exposes a way to mint a valid
    # password-reset token for any registered email. Defaults false so those routes return 404
    # everywhere it isn't explicitly switched on.
    e2e_test_mode: bool = False
    # Fernet key used to encrypt stored storage-provider credentials at rest (see
    # app.core.security). Empty default (like RESEND_API_KEY) so existing deploys/CI that don't
    # set it yet don't fail Settings construction - get_credential_cipher() raises a clear error
    # if it's actually used while unset. Must be a urlsafe-base64 32-byte key
    # (cryptography.fernet.Fernet.generate_key()); wire ENCRYPTION_KEY into QA/prod before the
    # storage-config write paths (issues #46/#47) go live.
    encryption_key: str = ""
    # API key for the Gemini LLM (google-genai SDK), used by the processing pipeline's
    # extraction step (Slice 4). Empty default (like RESEND_API_KEY / ENCRYPTION_KEY) so
    # deploys/CI that don't set it yet don't fail Settings construction - GoogleGeminiClient
    # raises a clear error if it's actually used while unset. Tests never call the live API
    # (they inject FakeGeminiClient), so they don't need a real key. Wire GEMINI_API_KEY into
    # QA/prod before the upload pipeline (issue #52) goes live.
    gemini_api_key: str = ""
    # Base URL for the app, used in notification emails (Slice 7).
    # Defaults to https://organize-me.app for production; override to http://localhost:3000 in dev.
    base_url: str = "https://organize-me.app"
    # Twilio credentials for SMS notifications (Slice 7.2). Empty defaults (like
    # RESEND_API_KEY/GEMINI_API_KEY) so deploys/CI that don't set them yet don't fail Settings
    # construction - TwilioSmsSender raises a clear error if it's actually used while unset.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
