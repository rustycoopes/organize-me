"""Pure combine logic for the collapsible, per-app sidebar nav groups.

Deliberately free of `Request`/DB/session imports (see docs/adr/sidebar-nav-groups-render-boundary.md
in the organize-me repo): every consuming service resolves its own current user's stored
preference and current request path, then calls `build_nav_groups`/`flat_nav_items` here with
plain data. This keeps the function trivially unit-testable and reusable across services that
otherwise share nothing about how they authenticate or store users.
"""

from dataclasses import dataclass

from organizeme_chrome.registry import AppEntry, AppNavItem

# Apps in this set render their nav items as permanent, always-visible flat entries (outside any
# collapsible group) rather than as a named group of their own — today this is just "organizeme",
# whose only nav items are the account-level Settings/Profile pages. Not a new registry field
# (the PRD deliberately avoids adding one): this is chrome-package-local rendering policy, not
# data any other consumer (e.g. the load-balancer's URL map) needs.
FLAT_SERVICE_NAMES = frozenset({"organizeme"})

_LABEL_OVERRIDES = {
    "organizeme": "Organize Me",
}


def _humanize_label(service_name: str) -> str:
    return _LABEL_OVERRIDES.get(service_name, service_name.replace("-", " ").title())


@dataclass(frozen=True)
class NavGroup:
    service_name: str
    label: str
    nav: list[AppNavItem]
    collapsed: bool


def build_nav_groups(
    apps: list[AppEntry],
    collapsed: dict[str, bool],
    current_path: str,
) -> list[NavGroup]:
    """Resolve each grouped app's render state from stored preference + the current page.

    Apps in `FLAT_SERVICE_NAMES` are skipped here entirely — they render via `flat_nav_items`
    instead. An app with no entry in `collapsed` defaults to expanded (`False`). If `current_path`
    matches one of an app's own nav items, that app's group is force-rendered expanded for this
    call only: `collapsed` itself is never mutated, so callers must not persist this override as
    the user's new stored preference.
    """
    groups = []
    for entry in apps:
        if entry.service_name in FLAT_SERVICE_NAMES:
            continue
        is_collapsed = collapsed.get(entry.service_name, False)
        if is_collapsed and any(item.path == current_path for item in entry.nav):
            is_collapsed = False
        groups.append(
            NavGroup(entry.service_name, _humanize_label(entry.service_name), entry.nav, is_collapsed)
        )
    return groups


def flat_nav_items(apps: list[AppEntry]) -> list[AppNavItem]:
    """Nav items for apps in `FLAT_SERVICE_NAMES`, always rendered outside any group."""
    return [item for entry in apps for item in entry.nav if entry.service_name in FLAT_SERVICE_NAMES]
