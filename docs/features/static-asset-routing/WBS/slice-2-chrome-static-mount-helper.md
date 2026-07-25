# Slice 2 — `organizeme_chrome`: static-mount-path helper + `tokens.css` fix + new package version

> Part of the `static-asset-routing` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A new, testable, versioned `organizeme_chrome` release containing everything every
later slice in this feature needs to consume — the shared prefix convention, its enforcement, and a
shared CSS fix — with zero effect on any currently-deployed app until they choose to bump their pin.

## What to build

Add `static_mount_path(service_name: str) -> str` (returns `/<service_name>/static`, no trailing
slash) to a new module colocated with `registry.py` in `organizeme_chrome` — the single source of
truth both for each hosted app's own FastAPI static mount and for the Load Balancer's URL-map
generator (Slice 3), so the two can never independently drift out of sync.

Add a `service_name` validator to `AppEntry` (`__post_init__`, pattern `^[a-z][a-z0-9-]*$`) — turns
the "service_name is always a safe URL path segment" assumption this feature now depends on into an
enforced constraint rather than an implicit fact.

Fix `tokens.css`'s `@font-face` `src` URLs from absolute (`/static/fonts/...`) to relative
(`../fonts/...`), so they resolve correctly under any app's own static prefix with no build-pipeline
changes anywhere.

Cut a new `organizeme_chrome` version tag once this lands and its own test suite passes.

## Design notes

Full reasoning for the module placement and the derive-vs-declare decision:
[`static-asset-routing-prefix-derivation`](../../../adr/static-asset-routing-prefix-derivation.md).
TDD "Design Decisions" also covers the `CHROME_STATIC_PREFIX` Jinja global
(`register_chrome()`/`chrome_base.html`) — that's part of this same package release, since it's the
mechanism the one shared hardcoded static reference in the whole platform (`chrome_base.html`'s
stylesheet `<link>`) uses to pick up the new prefix.

Before adding the `service_name` validator, check every existing `AppEntry.service_name` value across
all four repos' own registries actually matches the pattern — if any doesn't, that's a
backward-incompatible break worth catching before this ships, not after.

## Blocked by

None — independent of Slice 1, self-contained within the chrome package.

## Acceptance criteria

- [ ] `static_mount_path("doc-library")` returns `"/doc-library/static"` (no trailing slash).
- [ ] Constructing an `AppEntry` with a non-URL-safe `service_name` raises.
- [ ] `chrome_base.html`'s stylesheet link renders using the new `CHROME_STATIC_PREFIX` global
      instead of a hardcoded `/static/...` path.
- [ ] `tokens.css`'s font URLs are relative; existing consumers' compiled CSS still resolves fonts
      correctly when rebuilt against this version (verify against at least one real app's
      `build_css.py`, e.g. locally in `doc-library`, before tagging).
- [ ] A new version tag exists and every existing consumer of `organizeme_chrome` continues working
      unmodified against the *previous* tag (this slice ships nothing live — no consumer bumps its
      pin yet).

## Testing

Pure unit tests: `static_mount_path()` given a `service_name`; `AppEntry`'s new validator, alongside
existing coverage in `packages/chrome/tests/test_registry.py`. A template-rendering test asserting
`chrome_base.html` emits the prefixed link given a `register_chrome()`-configured environment,
following whatever existing test pattern covers `CHROME_ASSET_VERSION`'s rendering today.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
