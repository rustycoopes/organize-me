# Slice 4 — `doc-library`: migrate to prefixed static path

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** `doc-library`'s own compiled CSS and fonts actually reach the browser on the shared
domain — closing the exact bug that surfaced this whole feature (its TailAdmin tile redesign
rendering unstyled on QA).

## What to build

Bump `doc-library`'s `organizeme_chrome` pin to Slice 2's version. Change its static mount from
`app.mount("/static", ...)` to `app.mount(static_mount_path("doc-library"), ...)` — **while keeping
the old bare `/static/*` mount alive**, both serving the same directory, per the mount-transition
ADR. Audit `doc-library`'s own templates (and confirm no shared `organizeme_chrome` template beyond
the one already fixed in Slice 2 references a hardcoded `/static/...` path it renders) — this was
already checked during `/to-design` and came back clean (no hardcoded references beyond the CSS
link), so this audit step is confirming that's still true at implementation time, not expected to
turn up new work.

Deploy through `doc-library`'s own existing CI/CD (QA on PR, prod on merge to main — no special
handling needed, unlike `ha-dashboard`). After prod deploy, run Slice 3's verification script against
`doc-library` and confirm it now passes.

Note as a follow-up (not blocking this slice, not required for its acceptance criteria): once this
has been live for one release, a fast-follow PR removes the old bare `/static/*` mount, per the
mount-transition ADR.

## Design notes

[`static-asset-routing-mount-transition`](../../../adr/static-asset-routing-mount-transition.md)
covers the dual-mount reasoning. TDD's `CHROME_STATIC_PREFIX`/`chrome_base.html` mechanism (Slice 2)
means no per-app template change is needed for the CSS link itself — only the `main.py` mount and
the chrome-pin bump.

## Blocked by

- [Slice 3](slice-3-lb-static-rules-and-regen.md) — the LB must already route `doc-library`'s new
  prefix before this deploy, or requests to it would fall through to the Host during the gap.

## Acceptance criteria

- [x] `doc-library`'s QA deploy serves its own compiled CSS at `/doc-library/static/css/app.css`.
- [x] The shared QA domain's `.../doc-library` page now renders correctly — the tile flip transform,
      header illustration, and accent classes from the original TailAdmin redesign are visibly
      present (manual visual check, mirroring the original bug report).
- [x] Slice 3's verification script, run against `doc-library`, reports the shared domain and the
      direct Cloud Run URL serving byte-identical static assets, on both QA and prod.
- [x] The old bare `/static/*` mount still works during this transition window (dual-mount).

## Testing

`TestClient`-based test asserting the static mount resolves at the new prefixed path (via
`app.url_path_for("static", path=...)`, not a hardcoded string) and returns real, non-empty content
— plus the same assertion against the old bare path, confirming both are live during the transition.
Per TDD's Testing Approach, this is a different failure class than the verification script covers
(`TestClient` never exercises the actual GCP Load Balancer) — both are required, neither substitutes
for the other.

## Delivered (2026-07-25, doc-library#30, branch `feature/static-asset-routing-slice-4` in
`doc-library`)

Shipped as designed, no deviations. `organizeme-chrome` bumped to `chrome-v0.18.0`. `app/main.py`
now mounts `app/static` twice at the same directory: the new `static_mount_path("doc-library")`
prefix under the FastAPI route name `"static"` (so `CHROME_STATIC_PREFIX`, already wired via
`organizeme_chrome.templating.register_chrome()`, needed no template changes) and the old bare
`/static` path renamed to `"static_legacy_bare_path"` to avoid a route-name collision — the rename
is safe since nothing in this repo or `organizeme_chrome` resolves the static mount by name via
`url_for`/`url_path_for` (confirmed by grep during review). Template audit reconfirmed clean, as
expected — no hardcoded `/static/...` references beyond the CSS link.

New `tests/test_static_mount.py` covers both mounts: `TestClient`-style resolution via
`app.url_path_for(...)` for each route name, real non-empty content served at each path, and a
byte-identical-content check across both (a stronger check than the WBS's testing note strictly
asked for, added during review to guard against future directory drift between the two mounts).

Deployed through `doc-library`'s own CI/CD (PR #31: QA on the pull request, prod on merge to
main) — both green. Verified live:
- QA and prod shared-domain `.../doc-library/static/css/app.css` both return `200` with the
  compiled stylesheet (29505 bytes).
- The shared QA domain's `.../doc-library` page renders with the TailAdmin redesign intact —
  header illustration, styled tile cards, accent-colored badges — confirmed visually, closing the
  original bug report.
- `organize-me`'s `verify_static_routing.py` run against `doc-library` for both `--env qa` and
  `--env prod` reports byte-identical content between the shared domain and each direct Cloud Run
  URL (the script's default 30s `gcloud` timeout needed a warm-cache retry on each environment's
  first invocation — a cold `gcloud run services describe` call alone took longer than 30s; not a
  script bug, just its first real-world run against a cold local `gcloud` config).
- The old bare `/static/*` mount still serves the identical stylesheet directly against both the
  QA and prod Cloud Run URLs, confirming the dual-mount transition window is live as designed.
