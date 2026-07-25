# Slice 3 — `organize-me`: LB static-asset path rules + QA/prod regen + verification script

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Both QA's and prod's live Load Balancer URL maps have a static-asset path rule for
every hosted app, and an operator can verify (before or after any app migrates) whether the shared
domain is serving each app's own static assets correctly — with zero effect on currently-live
traffic, since nothing requests the new prefixes until Slices 4-6 ship.

## What to build

Bump `organize-me`'s own `organizeme_chrome` pin to the version from Slice 2. Extend
`generate_path_rules()` in `infra/gcp_lb/generate_url_map.py` to emit one additional `PathRule` per
app — `f"{static_mount_path(app.service_name)}/*"` routed to that app's existing backend service —
alongside its existing `nav`/`api_prefixes`-derived rules. Emit only the `/*` wildcard form, not the
bare-prefix exact-match GCP's `api_prefixes` handling adds for a different reason (TDD, "Load
Balancer path rule generation") — add a code comment explaining why this rule doesn't need that,
since the neighboring logic does the opposite for a similar-looking case.

Before running `provision.sh`/`provision-prod.sh`: `gcloud compute url-maps describe --format=yaml`
each live URL map and diff it against what the generator would currently produce from the
*pre-this-slice* registry state, to catch any out-of-band manual changes before they'd be silently
overwritten (`gcloud compute url-maps import` fully replaces the resource, it doesn't merge).

Run `provision.sh` (QA) and `provision-prod.sh` (prod) to push the updated URL maps. Explicitly diff
the two scripts' new static-rule-related changes against each other as a review step before merging
— this script pair has drifted out of sync once before (`doc-library` needed a follow-up fix to add
its prod block, per `infra/gcp_lb/README.md`).

Build the verification script (new file under `infra/gcp_lb/`): for a given app, fetch a known
static asset via the shared domain and via that app's own direct Cloud Run URL, assert byte-identical
content. Before comparing, assert the target Cloud Run service is serving 100% traffic from a single
revision (fails loudly otherwise, per TDD). The script only checks apps explicitly passed to it —
it's the caller's job (this slice's own manual run, and each of Slices 4-6) to only check apps that
have actually migrated, since the new rules for not-yet-migrated apps are inert by design and would
otherwise report a false failure.

## Design notes

TDD, "Load Balancer path rule generation," "Verification script," and "Operational safety steps for
the LB regen" cover this slice's full design. Requires Slice 1's fix already live — otherwise
regenerating QA's map fails the same way it does today.

## Blocked by

- [Slice 1](slice-1-ha-dashboard-qa-registry-fix.md) — QA's URL map can't be safely regenerated
  until the `ha-dashboard`/QA mismatch is fixed.
- [Slice 2](slice-2-chrome-static-mount-helper.md) — needs `static_mount_path()` to exist in a
  released chrome version.

## Acceptance criteria

- [ ] `organize-me`'s own chrome pin is bumped to Slice 2's version.
- [ ] `generate_url_map.py`'s output includes a static-asset path rule per hosted app, for both `qa`
      and any `-prod` suffix generation.
- [ ] Live QA and prod URL maps are updated (`gcloud compute url-maps describe` on each shows the
      new rules) with no observable change in behavior for any existing route (verify the existing
      smoke checks — `curl .../login`, `curl .../dashboard`, `curl .../doc-library`,
      `curl .../ha-dashboard` — still succeed identically to before this slice).
- [ ] The verification script exists, runs against at least one app (expected result: still a
      mismatch, since no app has migrated yet — this slice doesn't fix any app's actual bug, it
      only makes the infrastructure ready for Slices 4-6 to use).

## Testing

Extend `tests/test_url_map_generator.py` with cases asserting the new static-asset rule is generated
per app via the shared helper (not independently reconstructed logic in the test), per TDD's Testing
Approach. The pre-import diff check and the `provision.sh`/`provision-prod.sh` review step are
operational, not unit-testable — they're acceptance criteria for the person running this slice, not
automated coverage.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
