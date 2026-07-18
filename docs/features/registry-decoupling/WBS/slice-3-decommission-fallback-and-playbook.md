# Slice 3 — Decommission the compiled-in fallback + update the hosted-app playbook

> Part of the `registry-decoupling` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** The old build-time-pin mechanism for registry *data* is fully retired — there is no
longer a compiled-in `APPS` literal anywhere for a consumer to silently fall back to, and the
"how to add a hosted app" playbook reflects the new registration flow instead of the old
"bump every pin" workaround.

## What to build

- Delete the transitional compiled-in `APPS` literal from `organizeme_chrome.registry`, now that
  organize-me (Slice 1), event-creator (Slice 1), and doc-library (Slice 2) are all confirmed
  running the fetch-based (or in-process, for the Host) `RegistrySource`. After this slice, a
  consumer that never calls `configure_registry_source()` has no implicit fallback — this is
  intentional, since every real consumer now does.
- Cut a new `organizeme-chrome` release tag reflecting the removal, and confirm all three
  consumers' pins already point at (or are bumped to) a tag that includes Slice 1/2's client
  machinery, independent of this literal's removal.
- Update `docs/how-to-add-a-hosted-app.md`: a new app registers its nav/Settings/API surface by
  adding an entry to the Host's own app-registry data (organize-me repo only) and wiring the
  standard `configure_registry_source()`/background-refresh client — not by bumping a package pin
  in every existing consumer repo. Update the Quick-start checklist accordingly.
- Add a `## Slice — registry-decoupling` section to `docs/host-integration-guide.md`, per that
  doc's own "How to keep this doc current" convention, summarizing the new interface contract for
  future integrators.

## Design notes

See PRD "Further Notes" (this decommission step is deliberately its own reviewable slice, not
folded into whichever consumer migration happens to land last) and TDD "Rollout mechanics."

## Blocked by

- Slice 1 (organize-me + event-creator migrated)
- Slice 2 (doc-library migrated)

## Acceptance criteria

- [ ] `organizeme_chrome.registry` no longer contains a compiled-in `APPS` literal.
- [ ] All three consumer repos' `organizeme-chrome` pins point at a tag that both includes the new
      client machinery and postdates the literal's removal.
- [ ] `docs/how-to-add-a-hosted-app.md` describes the registration flow accurately for a
      hypothetical fourth hosted app, with no reference to the old per-consumer pin-bump
      workaround as the primary path.
- [ ] `docs/host-integration-guide.md` has a new slice section per its own currency convention.
- [ ] All three services (organize-me, event-creator, doc-library) render correct sidebars in both
      QA and prod after this slice ships, confirming nothing depended on the now-removed fallback.

## Testing

- `packages/chrome/tests/`: remove/update any test that exercised the now-deleted compiled-in
  fallback path; confirm `list_apps()`/`get_app()` raise or behave predictably (per whatever the
  TDD/implementation settles on) if called before `configure_registry_source()` — this is a
  genuine behavior change worth its own explicit test, since Slices 1-2 relied on the fallback
  masking that case.
- No new runtime test surface beyond that — this slice is a removal + documentation update, not
  new behavior.
