"""Theme config: the CDN links and DaisyUI theme-name strings that define OrganizeMe's visual
theme. There is no tailwind.config.js — the theme *is* these strings — so this module is the
single owner of them.
"""

TAILWIND_CDN = "https://cdn.tailwindcss.com"
ALPINE_CDN = "https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"
DAISYUI_CDN = "https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css"

LIGHT_THEME = "corporate"
DARK_THEME = "dark"


def theme_attr(dark_mode: bool) -> str:
    return DARK_THEME if dark_mode else LIGHT_THEME
