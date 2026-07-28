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

## Delivered (2026-07-25, ha-dashboard#15, branch `feature/slice-6-static-prefix-migration` in
`ha-dashboard`)

Shipped as designed. `organizeme-chrome` bumped to `chrome-v0.18.0`. `app/main.py` now mounts
`app/static` twice at the same directory: the existing bare `/static` mount (route name `"static"`)
and the new `static_mount_path("ha-dashboard")` prefix (route name `"static-prefixed"`) — no route-
name collision to work around here, unlike `doc-library`'s slice, since this app's bare mount
already had a distinct name from the start. Template/code audit reconfirmed clean, as expected — no
hardcoded `/static/...` references beyond the mount itself. New `tests/test_static_mount.py` covers
both mounts: route registration, real non-empty content served at the prefixed path, and a byte-
identical check between bare and prefixed.

One real deviation from the plan: implementing the canary step surfaced a bug in `organize-me`'s
`verify_static_routing.py` (the shared Slice 3 verification script) — its `--direct-url` addition
(added specifically to support this slice, `organize-me#263`) initially still compared against the
shared domain unconditionally, but pre-traffic-flip the shared domain is still 100% on the *old*
revision (the entire point of checking before the flip), so the one scenario the flag exists for was
structurally guaranteed to fail. Code review caught this before it reached production use. Fixed:
`--direct-url` mode instead compares the canary revision's new prefixed mount against its own bare
mount (both point at the same on-disk directory during the dual-mount transition window) — a
self-contained check with no dependency on the shared domain having cut over yet. That fix also
caught and corrected a masked test regression (a hand-rolled `verify_app` stub whose signature drifted
out of sync with a new kwarg, silently no longer exercising the scenario its own docstring claimed).

Deployed via the documented canary process, not the normal merge-to-main path:
- Built the migration branch's image via Cloud Build (`gcloud builds submit`) — no local Docker
  available in this environment — tagged
  `northamerica-northeast1-docker.pkg.dev/gen-lang-client-0791944342/ha-dashboard/app:canary-9697030`.
- `gcloud run deploy ha-dashboard-prod --no-traffic --tag=canary-slice6` produced revision
  `ha-dashboard-prod-00011-yom`, reachable directly at
  `https://canary-slice6---ha-dashboard-prod-n7cbjtsj5a-nn.a.run.app`, serving 0% of traffic.
- `verify_static_routing.py --env prod --direct-url <canary URL> ha-dashboard` (the fixed version)
  reported the canary's prefixed and bare mounts byte-identical (19,113 bytes) before any traffic
  reached it.
- Flipped traffic with `gcloud run services update-traffic ha-dashboard-prod --to-latest` —
  confirmed 100% on the new revision via `gcloud run services describe`.
- Manual visual check of `organizeme.russcoopersoftware.com/ha-dashboard` post-flip: renders fully
  styled (chrome sidebar, tile cards, icons, fonts all correct) — the incident is resolved.
- `verify_static_routing.py --env prod ha-dashboard` (no `--direct-url`, the standard check)
  re-run post-flip: shared domain and direct Cloud Run URL byte-identical (19,113 bytes) at
  `/ha-dashboard/static/css/app.css`.
- Only then merged `ha-dashboard#16` to `main`, which re-ran the normal `deploy.yml` pipeline
  (smoke-test + deploy-prod) against the now-verified code — redundant with the manual canary
  deploy but harmless, since it deploys the identical already-verified source.

One suggested improvement from code review filed as a follow-up, not blocking:
[ha-dashboard#17](https://github.com/rustycoopes/ha-dashboard/issues/17) (the new static-mount HTTP
tests require a live database via the `client` fixture even though they never touch it — a
pre-existing repo-wide pattern, not unique to this slice).

### Follow-up delivered (2026-07-27, ha-dashboard#17, branch `fix/static-mount-tests-no-db` in
`ha-dashboard`)

Added a `no_db_client` fixture to `tests/conftest.py` — a plain `ASGITransport(app=app)` client with
no `get_db` override and no `db_session` dependency — and switched `test_static_mount.py`'s two
HTTP-level tests plus `test_health.py`'s test onto it. All four now run without any reachable
`DATABASE_URL`. `code-review-master` and `code-quality-guardian` both reviewed the change and raised
no blocking issues.
