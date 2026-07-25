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

- [x] `organize-me`'s own chrome pin is bumped to Slice 2's version.
- [x] `generate_url_map.py`'s output includes a static-asset path rule per hosted app, for both `qa`
      and any `-prod` suffix generation.
- [x] Live QA and prod URL maps are updated (`gcloud compute url-maps describe` on each shows the
      new rules) with no observable change in behavior for any existing route (verify the existing
      smoke checks — `curl .../login`, `curl .../dashboard`, `curl .../doc-library`,
      `curl .../ha-dashboard` — still succeed identically to before this slice).
- [x] The verification script exists, runs against at least one app (expected result: still a
      mismatch, since no app has migrated yet — this slice doesn't fix any app's actual bug, it
      only makes the infrastructure ready for Slices 4-6 to use).

## Testing

Extend `tests/test_url_map_generator.py` with cases asserting the new static-asset rule is generated
per app via the shared helper (not independently reconstructed logic in the test), per TDD's Testing
Approach. The pre-import diff check and the `provision.sh`/`provision-prod.sh` review step are
operational, not unit-testable — they're acceptance criteria for the person running this slice, not
automated coverage.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-25, issue #255, branch `feature/lb-static-asset-rules`)

Shipped as designed. `organizeme-chrome` bumped to `chrome-v0.18.0`. `generate_path_rules()` now
emits one wildcard-only static-asset `PathRule` per registered app (`{static_mount_path(app)}/*`),
reusing the same `seen_paths` collision map as `nav`/`api_prefixes` — a small `_claim_path()`
helper was factored out during review to keep that three-times-repeated check from drifting in
wording as it grew a third caller. One real (if minor, pre-existing-scale) behavior change came
along for free: an app with empty `nav` and no `api_prefixes` now always gets a `PathRule` (just
its static wildcard) instead of being omitted — no such app exists in today's registry, but it's
now an explicit, tested invariant rather than an accidental side effect.

Live QA and prod URL maps were both diffed against the pre-slice generator output first (byte-for-byte
match — no out-of-band drift), then regenerated via `provision.sh`/`provision-prod.sh`; both scripts
call the same generator so no script-level changes were needed. Post-regen, `gcloud compute
url-maps describe` on both confirms the new `/*` rule per app, and the existing smoke checks
(`/login`, `/dashboard`, `/doc-library`, `/ha-dashboard` on both hosts) return the same status
codes as before.

`verify_static_routing.py` (new) and its unit tests shipped as specced, plus one hardening pass
found in code review: CLI-supplied app names are now validated against the same
`service_name` pattern `AppEntry` itself enforces before ever reaching a `gcloud` subprocess call
— on Windows, `gcloud` must run with `shell=True` (it's a `.cmd` wrapper), which made an
unvalidated argument a real, demonstrated command-injection vector via cmd.exe's `%VAR%`
expansion, not just a theoretical one. Also added: a timeout on `gcloud` calls (it previously had
none, unlike the HTTP fetches), and broadened `main()`'s per-app exception handling so one app's
unexpected failure (e.g. malformed `gcloud` JSON) doesn't abort evaluation of the rest. Ran live
against `doc-library` on QA: reports a 404 mismatch, as expected — no app has migrated its own
static mount yet, so the new rule is still inert.

**Diverged from plan — a real bug found and fixed, outside this slice's original "no app-side
changes" scope.** CI's `e2e-qa` Playwright suite failed repeatedly and reproducibly after bumping
the chrome pin, on tests unrelated to routing (`profile.spec.ts`, `sidebar.spec.ts`'s mobile
drawer). Investigation (traced network responses + computed styles in a live browser against QA,
not just re-running CI) found the actual cause: `chrome_base.html` in chrome-v0.18.0 unconditionally
links its stylesheet via `CHROME_STATIC_PREFIX`, which the Host's own `register_chrome(
app_service_name="organizeme")` call sets to `static_mount_path("organizeme")` — exactly like any
other app, since `chrome_base.html` has no way to know a given consumer *is* the Host. `organize-me`
itself only had the old bare `/static` mount, so every authenticated Host page's compiled CSS
404'd the moment the pin bumped, unstyling the whole app (this is what broke `sidebar.spec.ts`'s
`.fixed`-class assertion and, intermittently, `profile.spec.ts`'s render-timing). Fixed by
dual-mounting `app/main.py`'s static directory at both the bare and prefixed paths (see TDD's
updated "Host keeps bare `/static/*`..." section); added `tests/test_host_static_mount.py` as
regression coverage (an authenticated page's actual stylesheet `<link>` must resolve to a mounted,
200-returning path — the existing test suite had no such assertion, which is how this shipped in
chrome-v0.18.0 unnoticed until Slice 3 was the first to actually bump the pin and deploy it).
