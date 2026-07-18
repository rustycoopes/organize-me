# Slice 2 — doc-library migration

> Part of the `registry-decoupling` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A registry change made in organize-me reaches doc-library's live sidebar too, the
same way it already does for event-creator — doc-library is no longer the odd one out still
depending on a package pin for registry data.

## What to build

Apply the same client wiring Slice 1 built for event-creator, to doc-library:

- Add the new Settings fields (`registry_host_url`, `registry_refresh_interval_seconds`,
  `registry_fetch_timeout_seconds`, shared runtime service account identity) to doc-library's
  `app/core/config.py` — genuinely new fields there, since doc-library has no prior
  internal-endpoint pattern to draw on (unlike event-creator, which already had
  `/internal/pipeline/run`'s OIDC verification as prior art — that prior art doesn't help here
  since doc-library is the *minting*, not verifying, side).
- Wire doc-library's `lifespan` to construct a `FetchedRegistrySource` (self-only default =
  doc-library's own `AppEntry`), call `configure_registry_source()`, and spawn/cancel the
  background refresh task — identical shape to event-creator's Slice 1 wiring.
- Set `registry_host_url` as a plain (non-secret) env var per environment in doc-library's
  `deploy.yml`/CI config.
- Bump doc-library's `organizeme-chrome` pin to whatever tag includes Slice 1's
  `registry_client.py`/`RegistrySource` additions.

## Design notes

Identical pattern to Slice 1's event-creator wiring — see TDD "Background refresh loop (per
consumer)" and "Settings additions per consumer." No new design decisions in this slice; it's a
mechanical application of Slice 1's already-proven pattern to a second consumer, confirming the
mechanism generalizes rather than being event-creator-specific.

## Blocked by

- Slice 1 (needs `organizeme_chrome`'s `registry_client.py`/`RegistrySource` machinery and a live
  Host endpoint to fetch from)

## Acceptance criteria

- [ ] doc-library's sidebar renders correctly on a cold start with no reachable Host (self-only
      default).
- [ ] A registry change made only in organize-me appears in doc-library's live sidebar within one
      refresh interval, with no doc-library deploy.
- [ ] A sustained Host outage leaves doc-library serving its last-known-good cache indefinitely,
      same as event-creator's Slice 1 behavior.
- [ ] event-creator (migrated in Slice 1) is unaffected by this slice's changes.

## Testing

- doc-library: same test shape as Slice 1's event-creator tests — `lifespan` startup/shutdown
  task lifecycle, existing sidebar-rendering tests continuing to pass. No new tests needed in
  `packages/chrome/tests/` (the client machinery itself was already covered in Slice 1).
