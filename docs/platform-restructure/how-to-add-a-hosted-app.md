# How to Add a Hosted App

This is the playbook for standing up a **new** hosted app in the OrganizeMe platform — the
process `event-creator` (R6-R13) established, now written up as a repeatable pattern per the
Platform Restructure PRD's "adding a future app's nav entry + settings tab is a single Host
config change + redeploy" success metric.

It complements [`host-integration-guide.md`](host-integration-guide.md) (the slice-by-slice
"what infra/routing/secrets did each Platform Restructure slice actually require" log) — this
doc is the condensed, forward-looking "start here" version for app #3 and beyond. Every example
below is the real `event-creator` entry/config, not a hypothetical.

## 0. The one-sentence version

A hosted app is its own repo, its own Cloud Run service(s), and its own DB schema; it never
handles login, sessions, or passwords; it trusts a Host-issued JWT cookie; and it plugs into the
Host's sidebar/Settings/Load-Balancer routing entirely by adding one entry to a Python file in
the Host repo (`packages/chrome/src/organizeme_chrome/registry.py`) and regenerating the LB's
URL map from it.

## 1. The Host app-registry entry

`packages/chrome/src/organizeme_chrome/registry.py` is the single source of truth for a hosted
app's nav items, Settings tabs, and API path prefixes. Rendering (the shared chrome package) and
the Load Balancer's routing (step 2 below) are both driven from this one list — never
hand-maintain either separately.

The real `event-creator` entry, as of R13:

```python
AppEntry(
    service_name="event-creator",
    nav=[
        AppNavItem("/dashboard", "Dashboard"),
        AppNavItem("/upload", "Upload"),
        AppNavItem("/processing", "Processing"),
        AppNavItem("/logs", "Logs"),
        AppNavItem("/prompt", "Prompt"),
    ],
    settings_tabs=[
        SettingsTab("storage", "Storage"),
        SettingsTab("notifications", "Notifications"),
        SettingsTab("preferences", "Preferences"),
    ],
    api_prefixes=[
        "/api/v1/storage-config",
        "/api/v1/user-settings",
        "/settings/event-creator",
        "/api/v1/events",
        "/api/v1/llm-prompt",
        "/api/v1/upload",
        "/api/v1/import-pending-files",
        "/api/v1/processing-runs",
        "/processing-runs",
        "/api/html/processing-runs",
    ],
),
```

What each field does:

- **`service_name`** — the Cloud Run backend-service name suffix (`generate_url_map.py` builds
  `{service_name}-backend{-prod suffix}` from it) and the key you pass to
  `organizeme_chrome.registry.get_app(service_name)`.
- **`nav`** — `(path, label)` pairs. These render in the shared sidebar (merged across every
  registered app — see `organizeme_chrome.templating.register_chrome`, which builds
  `nav_items = [item for entry in list_apps() for item in entry.nav]`) **and** become URL-map
  path rules pointing at your service (step 2). Adding a nav item is simultaneously "show this in
  the sidebar" and "route this path to my backend" — one edit, both effects.
- **`settings_tabs`** — `(id, label)` pairs. Unlike `nav`, these don't get their own routes: the
  Host's `/settings` page (`app/pages/settings.py` in this repo) renders the tab bar and fetches
  each tab's *content* from your app at `GET /settings/{service_name}/{tab.id}` via HTMX
  (`hx-get`, `hx-trigger="load"`) — same-origin request through the shared LB domain, so the
  `organizeme_auth` cookie flows automatically. Your app owns the fragment route
  (`event-creator`'s is `app/pages/settings_fragments.py`); the Host never renders your tab's
  markup itself. If a tab needs no LB routing change, that's why: it's not a top-level nav path,
  it's a fragment fetched under a prefix your `api_prefixes` already covers.
- **`api_prefixes`** — every other route your app owns beyond its nav pages: your `/api/v1/*`
  surface and any `/settings/{service_name}/*` fragment routes. Feeds `generate_url_map.py` so the
  LB's path rules cover your **full** route surface, not just the pages that show up in the
  sidebar (this exact gap — API routes with no matching nav entry — was issue #178, fixed by
  adding this field).

**Concrete example if you're adding app #3** (say, a hypothetical `reminders` app with a single
`/reminders` nav page and a `Reminders` Settings tab, no other API routes beyond its own page):

```python
AppEntry(
    service_name="reminders",
    nav=[AppNavItem("/reminders", "Reminders")],
    settings_tabs=[SettingsTab("reminders", "Reminders")],
    api_prefixes=["/api/v1/reminders", "/settings/reminders"],
),
```

Add it to the `APPS` list in `registry.py`, bump `packages/chrome`'s version, and publish a new
`chrome-v*` tag (see step 3) — that's the entire Host-side change.

## 2. Load-Balancer URL-map regeneration

`infra/gcp_lb/generate_url_map.py` turns the registry above into the shared LB's URL-map path
rules automatically:

```bash
uv run python -m infra.gcp_lb.generate_url_map          # QA, prints YAML
uv run python -m infra.gcp_lb.generate_url_map prod      # prod, renames every backend -prod
```

Rules, enforced at generation time (build-time guards, not runtime checks):

- The Host's own fixed routes (`HOST_PATHS` in that module — `/`, `/login`, `/register`,
  `/forgot-password`, `/reset-password`, `/profile`) always win a collision; they aren't sourced
  from the registry at all, since they're Host-owned and never delegated to a hosted app.
- Two non-Host apps claiming the same nav path, or the same `api_prefixes` entry, is a hard
  error — the generator refuses to produce an ambiguous URL map.
- Each `api_prefixes` entry also gets its own `/*` wildcard pattern (GCP's URL-map path matching
  is an exact-string prefix match, not path-segment-aware — see the module's own docstring for
  why `"/processing-runs"` and `"/api/v1/processing-runs"` need separate entries despite looking
  related).

You need a Cloud Run service (and its own Serverless NEG + backend service in the LB) to exist
**before** your registry entry's paths mean anything — that's a one-time manual `gcloud` step via
`infra/gcp_lb/provision.sh` (QA) / `provision-prod.sh` (prod), the same idempotent script that
provisioned `event-creator`'s NEG/backend in R6. Once your service and registry entry both exist,
re-running the generator and importing it (`gcloud compute url-maps import
organizeme{-prod}-url-map --source=<generated.yaml>`) is the only routing step for every
subsequent nav/prefix change — you never hand-edit LB resources directly.

## 3. The shared-chrome-package dependency

Every hosted app pins `organizeme-chrome` as a direct dependency, published by the Host's own CI
as a versioned GitHub Release wheel/sdist on `chrome-v*` tag push (a git-tag dependency pin, not
a private PyPI registry):

```toml
# event-creator's pyproject.toml, real pin as of R13:
"organizeme-chrome @ git+https://github.com/rustycoopes/organize-me@chrome-v0.4.0#subdirectory=packages/chrome",
```

What it gives you:

- **Chrome templates** (`chrome_base.html`, `chrome_authenticated_base.html`, the sidebar,
  `macros/chrome_tabs.html`) — extend these for every page your app renders; never hand-roll
  sidebar/header markup. `organizeme_chrome.templating.register_chrome(env, app_service_name)`
  wires your Jinja environment up to them and exposes `nav_items`/`settings_tabs`/theme globals.
- **The app-registry data** (`organizeme_chrome.registry.get_app`/`list_apps`) — read-only from a
  hosted app's side; only the Host repo edits `registry.py` itself.
- **The JWT-verify helper** (`organizeme_chrome.jwt_verify`) — see step 4.
- **Theme constants** (Tailwind/DaisyUI CDN links, `theme_attr`) for a consistent look with zero
  build step.

Bumping the pin is a **deliberate, explicit action in your own repo** — a Host-side chrome edit
never silently changes what your app renders until you bump and redeploy. This bit an actual
slice: R6 shipped with a stale pin that silently kept the live URL map on a pre-split registry,
and again in R11 event-creator's pin had drifted to `chrome-v0.2.0` (missing R7's `api_prefixes`
field) with zero observable effect until something started depending on the missing field.
**Lesson: bump the pin in the same PR that needs the new registry data, and don't assume "no
visible bug" means the pin is current** — verify it explicitly (`grep organizeme-chrome
pyproject.toml`) when debugging anything registry-related.

## 4. The JWT-verify-helper usage pattern

A hosted app never handles login, sessions, or password verification — identity comes entirely
from verifying the Host-issued `organizeme_auth` cookie's JWT. `organizeme_chrome.jwt_verify`
(HS256, PyJWT-based, checks signature + expiry + the `fastapi-users:auth` audience only — no
`fastapi-users` import, no DB/network call) is the standalone helper every hosted app depends on
for this.

`event-creator`'s real implementation, `app/core/auth.py`:

```python
AUTH_COOKIE_NAME = "organizeme_auth"  # must match the Host's CookieTransport cookie_name

def current_user_id_optional(request: Request) -> uuid.UUID | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token is None:
        return None
    try:
        subject = verify_token(token, get_settings().jwt_secret)
        return uuid.UUID(subject)
    except (InvalidTokenError, ValueError):
        return None

def current_user_id(request: Request) -> uuid.UUID:
    user_id = current_user_id_optional(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id
```

Usage rules:

- **Page routes** depend on `current_user_id_optional` and redirect `None` to the Host's
  `/login` — a hosted app owns no login page of its own.
- **API routes** depend on `current_user_id` (raises 401) — the hosted-app equivalent of
  fastapi-users' `current_active_user`.
- Your Cloud Run service reads `JWT_SECRET` from the **exact same** GCP Secret Manager secret as
  the Host (`jwt-secret-{qa,prod}`, `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest`) — that
  byte-identical value is the entire SSO trust mechanism, not a coincidence.
- Never call the Host over the network to check a session, and never store your own session
  state — the JWT alone is the complete, stateless proof of identity.
- If your app needs to read Host-owned fields (e.g. `email`, `phone_number`) for display, do it
  via a read-only, cross-schema SQL mapping (`event-creator`'s `HostUser` — a SELECT-only ORM
  class over `host.users`, registered on your app's own `Base`/`MetaData` so
  `ForeignKey("host.users.id")` resolves), never a server-to-server API call to the Host at
  request time.

## 5. Test ownership

Unit tests and e2e tests live with the code they exercise, in the app's **own** repo:

- Every `event-creator` unit test (models, API endpoints, pipeline, storage providers, LLM
  prompt) lives in `event-creator/tests/`, and every `event-creator` Playwright spec lives in
  `event-creator/e2e/tests/` — none of it lives in this (`organize-me`) repo. R13 (#168) deleted
  the Host's now-redundant copies once `event-creator`'s own suite had equivalent (verified
  passing) coverage.
- **Exception: cross-repo boundary tests.** `e2e/tests/host-event-creator-boundary.spec.ts` stays
  in the Host, permanently — it asserts the *seam* between the two apps (logout at the Host
  clears the cookie a hosted app relies on; a hosted app's JWT-verify rejects a garbage/tampered
  token), not either app's internals. A future third app should get the same treatment: any test
  that exercises "does the Host's auth/cookie contract still hold from another app's point of
  view" belongs in the Host as a boundary spec; everything else belongs in that app's own repo.
- If your app's own CI wants to catch a boundary regression proactively (not just wait for the
  Host's CI to catch it), follow `event-creator`'s pattern: add a job that checks out the Host
  repo at a fixed ref and runs only the relevant boundary spec(s) against your freshly-deployed
  QA service (see `event-creator`'s `e2e-boundary-qa` CI job).

## 6. Quick-start checklist

Distilled from the above (and `host-integration-guide.md`'s own quick-start section) — everything
you need for a brand-new hosted app from scratch:

1. Own git repo, own CI/CD (build → test → deploy) — never a Host build/redeploy.
2. Own `<app>-qa` / `<app>-prod` Cloud Run service pair.
3. Pinned `organizeme-chrome` dependency (step 3).
4. An entry in `registry.py` (step 1) — Host-repo PR, reviewed like any other Host change.
5. Own Postgres schema, own independent Alembic history
   (`version_table_schema = <your_schema>`) — never write to another app's schema, and never
   more than a `REFERENCES`-only grant back to `host.users.id` if you need a real FK.
6. `GCP_SA_KEY` and your own `SUPABASE_QA_URL`/`SUPABASE_PROD_URL` as GitHub Actions secrets in
   **your own** repo.
7. `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest` on your deploy step (step 4).
8. If you store third-party credentials at rest: `--set-secrets=ENCRYPTION_KEY=encryption-key-
   {qa,prod}:latest`, encrypted with a `CredentialCipher` pattern (see `event-creator`'s
   `app/core/security.py` — the Host's own copy was removed in this same slice, since it stored
   no such credentials of its own) — never plaintext.
9. No login/session/registration/password code of your own, ever (step 4).
10. No server-to-server call to the Host at request time, for anything (step 4).
11. Regenerate and import the LB URL map once your service and registry entry both exist (step 2).
12. Your own `tests/` and `e2e/` — nothing shared except the boundary spec (step 5).
