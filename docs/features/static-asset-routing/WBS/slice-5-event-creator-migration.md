# Slice 5 — `event-creator`: migrate to prefixed static path

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** `event-creator`'s own compiled CSS and fonts actually reach the browser on the shared
domain, closing the same latent bug class before it produces a visible incident for this app the way
it already has for `doc-library` and `ha-dashboard`.

## What to build

Identical shape to [Slice 4](slice-4-doc-library-migration.md), applied to `event-creator`: bump its
`organizeme_chrome` pin, change its static mount to `static_mount_path("event-creator")` while
keeping the old bare mount alive for the transition window, audit its own templates (already
confirmed clean during `/to-design`), deploy through its own existing CI/CD (QA on PR, prod on merge
to main), verify with Slice 3's script.

Same fast-follow note as Slice 4: old-mount removal is a documented follow-up, not part of this
slice's acceptance criteria.

## Design notes

Same as Slice 4 — see
[`static-asset-routing-mount-transition`](../../../adr/static-asset-routing-mount-transition.md) and
the TDD's `CHROME_STATIC_PREFIX` mechanism.

## Blocked by

- [Slice 3](slice-3-lb-static-rules-and-regen.md). Not blocked by Slice 4 — no technical coupling
  between the two apps' migrations, confirmed during `/to-design`; the stated order (`doc-library`
  before `event-creator`) is a priority choice, not a dependency.

## Acceptance criteria

- [ ] `event-creator`'s QA deploy serves its own compiled CSS at `/event-creator/static/css/app.css`.
- [ ] Slice 3's verification script, run against `event-creator`, reports the shared domain and the
      direct Cloud Run URL serving byte-identical static assets, on both QA and prod.
- [ ] The old bare `/static/*` mount still works during this transition window (dual-mount).

## Testing

Same pattern as Slice 4's Testing section, applied to `event-creator`'s own test suite.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
