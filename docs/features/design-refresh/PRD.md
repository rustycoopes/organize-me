## Problem Statement

Every page in OrganizeMe except the landing page looks flat and generic. The whole app — auth
(login/register/forgot/reset), profile, settings — is built from unmodified DaisyUI components: the
same centered `card` shell, the same stock `corporate`/`dark` theme, the same default buttons and
inputs, with no color, typography, or layout choice that says "OrganizeMe" rather than "any DaisyUI
tutorial." The landing page only reads as "good" because it composes those same stock components
with better spacing and section rhythm — it isn't actually custom-designed either. The product
doesn't yet look, feel, or present like something worth trusting with someone's calendar.

Because all three OrganizeMe hosted apps (`organize-me`, `event-creator`, `doc-library`) render
through one shared chrome package, this problem isn't cosmetic-per-page — it's systemic: there is no
design system at all today, just a Tailwind CDN script and DaisyUI's defaults.

## Solution

Replace the current CDN-only Tailwind/DaisyUI setup with a real, custom design system: a compiled
Tailwind build with OrganizeMe's own color, typography, and spacing tokens, and hand-crafted
components (buttons, cards, inputs, badges, nav/sidebar, Settings tab-bar) that replace DaisyUI
entirely. Apply it first to the shared chrome package and to every existing page in `organize-me`
(landing, auth, profile, settings) — this is the pilot; `event-creator` and `doc-library` adopt the
same system as separate, later features once it's proven here.

The visual direction ("Signal") was chosen from a working comparison of two directions built and
reviewed during the design-alignment session: a confident, high-contrast system with one bold accent
color (coral "Flame" for calls to action, "Cobalt" for dates — since surfacing dates clearly is the
product's actual job), a heavy geometric display face for headlines, and a page-type split —
marketing/first-impression pages (landing, auth, empty states) get bold typography, color-blocked
sections, and a signature illustrated moment (a chat message visually resolving into a calendar
chip, literalizing what the product does); data-heavy authenticated pages (dashboard-adjacent
surfaces, settings) get a cooler, denser treatment that prioritizes clarity over illustration.

## User Stories

### Visual identity & design system
1. As a visitor, I want the app to have a distinctive, considered visual identity, so that it feels
   trustworthy and worth signing up for, not like a generic tutorial project.
2. As a returning user, I want every page I use — not just the landing page — to feel like part of
   the same considered product, so that the experience feels coherent rather than half-finished.
3. As a developer extending OrganizeMe, I want a shared set of design tokens (colors, typography,
   spacing) defined once in the chrome package, so that new pages and future hosted apps can be
   visually consistent without re-deriving the palette.
4. As a developer, I want a small set of reusable components (buttons, cards, inputs, badges) built
   on the new tokens, so that I compose pages from consistent building blocks instead of hand-rolling
   styles per page.

### Landing page
5. As a visitor, I want the landing page's hero to make it immediately obvious what OrganizeMe does,
   so that I don't have to read multiple sections to understand the value.
6. As a visitor, I want the landing page to show what OrganizeMe actually does — turning a chat
   agreement into a calendar event — as a visual moment, not just a text description, so that the
   product's value is felt, not just read.
7. As a visitor, I want clear, prominent calls to action (get started, see how it works), so that I
   know exactly how to proceed if I'm interested.

### Authentication
8. As a visitor, I want the login and registration pages to feel like an intentional part of the
   product's identity, so that my first real interaction with the app doesn't feel like a generic
   form.
9. As a user who forgot my password, I want the forgot-password and reset-password pages to carry
   the same visual identity as the rest of the app, so that the flow feels trustworthy rather than
   like a bolted-on afterthought.
10. As a user, I want form validation errors on auth pages to be visually clear (not just present),
    so that I immediately see what needs fixing.

### Profile & Settings
11. As a user, I want my Profile page to have real visual hierarchy (not just a single undifferentiated
    card), so that I can quickly find and edit the field I came for.
12. As a user, I want the Settings shell (tab bar + content area) to feel like a considered part of
    the product, so that configuring the app doesn't feel like an afterthought compared to the
    landing page.
13. As a user, I want status/state (e.g. a saved change, a connected/disconnected state) to be
    visually encoded — not just described in text — so that I can tell what's true at a glance.

### Navigation & chrome
14. As a user, I want the sidebar and header to carry the new visual identity, so that the chrome
    around every page feels as considered as the page content itself.
15. As a user, I want the visual redesign to work correctly with the existing sidebar structure
    (including any in-flight grouping/collapsing behavior from the `sidebar-nav-groups` feature), so
    that I don't experience a broken or inconsistent sidebar during rollout.

### Dark mode
16. As a user who has dark mode enabled in my profile, I want the new design system to look
    intentional in dark mode too — not just visually inverted — so that my preferred appearance
    doesn't feel like a second-class experience.
17. As a user, I want colors that carry meaning (e.g. a confirmed vs. pending state) to stay legible
    and correctly distinguishable in both light and dark mode.

### Accessibility & responsiveness
18. As a user relying on keyboard navigation, I want every redesigned interactive element (buttons,
    form fields, nav toggles) to have a visible focus state, so that I can navigate the app without a
    mouse.
19. As a user with low vision, I want text and interactive elements to meet accessible contrast
    ratios under the new color system, so that the redesign doesn't make the app harder to read than
    it was before.
20. As a user on a smaller screen, I want the redesigned pages to remain usable and legible, so that
    the visual refresh doesn't break the experience on mobile-width viewports.

### Platform / rollout
21. As a developer working on `event-creator` or `doc-library` in a future feature, I want the design
    tokens and component patterns established here to be directly reusable, so that adopting the new
    system elsewhere doesn't mean starting from scratch.
22. As a developer, I want the new build pipeline (compiled Tailwind via `pytailwindcss`) to produce
    correct CSS in CI and in the deployed container, so that the redesign actually ships correctly to
    QA and prod, not just locally.
23. As a developer, I want DaisyUI and the Tailwind CDN script fully removed once the new system is
    in place, so that there's no leftover dead dependency or conflicting styling source.

## Implementation Decisions

- **Drop DaisyUI entirely.** Replace it and the Tailwind CDN "Play" script with a real compiled
  Tailwind build (custom tokens, hand-crafted components) in `packages/chrome`. No DaisyUI classes
  remain anywhere in any consuming app once this is complete.
- **Build tooling: `pytailwindcss`.** A PyPI package bundling the standalone Tailwind CLI binary —
  produces a real compiled/purged CSS build with zero Node/npm added to the stack, consistent with
  the platform's Python-only convention. `event-creator`/`doc-library` are expected to adopt the
  same tooling pattern when they pick up the design system later (out of scope here, but the
  pipeline shape should anticipate being reused, not be organize-me-specific).
- **Design tokens ("Signal" direction):**
  - Colors: Ink (near-black text/sidebar), Paper (marketing-page background), Flame (primary CTA
    accent, coral), Cobalt (dates/links — functional color coding, since surfacing dates clearly is
    the product's core value), Mist (cooler background for data-heavy/authenticated pages, distinct
    from marketing-page Paper), Sage (confirmed/success state).
  - Typography: a heavy geometric display face for headlines (self-hosted webfont), a clean body
    face for UI text, and a monospace face for dates/timestamps/data (tabular figures where digits
    line up in columns).
  - Both light and dark-mode token sets must be defined — dark mode is an existing capability
    (`User.dark_mode`, DaisyUI's `dark` theme today) that must be preserved and carry the same
    design intent in the new system, not just an inverted default.
- **Page-type split in the component/layout system:** marketing/first-impression pages (landing,
  auth, empty states) use the bolder, more illustrated treatment (color-blocked sections, generous
  whitespace, the chat-bubble-to-calendar-chip signature moment on the landing hero); data-heavy
  authenticated pages (profile, settings, and future dashboard-style surfaces) use the denser, cooler
  treatment. Both draw from the same token system — the split is in layout/density/decoration, not a
  different palette per page type.
- **Scope: `packages/chrome` + all of `organize-me`'s existing pages.** Landing (restyle, not
  rebuild — its existing hero/features/CTA structure is sound), auth (login/register/forgot-password/
  reset-password), profile, settings shell, plus the shared components/tokens/build pipeline in
  `packages/chrome` that `event-creator`/`doc-library` will extend later.
- **Coordinate with concurrent chrome-package work.** Two other features are in flight against
  `packages/chrome`: `sidebar-nav-groups` (collapsible per-app nav groups — interaction/persistence
  only, no visual styling) and `registry-decoupling` (runtime registry architecture). Neither
  conflicts with this PRD's scope, but `/to-design`/`/to-wbs` should sequence sidebar restyling work
  to land on top of whatever structural markup `sidebar-nav-groups` produces, rather than styling the
  old flat-list markup and redoing it.
- **No new functional behavior.** This is a visual/presentation change. Existing page behavior,
  routes, and data flows are unchanged — only markup/styling changes.

## Testing Decisions

- Extend the existing Playwright E2E suite (`e2e/tests/`) with smoke coverage for the new build: the
  Tailwind CDN script and DaisyUI stylesheet are no longer referenced, and the new compiled
  stylesheet is served with a 200. Existing functional assertions (login works, forms submit,
  password reset flow completes, etc.) stay as-is — behavior isn't changing, so those tests should
  continue to pass unmodified and serve as the regression backstop during the restyle.
- Extend the existing macro-level pytest pattern (`tests/test_card_macro.py` is the prior art) to
  cover the new shared components in `packages/chrome` — testing Jinja macro output directly, without
  a full HTTP round-trip, mirrors how the current shared `card_page()` macro is already tested.
- No visual-regression/screenshot-diff tooling in this PRD — deferred as a possible future addition
  once the design system itself is stable.

## Out of Scope

- Redesigning `event-creator` or `doc-library` — both are separate, later features once this pattern
  is validated on `organize-me`.
- Implementing the `sidebar-nav-groups` collapsible-group interaction/persistence logic itself — that
  feature owns its own behavior; this PRD only needs to visually style whatever structure it produces.
- Any new product functionality — this is a visual/presentation-layer change only.
- Visual regression/screenshot-diff testing infrastructure.
- Custom font licensing/hosting research beyond standard self-hostable webfonts (e.g. Google Fonts
  licensed for self-hosting).

## Further Notes

- A working two-direction comparison (this PRD's chosen "Signal" direction vs. a rejected "Ledger"
  planner-inspired alternative) was built and reviewed during the design-alignment session before
  this PRD was written — see the session's `/grilling` transcript for the full rationale and the
  rejected alternative, in case a future revisit wants that context.
- `docs/features/original-organize-me/` documents the pages/flows in scope here from their original
  build; useful background on each page's existing behavior that must not regress.
