# Slice 2 — Settings: Google Drive Storage

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** User can connect Google Drive, set a folder path, and disconnect.

## Includes
- `storage_configs` table migration
- `StorageProvider` abstract base class (`list_new_files()`, `move_file()`, `download_file()`)
- Google Drive implementation of `StorageProvider`
- Google Drive OAuth flow (auth redirect + callback + token storage encrypted)
- Settings page > Storage tab (shows Drive fields; Dropbox/S3 stubs hidden)
- Form shows/hides fields based on selected provider (Alpine.js)
- `onboarding_storage_done` flag set on first successful connection

## Relevant schema — `storage_configs`
```
id                  UUID PK
user_id             UUID FK → users (UNIQUE — one active config per user)
provider            ENUM(google_drive, dropbox, s3)
folder_path         TEXT
oauth_access_token  TEXT NULLABLE (encrypted at rest)
oauth_refresh_token TEXT NULLABLE (encrypted at rest)
s3_access_key       TEXT NULLABLE (encrypted at rest)
s3_secret_key       TEXT NULLABLE (encrypted at rest)
s3_bucket_name      TEXT NULLABLE
s3_region           TEXT NULLABLE
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| GET/PUT | /storage-config | Get/set storage config |
| POST | /storage-config/google-drive/auth | Start Google Drive OAuth |
| GET | /storage-config/google-drive/callback | OAuth callback |

## Key utilities introduced (build once, reused later)
- `app/services/storage/base.py` — `StorageProvider` ABC
- `app/core/security.py` — encryption helpers for credential storage

## Testing
- Inject `FakeStorageProvider` (implements the ABC) — never hit live credentials.
- Playwright: storage config form conditional-field behaviour.
