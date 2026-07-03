"""Single source of truth for the authenticated sidebar navigation.

The order here is the documented sidebar order (Dashboard -> Upload -> Processing ->
Logs -> Prompt -> Settings -> Profile) and is relied on by tests/test_sidebar.py.
It is exposed to templates as the ``nav_items`` Jinja global (see app.core.templating),
so the sidebar layout renders from this list rather than hard-coding links.
"""

from typing import NamedTuple


class NavItem(NamedTuple):
    path: str
    label: str


NAV_ITEMS: list[NavItem] = [
    NavItem("/dashboard", "Dashboard"),
    NavItem("/upload", "Upload"),
    NavItem("/processing", "Processing"),
    NavItem("/logs", "Logs"),
    NavItem("/prompt", "Prompt"),
    NavItem("/settings", "Settings"),
    NavItem("/profile", "Profile"),
]
