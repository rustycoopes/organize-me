# Slice R6 — Event Creator Scaffold + SSO-Trust Tracer Bullet

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** A new `event-creator` repo + Cloud Run service that renders one real page
(`/dashboard` shell) wrapped in the shared chrome, trusting the Host-issued JWT with no login
logic of its own — the first end-to-end proof of the Host↔Event Creator boundary.

## What to build

Stand up Event Creator as an independent service and prove the whole boundary with the thinnest
possible vertical slice: a user logs in at the Host, navigates to `/dashboard`, and the Load
Balancer routes that request to the **Event Creator** service, which verifies the Host JWT
(signature + expiry only, via the R3 helper), extracts the user id, and renders a full page —
chrome from the shared package + a placeholder Dashboard body — with **no** call back to the Host.

This is the tracer bullet: minimal content, but every integration layer (routing, SSO trust,
shared chrome, per-app schema/Alembic, independent deploy) is exercised.

## Includes
- New `event-creator` git repo with its own CI/CD (independent build/test/deploy pipeline).
- Consumes the R3 shared chrome/theme package (pinned) + the JWT-verify helper.
- Owns the `event_creator` schema with its **own** Alembic history (`version_table_schema =
  event_creator`), connecting to the same shared Postgres instance as the Host.
- One content-only page: `GET /dashboard` → verify JWT → extract `user_id` → render chrome +
  placeholder Dashboard body. **No** login/session/registration code.
- New Cloud Run service `event-creator-qa`; attached to the R5 URL map's second NEG so
  `organizeme.qa.russcoopersoftware.com/dashboard` routes here.
- Reads the JWT signing secret from Secret Manager (per R4), same key as the Host.

## Relevant files (new repo)
- Pipeline mirrors the Host's `.github/workflows/` shape (build → test → deploy to Cloud Run).
- App skeleton mirrors the Host's FastAPI + Jinja layout, minus auth/chrome (those come from the
  package).
- Alembic config with `version_table_schema = event_creator`.

## Design notes
- **Trust, don't verify login:** Event Creator only answers "which user is this," never "is this a
  valid session" beyond the JWT signature/expiry check. No fastapi-users, no password handling.
- **No server-to-server call** to the Host at request time — identity comes entirely from the
  cookie's JWT.
- Independent deployability is part of the acceptance: an Event Creator deploy must not require a
  Host build or redeploy.
- The `event_creator` schema/tables already exist (moved in R1); this repo adopts them as its own
  and takes over their Alembic history going forward.

## Blocked by
- R3 (shared chrome package + JWT-verify helper), R4 (domain-scoped cookie + Secret Manager),
  R5 (Load Balancer + URL map to route `/dashboard` to this service).

## Acceptance criteria
- [ ] `event-creator` repo exists with an independent CI/CD pipeline that deploys
      `event-creator-qa` with **no** Host build/redeploy.
- [ ] Logging in at the Host, then requesting `organizeme.qa.russcoopersoftware.com/dashboard`, is served by the Event
      Creator service and renders a full page (shared chrome + placeholder body) for the correct user.
- [ ] Event Creator verifies the Host JWT (signature + expiry) with no network call to the Host and
      no login/session code.
- [ ] Event Creator owns the `event_creator` schema with its own Alembic history; `upgrade head`
      is clean and independent of the Host's history.
- [ ] An unauthenticated request to `/dashboard` is rejected/redirected to the Host login.

## Testing
- Boundary happy-path: Host login → `/dashboard` on Event Creator renders for the right user.
- Negative: no/expired/tampered cookie → access denied (redirect to Host login).
- Independent-deploy: push to `event-creator` main deploys without touching the Host.
