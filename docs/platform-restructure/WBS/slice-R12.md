# Slice R12 — Production Cutover

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The restructured platform live in production as a standard coordinated deploy — every
existing user logs in and sees their pre-existing data intact, with no maintenance window.

## What to build

Repeat the QA cutover in production. Because the database schemas were separated **in place** (R1)
and no data physically moves, this is a standard coordinated deploy — not a scheduled-downtime data
migration. Rollback is a routine Cloud Run revision / URL-map revert.

## Includes
- Provision the production Load Balancer, URL map, Serverless NEGs, and Google-managed cert for
  `organize-me.app` (prod), mirroring R5's QA setup.
- Apply the `host` + `event_creator` schema separation to the **production** database (the same
  metadata-only `ALTER TABLE … SET SCHEMA` proven in QA), if not already applied.
- Deploy the production Host (`organizeme-prod`, repurposed) and `event-creator-prod` services.
- Point the production URL map at both services per the app-registry; cut DNS live to the prod LB.
- Post-cutover verification against the Success Metrics.

## Design notes
- **No data migration:** `SET SCHEMA` is metadata-only; existing users, storage connections,
  prompts, and processing history stay exactly where they are. This is the whole reason the PRD
  calls the cutover a standard deploy, not a downtime event.
- **Rollback:** additive schema change (not destructive) + no data movement ⇒ rollback = revert the
  LB URL map or roll back a Cloud Run revision. No data reversal required.
- Confirm `E2E_TEST_MODE` is **never** set on any prod service.
- Post-cutover, watch for the lagging Success-Metric indicators (session/login friction, regressions)
  over the following 2–4 weeks.

## Blocked by
- R11 (QA cutover fully green — the P0 gate).

## Acceptance criteria
- [ ] Production LB + URL map + managed cert serve `https://organize-me.app` routing to both prod
      services.
- [ ] Every existing user can log in post-cutover and see their pre-existing data (events,
      processing history, settings) intact.
- [ ] No maintenance window was required; no data was migrated.
- [ ] A rollback path (URL-map revert / Cloud Run revision rollback) is verified available.
- [ ] Success-Metric leading indicators confirmed in prod immediately post-cutover.

## Testing
- Smoke test in prod: log in as a real pre-existing account; confirm events/history/settings present.
- Confirm an Event Creator prod deploy needs no Host redeploy.
- Monitor for 2–4 weeks against the lagging Success Metrics (0 session friction, 0 regressions).
