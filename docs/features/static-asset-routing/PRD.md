## Problem Statement

Every hosted app on the OrganizeMe platform (`organize-me` itself, `event-creator`, `doc-library`,
`ha-dashboard`) serves its own compiled stylesheet, fonts, and other static assets from the same
bare path: `/static/*`. On the shared domain (`organizeme.qa.russcoopersoftware.com` /
`organizeme.russcoopersoftware.com`), the Load Balancer's URL map routes page and API requests to
the correct per-app backend using explicit path rules generated from each app's registry entry —
but no such rule exists (or *can* exist, as currently structured) for `/static/*`, because the path
is identical across every app. Every hosted app's static-asset request silently falls through to
the URL map's `defaultService` (`host-backend`) and gets served the **Host's own** compiled
stylesheet instead of its own.

The failure mode is silent and highly misleading: shared `organizeme_chrome` component styling
(cards, buttons, colors) still looks correct, because the Host's own pages render the same shared
macros — so only the parts of a page unique to that app's own templates are missing, with no error,
no 404, nothing in the browser console pointing at the cause. This has already caused at least one
live incident: HA Dashboard's tile redesign shipped correctly but rendered with the wrong colors,
wrong font, and a broken layout on both QA and (confirmed during this investigation) **prod today**.
That incident was diagnosed as an intermediate-cache staleness problem and "fixed" via a
cache-busting query string (`docs/adr/chrome-static-asset-cache-busting.md`) — a fix that cannot
actually work here, since GCP's URL map matches on path only and a query string doesn't change
which backend a request is routed to. Doc Library's own TailAdmin tile redesign hit the identical
symptom on QA, which is what surfaced this root cause.

Until this is fixed, every hosted app is at risk of shipping template/CSS changes that appear
broken on the shared domain regardless of how correct the underlying build is — and today, nothing
would catch that before a user (or the developer debugging on their behalf) notices visually.

## Solution

Give each hosted app's static assets a URL path that is unique per app, so the Load Balancer can
route them like it already does for page and API routes: `/<service_name>/static/*` instead of the
current bare `/static/*`. Derive this prefix in exactly one place — a shared helper in
`organizeme_chrome` — and use that same helper both in each app's own FastAPI static mount and in
the Load Balancer's URL-map generator, so the convention can't drift between what an app serves and
what the LB expects to route.

The Host (`organize-me`) is not part of the ambiguity this fixes (it's already the URL map's
`defaultService`, so its own bare `/static/*` already resolves correctly) and is explicitly left
unprefixed.

Because `tokens.css` (the one CSS file shared byte-for-byte across every app via the `organizeme_chrome`
package) currently hardcodes absolute font URLs (`/static/fonts/...`), those become relative paths
so they resolve correctly under any app's prefix with no build-time templating required.

Roll out per app, one at a time, starting with `doc-library` (the app with the currently-visible
QA symptom): `organizeme_chrome` package change first, then `organize-me`'s Load Balancer
config (QA and prod together, since new path rules are additive and inert until an app actually
uses them), then each hosted app's own migration slice.

## User Stories

1. As a developer shipping a template/CSS-only change to a hosted app, I want that app's compiled
   stylesheet to actually reach the browser on the shared domain, so that what I verified locally
   and on the app's own direct Cloud Run URL is what a real user sees.
2. As a developer debugging "my new styles aren't showing up," I want the platform's routing to be
   correct by construction, so that I'm not left guessing between a build problem, a cache problem,
   and a routing problem the way this investigation had to.
3. As a developer adding a new hosted app to the platform in the future, I want its static assets to
   be routed correctly automatically (derived from its registry entry), so that I don't have to
   remember to hand-write a Load Balancer path rule for it.
4. As a developer authoring shared `organizeme_chrome` styles (tokens, fonts), I want the shared
   package to have no baked-in assumption about which app's path prefix is serving it, so that the
   same package version works unmodified across every consuming app.
5. As an operator who just re-provisioned the Load Balancer (QA or prod), I want a quick way to
   confirm each hosted app's static assets are actually reaching visitors correctly, so that a
   misconfigured or missing path rule is caught immediately instead of silently shipping.
6. As the maintainer of the HA Dashboard cache-busting ADR, I want its actual effectiveness
   re-examined once this fix ships, so that the platform doesn't carry a fix that never addressed
   the real failure mode it was written for.
7. As a developer migrating an existing hosted app to the new static-asset prefix, I want an
   explicit audit step for other hardcoded `/static/...` references (favicons, OG images, JS
   assets) in that app's own templates and any shared chrome templates it renders, so that nothing
   beyond the compiled stylesheet silently breaks under the new prefix.
8. As a developer relying on the app-registry as the single source of truth for routing, I want the
   static-asset prefix to be derived from `service_name` rather than separately declared per app,
   so that there's no second place this convention can drift out of sync.

## Implementation Decisions

- **New shared helper in `organizeme_chrome`**: a function (e.g. `static_mount_path(service_name)`)
  that deterministically renders an app's static-asset URL prefix as `/<service_name>/static`. This
  is the single source of truth for the convention — both an app's own FastAPI static mount and the
  Load Balancer's URL-map generator call it, rather than each independently hardcoding the pattern.
- **`infra/gcp_lb/generate_url_map.py` changes**: for each `AppEntry` returned by `list_apps()`,
  synthesize a static-asset path rule via the same shared helper (`<prefix>/*`) routed to that app's
  existing backend service, alongside its existing `nav`/`api_prefixes`-derived rules. No new field
  is added to `AppEntry` — the prefix is fully determined by `service_name`, which is already the
  key everything else (backend service naming, nav routing) derives from.
- **Each hosted app's own `main.py`**: static files mount changes from `app.mount("/static", ...)`
  to `app.mount(static_mount_path(app's own service_name), ...)`, and every template reference to
  the compiled stylesheet, fonts, or other static assets updates to the new prefixed path.
- **`tokens.css` (shared, in `organizeme_chrome`)**: `@font-face` `src` URLs change from absolute
  (`/static/fonts/baloo-2-700.woff2`) to relative (`../fonts/baloo-2-700.woff2`), resolving correctly
  regardless of which app's prefix is serving the compiled CSS that imports it. No changes needed to
  any app's `build_css.py`, which already copies chrome's fonts into that app's own
  `app/static/fonts/` at build time.
- **Host (`organize-me`) is explicitly out of this migration**: its own static mount and templates
  stay on bare `/static/*`; it continues to be the URL map's `defaultService`, so unprefixed
  requests keep resolving to it — now correctly limited to genuinely being *its own* requests, no
  longer accidentally absorbing every other app's too.
- **Rollout order** (see User Stories 1–8 for the "why" of each piece):
  1. `organizeme_chrome`: add the shared helper, fix `tokens.css`'s font URLs, cut a new package
     version tag.
  2. `organize-me`: update `generate_url_map.py`, re-run `provision.sh` and `provision-prod.sh` to
     push the new URL map to both QA and prod (additive/inert until an app actually uses the new
     prefix — no risk to currently-live traffic).
  3. `doc-library` migration slice: bump the chrome pin, switch its static mount and template
     references to its own prefix, audit for other hardcoded `/static/...` references, deploy,
     verify (QA via its existing PR-triggered deploy, prod via merge-to-main, matching its existing
     CI/CD pattern).
  4. `event-creator` migration slice: same pattern.
  5. `ha-dashboard` migration slice: same pattern — this is also the app with the live, currently
     unresolved prod incident, so its slice should note the cache-busting ADR explicitly and flag
     it for re-examination once this ships.
- **Verification tooling**: a small script under `infra/gcp_lb/` that, for each app in the
  registry, fetches a known static asset via the shared domain and via that app's own direct Cloud
  Run URL and asserts they match byte-for-byte (the same manual check performed during this
  investigation, automated). Manual-run only for this feature (e.g. after any LB re-provision) —
  wiring it into a recurring CI job is explicitly deferred as future work, not part of this feature.

## Testing Decisions

- **`infra/gcp_lb/generate_url_map.py`**: extend the existing `tests/test_url_map_generator.py`
  (pure-Python, given a list of `AppEntry` objects, asserting on the generated `PathRule`/YAML
  output) with cases asserting the new static-asset path rule is generated per app, using the
  shared `static_mount_path()` helper rather than ad-hoc string construction in the test itself —
  so the test would actually catch the helper and the generator drifting apart.
- **`organizeme_chrome.static_mount_path()`**: a small, pure unit test (given a `service_name`,
  asserts the returned prefix) alongside the existing `packages/chrome/tests/test_registry.py`
  conventions.
- **Each hosted app's static mount**: a request-level test (existing `TestClient`-based test
  conventions already used per app) asserting a known static asset resolves under the new prefixed
  path and that the old bare path no longer does (or 404s, per that app's own migration slice).
- **The verification script**: tested by running it against the real QA/prod environment as part of
  each migration slice's acceptance criteria (an infra/operational check, not a unit test) — its
  value is in actually being run against live infrastructure, not in a mocked unit test of its own
  logic.
- Only test external behavior (the resolved path, the actual bytes served) — not internal
  implementation details of how a given app's `main.py` constructs its mount.

## Out of Scope

- Migrating the Host (`organize-me`) itself to a prefixed static path — it is not part of the
  ambiguity this fixes and stays on bare `/static/*` (see Implementation Decisions).
- Any subdomain-per-app or other DNS/certificate-based routing approach — path-prefixing was chosen
  specifically to avoid this.
- Enabling Cloud CDN or introducing any other intermediate caching layer — Cloud CDN is confirmed
  disabled platform-wide today and is unrelated to this fix.
- Wiring the verification script into a recurring/scheduled CI job — the script itself is in scope;
  ongoing automated scheduling is explicit future work.
- Re-litigating or removing the cache-busting ADR's mechanism (`CHROME_ASSET_VERSION` query
  string) — that mechanism solves a real (if different) problem and stays in place. This PRD only
  flags that the specific incident it was written for was likely actually this routing bug, for the
  benefit of whoever revisits that ADR later.
- Any change to how `api_prefixes` or `nav` are declared or validated — this feature adds one new
  derived category of path rule (static assets) alongside the existing two, without changing their
  own mechanics.

## Further Notes

- The live prod HA Dashboard incident this investigation surfaced (`organizeme.russcoopersoftware.com/static/css/app.css`
  serving the Host's 25,403-byte CSS instead of `ha-dashboard-prod`'s own 19,128-byte build,
  confirmed by direct comparison during this PRD's research) means `ha-dashboard`'s migration slice
  is not purely precautionary — it resolves an active, currently-shipping production bug.
- `docs/adr/chrome-static-asset-cache-busting.md` should be revisited once `ha-dashboard`'s slice
  ships: if the shared domain then correctly serves its own CSS, that's strong evidence the original
  incident this ADR describes was this routing bug misdiagnosed as cache staleness, not a
  cache-staleness problem the query string ever actually fixed.
- This feature spans four repos (`organize-me`, `event-creator`, `doc-library`, `ha-dashboard`) plus
  the `organizeme_chrome` package (versioned, subdirectory of `organize-me`). Per this repo's
  feature-workflow convention, the PRD/TDD/WBS live here in `organize-me` as the cross-app/platform
  feature; each WBS slice's GitHub issue will be filed in whichever repo that slice actually touches.
