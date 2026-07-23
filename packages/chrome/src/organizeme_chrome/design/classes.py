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

DENSITY_BADGE_TEXT: dict[str, str] = {
    "product": "text-xs",
    "marketing": "text-sm",
}

FOCUS_RING = (
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 "
    "focus-visible:outline-flame"
)

# input's error state (see docs/features/design-refresh/WBS/slice-3-auth-pages.md and
# issue #233) reuses flame - the same token STATUS_VARIANT_CLASSES uses for "danger" - rather
# than introducing a second red into the palette.
INPUT_ERROR_BORDER = "border-flame dark:border-flame"
INPUT_ERROR_MESSAGE_TEXT = "text-flame dark:text-flame"

# Default (non-error) field border/fill, shared by input.html and select.html - see issue #240.
# A 30%-opacity border with a fill matching the page's own background (bg-paper on Paper) reads as
# invisible in practice even though the token looks fine in isolation; paper-2/ink-2 fills actually
# differ in lightness from the Paper/Ink page backgrounds they sit on, and the border opacity is
# raised so the boundary itself is visible without a fill difference to lean on.
INPUT_DEFAULT_BORDER = "border-ink-2/40 dark:border-paper/40"
INPUT_DEFAULT_FILL = "bg-paper-2 dark:bg-ink-2"

# Every color pairing here also carries its dark: variant (per
# docs/adr/design-refresh-dark-mode-css-strategy.md) - tokens.css's palette has no light/dark pair
# built in, so each component must state its own dark:-prefixed classes rather than relying on a
# `dark` theme automatically producing readable colors.

BUTTON_VARIANT_CLASSES: dict[str, str] = {
    "primary": "bg-flame text-paper hover:bg-flame/90",
    "secondary": "bg-cobalt text-paper hover:bg-cobalt/90",
    # A transparent fill with a 30%-opacity border was indistinguishable from Paper/Mist page
    # backgrounds (both near-identical lightness) - see issue #240. An alpha-blended ink/paper
    # tint (rather than a literal bg-paper-2/bg-mist-2 fill) contrasts against either page
    # background without needing to know which one the button happens to sit on.
    "ghost": (
        "bg-ink/5 text-ink border border-ink/30 hover:bg-ink/10 "
        "dark:bg-paper/10 dark:text-paper dark:border-paper/40 dark:hover:bg-paper/15"
    ),
    # Outline-only destructive action (e.g. profile's "Delete account" trigger) - reuses flame,
    # the same token STATUS_VARIANT_CLASSES/ALERT_VARIANT_CLASSES use for "danger", rather than
    # introducing a second red into the palette.
    "danger": "border border-flame text-flame hover:bg-flame-tint dark:hover:bg-flame/10",
    # Filled destructive action (event-creator dashboard row deletes) - outline "danger" reads too
    # faint at small sizes inside a table row; this mirrors "primary"'s own fill/hover pattern with
    # the same flame token so a row-level delete is unmistakable at a glance.
    "danger-solid": "bg-flame text-paper hover:bg-flame/90",
}

# page_header's pill background (event-creator's Dashboard heading blended into the data below
# it). Confirmed live on QA (organizeme.qa) that dark:bg-ink-2 here was literally invisible -
# card_shell's own dark background is ALSO dark:bg-ink-2, so a 100%-opaque fill of the same token
# painted on top of itself produces zero contrast (same class of bug as issue #240's ghost-button
# fix). Uses that same alpha-blended-over-paper idiom instead, which contrasts regardless of the
# surface it sits on.
PAGE_HEADER_WRAP_CLASSES = "inline-flex items-center rounded-full bg-mist px-4 py-1.5 dark:bg-paper/10"
PAGE_HEADER_TEXT_CLASSES = "font-display text-2xl font-semibold text-ink dark:text-paper"

BADGE_VARIANT_CLASSES: dict[str, str] = {
    "neutral": "bg-mist text-ink-2 dark:bg-ink-2 dark:text-paper-2",
    "primary": "bg-flame-tint text-flame dark:bg-flame/20",
    "secondary": "bg-cobalt-tint text-cobalt dark:bg-cobalt/20",
    "success": "bg-sage-tint text-sage dark:bg-sage/20",
}

STATUS_VARIANT_CLASSES: dict[str, str] = {
    "success": "bg-sage",
    "info": "bg-cobalt",
    "danger": "bg-flame",
    "neutral": "bg-ink-2/40 dark:bg-paper-2/40",
}

ALERT_VARIANT_CLASSES: dict[str, str] = {
    "danger": "border-flame/30 bg-flame-tint text-flame dark:border-flame/40 dark:bg-flame/10",
    "info": "border-cobalt/30 bg-cobalt-tint text-cobalt dark:border-cobalt/40 dark:bg-cobalt/10",
    # Added for event-creator#26's run-status banner (success/waiting states) - reuses sage/mist
    # the same way BADGE_VARIANT_CLASSES["success"] and STATUS_VARIANT_CLASSES["neutral"] do.
    "success": "border-sage/30 bg-sage-tint text-sage dark:border-sage/40 dark:bg-sage/10",
    "neutral": "border-ink-2/20 bg-mist text-ink-2 dark:border-paper-2/20 dark:bg-ink-2 dark:text-paper-2",
}

# Table primitive (event-creator#26): header/row/border treatment that used to come from
# DaisyUI's `.table` class. No <table> macro exists here because column count/content varies per
# caller; these are raw class strings applied directly to <table>/<thead>/<tr>/<th>/<td>, the same
# way FOCUS_RING/DENSITY_PADDING are consumed without a wrapping macro.
TABLE_CLASSES = "w-full text-left font-body text-sm border-collapse"
TABLE_HEAD_ROW_CLASSES = "border-b border-ink-2/30 bg-mist dark:border-paper-2/30 dark:bg-ink-2"
TABLE_HEAD_CELL_CLASSES = "px-3 py-2 font-medium text-ink-2 dark:text-paper-2"
TABLE_BODY_ROW_CLASSES = "border-b border-ink-2/10 last:border-0 dark:border-paper-2/10"
# Opt-in zebra striping - a separate constant rather than folding into TABLE_BODY_ROW_CLASSES since
# not every table wants it; callers pick whichever fits (see event-creator's dashboard events
# table, which asked for alternating rows to make dense data easier to scan). dark:even:bg-ink-2/40
# was confirmed live on QA to have zero visible effect: card_shell's own dark background is ALSO
# dark:bg-ink-2, so blending that same color over itself at any opacity is a no-op (same bug as
# page_header's pill, see its comment above) - dark:even:bg-paper/5 lightens instead, visible
# regardless of the surface underneath.
TABLE_BODY_ROW_ZEBRA_CLASSES = (
    "border-b border-ink-2/10 last:border-0 dark:border-paper-2/10 even:bg-mist/40 dark:even:bg-paper/5"
)
TABLE_BODY_CELL_CLASSES = "px-3 py-2 align-middle"

# Inline text-link treatment (event-creator#29) - the one color decision in event-creator's
# events_panel.html that wasn't already pulled from a named constant here, duplicated verbatim at
# two call sites. Carries FOCUS_RING/rounded-sm, matching organize-me's own text-cobalt link
# convention (see e.g. app/templates/auth/login.html's "Forgot password?"/"Register" links).
LINK_CLASSES = (
    "font-medium text-cobalt underline-offset-2 hover:underline dark:text-cobalt "
    + FOCUS_RING
    + " rounded-sm"
)
