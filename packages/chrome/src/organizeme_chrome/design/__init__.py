"""Shared design-system building blocks for the `templates/components/` Jinja macros.

Class-name lookups (variant/density -> Tailwind utility classes) live here rather than inline in
each macro so that the same primitive (e.g. a focus ring, a density's padding scale) is defined
once and reused across button/input/badge/card_shell/status_dot, the same way `nav_groups.py`
centralizes sidebar-state logic that `chrome_nav.html` only renders.
"""

from organizeme_chrome.design.classes import (
    ALERT_VARIANT_CLASSES,
    BADGE_VARIANT_CLASSES,
    BUTTON_VARIANT_CLASSES,
    DENSITY_BADGE_TEXT,
    DENSITY_CARD_PADDING,
    DENSITY_PADDING,
    FOCUS_RING,
    INPUT_DEFAULT_BORDER,
    INPUT_DEFAULT_FILL,
    INPUT_ERROR_BORDER,
    INPUT_ERROR_MESSAGE_TEXT,
    LINK_CLASSES,
    STATUS_VARIANT_CLASSES,
    TABLE_BODY_CELL_CLASSES,
    TABLE_BODY_ROW_CLASSES,
    TABLE_CLASSES,
    TABLE_HEAD_CELL_CLASSES,
    TABLE_HEAD_ROW_CLASSES,
)

__all__ = [
    "ALERT_VARIANT_CLASSES",
    "BADGE_VARIANT_CLASSES",
    "BUTTON_VARIANT_CLASSES",
    "DENSITY_BADGE_TEXT",
    "DENSITY_CARD_PADDING",
    "DENSITY_PADDING",
    "FOCUS_RING",
    "INPUT_DEFAULT_BORDER",
    "INPUT_DEFAULT_FILL",
    "INPUT_ERROR_BORDER",
    "INPUT_ERROR_MESSAGE_TEXT",
    "LINK_CLASSES",
    "STATUS_VARIANT_CLASSES",
    "TABLE_BODY_CELL_CLASSES",
    "TABLE_BODY_ROW_CLASSES",
    "TABLE_CLASSES",
    "TABLE_HEAD_CELL_CLASSES",
    "TABLE_HEAD_ROW_CLASSES",
]
