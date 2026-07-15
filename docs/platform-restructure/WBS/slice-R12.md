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
  `organizeme.russcoopersoftware.com` (prod), mirroring R5's QA setup. Point the production
  subdomain at the LB with a Squarespace **Custom A/AAAA record** (not Domain Forwarding).
- Apply the `host` + `event_creator` schema separation to the **production** database (the same
  metadata-only `ALTER TABLE … SET SCHEMA` proven in QA), if not already applied.
- Provision the production Cloud Tasks queue (`event-creator-pipeline-prod`) and its IAM grants
  via `event-creator`'s `infra/cloud_tasks/provision.sh prod` (the R11-redesign dispatch mechanism
  that replaced Celery/Redis — see `docs/adr/0001-event-creator-worker-cpu-throttling.md`). Not
  optional: without this, `event-creator-prod`'s upload/import endpoints will enqueue against a
  queue that doesn't exist, and the push endpoint's OIDC check has nothing to verify against —
  every processing run would fail immediately, invisibly to the LB-routing/login smoke tests
  below (they don't exercise the pipeline).
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
- Confirm prod stays on **request-based billing** (no `--no-cpu-throttling`, no `min-instances`)
  on both services — the R11 redesign's whole point was making this compatible with Cloud Run's
  default billing model; a regression back to instance-based billing here would silently
  reintroduce the cost problem the redesign solved.
- Post-cutover, watch for the lagging Success-Metric indicators (session/login friction, regressions)
  over the following 2–4 weeks.

## Blocked by
- R11 (QA cutover fully green — the P0 gate).

## Acceptance criteria
- [ ] Production LB + URL map + managed cert serve `https://organizeme.russcoopersoftware.com`
      routing to both prod services.
- [ ] Every existing user can log in post-cutover and see their pre-existing data (events,
      processing history, settings) intact.
- [ ] No maintenance window was required; no data was migrated.
- [ ] A rollback path (URL-map revert / Cloud Run revision rollback) is verified available.
- [ ] Production Cloud Tasks queue provisioned; a real upload in prod runs the pipeline to
      completion (SSE progress advances, events land, notification fires) — not just login/data
      checks, since a missing queue/IAM grant wouldn't surface any other way.
- [ ] Both prod services confirmed on request-based billing (no CPU-always-allocated flag).
- [ ] Success-Metric leading indicators confirmed in prod immediately post-cutover.

## Testing
- Smoke test in prod: log in as a real pre-existing account; confirm events/history/settings present.
- Pipeline smoke test in prod: upload a real file, confirm it processes to completion end-to-end.
- Confirm an Event Creator prod deploy needs no Host redeploy.
- Monitor for 2–4 weeks against the lagging Success Metrics (0 session friction, 0 regressions).
