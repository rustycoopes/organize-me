"""Shared design-system building blocks for the `templates/components/` Jinja macros.

Class-name lookups (variant/density -> Tailwind utility classes) live here rather than inline in
each macro so that the same primitive (e.g. a focus ring, a density's padding scale) is defined
once and reused across button/input/badge/card_shell/status_dot, the same way `nav_groups.py`
centralizes sidebar-state logic that `chrome_nav.html` only renders.
"""

from organizeme_chrome.design.classes import (
    BADGE_VARIANT_CLASSES,
    BUTTON_VARIANT_CLASSES,
    DENSITY_BADGE_TEXT,
    DENSITY_CARD_PADDING,
    DENSITY_PADDING,
    FOCUS_RING,
    STATUS_VARIANT_CLASSES,
)

__all__ = [
    "BADGE_VARIANT_CLASSES",
    "BUTTON_VARIANT_CLASSES",
    "DENSITY_BADGE_TEXT",
    "DENSITY_CARD_PADDING",
    "DENSITY_PADDING",
    "FOCUS_RING",
    "STATUS_VARIANT_CLASSES",
]
