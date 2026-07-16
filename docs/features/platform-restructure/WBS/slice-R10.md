# Slice R10 — Host↔Event Creator Boundary E2E Test Suite

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** An automated test suite that exercises the *real* Host↔Event Creator boundary, giving
confidence the split introduced no regressions — the P0 evidence gate before any cutover.

## What to build

Add an automated suite (Playwright + integration tests, extending the existing `e2e/` pattern)
that drives the two services through the Load Balancer exactly as a user would, asserting the
seams the split created hold:

1. **Single sign-on:** log in once at the Host → the session is honoured by Event Creator with no
   second login; logging out at the Host ends the Event Creator session too.
2. **Host-owned data reaching Event Creator:** a Host Profile field (e.g. phone number) set at the
   Host is reflected where Event Creator depends on it (SMS notifications).
3. **Trust boundary:** Event Creator rejects requests with no/expired/tampered JWT (redirect to
   Host login).

## Includes
- Playwright specs added to the shared `e2e/` suite, run against the QA shared-domain setup.
- Cross-service assertions: cookie issued by Host is accepted by Event Creator; account deletion
  at Host cascades to Event Creator data (DB-level `ON DELETE CASCADE` from R1).
- Wire the suite into Event Creator's CI (run against a QA Host), per the design's CI/CD note.

## Relevant files
- `e2e/` (existing Playwright tooling) — new boundary specs.
- Event Creator CI pipeline — add the boundary-suite job against QA.

## Design notes
- This suite is explicitly the PRD's P0 gate: it must be **green in QA before the production
  cutover deploy** (R11/R12).
- Google OAuth login stays excluded from headless E2E (unreliable against Google's real consent
  screen) — covered by backend tests, as today.
- The suite exercises the *real* boundary (through the LB), not mocked services — that's the point.

## Blocked by
- R7, R8, R9 (Event Creator must have the features whose boundary behaviour is being tested).

## Acceptance criteria
- [ ] A boundary E2E suite runs in CI against the QA shared-domain setup.
- [ ] It asserts: login-once SSO, logout propagation, Host Profile field → Event Creator
      dependency, and JWT-trust rejection of bad tokens.
- [ ] It asserts account deletion at the Host removes the user's Event Creator data.
- [ ] The suite is green in QA.

## Testing
- The suite *is* the test deliverable; success = it passes against QA and fails loudly on a
  deliberately broken boundary (e.g. wrong signing key).
