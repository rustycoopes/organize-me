# Slice R7 — Parity 1: Storage + Settings Tabs

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** Storage configuration (Google Drive / Dropbox / S3) and the Settings tabs
(Storage / Notifications / Preferences) rebuilt in Event Creator with full functional parity —
the first real feature area to move.

## What to build

Migrate the storage-connection and settings functionality from the monolith into the Event
Creator repo, contributing its Settings tabs to the Host-owned Settings shell via the app-registry
(R3). Behaviour is unchanged for the user: connect/disconnect a storage provider, toggle
notifications, set preferences — now served by Event Creator, reading/writing the
`event_creator`-owned tables (including the R2 settings table).

## Includes
- Storage config CRUD + provider OAuth: Google Drive, Dropbox, S3 (from
  `app/api/v1/storage_config.py`, `storage_google_drive.py`, `storage_dropbox.py`,
  `app/services/storage/*`).
- Settings tabs contributed to the Host Settings shell via the app-registry: **Storage**,
  **Notifications**, **Preferences** (routes `/settings/event-creator/{storage,notifications,preferences}`).
- Notifications toggles read/write the R2 `event_creator` settings table.
- Encrypted-at-rest credential storage carried over (`app/core/security.py` Fernet helpers).
- Cookie-set-on-OAuth-callback sites (`storage_google_drive.py`, `storage_dropbox.py`) honour the
  R4 domain-scoped cookie.

## Relevant schema — `event_creator`
- `storage_configs` (encrypted creds, one active per user), plus the R2 `user_settings`
  (notifications/onboarding).

## Relevant endpoints (moved into Event Creator)
| Method | Path | Purpose |
|---|---|---|
| GET/PUT | /api/v1/storage-config | Get/set storage config |
| POST | /api/v1/storage-config/google-drive/auth | Start Drive OAuth |
| GET | /api/v1/storage-config/google-drive/callback | Drive OAuth callback |
| … | (Dropbox / S3 equivalents) | Provider connect/disconnect |
| GET | /settings/event-creator/storage · /notifications · /preferences | Settings tabs |

## Design notes
- The **Host** still renders the Settings *shell* (tab-bar chrome); Event Creator supplies the tab
  *content* and declares the tabs via the app-registry — no Event-Creator chrome code.
- **Preferences tab** was never built in the monolith (dark-mode lives on the Host Profile); build
  it here as the Event-Creator preferences home, or leave a stub matching today — confirm scope
  during the slice.
- Storage-provider tests inject `FakeStorageProvider` (the existing ABC pattern) — never hit live
  credentials.

## Blocked by
- R6 (Event Creator scaffold + SSO trust).

## Acceptance criteria
- [ ] Connect/disconnect for Google Drive, Dropbox, and S3 works in Event Creator with parity to
      today (credentials encrypted at rest).
- [ ] The Settings shell (Host) shows Event Creator's Storage / Notifications / Preferences tabs,
      declared via the app-registry, with no Event-Creator chrome code.
- [ ] Notification toggles persist to the `event_creator` settings table and drive delivery.
- [ ] PRD stories covering storage + settings pass their acceptance criteria via the new structure.

## Testing
- Storage-provider unit tests with `FakeStorageProvider`.
- OAuth connect/disconnect happy-path per provider (Drive/Dropbox; S3 key-based).
- E2E: Settings tabs render under the Host shell and drive the correct Event Creator endpoints.
