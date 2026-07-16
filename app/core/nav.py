from fastapi import Request
from organizeme_chrome import NavGroup, build_nav_groups, flat_nav_items, list_apps

from app.models.user import User


def sidebar_nav_context(user: User, request: Request) -> dict[str, object]:
    """Per-request sidebar context: grouped nav, flat nav, and the client's collapsed-state maps.

    Every page rendering chrome_authenticated_base.html must merge this into its own template
    context — see docs/adr/sidebar-nav-groups-render-boundary.md for why this isn't computed as a
    Jinja environment global.

    Two separate maps are exposed, both keyed by service_name to a collapsed boolean:

    - `nav_collapsed_json`: what's actually rendered/displayed, including build_nav_groups()'s
      current-page force-open override.
    - `nav_stored_collapsed_json`: the user's real stored preference (`user.nav_collapsed_groups`,
      minus any force-open override), which the client toggle PATCHes back on every click.

    Keeping these separate matters: if the toggle's PATCH body were built from the *displayed*
    map instead, clicking any group while a different, unrelated group happens to be
    force-open (because the current page lives inside it) would silently persist that
    temporary override as the user's new stored preference for the untouched group — exactly the
    leak build_nav_groups()'s own docstring warns callers not to cause.
    """
    apps = list_apps()
    nav_groups: list[NavGroup] = build_nav_groups(
        apps, collapsed=user.nav_collapsed_groups, current_path=request.url.path
    )
    return {
        "nav_groups": nav_groups,
        "flat_nav_items": flat_nav_items(apps),
        "nav_collapsed_json": {group.service_name: group.collapsed for group in nav_groups},
        "nav_stored_collapsed_json": {
            group.service_name: user.nav_collapsed_groups.get(group.service_name, False)
            for group in nav_groups
        },
    }
