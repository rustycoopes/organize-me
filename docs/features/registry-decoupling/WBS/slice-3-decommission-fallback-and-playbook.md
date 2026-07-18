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

## Delivered (2026-07-18, issue #220)

Shipped across four PRs/repos, in this order:

- **organize-me PR #230** (`feature/registry-decoupling-slice-3`) — deleted `APPS`/
  `_CompiledRegistrySource` from `organizeme_chrome.registry`; `list_apps()`/`get_app()` now raise
  `RuntimeError` if called before `configure_registry_source()`; rewrote
  `how-to-add-a-hosted-app.md` and added the `host-integration-guide.md` slice section; bumped
  `packages/chrome` to `0.9.0`.
- **`chrome-v0.9.0` tag** cut and published (`publish-chrome.yml`) once #230 merged.
- **organize-me PR #231** (`feature/registry-decoupling-slice-3-host-pin`) — bumped this repo's own
  `organizeme-chrome` pin to `chrome-v0.9.0`. No runtime effect (the Host's `InProcessRegistrySource`
  was already the configured source).
- **event-creator PR #22** and **doc-library PR #15** (both branch `feature/registry-decoupling-
  slice-3` in their own repos) — bumped their `organizeme-chrome` pins to `chrome-v0.9.0` and wired
  an autouse `conftest.py` fixture (`configure_client_registry_source()`) so their own test suites
  don't rely on the now-deleted fallback.

Two problems surfaced mid-implementation that weren't anticipated by the plan above, both fixed
before merging:

1. **The design-refresh theme rewrite was coupled to the same tag line.** event-creator and
   doc-library were both still pinned to `chrome-v0.6.1`, predating the unrelated "design-refresh"
   visual overhaul (`chrome-v0.7.0`+ replaced the DaisyUI `data-theme` attribute with a Tailwind CSS
   class, and `chrome_base.html` now requires a compiled stylesheet at `/static/css/app.css`
   instead of CDN links). There is no tag containing only the registry-fallback removal without
   also carrying that rewrite. After confirming with the user, both consumer repos adopted
   organize-me's own design-refresh Slice 1 pattern (`docs/adr/design-refresh-per-service-tailwind-
   build.md`) as part of these same PRs: a `build` dependency group (`pytailwindcss`), `scripts/
   build_css.py` + `verify_css_build.py`, a two-stage Dockerfile, CI build/verify steps, a
   `/static` mount, and updated dark-mode test assertions.
2. **A real, pre-existing production bug was exposed, not introduced.** Both event-creator's and
   doc-library's `app/main.py` only called `configure_client_registry_source()` inside `lifespan`
   — which runs *after* every module-level import completes. Their own page routers transitively
   import `organizeme_chrome.templating.register_chrome()`, itself a module-level call to
   `get_app()`, at *import* time. Before this slice, an unconfigured `get_app()` silently degraded
   to the compiled-in fallback, masking the ordering bug entirely; after the fallback's removal,
   every container crashed on startup (`RuntimeError: ... not configured`), confirmed via a live
   doc-library-qa Cloud Run deploy failure. Fixed in both repos the same way organize-me's own Host
   already does it: `app/core/registry.py` now also configures a source as a module-import-time
   side effect, and `app/main.py` imports that module first, before any router.

**Verified live** after all four PRs merged and auto-deployed (QA and prod both auto-deploy on
push to `main`): `/` (organize-me), `/dashboard` (event-creator), and `/doc-library` (doc-library)
all resolve through the shared LB domain with correct redirect/200 behavior (no crashes), and
`/static/css/app.css` serves 200 on both `organizeme.qa.russcoopersoftware.com` and
`organizeme.russcoopersoftware.com` — confirming the compiled design-refresh stylesheet and the
new no-fallback registry wiring both work end-to-end in every environment.
