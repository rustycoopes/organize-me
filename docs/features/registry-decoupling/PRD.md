# PRD: Decouple the shared chrome/nav registry from per-app build-time pins

**Source issue:** organize-me#217
**Related:** doc-library#2, organize-me#215 (separate, not blocked on this)

## Problem Statement

Every hosted app (organize-me itself, event-creator, doc-library, and any future app) renders the
same shared sidebar/Settings chrome via the `organizeme-chrome` package. What nav items, Settings
tabs, and API prefixes each app owns is driven by `organizeme_chrome.registry.APPS` — a plain
Python list compiled into that package at build time. Each consuming service pins
`organizeme-chrome` independently, via its own git-tag dependency in its own `pyproject.toml`.

There is no runtime source of truth: the registry each service actually renders from is whatever
tagged snapshot its dependency tree happened to resolve at its last build. A registry change (new
app, new nav item, new API prefix) requires bumping the pin and rebuilding/redeploying **every**
consumer, not just the app that changed — and it's silent when missed: the forgotten service just
keeps rendering its last-shipped snapshot, with no error anywhere.

This has already bitten three times during the Doc Library rollout alone (organize-me's own root
pin drifting separately from `packages/chrome`'s own version; event-creator's pin going stale and
losing the "Doc Library" nav entry on every event-creator-served page; and a second manual step
needed just to get a QA redeploy to pick up the fix). It directly contradicts the platform's
stated goal of independent, decoupled hosted apps: today, the one thing every app shares — the
chrome — requires N-way coordinated redeploys for any change, where N grows with every new hosted
app.

## Solution

Move the registry **data** (which apps exist, their nav items, Settings tabs, API prefixes) out of
the versioned `organizeme-chrome` package and into the Host's own runtime. The Host
(organize-me) becomes the single, live source of truth, serving the registry from an internal
endpoint. Every consumer (including apps not yet built) reads a background-refreshed in-memory
cache backed by that endpoint, so a registry change takes effect for every consumer within one
refresh interval — no rebuild, no redeploy, no pin to remember to bump.

The `organizeme-chrome` package itself keeps existing and keeps its normal versioned-pin discipline
— it still carries real code (Jinja templates, `nav_groups.py` combine logic, `jwt_verify`, theme
helpers, and the new registry-fetch client). What changes is that pure **data** no longer requires
a package release to propagate.

This is compatible with, not a reversal of,
[`sidebar-nav-groups-cross-repo-sync`](../../adr/sidebar-nav-groups-cross-repo-sync.md)'s decision
to keep `organizeme-chrome` on a tag-pinned (not floating) dependency — that ADR is about the
package's *code*, which keeps its deliberate pin-and-bump convention unchanged here. Only registry
*data* moves off that mechanism.

## User Stories

1. As a platform engineer adding a new nav item to an existing hosted app, I want that change to
   reach every consumer's sidebar without touching any other repo, so that I don't need to
   coordinate a multi-repo redeploy for a one-line change.
2. As a platform engineer standing up a brand-new hosted app, I want to register its nav/Settings/
   API surface once, in the Host, so that every existing consumer (and the Host's own Settings
   shell / Load Balancer routing) picks it up without a pin bump anywhere else.
3. As an on-call engineer, I want a hosted app's sidebar to keep rendering correctly during a
   transient Host outage, so that a blip in the Host's availability doesn't break every other
   app's chrome.
4. As an on-call engineer, I want a hosted app whose very first request happens before the Host is
   reachable (cold start racing a Host outage) to still render its own nav correctly, so that the
   app isn't fully broken by a dependency it doesn't fully control the timing of.
5. As a developer migrating a consumer repo to the new fetch-based registry, I want to do so on my
   own schedule and in my own PR, so that this migration doesn't require a flag-day, all-repos-at-
   once coordinated deploy.
6. As a developer reading `organizeme_chrome`'s public API, I want `list_apps()`/`get_app()` to
   keep their existing synchronous signatures, so that migrating doesn't ripple into an `async`
   rewrite of every page handler and template-context builder across three repos.
7. As a security-conscious platform engineer, I want the Host's registry endpoint to only be
   reachable by the platform's own services, not the public internet, so that no new
   internet-facing attack surface is introduced even though the payload itself isn't sensitive.
8. As a developer running `infra/gcp_lb/generate_url_map.py` to regenerate Load Balancer routing, I
   want it to keep working the same way it does today (a local, operator-run script against the
   checked-out registry), so that LB provisioning doesn't gain a runtime dependency on the LB
   already being up.
9. As a developer reviewing the Host's own Settings/Profile pages, I want the Host to resolve its
   own registry entries without a self-directed HTTP call, so that the Host never depends on its
   own network reachability to render its own chrome.
10. As a future maintainer debugging a stale-looking sidebar, I want the staleness of a consumer's
    cached registry to be observable (logged/metriced), so that a sustained Host-unreachability
    problem is diagnosable without it first becoming a user-visible outage.
11. As a developer adding a new hosted app after this migration, I want the "how to add a hosted
    app" playbook updated to describe the new registration flow, so that I don't follow a stale
    "bump every pin" workaround.

## Implementation Decisions

- **Data ownership move:** the hand-authored `APPS` list moves out of
  `organizeme_chrome.registry` and into the Host's own application code (organize-me repo, not the
  `packages/chrome` package). `organizeme_chrome.registry` keeps its `AppEntry`/`AppNavItem`/
  `SettingsTab` dataclasses (unchanged shape) as the deserialization target, plus `list_apps()`/
  `get_app()`, whose implementation changes from "return the compiled-in literal" to "return the
  current contents of a background-refreshed in-memory cache."

- **New Host endpoint:** organize-me exposes an internal endpoint (e.g.
  `GET /internal/app-registry.json`) that serializes its own in-process `APPS` data to JSON. The
  Host's own page handlers do **not** call this endpoint — the Host resolves `list_apps()`/
  `get_app()` against the same in-process data directly, with no self-HTTP round trip and no
  startup-ordering dependency on itself.

- **Reachability and auth:** the endpoint is reached via direct Cloud-Run-to-Cloud-Run calls (the
  Host's own `*.run.app` URL per environment), not the public Load Balancer domain. Every service
  on this platform already runs as the same shared Cloud Run runtime service account. A consumer
  mints a Google-signed OIDC identity token for that service account via the metadata server
  (audience = the Host's own URL) and presents it on the request; the Host's endpoint handler
  verifies the token's `aud` and `email` claims in application code, mirroring the existing
  `POST /internal/pipeline/run` pattern (event-creator's Cloud-Tasks-push endpoint) rather than
  relying on Cloud Run's built-in IAM invoker gate (both services stay `--allow-unauthenticated`
  overall). No new service accounts or IAM grants are required.

- **Fetch/cache client (new module in `organizeme_chrome`):** each consumer's FastAPI app starts a
  periodic background task on startup (60-second interval) that fetches the Host's endpoint and
  atomically swaps an in-memory cache on success. `list_apps()`/`get_app()` read only from this
  cache — both stay synchronous, unchanged in signature, so no call site anywhere in any of the
  three repos needs to become `async`.

- **Failure handling:** on a failed fetch, the background task logs/metrics the failure and leaves
  the existing cache untouched — a consumer keeps serving its last-known-good registry
  indefinitely through a Host outage of any duration, never degrading the UI on its own. There is
  no "N consecutive failures, fall back to self-only" escalation; staleness is an
  observability concern (logs/metrics), not a UI-visible one.

- **Cold-start fallback:** before a consumer's first successful fetch completes (e.g. a fresh
  deploy racing a Host outage), `list_apps()` returns a small hardcoded default containing only
  that consumer's own `AppEntry` (its own nav items, Settings tabs, API prefixes — the one thing it
  can vouch for about itself). This default is maintained per-consumer-repo (each repo already
  knows its own nav surface) and is replaced the moment the first real fetch succeeds.

- **`generate_url_map.py`:** keeps importing the registry directly from Python (the Host's own
  in-process data, via the same code path the Host's own page handlers use) rather than switching
  to the JSON endpoint. It's a local, operator-run script, not a live service, and depending on the
  Host/LB already being reachable to generate the LB's own routing config would be circular.

- **Migration is a backward-compatible transition, not a flag day:** for one transitional release,
  `organizeme_chrome.registry` keeps a compiled-in fallback snapshot (today's existing `APPS`
  literal) so an as-yet-unmigrated consumer doesn't break. Each of the three consumer repos
  (organize-me, event-creator, doc-library) migrates to the new fetch-based client independently,
  in its own PR, in any order. Once all three are confirmed migrated, the compiled-in fallback is
  deleted from the package in a follow-up cleanup PR.

- **`organizeme-chrome` package versioning:** unaffected in spirit — the package still gets
  versioned git-tag releases, still via the existing convention
  ([`sidebar-nav-groups-cross-repo-sync`](../../adr/sidebar-nav-groups-cross-repo-sync.md)). What
  changes is that a *pure registry data* change (new app, new nav item) no longer requires a
  package release at all, since that data no longer lives in the package.

## Testing Decisions

- Tests target external behavior (what a caller observes), not internals — matching this
  codebase's existing convention throughout `packages/chrome/tests/` and each service's own test
  suite.
- **New fetch/cache client module** (`organizeme_chrome`): unit-tested in
  `packages/chrome/tests/`, in the same style as the existing `test_registry.py`/
  `test_nav_groups.py` — pure logic, no real network. Use `httpx`'s `MockTransport` (or equivalent)
  to fake the Host's endpoint responses rather than hand-mocking the fetch function, so the real
  HTTP client code path (including OIDC header construction) is exercised. Cases: successful fetch
  populates the cache; a failed fetch after a warm cache leaves the previous data in place
  (last-known-good); `list_apps()` before any successful fetch returns the self-only cold-start
  default; a background task correctly retries on the configured interval.
- **Host's new endpoint** (organize-me): tested via the existing FastAPI `AsyncClient`
  test-client pattern already used throughout organize-me's `tests/` directory — a valid
  shared-SA-signed token gets a 200 with the current registry JSON; a missing/invalid/wrong-`aud`
  token gets rejected; the response shape round-trips correctly through
  `organizeme_chrome`'s own dataclasses on the consuming side.
- **Consumer integration** (event-creator, doc-library): each repo's existing sidebar-rendering
  tests (e.g. the `storedCollapsed`-assertion tests already fixed in event-creator's
  `test_*_page.py` files) continue to exercise the rendered chrome end-to-end; no new integration
  test class is needed beyond swapping in the new client under test doubles the same way the
  compiled-in registry was implicitly "faked" by the pinned package version before.
- `generate_url_map.py`'s existing test coverage (if any) is unaffected, since its data source
  doesn't change.

## Out of Scope

- organize-me#215 (QA Cloud Run only redeploying on PR, not on direct push-to-main) — a separate,
  narrower CI/CD gap, explicitly not blocked on this issue.
- Rewriting `docs/how-to-add-a-hosted-app.md` for the new registration flow — real follow-up work,
  but not part of this PRD's implementation slices; tracked as a note for whoever picks up the
  final slice to also update the doc, per this repo's CLAUDE.md documentation-upkeep rule.
- Retroactively fixing any other Host-owned-preference sync gaps (e.g. `dark_mode`'s existing
  hardcoded-default issue in event-creator) — unrelated to this registry-data mechanism.
- Changing `organizeme-chrome`'s tag-pin dependency convention for *code* (templates, jwt_verify,
  nav_groups logic) — that stays exactly as-is per the existing ADR.
- Any new per-consumer service accounts or IAM invoker grants — explicitly decided against in favor
  of reusing the existing shared runtime service account.
- Read-through / synchronous inline fetching of the registry per-request — explicitly decided
  against in favor of the background-refreshed cache, to keep `list_apps()`/`get_app()`
  synchronous.

## Further Notes

- This PRD assumes doc-library's own repo will need a corresponding WBS slice/PR to migrate off
  its current `organizeme-chrome` pin, same as event-creator and organize-me itself — three
  consumer-side migration slices plus one Host-side (endpoint + data move) slice is the expected
  shape once this reaches `/to-wbs`.
- The compiled-in fallback's *removal* (once all three consumers are confirmed migrated) is
  itself worth its own small slice/PR, separate from the three migrations, so there's a clean,
  reviewable "decommission the old mechanism" step rather than folding it into whichever
  migration happens to land last.
- Given the "Why this issue, why now" framing in the source issue, this PRD deliberately does not
  invent scope beyond the issue's own proposed sketch — every implementation decision above traces
  back either to the issue body or to a decision made during the `/grilling` session that produced
  this PRD.
