# Derive each app's static-asset URL prefix from `service_name`, colocated with the registry

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`static-asset-routing`](../features/static-asset-routing/TDD.md)

## Context

Every hosted app on the platform (`event-creator`, `doc-library`, `ha-dashboard`) currently serves
its own compiled CSS and fonts from the identical bare path, `/static/*`. The shared domain's Load
Balancer can't express a per-app path rule for an identical path across apps, so every hosted app's
static-asset request silently falls through to the Host's backend. The fix requires each app's
static assets to live at a distinguishing URL prefix, `/<service_name>/static/*`.

That prefix is needed in (at least) two independent places that must never disagree: each app's own
FastAPI static mount (`main.py`), and the Load Balancer's URL-map generator
(`infra/gcp_lb/generate_url_map.py`, which already imports `AppEntry`/`list_apps` directly from
`organizeme_chrome.registry` for its existing `nav`/`api_prefixes`-derived rules). Two open
questions had to be resolved together: where does the prefix-computing code live, and where does the
prefix *value* come from — a new declared field, or something derived?

## Decision

Add one pure function, `static_mount_path(service_name: str) -> str`, to a new module colocated with
`registry.py` in the `organizeme_chrome` package (not `paths.py`, which is exclusively filesystem
paths into the installed package; not `assets.py`, which is cache-busting). `generate_url_map.py`
imports and calls this same function rather than reimplementing the one-line convention itself.

The prefix is derived purely from `service_name` — no new field on `AppEntry`. `service_name`
already does double duty as the GCP backend service name (`f"{service_name}-backend"`) and the
registry lookup key; deriving the URL prefix from it is the same coupling this field already
carries, applied once more, not a new kind of coupling. A `service_name` validator
(`^[a-z][a-z0-9-]*$`, enforced via `AppEntry.__post_init__`) makes the "URL-path-segment-safe"
assumption this now depends on explicit and enforced, rather than an implicit fact that happens to
be true today.

The function is pure and local — a function of `service_name` alone, computed without any registry
fetch or network call — the same category as `service_name` itself, or the way
`organizeme_chrome.assets.chrome_asset_version()` already reads a hosted app's own compiled CSS
straight off local disk rather than asking the Host for a cache-busting value. An app must be able
to determine its own static-asset prefix unconditionally, the same way it already knows its own
`service_name` and can already build its own compiled CSS, regardless of whether the Host is
reachable.

## Alternatives considered

- **Each call site independently hardcodes the `/<service_name>/static` convention** (no shared
  helper at all). Rejected: this is structurally the same shape of bug as the one being fixed — a
  URL-path fact known independently in two places with nothing forcing them to agree. Duplicating a
  one-line convention doesn't buy meaningful decoupling, since `generate_url_map.py` already depends
  on `organizeme_chrome.registry` for the actual app list; it just reintroduces the exact drift risk
  this feature exists to close.
- **Add an explicit `static_prefix` field to `AppEntry`**, declared per app in each app's own
  registry entry. Rejected: creates two independently-settable pieces of data (`service_name` and
  `static_prefix`) that happen to agree today but aren't forced to — the same drift risk as the
  previous alternative, just moved from "two files" to "two fields on one record." Also means all
  four repos' own registry entries need updating for a value that's fully computable from data they
  already declare.
- **`static_mount_path()` in `paths.py`**. Rejected: `paths.py`'s existing contract is exclusively
  "filesystem paths into this installed package" (fonts dir, templates dir, tokens.css path) —
  every function in it returns a `pathlib.Path`. A URL-prefix string has nothing to do with the
  filesystem and would mislead the next person adding a helper there.
- **Derive the prefix from a live registry fetch** (matching how hosted apps fetch `nav`/
  `settings_tabs`/`api_prefixes` from the Host's `/internal/app-registry.json` under
  registry-decoupling). Rejected: registry-decoupling's model tolerates staleness for that data
  (nav items degrading briefly is low-stakes) — but a hosted app's ability to serve its *own* static
  assets correctly must not depend on the Host being reachable at cache-populate time. That would be
  strictly worse than today's bug: instead of serving the wrong CSS, an app could serve no CSS, or
  serve it at the wrong path, during a Host outage or slow first fetch.

## Consequences

- `organizeme_chrome` now visibly has two bundled responsibilities under one package name — a
  routing/registry concern (`registry.py`, `registry_client.py`, and now this) and a
  presentation/chrome concern (`paths.py`, `assets.py`, `templating.py`, `design.py`, `theme.py`,
  `nav_groups.py`, `cdn.py`). Not addressed by this decision; flagged as a future ticket in the
  feature's TDD.
- Any future hosted app just needs a valid `service_name` to get correct static-asset routing for
  free, both in its own code and in the generated Load Balancer config — no separate declaration to
  remember, and no way for the two to disagree.
- The `service_name` validator is a new, small backward-incompatible constraint on `AppEntry`
  construction — if any existing `service_name` in any of the four repos' registries doesn't already
  match `^[a-z][a-z0-9-]*$`, adding it will break that app's startup. Worth a one-time check across
  all four repos before landing.
