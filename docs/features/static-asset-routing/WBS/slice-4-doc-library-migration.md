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

- [ ] `doc-library`'s QA deploy serves its own compiled CSS at `/doc-library/static/css/app.css`.
- [ ] The shared QA domain's `.../doc-library` page now renders correctly — the tile flip transform,
      header illustration, and accent classes from the original TailAdmin redesign are visibly
      present (manual visual check, mirroring the original bug report).
- [ ] Slice 3's verification script, run against `doc-library`, reports the shared domain and the
      direct Cloud Run URL serving byte-identical static assets, on both QA and prod.
- [ ] The old bare `/static/*` mount still works during this transition window (dual-mount).

## Testing

`TestClient`-based test asserting the static mount resolves at the new prefixed path (via
`app.url_path_for("static", path=...)`, not a hardcoded string) and returns real, non-empty content
— plus the same assertion against the old bare path, confirming both are live during the transition.
Per TDD's Testing Approach, this is a different failure class than the verification script covers
(`TestClient` never exercises the actual GCP Load Balancer) — both are required, neither substitutes
for the other.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
