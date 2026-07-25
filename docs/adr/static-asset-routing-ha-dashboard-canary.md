# Roll out HA Dashboard's static-prefix migration via a no-traffic canary, not the standard QA-first path

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`static-asset-routing`](../features/static-asset-routing/TDD.md)

## Context

`doc-library` and `event-creator` each migrate to their new static-asset prefix through their
existing, independent per-repo CI/CD: a pull request deploys to that app's own QA Cloud Run service
first, gets verified there, and only reaches prod on merge to main. `ha-dashboard` has no QA
environment at all — no QA Cloud Run service and no QA Load Balancer entry — a prior, deliberate
decision (`docs/adr/ha-dashboard-no-qa-environment.md`). That means the "QA verified, then ship to
prod" safety net every other app's migration relies on doesn't exist for `ha-dashboard`; a standard
merge-to-main deploy would make prod, at 100% traffic immediately, the first live test of its new
mount path.

This is the one app in this feature's scope with a *confirmed, already-live* production incident
from the underlying routing bug (the shared prod domain serves the Host's CSS instead of
`ha-dashboard-prod`'s own — verified by direct byte comparison during this investigation). Its own
existing ADR already floats `--no-traffic` canary revisions as a future hardening option for this
specific app.

## Decision

`ha-dashboard`'s migration deploys with `gcloud run deploy --no-traffic`, gets verified directly
against its tagged revision URL using the feature's verification script (comparing that revision's
own static assets against the expected content), and only then has traffic flipped to it via
`gcloud run services update-traffic`. This replaces the immediate-100%-traffic deploy the other two
apps get, specifically for this app's migration.

## Alternatives considered

- **Deploy the same way as `doc-library`/`event-creator`** (merge to main, immediate 100% traffic).
  Rejected: this app specifically has no QA dress rehearsal and already has a live incident from
  this exact bug class — treating it identically to the two apps that do have a QA safety net
  ignores the one asymmetry that matters most here.
- **Stand up a QA environment for `ha-dashboard` as a prerequisite**, so it can follow the standard
  path like the other two apps. Rejected as out of scope for this feature: reversing the prior
  deliberate no-QA-environment decision is a separate, larger decision with its own trade-offs (cost,
  infra) that shouldn't be bundled into a routing-gap fix. A one-time canary for this migration is a
  narrower, cheaper way to de-risk this specific deploy without relitigating that decision.

## Consequences

- `ha-dashboard`'s migration slice has an extra manual step (flip traffic after verifying the
  tagged revision) that the other two apps' slices don't — `/to-wbs` should call this out explicitly
  rather than templating all three apps' slices identically.
- This is a one-time mitigation for this specific migration, not a standing change to how
  `ha-dashboard` deploys going forward — future deploys of that app revert to its normal
  immediate-100%-traffic pattern unless a separate decision changes that.
