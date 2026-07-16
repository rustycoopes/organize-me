# Slice 8 — Dropbox + S3 Storage Providers

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** Settings > Storage tab fully supports all three providers.

> Note: Dropbox and S3 are independent implementations of the same `StorageProvider` ABC —
> a reasonable candidate for parallel work if splitting the slice across agents.

## Includes
- Dropbox `StorageProvider` implementation (OAuth 2.0 flow)
- S3 `StorageProvider` implementation (manual credentials: access key, secret, bucket, region)
- Settings > Storage tab updated: provider selector shows all three; form fields
  conditionally shown per provider (Alpine.js)

## Relevant schema — `storage_configs` (created in Slice 2)
S3 uses the `s3_access_key`, `s3_secret_key`, `s3_bucket_name`, `s3_region` columns;
Dropbox uses `oauth_access_token` / `oauth_refresh_token`. All credential columns are
encrypted at rest via `app/core/security.py`.

## Depends on
- Slice 2's `StorageProvider` ABC (`app/services/storage/base.py`) and encryption helpers.

## Testing
- Inject `FakeStorageProvider` per provider — never hit live credentials.
