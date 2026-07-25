# Local Development Environment — PRD

## Problem Statement

Testing a change to a hosted app (`event-creator`, `doc-library`, `ha-dashboard`) today
effectively requires a git push, a CI run, and a QA Cloud Run deploy before it can be clicked
through in a browser as a real logged-in user. That's because:

- Hosted apps only render meaningful pages once they can verify a real SSO JWT cookie issued by
  the Host — there's no way to get that login context without either logging into a real deployed
  environment or reconstructing the same trust locally.
- Several hosted apps depend on real, often costly or side-effecting third-party integrations
  (Gemini LLM calls, Twilio SMS, Resend email, Google Drive/Dropbox OAuth, a real Home Assistant
  instance) just to render meaningful UI — not every local session should require exercising these
  for real.
- The shared chrome/nav assumes one shared origin (the role the GCP Load Balancer plays in
  QA/prod); simply starting each hosted app's server locally doesn't reproduce that, so cross-app
  navigation and the shared cookie don't behave the same way locally as they do in a real
  environment.
- The reference development machine has no local Docker available (an ARM64 gap), which rules out
  the "just docker-compose everything" approach other platforms might reach for.

The net effect: iterating on a hosted-app change costs a full commit + CI + QA-deploy cycle just to
see it render, which discourages fast, exploratory iteration.

## Solution

A developer can bring up the whole platform locally — the Host plus any subset of hosted apps —
with a single command, log in for real, and click through any started app's UI, all without a git
push, CI run, or GCP deploy:

- A new local-dev launcher starts the Host and a chosen subset of hosted apps (defaulting to every
  hosted app repo found checked out locally), each running its existing dev server and CSS watcher
  as plain local processes — no containers.
- A local reverse proxy, configured by generating its routing rules from the same app-registry data
  that already drives the real Load Balancer's routing, presents one shared local origin so
  cross-app nav links, the shared SSO cookie, and static assets all behave the same way locally as
  they do in QA/prod.
- Login happens for real, through the Host's real login route; every hosted app trusts the
  resulting JWT cookie exactly as it does today. No local-only auth shortcut.
- Each hosted app's costly/side-effecting third-party integrations become mockable at runtime via a
  new flag, reusing each app's existing test-only fake implementations rather than building new
  ones.
- The local database is unchanged: every app keeps connecting directly to the same shared QA
  Supabase database it already does today.
- Whether the QA Cloud Run tier is still needed once this ships is an explicit, separate decision
  to revisit later — not part of this feature.

## User Stories

1. As a platform developer, I want to start the Host and any hosted apps I'm working on with a
   single command, so that I don't have to remember and juggle multiple terminal windows and
   commands per app.
2. As a platform developer, I want to choose which hosted apps to start for a given session (e.g.
   just `event-creator`), so that I don't waste local resources or ports starting apps I'm not
   touching that day.
3. As a platform developer, when I don't specify which apps to start, I want the launcher to start
   every hosted app repo it finds checked out locally, so that the default behavior "just works"
   without extra flags.
4. As a platform developer, I want the launcher to find each hosted app's repo automatically
   assuming the existing sibling-directory layout, so that I don't have to configure paths for the
   common case.
5. As a platform developer working on an in-progress branch in a git worktree, I want to override
   which checkout of a given app the launcher starts, so that I can test my worktree's changes
   instead of whatever happens to be checked out in the main sibling folder.
6. As a platform developer, I want each app's CSS watcher started automatically alongside its web
   server, so that template/style changes are reflected without a separate manual step.
7. As a platform developer running multiple services at once, I want each service's console output
   clearly labeled and color-coded, so that I can tell which service produced which log line.
8. As a platform developer, I want one local origin that path-routes to whichever service owns a
   given path, so that cross-app sidebar/nav links work the same way locally as they do through the
   real Load Balancer.
9. As a platform developer, I want the local routing configuration generated from the same
   app-registry data that drives the real Load Balancer's routing, so that local routing can never
   silently drift out of sync with QA/prod routing.
10. As a platform developer adding a new hosted app's nav path, I want the local routing to pick it
    up automatically the next time I regenerate the local proxy config, the same mental model as
    regenerating the real URL map.
11. As a platform developer, I want static assets (CSS/JS/images) for each hosted app to route
    correctly through the local proxy, so that pages render with correct styling and scripts, not
    just bare HTML.
12. As a platform developer, I want to log in through the Host's real login page when running
    locally, so that I'm exercising the actual authentication flow rather than a special-cased
    local shortcut.
13. As a platform developer, I want the JWT cookie set by a local Host login to be honored by any
    hosted app running locally too, so that I don't have to log in separately per app.
14. As a platform developer, I want local dev to keep using the same shared QA Supabase database
    the Host already connects to, so that I see realistic data without provisioning a new database.
15. As a platform developer testing `event-creator`'s upload/pipeline flow, I want a mock mode that
    swaps in the existing fake storage provider instead of a real Google Drive/Dropbox/S3
    connection, so that I can exercise the flow without real OAuth credentials.
16. As a platform developer testing `event-creator`'s LLM extraction pipeline, I want mock mode to
    swap in a canned Gemini response instead of a real API call, so that I don't need a real API
    key or incur real API cost just to click through the UI.
17. As a platform developer testing `event-creator`'s notification flows, I want mock mode to swap
    in the existing fake SMS/email senders instead of real Twilio/Resend calls, so that I don't
    accidentally send a real text message or email while iterating locally.
18. As a platform developer testing `ha-dashboard`, I want mock mode to swap in the existing fake
    Home Assistant transport instead of a real WebSocket connection, so that I can render dashboard
    tiles without a real Home Assistant instance reachable from my machine.
19. As a platform developer, I want the mock-integrations flag to be distinct from the existing
    e2e-test-mode flag, so that turning on mocks for local dev doesn't also silently expose the
    Playwright-only reset-token endpoint.
20. As a platform developer who does want to run the e2e suite locally, I want to be able to set
    both the mock-integrations flag and the e2e-test-mode flag together, so that combining them
    isn't blocked when I actually need to.
21. As a platform developer working on `doc-library`, I want local dev to work with the same
    launcher/proxy/auth pattern even though `doc-library` has no third-party integrations to mock,
    so that the pattern is consistent across every hosted app regardless of its own integration
    surface.
22. As a platform developer, I want clear documentation of the local-dev setup (installing the
    reverse proxy, running the launcher, setting the mock-integrations flag), so that a new
    contributor (or a future me) can get a full local platform running without re-deriving this
    from scratch.
23. As a platform developer, I want none of this local-dev tooling to require Docker, so that it
    works on development machines where Docker isn't available.
24. As a platform developer, I want the per-app local port assignments to live in one shared,
    checked-in config, so that the launcher and the proxy-config generator agree on which port each
    app runs on without duplicating that data.
25. As a platform developer, I want to add a brand-new hosted app to local dev by adding one entry
    to the port-mapping config (alongside its already-required registry entry), so that onboarding
    app #4+ into local dev follows the same low-friction pattern the platform's other
    "how to add a hosted app" steps already establish.
26. As a platform developer, I want the existing CI (pytest/mypy/e2e) to remain unaffected by these
    changes, so that this local-only tooling doesn't introduce regressions in deployed-environment
    behavior.
27. As a platform developer without access to a real Home Assistant instance, I want to be able to
    skip starting `ha-dashboard` locally without any special-casing, so that I can still work on the
    rest of the platform locally.
28. As a platform developer, I want each hosted app's own README to point to this shared local-dev
    launcher, so that I don't have to already know about the Host's tooling to discover it from a
    hosted app's own repo.

## Implementation Decisions

- **Orchestration:** a new local-dev launcher script (Python, run the same way the repo's existing
  build scripts are run) lives in the Host repo. It starts a configurable subset of hosted apps'
  dev servers and CSS watchers as separate local processes, plus the local reverse proxy. No
  containers are involved anywhere in this design; the launcher manages plain subprocesses
  directly.
- **Repo discovery:** convention-based sibling-directory lookup — each hosted app repo is assumed
  to be checked out as a sibling directory of the Host repo, whatever branch happens to be checked
  out there. A per-app override (environment variable or CLI flag) lets a developer point at an
  alternate checkout instead (e.g. a git worktree holding an in-progress branch). No special
  worktree-detection logic is needed — it's a plain configurable path.
- **App selection:** the launcher's CLI accepts an optional list of service names to start; when
  omitted, it starts every hosted app repo it finds present on disk.
- **Local routing:** a new generator script, a sibling of the existing GCP Load-Balancer URL-map
  generator, reads the same app-registry data that generator already reads and emits a
  configuration file for a lightweight local reverse proxy (Caddy). Local routing therefore derives
  from the identical source of truth as QA/prod routing and only needs regenerating (never
  hand-editing) when the registry changes. Static-asset path rules reuse the same path-prefix
  derivation logic the LB generator already uses, so asset requests route correctly too, not just
  page navigation.
- **Port assignment:** a new, separate local-dev-only configuration maps each app's service name to
  its local port; both the launcher and the proxy-config generator read it. This is deliberately
  kept out of the shared app-registry's per-app entry type, since that type also drives real
  (QA/prod) routing and ships as part of the versioned shared chrome package — local-only data
  shouldn't force a package version bump.
- **Auth:** no change to the SSO mechanism itself. The existing JWT-cookie trust model (a shared
  signing secret, a cookie scoped by host rather than port) is relied on as-is. Developers
  authenticate through the Host's real login route; no mock-JWT or bypass code path is introduced.
- **Mock integrations:** a new boolean configuration flag, independent of the existing
  `E2E_TEST_MODE` flag, is added to each hosted app's settings. Each app's existing
  integration-selection seam — the factory/dependency-provider function that already branches on
  `E2E_TEST_MODE` to select a fake implementation under test — is extended to also branch on this
  new flag, selecting the same already-existing fake/mock implementation. Concretely: `event-
  creator`'s storage-provider factory (real Google Drive/Dropbox/S3 vs. its existing fake), its
  Gemini client factory (real call vs. its existing canned-response fake), and its notification
  senders (real Twilio/Resend vs. their existing fake senders); `ha-dashboard`'s Home Assistant
  transport factory (real WebSocket vs. its existing test-only fake transport, promoted to a
  runtime-selectable option). `doc-library` has no third-party integration and needs no change
  here. The new flag is kept separate from `E2E_TEST_MODE` specifically because that flag also
  exposes a Playwright-only internal endpoint that shouldn't be incidentally exposed by turning on
  mocks for everyday local dev; the two flags can be set together when a developer wants both
  effects.
- **Logging:** no application-level logging changes anywhere — every app already logs to the
  console with no Cloud-specific handler, so console output already works locally as-is. The
  launcher itself is responsible for prefixing and color-coding each subprocess's output by service
  name when relaying it to the developer's terminal.
- **Database:** unchanged. Every app's local database configuration keeps pointing at the shared QA
  Supabase instance, exactly as already documented for the Host today.
- **Documentation:** the Host's local-dev documentation gains a section covering the full workflow
  (installing the reverse proxy, running the launcher, setting the mock-integrations flag, adding a
  new app to the port-mapping config); each hosted app's own README gets a short pointer to it.

## Testing Decisions

- Good tests here assert observable behavior, not incidental formatting: the new proxy-config
  generator should be tested the same way the existing Load-Balancer URL-map generator already is
  — direct unit tests of its path-rule-generation function against constructed app-registry
  entries, with no real network/subprocess/file dependency. That existing test suite is the prior
  art to follow.
- The port-mapping config lookup and the sibling-repo-discovery/override logic should each be
  tested as pure functions (given a service name and a set of inputs, resolve the path/port to
  use), using simple constructed inputs rather than a real filesystem or subprocess.
- The launcher's actual process-orchestration behavior (starting/stopping subprocesses, relaying
  and prefixing their output) is lower-value to unit test exhaustively end-to-end; prefer a thin,
  manually-verified check documented in the relevant implementation slice over mocking subprocess
  machinery extensively.
- The mock-integrations flag's wiring should be tested exactly the way each app already tests its
  `E2E_TEST_MODE`-driven fake-provider selection today: a direct test of the
  factory/provider-selection function asserting it returns the fake implementation when the new
  flag is set and the real implementation otherwise. `event-creator`'s existing storage-factory and
  Gemini-client tests are the prior art for this pattern; `ha-dashboard`'s HA-transport tests are
  the prior art for extending the same pattern there.
- No changes are needed to any deployed-environment (QA/prod) test suite. CI's existing
  pytest/mypy/e2e jobs are unaffected, since none of this new behavior is reachable unless the new
  flag is explicitly set (it defaults to off).

## Out of Scope

- Whether to remove or keep the QA Cloud Run environment for any app — an explicit, separate
  decision to revisit only after this feature ships and local dev is proven out in practice.
- Any change to the local database story: no per-developer isolated database, no local
  Postgres/SQLite, no synthetic seed-data/fixture generation.
- Any local-only authentication bypass or mock-JWT shortcut — real login via the local Host is the
  only supported path.
- Retargeting or expanding the Playwright e2e suite to run against the new local stack (it already
  supports a base-URL override today; wiring it to the new local proxy is a natural, low-cost
  follow-up, not part of this feature).
- Any change to how logging works in deployed (QA/prod) environments, or introducing a structured-
  logging framework — this feature only affects the local console UX of the multi-process launcher.
- Supporting a workflow for testing hosted apps against an unpublished/locally-modified version of
  the shared chrome package — the versioned-wheel pin flow is unchanged.
- Docker/container-based local orchestration of any kind.

## Further Notes

- The reference development machine has no local Docker available (an ARM64 gap), which is why
  every orchestration and routing decision above avoids containers entirely.
- Every hosted app with a third-party integration already has a `Protocol`-based seam, a real
  implementation, and a test-only fake for that integration (storage, LLM, SMS/email, Home
  Assistant) — this feature's mock-integrations work is almost entirely about promoting existing,
  already-tested fakes into a runtime-selectable option, not about writing new mocks.
- Recent, in-flight work on the platform's static-asset routing (path-prefix derivation for the
  real Load Balancer) produced logic the new local proxy-config generator should reuse rather than
  reimplement, so static-asset routing behaves identically locally and in QA/prod.
- `ha-dashboard`'s existing "no QA environment" ADR already sets a precedent for a hosted app
  opting out of parts of the platform's standard environment story via a declarative flag on its
  registry entry — worth keeping in mind as a reference pattern if/when the deferred QA-removal
  decision is revisited later.
