from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from organizeme_chrome.static_paths import static_mount_path

# Imported first, deliberately - configures organizeme_chrome's registry source (see
# app/core/registry.py's module docstring) before any router module below can call
# organizeme_chrome.get_app()/list_apps() at its own module-import time. app/pages/app_shell.py
# is the one call site that genuinely needs this: it derives its placeholder routes'
# paths/labels from get_app("organizeme").nav at *import* time (FastAPI routes must exist before
# the app starts serving, so this can't be deferred to per-request the way app/pages/settings.py's
# equivalent lookup now is). tests/test_registry_wiring.py asserts this ordering actually holds.
from app.core import registry as _registry  # noqa: F401
from app.api.internal.registry import router as internal_registry_router
from app.api.v1.auth import router as auth_router
from app.api.v1.internal_e2e import router as internal_e2e_router
from app.api.v1.users import router as users_router
from app.pages.app_shell import router as app_shell_pages_router
from app.pages.auth import router as auth_pages_router
from app.pages.landing import router as landing_pages_router
from app.pages.profile import router as profile_pages_router
from app.pages.settings import router as settings_pages_router

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Imported here, not at module level, so importing app.main (e.g. for /health tests that
    # never touch the DB) doesn't force DATABASE_URL/Settings to be resolved at import time.
    from app.db.session import get_engine

    await get_engine().dispose()


app = FastAPI(title="OrganizeMe", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# static-asset-routing (organize-me#255): organizeme_chrome's shared chrome_base.html (chrome-v0.18.0+)
# unconditionally links its stylesheet via the CHROME_STATIC_PREFIX Jinja global that
# register_chrome(app_service_name="organizeme") (app/core/templating.py) sets to
# static_mount_path("organizeme") - it has no way to know this particular consumer is the Host,
# so the Host's own authenticated pages need this prefixed mount too, even though the Host's own
# bare /static/* mount above never goes away (unlike every other hosted app's one-release dual
# mount, docs/adr/static-asset-routing-mount-transition.md - the Host was never part of the
# routing ambiguity that ADR's transition exists for, so there's no follow-up removal here).
app.mount(
    static_mount_path("organizeme"), StaticFiles(directory=BASE_DIR / "static"), name="static-prefixed"
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(internal_registry_router)
# Always mounted but gated by the E2E_TEST_MODE flag (404 + hidden from schema when off) - see
# app.api.v1.internal_e2e. Safe to include unconditionally; it does nothing unless QA opts in.
app.include_router(internal_e2e_router)
app.include_router(auth_pages_router)
app.include_router(profile_pages_router)
app.include_router(settings_pages_router)
app.include_router(app_shell_pages_router)
app.include_router(landing_pages_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
