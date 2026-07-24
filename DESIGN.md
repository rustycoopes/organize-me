# Design

<!-- impeccable:design-schema 1 -->

## Direction

**Redesign, not refinement.** The prior "Signal" system (near-black ink, flame-red primary,
Bricolage Grotesque, no photography) is retired and treated as anti-reference. Direction is
brief-pinned by the user to **FamilyWall**'s visual language (warm, photographic, rounded,
blue-accented family-organization app), adapted — not copied — to OrganizeMe's actual product
truth: a multi-app **Host** shell, not a single consumer app. FamilyWall's own photography is
never reproduced; imagery is independently sourced in the same warm-lifestyle mood (see Evidence).

- **THESIS.** OrganizeMe should feel like the one warm, human place a household's tools live —
  not a cold internal-tools console — because a caregiver logs in here daily. Refuses the
  "Laravel-inspired dark dev-console" the original PRD asked for, and refuses the prior system's
  choice to make its primary brand color the same red used for destructive actions.
- **OWN-WORLD.** Warm off-white paper, a confident rounded blue as the one brand accent, a warm
  amber as its secondary partner, pill-shaped buttons and badges, generously rounded cards, a
  bold rounded-terminal display face (Baloo 2) over a clean workhorse body face (IBM Plex Sans,
  unchanged). Full-bleed warm lifestyle photography on the public/marketing surfaces (landing,
  auth); the authenticated shell stays photography-free and scan-first, carrying the same palette
  and roundness through color and type alone.
- **STORY.** A visitor understands within seconds: this is where my household's tools live, it's
  friendly and made for real family logistics (not corporate SaaS), and it's trustworthy with
  personal data. They register or log in. A returning user is greeted by a shell that feels
  consistent across every hosted app, not bolted together.
- **FIRST VIEWPORT** (landing page). Full-bleed warm photo of two people coordinating household
  errands on a wall whiteboard/smart panel (the product's actual mechanism, not stock-generic) —
  bold rounded headline and pill CTA over a gradient scrim on the left/lower third; the existing
  chat-message → calendar-chip proof card floats over the photo's lower-right corner as a
  demonstration of the mechanism, not replaced by the photo.
- **FORM.** Brief-pinned direction (FamilyWall), not rolled via concept-seed — the user selected
  it directly from a five-site competitor scan. No staging/challenger process applies.

## Color

Restrained-to-committed strategy: warm neutral ground, one saturated brand accent (cobalt) at
page scale on primary actions and active/selected state, one secondary warm accent (amber) held
in reserve for secondary emphasis, semantic colors (sage/flame) kept strictly to their status
role rather than doubling as brand color.

| Token | Light hex | Role |
|---|---|---|
| `ink` | `#21252c` | Primary text (light) / page background (dark, via `dark:bg-ink`) |
| `ink-2` | `#454b56` | Muted text (light) / card & surface fill (dark) |
| `paper` | `#fbf9f5` | Page background (light) / primary text (dark, via `dark:text-paper`) |
| `paper-2` | `#f1ede3` | Secondary surface (light) / muted text (dark) |
| `mist` / `mist-2` | `#eef1eb` / `#e3e6de` | Neutral fills — hover states, table headers, neutral badges |
| `cobalt` / `cobalt-tint` | `#3f6fe0` / `#e7edfc` | **Brand primary.** Primary buttons, links, active nav/tab state, focus ring, info status |
| `amber` / `amber-tint` | `#e2932f` / `#faecd8` | **Secondary accent.** Secondary buttons, secondary badges, warm highlight moments |
| `sage` / `sage-tint` | `#3f8a5f` / `#e3f1e7` | Success status only |
| `flame` / `flame-tint` | `#e14b3f` / `#fbe4e1` | **Danger only** — no longer doubles as brand primary (the prior system's flame served both roles; this redesign separates them so "primary action" and "destructive action" are never the same color) |

`ink`/`paper` and `ink-2`/`paper-2` keep the existing bipolar pattern (each token doubles as the
opposite-mode's text-or-surface color via explicit `dark:` utility classes per component) —
unchanged mechanism from the prior system, see `docs/adr/design-refresh-dark-mode-css-strategy.md`.

Dark mode is not a token redefinition; every component states its own `dark:`-prefixed classes
(unchanged architecture).

## Type

- **Display** — Baloo 2, weight 700. Bold rounded-terminal grotesk carrying FamilyWall's warm,
  friendly headline energy; self-hosted (`packages/chrome/.../static/fonts/baloo-2-700.woff2`,
  OFL-licensed). Used sparingly: page headers, hero/section headings, card titles.
- **Body** — IBM Plex Sans, weight 400. Unchanged from the prior system — already self-hosted,
  already the workhorse face for an Operate-heavy surface; no reason to replace a face that was
  never the prior system's problem.
- **Mono** — JetBrains Mono, weight 400. Unchanged — logs, timestamps, tabular data.

## Shape & density

- Buttons: pill (`rounded-full`), not `rounded-md` — FamilyWall's signature CTA shape.
- Cards: `rounded-2xl`, up from `rounded-lg` — warmer, less boxy.
- Badges / page-header pill: unchanged `rounded-full`.
- Inputs/selects: unchanged `rounded-md` — form fields stay legible and un-precious; roundness is
  spent on buttons and cards, not every element (see craft-floor: don't round everything just
  because the world is round).
- Density system (`product` vs `marketing` padding scale): unchanged.

## Imagery

Real, independently-sourced photography (Unsplash License — free for commercial use, no
permission required) in FamilyWall's warm-lifestyle mood. Never FamilyWall's own photos.

- Landing hero: `app/static/images/hero-household-planning.jpg` — a couple coordinating errands
  on a wall whiteboard/smart panel. Photo by Sable Flow
  (unsplash.com/photos/a-man-and-a-woman-standing-in-a-kitchen-NBkdwxbAVDg).
- Auth split panel: `app/static/images/auth-morning-notebook.jpg` — coffee, notebook, and morning
  light. Photo by Brandon Cormier
  (unsplash.com/photos/black-coffee-in-ceramic-mug-near-black-click-pen-on-top-of-open-notebook-Hy4eZgKCcXI).
- The authenticated shell (nav, dashboard chrome, Settings, Profile) carries the world through
  color/type/shape only — no photography — per Operate-mode guidance (task/scan legibility
  outranks expression once a visitor is inside the tool).

## Components affected

`packages/chrome/src/organizeme_chrome/`: `static/css/tokens.css`, `design/classes.py`,
`templates/components/{button,card_shell,toggle}.html`, `templates/macros/{chrome_nav,
chrome_tabs}.html`. `app/templates/`: `landing.html`, `auth/*.html`, `settings.html`,
`pages/placeholder.html`. See `docs/adr/container-redesign-familywall-visual-system.md` for the
primary/secondary color-role swap rationale.

## Scope

This pass covers every Host-owned surface: landing, auth (login/register/forgot/reset password),
and the authenticated shell (sidebar nav, header, Settings, Profile, shared components). Hosted
apps (Event Creator, Doc Library, HA Dashboard) are **out of scope** — they consume this same
`organizeme-chrome` package and will pick up the shared tokens/components automatically once each
repo bumps its pin, but their own app-specific templates are a deliberate follow-on pass (per the
user's own stated sequencing: container first, then the hosted apps).
