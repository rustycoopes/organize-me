# Slice 1 — Project Scaffold + Auth + CI/CD

> Part of the OrganizeMe build plan. Shared context (stack, full schema, testing approach)
> lives in [`../implementation-plan.md`](../implementation-plan.md). This file is self-contained
> for implementing Slice 1 issues — read it instead of the full plan.

**Delivers:** Runnable app deployed to Cloud Run. Users can register, log in (email or Google),
reset password, view/edit profile, toggle dark mode, delete account.

**GitHub issues:** #10 scaffold+CI/CD · #11 DB foundation · #12 email/password auth ·
#13 Google OAuth · #14 forgot/reset password · #15 profile+dark mode+deletion ·
#16 landing page · #17 sidebar shell · #23 (Slice 1.8) Playwright E2E.

## Includes
- `pyproject.toml`, `Dockerfile`, `supervisord.conf`
- `.env.local` structure + `.gitignore`
- FastAPI app skeleton (`app/main.py`, routers, lifespan)
- Supabase connection + SQLAlchemy async engine + Alembic init migration
- FastAPI-Users setup: User model, auth backends (email/password + Google OAuth)
- `users` table migration
- Landing page (hero + features + CTA sections)
- Login / register / forgot-password / reset-password pages (DaisyUI forms)
- Profile page (name, email, phone, dark/light mode toggle)
- Sidebar shell (all nav items present but links to placeholder pages)
- GitHub Actions `ci.yml` + `deploy.yml`
- GCP Cloud Run services (QA + prod), Artifact Registry, Secret Manager secrets
- Playwright E2E suite validating the full slice against the deployed QA instance (`e2e-qa` CI job)

## Relevant schema — `users`
```
id                            UUID PK
email                         TEXT UNIQUE NOT NULL
hashed_password               TEXT
is_active                     BOOL
is_verified                   BOOL
is_superuser                  BOOL
name                          TEXT
phone_number                  TEXT NULLABLE
dark_mode                     BOOL DEFAULT FALSE
notification_sms              BOOL DEFAULT TRUE
notification_email            BOOL DEFAULT TRUE
onboarding_storage_done       BOOL DEFAULT FALSE
onboarding_notifications_done BOOL DEFAULT FALSE
onboarding_first_upload_done  BOOL DEFAULT FALSE
created_at                    TIMESTAMPTZ
updated_at                    TIMESTAMPTZ
```

## Relevant endpoints (all under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| POST | /auth/register | Email/password registration |
| POST | /auth/login | Login, set JWT cookie |
| POST | /auth/logout | Clear cookie |
| GET/POST | /auth/google | Google OAuth flow |
| POST | /auth/forgot-password | Send reset email |
| POST | /auth/reset-password | Apply new password |
| GET/PATCH | /users/me | Get/update profile |
| DELETE | /users/me | Delete account |

HTML pages served at root paths: `/`, `/login`, `/register`, `/forgot-password`,
`/reset-password`, `/profile`.

## Design notes
- **Auth:** FastAPI-Users, JWT in HTTPOnly cookies, 7-day expiry. bcrypt password hashing.
- **Sidebar order:** Dashboard → Upload → Processing → Logs → Prompt → Settings → Profile.
- **Account deletion:** immediate and permanent — all user data deleted, user logged out.
  No soft delete or grace period.
- **CI/CD:** `ci.yml` (PR: test + mypy + build + deploy to QA), `deploy.yml`
  (main merge: test + deploy to prod).

## Testing
- Auth tests: register, login, forgot-password flows via httpx TestClient.
- Playwright `e2e-qa`: landing page, register/login/logout, forgot/reset password,
  dark/light toggle persistence, profile edit, account deletion, sidebar nav.
  Google OAuth excluded from E2E (unreliable headlessly) — covered by backend tests.
