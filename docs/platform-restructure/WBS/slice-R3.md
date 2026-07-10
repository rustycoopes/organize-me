# Slice R3 — Extract Shared Chrome/Theme Package + App-Registry

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** A single versioned package — published by the Host repo — that owns the sidebar /
header / Settings tab-bar templates, the theme config, the app-registry data, and a standalone
JWT-verification helper, with the Host itself consuming it as a pinned dependency and rendering
identically.

## What to build

Today the chrome lives inline in the monolith: `app/pages/nav.py` (`NAV_ITEMS`),
`app/templates/base.html` + `authenticated_base.html` + `macros/ui.html`,
`app/core/templating.py`, and the theme string / CDN links in `base.html`. JWT verification is
entangled in `app/auth/backend.py` via fastapi-users.

Extract these into one installable package so there is exactly one visual definition of the
chrome and one identity-verification helper, shared by the Host and every future hosted app —
without any runtime call between services. Prove it by making the Host consume the package and
render byte-for-byte the same UI.

## Includes
- New package (recommend publishing to **GitHub Packages**, matching the GitHub-hosted repos)
  containing:
  1. Jinja macros/templates for sidebar, header, Settings tab-bar (from `authenticated_base.html`,
     `base.html`, `macros/ui.html`).
  2. Theme config — the `data-theme` corporate/dark string + Tailwind/DaisyUI/Alpine CDN links
     (there is no `tailwind.config.js` today; the theme *is* these strings).
  3. **App-registry data** (from `NAV_ITEMS`) — the single source of truth for nav headings /
     sub-items and Settings tabs, bundled and versioned with the templates.
  4. A **signature-+-expiry-only JWT-verify helper** — no login, no password handling — extracted
     from the fastapi-users wiring, reading the shared `jwt_secret`.
- Host repo publishes a versioned release on tag; Host declares the package as a **pinned**
  dependency and renders its chrome from it.
- App-registry shape per the design doc sketch (`apps[].nav`, `apps[].settings_tabs`,
  `apps[].service_name`).

## Relevant files
- Source of extraction: `app/pages/nav.py`, `app/core/templating.py`,
  `app/templates/base.html`, `app/templates/authenticated_base.html`,
  `app/templates/macros/ui.html`, JWT logic in `app/auth/backend.py`.
- Host consumption: `app/main.py`, `app/core/templating.py`, `pyproject.toml` (add pinned dep),
  CI (`.github/workflows/ci.yml` / `deploy.yml`) — add a publish-on-tag step.

## Design notes
- **Pinned, opt-in versioning:** a Host-side chrome edit never silently changes what a hosted app
  renders until that app bumps the pinned version — deliberate, per the design.
- **One file drives two things:** the app-registry feeds *rendering* (via this package) and later
  *routing* (the LB URL map in R5). Author it once, here.
- The verify helper must be usable with **no** fastapi-users dependency and **no** network call —
  Event Creator (R6) will depend only on this helper for identity.
- Registry choice (GitHub Packages) is a recommendation; confirm during this slice.

## Blocked by
- None — can run in parallel with R1/R2.

## Acceptance criteria
- [ ] The chrome package builds and publishes a versioned artifact from the Host repo's CI on tag.
- [ ] The package exposes: chrome templates, theme config, app-registry data, and a standalone
      JWT-verify helper (signature + expiry only).
- [ ] The Host consumes the package as a pinned dependency and renders the sidebar/header/Settings
      shell byte-for-byte identically to before (QA visual + E2E check).
- [ ] The JWT-verify helper verifies a Host-issued token with no fastapi-users import and no
      network call (unit-tested in isolation).
- [ ] pytest + mypy + QA E2E pass.

## Testing
- Unit: JWT-verify helper accepts a valid Host token, rejects tampered/expired tokens, with no
  network/DB access.
- Snapshot/E2E: Host chrome renders identically before vs. after consuming the package.
- Package build: CI publish step produces an installable, version-tagged artifact.
