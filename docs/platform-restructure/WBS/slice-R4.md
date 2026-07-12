# Slice R4 — Domain-Scoped SSO Cookie + Secret Manager

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The auth cookie scoped to the shared domain and the JWT signing secret served from
GCP Secret Manager — so a single sign-in at the Host produces a token every hosted app can verify
independently.

## What to build

Today the auth cookie (`organizeme_auth`, `app/auth/backend.py`) has **no `Domain=`** — it is
implicitly host-scoped, so it wouldn't ride across two services under one domain. And the JWT
signing secret is injected as a plaintext env var (GitHub secret → `--env-vars-file`), while the
design's SSO model assumes both services read the signing secret from Secret Manager.

This slice makes the cookie and secret ready for cross-service SSO, still inside the monolith
(the second service arrives in R6). No functional change for the user — login/logout behave
exactly as today, just with an explicitly domain-scoped cookie and a Secret-Manager-sourced key.

## Includes
- Set the auth cookie attributes to `Domain=<origin host>`, `Path=/`, `SameSite=Lax`,
  `HttpOnly`, `Secure` — matching today's approach but explicitly scoped to the shared origin. The
  `Domain` value is **per-environment**, sourced from config (`base_url` host), not hard-coded:
  `organizeme.russcoopersoftware.com` in prod, `organizeme.qa.russcoopersoftware.com` in QA. Scope
  to the **exact host** — never `.russcoopersoftware.com` — so the auth cookie is not sent to the
  main Squarespace site.
- Wire the JWT signing secret through **GCP Secret Manager** (`--set-secrets` on the Cloud Run
  deploy, replacing the plaintext env-var injection for this secret); the R3 verify helper reads
  the same secret.
- Keep per-environment secrets (QA vs prod signing keys) distinct, as today.
- Confirm cookie issuance sites also pick up the domain scope: `app/api/v1/auth.py`,
  `app/api/v1/storage_google_drive.py`, `app/api/v1/storage_dropbox.py`.

## Relevant files
- `app/auth/backend.py` — `CookieTransport` domain/attributes.
- `app/api/v1/auth.py` (`_redirect_with_login_cookie`), `storage_google_drive.py`,
  `storage_dropbox.py` — cookie-set call sites.
- `app/core/config.py` — `jwt_secret` sourced via Secret Manager.
- `.github/workflows/ci.yml` / `deploy.yml` — `--set-secrets` wiring for the signing secret.

## Design notes
- Logout stays client-side cookie-clear (stateless JWT) — this slice adds no server-side session
  revocation, inheriting today's property.
- Until the Load Balancer (R5) puts both services on the shared origin, testing the domain scope
  in QA means exercising it against the shared-domain QA setup once R5 lands; the cookie/secret
  wiring itself is verifiable now.
- Secret-rotation policy inherits today's approach unless a reason emerges to change it (open item).

## Blocked by
- R3 (the standalone JWT-verify helper the hosted-app side will use).
- R0 (DNS control of the `russcoopersoftware.com` subdomains — the origin host the cookie is scoped to).

## Acceptance criteria
- [ ] The auth cookie is issued with `Domain=<per-env origin host>` (`organizeme.russcoopersoftware.com`
      / `organizeme.qa.russcoopersoftware.com`), `Path=/`, `SameSite=Lax`, `HttpOnly`, `Secure`
      from every issuance site.
- [ ] The JWT signing secret is read from GCP Secret Manager on Cloud Run (not a plaintext
      env-vars-file entry) for both QA and prod.
- [ ] Login and logout behave identically for the user in QA.
- [ ] The R3 verify helper validates a token signed with the Secret-Manager-sourced key.
- [ ] pytest + mypy + QA E2E pass.

## Testing
- Inspect the `Set-Cookie` header in QA — assert the `Domain`/`SameSite`/`Secure` attributes.
- Verify a token signed with the Secret-Manager key passes the R3 helper.
- Regression: existing auth/login/logout E2E specs pass.
