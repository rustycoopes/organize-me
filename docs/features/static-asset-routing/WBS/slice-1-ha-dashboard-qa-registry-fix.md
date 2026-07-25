# Slice 1 — Fix `ha-dashboard`/QA registry-backend mismatch (prerequisite)

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Regenerating QA's Load Balancer URL map no longer references a GCP backend service
that doesn't exist, unblocking every later slice in this feature that touches QA's LB config.

## What to build

`app/core/registry.py`'s `APPS` list includes `ha-dashboard` unconditionally. `generate_path_rules()`
(and everything downstream of `list_apps()` in `infra/gcp_lb/generate_url_map.py`) has no concept of
"this app isn't deployed in this environment" — it emits a path rule for every app in the registry,
every time, regardless of which environment (`qa` vs a `-prod` suffix) is being generated. But
`ha-dashboard` deliberately has no QA Cloud Run service and no QA backend service
(`docs/adr/ha-dashboard-no-qa-environment.md`) — confirmed by reading `provision.sh`, which has no
`ha-dashboard` block at all (only `provision-prod.sh` does). Running
`uv run python -m infra.gcp_lb.generate_url_map` (QA, the default) today emits a path rule pointing
at `global/backendServices/ha-dashboard-backend`, which was never created — `gcloud compute url-maps
import` will reject the whole map when this is actually re-run.

Add environment-awareness so the QA generation path skips any app with no QA deployment. The exact
mechanism is an implementation choice for this slice (an environment-gating field on `AppEntry`, a
filter list passed into `generate_path_rules()`, or similar) — pick whichever fits the existing
`generate_path_rules(apps, *, backend_suffix)` signature most naturally, since that function already
takes an explicit `apps` list in its tests today.

## Design notes

This bug is pre-existing and unrelated to this feature's own core design — it was surfaced by the
microservices-architect review during `/to-design` because this feature's rollout (Slice 3) requires
safely re-running `provision.sh` for the first time since `ha-dashboard` was registered. See TDD,
"Architecture at a Glance" and Open Questions #1 for the full context. Prod generation is unaffected
(`provision-prod.sh` already has a full `ha-dashboard` block), so this is a QA-only gap.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] Generating QA's URL map (`uv run python -m infra.gcp_lb.generate_url_map`, no args) no longer
      emits any path rule referencing `ha-dashboard-backend` (or any other backend service that
      doesn't exist in QA).
- [ ] Generating prod's URL map (`uv run python -m infra.gcp_lb.generate_url_map prod`) still
      includes `ha-dashboard`'s existing path rules, unchanged.
- [ ] The mechanism generalizes — a future app with no QA environment doesn't need a one-off special
      case in the generator, it uses the same gating mechanism this slice introduces.

## Testing

Extend `tests/test_url_map_generator.py` (pure-Python, given a list of `AppEntry` objects, asserting
on `generate_path_rules()`'s output) with a case asserting an app marked as QA-unavailable produces
no path rule when generating for the `qa` environment, but does produce one when generating for
`prod`. Follows the same test shape already used for `HOST_PATHS`/`api_prefixes` coverage in that
file.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-25, issue #257, branch `fix/ha-dashboard-qa-registry-mismatch`)

Shipped as planned: `AppEntry` gained a `qa_available: bool = True` field
(`packages/chrome/src/organizeme_chrome/registry.py`), `app/core/registry.py` sets it `False` on the
`ha-dashboard` entry, and `generate_path_rules()` (`infra/gcp_lb/generate_url_map.py`) skips any
QA-unavailable app when generating the unsuffixed (QA) URL map — inferring "this is QA" from
`backend_suffix == ""`, the same convention `__main__` already used. Verified manually:
`uv run python -m infra.gcp_lb.generate_url_map` (QA) emits zero `ha-dashboard` references;
`... generate_url_map prod` still emits `ha-dashboard`'s full path set unchanged.

One thing the plan didn't anticipate: `packages/chrome/src/organizeme_chrome/registry_client.py`'s
`_parse_apps()` (the client-side JSON parse every other hosted app uses to fetch the Host's
registry) wasn't reading `qa_available` off the wire at all, so a fetching consumer's cached
`AppEntry` would have silently reset `qa_available` back to its default `True` regardless of what
the Host configured. Caught by the pre-existing round-trip test
(`tests/test_internal_registry.py::test_response_round_trips_through_the_client_side_dataclasses`)
failing once `ha-dashboard.qa_available` was set to `False`; fixed alongside the main change, with
its own regression test added in `packages/chrome/tests/test_registry_client.py`.

`organizeme-chrome` bumped `0.17.0` → `0.17.2` (`chrome-v0.17.1` added the field, `chrome-v0.17.2`
fixed the round-trip gap above); this repo's own pin was bumped to match. Bumping past the
already-tagged-but-unconsumed `chrome-v0.17.0` (PR #252's stylesheet cache-busting fix, tagged but
never picked up by this repo's own pin) was unavoidable — the git-tag dependency always resolves the
full tagged source tree, not just this slice's diff — so this repo's chrome consumer now also
transparently picks up `CHROME_ASSET_VERSION` cache-busting with no Host-side code change required.

Code review (code-review-master, code-quality-guardian) found no blocking issues. One non-blocking
design suggestion — making `generate_path_rules()`'s QA-vs-other-env detection an explicit parameter
instead of inferring it from `backend_suffix == ""` — filed as
[#258](https://github.com/rustycoopes/organize-me/issues/258) rather than implemented here, since
current behavior is correct for the two environments (`qa`, `prod`) that exist today.
