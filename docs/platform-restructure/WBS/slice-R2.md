# Slice R2 — Decouple Event-Creator Data from the Host `users` Model

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** Event-Creator-owned user settings moved off the Host `users` table into the
`event_creator` schema, and the registration-time `LLMPrompt` seed removed — so the Host user
model no longer carries or writes any Event-Creator data.

## What to build

Two of today's Host↔Event-Creator couplings live in the data layer. This slice removes both,
still inside the monolith:

1. **Settings columns on `users`.** `notification_sms`, `notification_email`, and the three
   onboarding flags (`onboarding_storage_done`, `onboarding_notifications_done`,
   `onboarding_first_upload_done`) are conceptually Event-Creator settings but sit on the Host
   `users` table and are written by Event-Creator flows. Move them into a new
   `event_creator`-owned table keyed by `user_id`.
2. **Registration seed.** `app/auth/users.py::on_after_register` inserts an `LLMPrompt` row — a
   Host action reaching into Event-Creator's domain. Drop it; rely on the existing lazy
   `get_or_create_user_prompt` in `app/api/v1/llm_prompt.py` to create the prompt on first use.

End-to-end: notifications toggles, the onboarding checklist, and the prompt page all behave
identically, but the Host code path no longer references Event-Creator columns or seeds
Event-Creator rows.

## Includes
- New table `event_creator.user_settings` (or similar): `user_id` (FK → `host.users.id`,
  cascade), `notification_sms`, `notification_email`, `onboarding_storage_done`,
  `onboarding_notifications_done`, `onboarding_first_upload_done`, timestamps.
- Data migration: backfill the new table from existing `users` columns, then drop the columns
  from `users`.
- Repoint writers/readers: `app/pages/settings.py`, `app/templates/settings.html` (Notifications
  tab → `/api/v1/users/me` today), `app/core/onboarding.py`, `app/api/v1/upload.py`,
  `app/api/v1/users.py` (PATCH currently flips `onboarding_notifications_done`).
- Remove the `LLMPrompt` insert from `app/auth/users.py::on_after_register`; confirm
  `get_or_create_user_prompt` covers first-visit creation and the Prompt page's reset flow.

## Relevant files
- `app/models/user.py` — drop moved columns; `app/models/` — new `user_settings` model.
- `app/auth/users.py` — remove seed from `on_after_register`.
- `app/api/v1/llm_prompt.py` — confirm lazy `get_or_create_user_prompt` path.
- `app/pages/settings.py`, `app/templates/settings.html`, `app/core/onboarding.py`,
  `app/api/v1/upload.py`, `app/api/v1/users.py` — repoint reads/writes.
- `migrations/versions/` — backfill + column-drop migration in the `event_creator` schema.

## Design notes
- Notifications/onboarding endpoints may still be exposed under the same URLs for now; only the
  storage layer changes. The URL ownership move to Event Creator happens in R7.
- Backfill-then-drop keeps rollback safe (columns can be re-added and re-backfilled if needed).
- The lazy prompt seed already exists — this slice just deletes the eager Host-side seed and
  verifies the lazy path on a brand-new account.

## Blocked by
- R1 (the `event_creator` schema must exist to own the new table).

## Acceptance criteria
- [ ] `notification_*` and `onboarding_*` no longer exist on `host.users`; they live in the new
      `event_creator` settings table, backfilled with existing values.
- [ ] Notification toggles, the onboarding checklist, and account-scoped settings behave
      identically in QA.
- [ ] `on_after_register` no longer inserts an `LLMPrompt`; a newly-registered user still gets a
      working default prompt on first visit to the Prompt page, and Reset-to-Default still works.
- [ ] pytest + mypy + QA E2E pass.

## Testing
- Migration test: backfill correctness (values preserved) + columns dropped.
- New-user test: register → Prompt page auto-creates the default prompt (no eager seed).
- Regression: notification toggle + onboarding-checklist E2E specs still pass.
