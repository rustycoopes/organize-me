from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import BaseOAuth2

from app.core.config import get_settings

GOOGLE_OAUTH_NAME = "google"

# Dropbox has no dedicated client in httpx_oauth (unlike Google/GitHub/etc.), so it's built directly
# on the generic BaseOAuth2 with Dropbox's documented endpoints (developers.dropbox.com/oauth-guide).
DROPBOX_AUTHORIZE_ENDPOINT = "https://www.dropbox.com/oauth2/authorize"
DROPBOX_TOKEN_ENDPOINT = "https://api.dropboxapi.com/oauth2/token"


def get_google_oauth_client() -> GoogleOAuth2:
    # A function (not a module-level value) so get_settings() - and therefore the
    # GOOGLE_OAUTH_CLIENT_ID/SECRET env vars - is resolved lazily per-request, not at import
    # time. Mirrors app.auth.backend.get_jwt_strategy. Overridden in tests with a fake client
    # that never calls Google, per issue #13's "no live Google credentials touched" requirement.
    settings = get_settings()
    return GoogleOAuth2(settings.google_oauth_client_id, settings.google_oauth_client_secret)


def get_dropbox_oauth_client() -> BaseOAuth2[dict[str, str]]:
    # Dropbox's token endpoint doubles as both the code-exchange and refresh-token endpoint (like
    # Google's). It has no revoke endpoint usable via this generic base client - Dropbox revokes
    # whichever token authenticates the /2/auth/token/revoke call itself, not a token passed in the
    # request body - so app.api.v1.storage_dropbox calls that endpoint directly, mirroring how
    # storage_google_drive.py's revoke_google_token bypasses httpx_oauth for the same reason.
    settings = get_settings()
    return BaseOAuth2(
        settings.dropbox_oauth_client_id,
        settings.dropbox_oauth_client_secret,
        DROPBOX_AUTHORIZE_ENDPOINT,
        DROPBOX_TOKEN_ENDPOINT,
        DROPBOX_TOKEN_ENDPOINT,
        name="dropbox",
        token_endpoint_auth_method="client_secret_post",
    )
