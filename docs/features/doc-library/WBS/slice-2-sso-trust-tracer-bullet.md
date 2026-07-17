# Slice 2 — SSO-trust tracer bullet

> Part of the `doc-library` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** `/doc-library` is reachable through the shared platform domain, appears in the
sidebar, renders the shared chrome (including dark-mode) for a logged-in user, and redirects an
unauthenticated visitor to the Host's login — proving the entire cross-repo trust seam end to end
before any real feature logic is built.

## What to build

An empty-state `/doc-library` page wired into the full platform seam:

- Pin `organizeme-chrome` in the new repo at the current `chrome-v*` tag; use it to render
  `chrome_base.html`/`chrome_authenticated_base.html` for the page.
- `GET /doc-library` page route: resolves the current user via
  `Depends(current_user_id_optional)` (copied verbatim from `event-creator`'s `app/core/auth.py`
  JWT-verify pattern), redirects to the Host's `/login` when unauthenticated, otherwise renders an
  empty-state page (no doc links exist yet — that's fine, Slice 3 adds them) using the shared
  chrome.
- Reads and passes `dark_mode` into the template context via a `HostUser`/`get_dark_mode()`
  helper (cross-schema read-only mapping to `host.users`), matching the R7 gotcha pattern — do not
  skip this the way early `event-creator` page ports did.
- Host-repo PR: add the `doc-library` `AppEntry` to `packages/chrome/src/organizeme_chrome/
  registry.py` (`nav=[AppNavItem("/doc-library", "Doc Library")]`, `settings_tabs=[]`,
  `api_prefixes=["/api/v1/doc-links", "/doc-library/fragments"]` — the prefixes aren't used by any
  route yet, but registering them now avoids a second registry PR in Slice 3).
- Provision `doc-library-qa`'s Serverless NEG + backend service (`infra/gcp_lb/provision.sh`),
  regenerate the URL map (`infra/gcp_lb/generate_url_map.py`) and import it
  (`gcloud compute url-maps import organizeme-qa-url-map ...`).

## Design notes

Implements TDD's "Manual setup" section B and the "No login/session code" / JWT-verify design
decisions. Mirrors `event-creator`'s Slice R6 almost exactly — see
[`host-integration-guide.md`](../../../host-integration-guide.md)'s R6 section for the pattern and
its one gotcha (the Host's own `organizeme-chrome` pin must also be bumped, or the live URL map
silently stays on the pre-registration registry snapshot).

**Sequencing risk (flagged in the TDD):** `provision.sh` will fail if `doc-library-qa` isn't
already deployed (Slice 1) — order is strictly deploy service → merge registry PR → run
`provision.sh` → regenerate/import the URL map.

## Blocked by

- Slice 1 (needs a deployed `doc-library-qa` Cloud Run service to point the NEG/backend at)

## Acceptance criteria

- [ ] Unauthenticated `GET https://organizeme.qa.russcoopersoftware.com/doc-library` redirects to
      the Host's `/login`.
- [ ] Authenticated request renders the empty-state page with the shared sidebar/header chrome,
      "Doc Library" present in the sidebar nav.
- [ ] A user with `dark_mode=true` in their Host Profile sees the page rendered in dark mode (not
      hardcoded light).
- [ ] A tampered/garbage `organizeme_auth` cookie value is rejected (treated as unauthenticated),
      not trusted.
- [ ] `organizeme-chrome` pin in the new repo matches the registry entry actually live in
      `organize-me`'s `main` at time of merge (no stale-pin gap per the R6/R11 gotcha).

## Testing

HTTP-level: `tests/test_doc_library_page.py` (mirrors `event-creator`'s
`tests/test_dashboard_auth.py` / `tests/test_dashboard_page.py`) — unauthenticated redirect,
authenticated 200 + empty-state content, tampered-token rejection, `dark_mode` context flows
through. No new cross-repo boundary spec is needed in `organize-me` for this slice specifically —
the existing `host-event-creator-boundary.spec.ts`-style coverage already asserts the generic
Host↔hosted-app auth seam; only add a Doc-Library-specific boundary spec later if a
Doc-Library-specific auth edge case is found (per the TDD's Testing Approach).

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
