# OrganizeMe Platform Restructure — PRD

**Version:** 2.0
**Date:** 2026-07-10
**Status:** Implemented — all slices (R0–R13) shipped and the P0 requirements below are live in
production; see `docs/changelog.md` for the slice-by-slice record. Retained as the structural
rationale/requirements record, not as a forward-looking proposal.

**Relationship to other docs:** [`docs/features/original-organize-me/prd.md`](prd.md) captures the *functional* requirements of the event-extraction product (dashboard, upload, processing, prompt, notifications, etc.) as it exists today. This document governs the *structural* restructuring of that same functionality into a multi-repo, multi-application platform. `docs/features/original-organize-me/prd.md` doesn't change — it becomes the functional spec for the **Event Creator** application described here. `docs/features/original-organize-me/technical-approach.md` remains the technical reference for today's single-repo build and will be superseded by per-repo technical-approach docs once implementation begins.

---

## Problem Statement

OrganizeMe is a single application in a single repository, where one codebase owns both the "chrome" every page shares (login, session, sidebar nav, profile, settings) and the one piece of business functionality that exists today (message-to-calendar-event extraction). The user — sole product owner and maintainer — wants to build several more, functionally unrelated and reasonably complex capabilities over time. Continuing to add each one into today's single codebase means every feature area shares one deploy and one growing ball of coupled code, with no way to build, test, ship, or roll back one capability independently of another.

## Goals

1. **Extract shared chrome into a standalone Host application** ("OrganizeMe") that owns authentication/session, profile management, the settings shell, and sidebar navigation — independent of any specific feature.
2. **Achieve full functional parity** for today's event-extraction functionality after it moves into a new, separately-repo'd application, **Event Creator** — no user-visible behavior change.
3. **Establish a repeatable, documented pattern** for how a hosted application contributes a sidebar section and a settings tab to the Host, so a future second app can be added via a new repo + a Host config change alone.
4. **Preserve single sign-on**: log in once, at the Host; every hosted app honors that session automatically.
5. **Cut over existing production users and data to the new structure with zero data loss and zero downtime**, as a standard coordinated deploy (not a data migration — see Design Tenets).

## Non-Goals

- **Building a second hosted app in this phase.** The add-an-app pattern is documented, but proven for real only once a second app exists. *Deferred as a follow-on initiative to keep this phase to "extract + cut over."*
- **Per-user app entitlements/access control.** Every user sees every installed app. *No current use case; adds a permissions model nobody needs yet.*
- **A runtime "app marketplace" or admin UI for installing apps.** Installing an app is a Host config change + redeploy. *Matches a static, single-operator platform — no admin tooling to build.*
- **New Event Creator functionality.** This is a structural move, not a feature-enhancement initiative.
- **Physical infrastructure isolation per app** (separate GCP projects, separate database instances). *See Design Tenets — deliberately shared.*
- **Event Creator as an independently browsable site.** The Host is the sole public entry point and sole renderer of the chrome; Event Creator is never reached directly by users. *See Design Tenets.*
- **Native mobile apps.** Unchanged from the original PRD.

## Design Tenets

These two principles apply to Event Creator now and to every future hosted app — they're settled architecture, not open questions:

1. **Shared infrastructure, logical separation.** One GCP project, one database instance, one shared QA environment, one shared production environment — used by the Host and every hosted app alike. Separation is enforced by service boundaries (separate Cloud Run service per app, separate repo and CI/CD pipeline per app, separate database tables/schema per app), never by duplicating infrastructure. A new hosted app doesn't get its own project or database — it gets its own tables and its own deploy pipeline within the shared platform.
2. **Host owns identity and presentation; hosted apps trust, don't verify.** The Host is the single point of authentication (email/password, Google OAuth, sessions) and the single renderer of the persistent chrome (sidebar, header). It sits in front of every hosted app under one shared domain, forwarding each request with a Host-asserted, trusted user identity. Hosted apps never implement login, session verification, or their own copy of the navigation shell — they render content-only pages that the Host wraps, and they trust the identity the Host hands them.

## User Stories

### Platform / End User

1. As a user, I want to log in once at OrganizeMe, so that I can use every hosted application without signing in again per app.
2. As a user, I want a persistent left sidebar with a heading per installed application and that application's own sub-items beneath it, so that I can navigate within and across applications from one place.
3. As a user, I want every page — including each hosted app's own content, not just the shared sidebar/header — to look and feel like one consistent product, so the platform doesn't read as several apps bolted together.
4. As a user, I want a single Profile page (name, email, phone, password, dark/light mode) that applies platform-wide, so I manage my identity once, not once per app.
5. As a user, I want a single Settings page whose tabs are organized per installed application, so each app's configuration lives in a predictable, consistent place.
6. As a returning user, I want my existing account, storage connection, prompt, and historical events/processing runs all present and working immediately after the platform cuts over, so the restructuring is invisible to me.

### Event Creator User (today's functionality, unchanged)

7. As a user, I want the Dashboard, Upload, Processing, Logs, and Prompt pages to work exactly as they do today.
8. As a user, I want the Storage, Notifications, and Preferences settings — today under one Settings page — to appear as Event Creator's tabs within the platform's shared Settings page.

### Platform Operator (the user, as maintainer/deployer)

9. As the operator, I want Host and Event Creator in separate git repos with independent CI/CD, so I can build, test, and deploy one without touching the other.
10. As the operator, I want a documented, repeatable recipe for how a hosted app declares its sidebar section and settings tab to the Host, so adding a future app is a known process, not a bespoke integration.
11. As the operator, I want the cutover to require no database migration — because the database doesn't move — so the highest-risk part of a typical migration (data loss, reconciliation) doesn't apply here.
12. As the operator, I want confidence, via an automated test suite exercising the real Host↔Event Creator boundary, that the split introduced no regressions, verified in QA before any production cutover deploy.

## Requirements

### Must-Have (P0)

**Host — identity & session**
- The Host owns registration, login (email/password + Google OAuth), logout, password reset, and account deletion, per `docs/features/original-organize-me/prd.md`'s Authentication & Account Management stories.
- Acceptance: a user authenticated at the Host is recognized by Event Creator with no separate login step; logging out at the Host ends the session for Event Creator too.

**Host — Profile**
- The Host owns the Profile page (name, email, phone, dark/light mode, account deletion), per `docs/features/original-organize-me/prd.md`'s Profile & Preferences stories.
- Acceptance: profile changes made at the Host are immediately available to Event Creator (e.g. phone number for SMS).

**Host — chrome & Settings shell**
- The Host is the sole renderer of the persistent sidebar and header, and of the Settings page shell. Hosted apps never render their own copy of either.
- Installed apps, their sidebar heading/sub-items, and their settings tabs are defined by static Host-side configuration (not runtime self-registration).
- Settings has no Host-owned tab in v1 — it's purely a composition of hosted-app tabs (today: Event Creator's Storage, Notifications, Preferences). Anything Host-level belongs on Profile instead.
- Acceptance: adding Event Creator's sidebar section and settings tabs requires only a Host config entry, no Event Creator UI-shell code.

**Host → hosted app routing & trust**
- The Host and every hosted app sit under one shared domain; the Host routes requests to the correct app based on path.
- Every request the Host forwards to a hosted app carries a Host-asserted, trusted user identity; the hosted app relies on it without independently verifying login (per Design Tenet 2).
- Hosted apps render content-only pages (no chrome) that the Host wraps.
- Acceptance: Event Creator's pages never implement or check session/login state themselves, only "which user is this."

**Event Creator — functional parity**
- All existing functionality from `docs/features/original-organize-me/prd.md` — excluding Authentication & Account Management, Profile & Preferences (dark mode), and the sidebar shell, which move to the Host — is rebuilt in the Event Creator repo with no user-visible behavior change.
- Acceptance: every `docs/features/original-organize-me/prd.md` user story 13–52 continues to pass its existing/equivalent acceptance criteria through the new structure.

**Repo, infra & deployment structure**
- The existing `organize-me` repo is repurposed as the **Host**: event-extraction-specific code is removed, leaving auth/profile/settings-shell/nav-shell. **Event Creator** is a new repo, built fresh.
- Both deploy as separate Cloud Run services within one shared GCP project, sharing the database instance, Secret Manager, and Artifact Registry (per Design Tenet 1) — one shared QA environment, one shared production environment.
- Each repo has its own CI/CD pipeline, deployable independently.
- Acceptance: a change merged to Event Creator's main branch deploys without a Host build, deploy, or code change (and vice versa).

**Data**
- Host and Event Creator share the existing database instance. Host owns `users`/`oauth_accounts`; Event Creator owns its existing tables (storage configs, prompts, processing runs/steps, events), referencing the Host's user ID as a plain value — no cross-app table access, no data migration required.

**Cutover**
- Event Creator is built and fully verified in QA — including an automated test suite exercising the real Host↔Event Creator boundary (login at Host → session honored by Event Creator; Host-owned Profile field → reflected where Event Creator depends on it) — before any production deploy.
- Production cutover is a standard coordinated deploy of the new Host + Event Creator, not a scheduled-downtime event: no database migration is required (data doesn't move), and rollback is a standard Cloud Run revision rollback if issues surface post-deploy.
- Acceptance: every existing user can log in post-cutover and see their pre-existing data (events, processing history, settings) intact, with no maintenance window required.

### Nice-to-Have (P1)

- **Shared styling foundation**: Host and Event Creator (and future apps) consume one shared visual design system/theme config, rather than each repo independently maintaining its own copy that can silently drift. **Done (R3):** the `organizeme-chrome` package bundles the Tailwind/DaisyUI theme config alongside the chrome templates and app-registry, published as a pinned git-tag dependency.
- A written "how to add a hosted app" playbook documenting the Host config steps and the sidebar/settings contribution pattern Event Creator establishes. **Done (R13):** [`host-integration-guide.md`](host-integration-guide.md) (the slice-by-slice log) and [`how-to-add-a-hosted-app.md`](how-to-add-a-hosted-app.md) (the condensed, forward-looking playbook).
- A cleanup plan for removing leftover event-extraction code from the Host (`organize-me`) repo once Event Creator is verified stable in production — not a full repo retirement, since `organize-me` *is* the Host going forward. **Done (R13, issue #168).**

### Future Considerations (P2)

- Per-user app entitlements (explicit non-goal for this phase; the contribution model shouldn't preclude adding this later).
- A second hosted application — the first real test of the repeatable-pattern goal, including whether it needs its own notification framework (today's SMS/email toggles are deliberately Event-Creator-specific).
- Dynamic self-registration of hosted apps, upgrading from static Host config, if adding apps ever becomes frequent enough that a Host redeploy per app feels heavy.

## Success Metrics

**Leading indicators (checked before/at cutover)**
- 100% of `docs/features/original-organize-me/prd.md` user stories 13–52 pass their acceptance criteria against the new structure.
- The Host↔Event Creator boundary test suite is green in QA before the production cutover deploy.
- Event Creator deploys (build → QA → prod) at least once with zero changes to, or redeploys of, the Host.

**Lagging indicators (checked 2-4 weeks post-cutover)**
- 0 user-reported session/login friction (e.g. asked to log in twice, or losing session between areas that used to be one app).
- 0 regressions filed against previously-working Event Creator functionality.
- Adding a future hosted app's nav entry and settings tab is, per the P1 playbook, a single Host config change + redeploy — validated by a dry run or the actual second app.

## Open Questions

- **Shared styling foundation mechanism** — how Host and Event Creator actually share one visual design system (a shared package, a git submodule, copy-at-scaffold-time, etc.) — **Resolved (R3):** a shared `organizeme-chrome` package, published as a pinned git-tag dependency; see the P1 item above.

## Timeline Considerations

- No external hard deadline; user-initiated architectural work.
- Suggested phasing:
  1. This PRD.
  2. Lightweight technical design — resolve the shared-styling-mechanism question and turn the settled architecture decisions above into an implementation plan (exact routing/proxy config, trusted-identity header format, etc.).
  3. Strip `organize-me` down to the Host (keep auth/profile/settings-shell/nav-shell, remove event-extraction code).
  4. Build the Event Creator repo, migrating functionality, verified against `docs/features/original-organize-me/prd.md`'s acceptance criteria plus the new Host↔Event Creator boundary test suite.
  5. QA verification of the full boundary flow (P0 gate).
  6. Coordinated production deploy — a standard deploy, not a scheduled-downtime event.
  7. Post-cutover verification against Success Metrics, then the P1 cleanup pass on the Host repo.
- Because production already carries real user data, no step from #3 onward touches production until the cutover deploy in #6 — QA is the proving ground throughout.
