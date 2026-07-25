# Slice 6 — `ha-dashboard`: migrate to prefixed static path (canary rollout)

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Resolves the confirmed, currently-live production incident — `ha-dashboard-prod`'s own
compiled CSS actually reaches the browser on the shared prod domain, instead of the Host's.

## What to build

Same core change as Slices 4-5 — bump `ha-dashboard`'s `organizeme_chrome` pin, change its static
mount to `static_mount_path("ha-dashboard")` while keeping the old bare mount alive for the
transition window, audit its own templates (already confirmed clean during `/to-design`) — but
deployed differently, since `ha-dashboard` has no QA environment
(`docs/adr/ha-dashboard-no-qa-environment.md`) and is the app with the confirmed live incident:

Deploy with `gcloud run deploy --no-traffic`. Run Slice 3's verification script directly against the
new tagged revision's URL (not the service's main URL, which is still serving the previous
revision at 100% traffic) to confirm the new mount serves correct content before any real traffic
reaches it. Only then flip traffic via `gcloud run services update-traffic`.

Same fast-follow note as Slices 4-5: old-mount removal is a documented follow-up, not part of this
slice's acceptance criteria.

## Design notes

[`static-asset-routing-ha-dashboard-canary`](../../../adr/static-asset-routing-ha-dashboard-canary.md)
covers why this app gets a different rollout than Slices 4-5. Once this ships and is confirmed
working, revisit `docs/adr/chrome-static-asset-cache-busting.md` per the PRD's Further Notes — the
incident that ADR was written for was very likely this routing bug, not cache staleness.

## Blocked by

- [Slice 3](slice-3-lb-static-rules-and-regen.md). Not blocked by Slices 4 or 5 — no technical
  coupling; this is the highest-priority app to fix given the live incident, but that's a priority
  choice, not a dependency (it could ship before or after the other two).

## Acceptance criteria

- [ ] `ha-dashboard`'s new tagged revision, hit directly (pre-traffic-flip), serves its own compiled
      CSS at `/ha-dashboard/static/css/app.css`.
- [ ] Slice 3's verification script, run against the tagged revision, reports byte-identical content
      to the expected build before traffic is flipped.
- [ ] After the traffic flip, the shared prod domain's `.../ha-dashboard` page renders with the
      correct colors, fonts, and layout (the exact symptom from the original incident report) —
      manual visual check.
- [ ] Slice 3's verification script, re-run post-flip against the service's normal URL, confirms the
      shared domain and the direct Cloud Run URL now serve byte-identical static assets.

## Testing

Same `TestClient`-based pattern as Slices 4-5, applied to `ha-dashboard`'s own test suite. The
canary/traffic-flip steps are operational and verified manually via the steps above, not covered by
automated tests.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
