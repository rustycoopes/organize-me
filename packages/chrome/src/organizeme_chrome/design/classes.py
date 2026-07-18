"""Tailwind class-name tables for the shared component primitives.

Every entry here is keyed off a token from `static/css/tokens.css`'s `@theme` block (ink/paper/
flame/cobalt/mist/sage) - see docs/adr/design-refresh-shared-component-library.md. Density is the
one axis shared by every sizeable primitive (button/input/card), so its two variants live in one
place rather than being repeated per-macro.
"""

DENSITY_PADDING: dict[str, str] = {
    # Product pages (the app itself) favor compactness; marketing pages (landing) favor room.
    "product": "px-3 py-1.5 text-sm",
    "marketing": "px-5 py-2.5 text-base",
}

DENSITY_CARD_PADDING: dict[str, str] = {
    "product": "p-4",
    "marketing": "p-6",
}

FOCUS_RING = (
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 "
    "focus-visible:outline-flame"
)

BUTTON_VARIANT_CLASSES: dict[str, str] = {
    "primary": "bg-flame text-paper hover:bg-flame/90",
    "secondary": "bg-cobalt text-paper hover:bg-cobalt/90",
    "ghost": "bg-transparent text-ink border border-ink-2/30 hover:bg-mist",
}

BADGE_VARIANT_CLASSES: dict[str, str] = {
    "neutral": "bg-mist text-ink-2",
    "primary": "bg-flame-tint text-flame",
    "secondary": "bg-cobalt-tint text-cobalt",
    "success": "bg-sage-tint text-sage",
}

STATUS_VARIANT_CLASSES: dict[str, str] = {
    "success": "bg-sage",
    "info": "bg-cobalt",
    "danger": "bg-flame",
    "neutral": "bg-ink-2/40",
}
