from httpx_oauth.clients.google import GoogleOAuth2

from app.core.config import get_settings

GOOGLE_OAUTH_NAME = "google"


def get_google_oauth_client() -> GoogleOAuth2:
    # A function (not a module-level value) so get_settings() - and therefore the
    # GOOGLE_OAUTH_CLIENT_ID/SECRET env vars - is resolved lazily per-request, not at import
    # time. Mirrors app.auth.backend.get_jwt_strategy. Overridden in tests with a fake client
    # that never calls Google, per issue #13's "no live Google credentials touched" requirement.
    settings = get_settings()
    return GoogleOAuth2(settings.google_oauth_client_id, settings.google_oauth_client_secret)
