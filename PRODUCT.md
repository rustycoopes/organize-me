# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: individuals coordinating household/life logistics — co-parents, caregivers, and small
business owners — who use the hosted applications (event extraction from chat exports, document
library, home-assistant-style dashboard). Secondary: the platform operator (the user, as sole
maintainer/deployer of a single-operator multi-tenant platform). Registration is open
self-service; every registered user sees every installed app (no per-user entitlements).

## Product Purpose

OrganizeMe is the **Host** of a multi-repo platform: it owns authentication/session (email+password
and Google OAuth), the Profile page, the Settings shell, and the persistent left-sidebar navigation
shared by every hosted application. It is the sole public entry point and the sole renderer of
chrome — hosted apps (Event Creator, Doc Library, HA Dashboard) render content-only pages that the
Host wraps, trusting a Host-asserted identity rather than implementing their own login. Success
means a user logs in once and experiences every hosted app as one consistent product, not several
apps bolted together.

## Positioning

Not a single-purpose SaaS tool but a personal/household "internal tools" platform: one identity,
one nav, one visual language, wrapping an evolving family of small, functionally unrelated
household-coordination apps that a neighboring single-app competitor (e.g. a dedicated calendar
app) could not truthfully claim to be.

## Operating Context

- Currently hosts: **event-creator** (WhatsApp/SMS chat export → calendar/task extraction via
  Gemini LLM: Dashboard, Upload, Processing, Logs, Prompt), **doc-library** (Doc Library),
  **ha-dashboard** (Home Assistant–style dashboard), and the Host's own Settings/Profile pages.
- Installed apps, their sidebar sections, and their settings tabs are static Host-side
  configuration (`app/core/registry.py`), not runtime self-registration.
- Shared infrastructure: one GCP project, one database instance, one shared QA/production
  environment; separation is per-repo/per-Cloud-Run-service, not per-infrastructure.
- The chrome (sidebar, header, page shell, shared components) ships as a separately-versioned
  package, `organizeme-chrome`, consumed by the Host and (eventually) styling other hosted apps.

## Capabilities and Constraints

- Auth: registration (open, self-service), Google OAuth + email/password login, password reset,
  account deletion (self-service, removes all data).
- Profile: name, email, phone (for SMS), dark/light mode toggle — platform-wide, applies to every
  hosted app.
- Settings: shared shell, tab-per-installed-app (no Host-owned tab today — Host-level items live
  on Profile).
- Class-based (DB-driven) dark mode, not OS-preference based.
- Undecided: no accessibility standard has been explicitly established for this product.

## Brand Commitments

- Product name **OrganizeMe** is finalized — not to be changed.
- Existing visual system ("Signal"): tokens defined in
  `packages/chrome/src/organizeme_chrome/static/css/tokens.css` — ink `#14161c`, paper `#f6f4ef`,
  flame `#ff4b33`, cobalt `#2f4b7c`, sage `#2f7d5c`; display face "Bricolage Grotesque", body
  "IBM Plex Sans", mono "JetBrains Mono". Original PRD called for a "Laravel-inspired aesthetic."
  This is being actively redesigned (see current request) — treated as prior-art evidence, not a
  binding constraint.

## Evidence on Hand

- `docs/features/original-organize-me/prd.md` — functional spec for Event Creator's product
  surface (now a separate hosted app, still governs its UI content).
- `docs/features/platform-restructure/platform-restructure-prd.md` — structural rationale for the
  Host/hosted-app split, the design tenets, and the chrome ownership model.
- `docs/host-integration-guide.md` — what a hosted app must do to plug into the Host.
- No customer testimonials, benchmarks, or pricing exist — do not fabricate any.

## Product Principles

1. One login, one nav, one visual language — the platform must never read as apps bolted together.
2. The Host owns presentation; hosted apps trust it and stay content-only.
3. Adding a hosted app is a config change, not a bespoke integration — the chrome must stay
   generic enough to keep that true.
4. Shared infrastructure, logical separation — visual and technical changes to the Host should not
   assume it can special-case a single hosted app's needs.

## Accessibility & Inclusion

No product-specific requirement established.
