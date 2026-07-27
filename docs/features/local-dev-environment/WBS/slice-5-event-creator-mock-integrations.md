# Slice 5 — `event-creator`: `mock_integrations` flag

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer running `event-creator` locally (Slice 4) with `MOCK_INTEGRATIONS=true`
can click all the way through the upload → extraction → notification pipeline — no real Google
Drive/Dropbox OAuth, no real Gemini API call/cost, no real Twilio SMS or Resend email sent — using
`event-creator`'s existing, already-tested fake implementations.

## What to build

Add `mock_integrations: bool = False` to `event-creator`'s `Settings`.

- `build_storage_provider()` (`app/services/storage/factory.py`): add `or
  settings.mock_integrations` alongside its existing `e2e_test_mode` check — both already select
  the existing fake storage provider.
- The Gemini client factory (`app/services/llm/gemini.py`): same one-clause addition, selecting
  the existing canned-response fake.
- `get_pipeline_notifier()` (`app/services/notifications/pipeline.py`): currently has **no**
  real/fake branch at all — add one, selecting `FakeSmsSender`/the fake email sender when
  `mock_integrations or e2e_test_mode` is true, real Twilio/Resend-backed senders otherwise.

The two flags (`mock_integrations`, `e2e_test_mode`) stay independent and OR-able — setting both
together (e.g. running the e2e suite locally with mocks on) must not be blocked.

## Design notes

Full rationale (including why no shared cross-repo abstraction is introduced) in
[`docs/adr/local-dev-environment-mock-integrations-flag.md`](../../../adr/local-dev-environment-mock-integrations-flag.md).
The ADR explicitly calls out that `event-creator`'s three integration points are at different
levels of readiness — two need only one added clause, the notification-pipeline factory needs a
new branch built from scratch — size the PR accordingly rather than assuming uniform effort.

## Blocked by

- [Slice 4](slice-4-event-creator-launcher-integration.md) — needs `event-creator` running via the
  local launcher at all before its mocked pipeline is clickable end-to-end.

## Acceptance criteria

- [ ] `MOCK_INTEGRATIONS=true` (unset `E2E_TEST_MODE`) selects the fake storage provider, fake
      Gemini client, and fake SMS/email senders — verified via each factory/provider-selection
      function directly, not just manual clicking.
- [ ] With both flags unset, all three still select their real implementations (no regression to
      default/QA/prod behavior).
- [ ] Setting both `MOCK_INTEGRATIONS=true` and `E2E_TEST_MODE=true` together works — mocks apply
      and the Playwright-only reset-token endpoint is exposed, exactly as `E2E_TEST_MODE` alone
      already does.
- [ ] Manually clicking through the upload → extraction → notification flow locally with
      `MOCK_INTEGRATIONS=true` completes with no real Drive/Gemini/Twilio/Resend network call made
      (verifiable via the fakes' own call-recording, or via network-call absence).

## Testing

Exactly the pattern `event-creator` already uses for its `E2E_TEST_MODE`-driven fake-provider
selection: a direct test of each factory/provider-selection function asserting it returns the fake
implementation when `mock_integrations` is set and the real implementation otherwise.
`tests/test_storage_factory.py` and `tests/test_gemini.py` are the direct prior art to extend; the
new `get_pipeline_notifier()` branch needs an equivalent new test following the same shape.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-27, issue event-creator#37, branch `feature/mock-integrations-flag`)

Shipped as described: `Settings.mock_integrations: bool = False`, OR'd alongside `e2e_test_mode`
at `build_storage_provider()` and `get_gemini_client()` (one-clause additions), and a new branch
built from scratch in `get_pipeline_notifier()` — under either flag it still returns
`RealNotificationSender` (preserving per-user email/SMS preference gating and templating) but with
`FakeEmailSender`/`FakeSmsSender` injected in place of the real Resend/Twilio clients.

One addition beyond the three named call sites: code review surfaced that
`app/api/v1/import_pending_files.py`'s `get_import_storage()` has its own early
`e2e_test_mode`-only gate ahead of `build_storage_provider()` (used because the import-pending-files
endpoint has no ephemeral-storage fallback, unlike manual upload) — `MOCK_INTEGRATIONS` alone
wouldn't have bypassed the connected-storage requirement there. OR'd the same flag in for
consistency, with a mirrored test. Also added `MOCK_INTEGRATIONS` to `.env.local.example` for
discoverability, and reworded the `Settings` docstring's reset-token-endpoint aside (carried over
from the ADR/organize-me context) to clarify event-creator itself has no such endpoint.

Filed as a follow-up rather than fixed here: `is_storage_connected()`
(`app/api/v1/storage_config.py`) and `upload_page()`'s `using_ephemeral` check
(`app/pages/upload.py`) still branch on `e2e_test_mode` only, so the "storage not connected"/
"using ephemeral storage" UI banners don't reflect `mock_integrations` — cosmetic (no real network
calls are affected), tracked as
[event-creator#39](https://github.com/rustycoopes/event-creator/issues/39).

`tests/test_storage_factory.py`, `tests/test_gemini.py`, `tests/test_pipeline_notifications.py`,
and `tests/test_import_pending_files_api.py` were extended with `mock_integrations`-alone,
`e2e_test_mode`-alone, both-together, and both-unset cases for every affected factory/provider
function — `mypy app tests` and the full non-DB-dependent test suite pass locally; DB-backed
integration tests (including the pre-existing `e2e_test_mode` equivalent) couldn't be exercised in
this sandbox due to no local network route to the shared Supabase pooler, left to CI.
