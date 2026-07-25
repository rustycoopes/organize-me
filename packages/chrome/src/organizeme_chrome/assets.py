"""Cache-busting for the compiled stylesheet - see docs/adr/chrome-static-asset-cache-busting.md.

Each consuming service serves the compiled `app.css` from a fixed path (`/static/css/app.css`,
scripts/build_css.py in every consuming repo) with no fingerprint in the filename, so a shared
Load Balancer/CDN layer in front of Cloud Run can keep serving a pre-deploy copy indefinitely -
a real deploy can update every dynamically-rendered page instantly while the stylesheet a visitor
receives (even after a hard refresh, since an intermediate cache - not the browser - is what's
stale) still reflects the previous release.
"""

import hashlib
from pathlib import Path

# Every consuming repo's own scripts/build_css.py writes here, and every consuming repo's own
# process (uvicorn locally, the Dockerfile's WORKDIR /app + CMD in production) runs with the repo
# root as cwd - the same relative layout `register_chrome()`'s own caller lives in, so this
# resolves correctly without needing the caller to pass its own static directory in.
_COMPILED_CSS_PATH = Path("app/static/css/app.css")


def chrome_asset_version() -> str:
    """A short hash of the calling service's own compiled `app.css`, appended as `?v=...` to its
    URL so any cache keying on the full URL (not just headers) is guaranteed to miss whenever that
    file's actual content changes - whether from a chrome-level change or a change local to that
    one service's own templates - regardless of what Cache-Control the previous deploy sent.

    Computed once per process, when `register_chrome()` runs at Jinja-environment setup time -
    after the compiled CSS already exists in its final on-disk form (a separate build step, both
    locally and in the Docker multi-stage build), so this always reflects what's actually being
    served, not a value someone has to remember to bump. Falls back to a fixed placeholder if the
    file isn't present (e.g. this package's own test suite, which has no app/static tree at all)
    rather than raising - the cache-busting value doesn't need to be meaningful there, only
    present and stable within that process's lifetime.
    """
    try:
        data = _COMPILED_CSS_PATH.read_bytes()
    except FileNotFoundError:
        return "dev"
    return hashlib.sha256(data).hexdigest()[:12]
