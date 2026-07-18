"""Registry-decoupling (organize-me#218): guards the import-ordering invariant app/main.py and
app/core/registry.py's docstrings both call out - if `app/core/registry` were ever imported after
`app/pages/app_shell` (whose placeholder routes are derived from `get_app("organizeme").nav` at
import time), `list_apps()`/`get_app()` would silently fall back to
`organizeme_chrome.registry`'s own compiled-in literal instead of the Host's real `APPS`, with no
exception anywhere to surface it. Importing `app.main` here (as every other test in this suite
already does, transitively, via the `client`/`app` fixtures) is what exercises the real ordering;
this test only adds the missing assertion that it landed on the right source.
"""

import app.main  # noqa: F401  # the import itself is what exercises the ordering under test
from app.core.registry import APPS as HOST_APPS
from organizeme_chrome.registry import list_apps


def test_host_registry_resolves_against_its_own_in_process_source() -> None:
    # `is`, not `==`: InProcessRegistrySource.get_apps() returns HOST_APPS by reference. Identity
    # is what actually distinguishes "configured correctly" from "silently using the package's
    # separately-maintained fallback copy" - the two currently hold equal (but not identical)
    # content, so an `==` check alone wouldn't catch a broken import order.
    assert list_apps() is HOST_APPS
