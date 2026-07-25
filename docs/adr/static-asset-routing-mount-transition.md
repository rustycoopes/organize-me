# Keep each app's old bare `/static/*` mount alive for one release during migration

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`static-asset-routing`](../features/static-asset-routing/TDD.md)

## Context

Each hosted app's migration changes its FastAPI static mount from bare `/static/*` to its own
prefixed path (`/<service_name>/static/*`) and updates the one shared template reference
(`chrome_base.html`'s stylesheet link, via the new `CHROME_STATIC_PREFIX` Jinja global) to match.
This repo's deploy pattern (confirmed by reading `deploy.yml`) uses plain `gcloud run deploy` with
no traffic-splitting or canary flags — a new revision must pass health checks before receiving any
traffic, and the old revision drains in-flight requests but receives no new ones. That makes the
server-side cutover for a given app effectively atomic: there's no window where one Cloud Run
revision serves old-mount responses while another serves new-mount responses for the same app.

The residual risk is client-side, not server-side: a browser tab that already rendered HTML from the
*previous* revision (with the old `<link href="/static/css/app.css">`) and stays open across the
deploy will, on its next asset fetch, request the now-unmounted bare path. Once that app's old mount
is removed, the Load Balancer falls through to `defaultService` (the Host) for that request — the
exact bug this feature exists to fix, reproduced for any tab that didn't get a fresh page load. This
matters disproportionately for `ha-dashboard`, a dashboard-class app users are likely to leave open
in a tab for extended periods, and which already has one confirmed live incident from this bug
class.

## Decision

Each app's migration deploy adds the new prefixed mount **and keeps the old bare `/static/*` mount
active**, both serving the same on-disk static directory, for one release. A fast-follow, low-risk
PR removes the old mount shortly after (the exact timing per app is left to `/to-wbs` to slice — see
the feature's TDD, Open Questions).

## Alternatives considered

- **Remove the old mount in the same deploy that adds the new one.** The static case for this is
  real: the old bare path was never reachable via the shared domain in the first place (every such
  request already fell through to the Host before this fix), so there's no shared-domain traffic to
  preserve compatibility with. But it ignores the direct-Cloud-Run-URL and stale-tab audiences: a
  tab that loaded before the deploy still requests the bare path directly against whatever backend
  the Load Balancer resolves it to, and once the old mount is gone, that resolves to the Host again
  — silently regressing to the exact symptom this feature fixes, just scoped to already-open tabs
  instead of every request. Rejected in favor of the one-release transition window, since the
  mitigation (two `app.mount()` calls pointing at the same directory, for one release) is
  inexpensive relative to the risk it removes.
- **Keep both mounts indefinitely, no planned removal.** Rejected: two live paths serving identical
  content forever is exactly the kind of routing ambiguity this feature exists to eliminate, even if
  harmless today — it should be closed out deliberately, not left open indefinitely by default.

## Consequences

- Each app's migration is technically two changes rather than one: the cutover deploy (dual mount)
  and a trivial follow-up removal deploy. `/to-wbs` needs to decide whether these are one slice with
  two commits or two slices per app.
- The verification script (TDD, Design Decisions) checking "shared domain serves this app's own
  assets" remains meaningful throughout the transition window, since the new prefix is what it
  checks — the old mount being alive doesn't affect that check either way.
- If the follow-up removal is forgotten for a given app, the cost is bounded and inert (an unused,
  harmless duplicate mount) rather than a live bug — a reasonable failure mode to leave unmitigated
  further than "flagged for `/to-wbs` to schedule."
