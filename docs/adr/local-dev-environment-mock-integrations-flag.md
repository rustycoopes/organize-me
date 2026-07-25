# A new `MOCK_INTEGRATIONS` flag, ORed alongside each app's existing test-mode branch, no shared abstraction

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`local-dev-environment`](../features/local-dev-environment/TDD.md)

## Context

Several hosted apps' UI depends on costly or side-effecting third-party integrations — Gemini LLM
calls, Twilio SMS, Resend email, Google Drive/Dropbox OAuth, and `ha-dashboard`'s Home Assistant
WebSocket connection. Each already has, or is close to having, a `Protocol` + real implementation +
fake implementation. The existing `E2E_TEST_MODE` flag already triggers similar fake-selection
behavior in `event-creator`, but that flag also exposes a Playwright-only internal endpoint
(`GET /api/v1/internal/e2e/last-reset-token`) that shouldn't be incidentally switched on just to
get mocks for everyday local dev.

Auditing the actual call sites surfaced that they're at different levels of readiness, not a
single uniform pattern to extend:

- `event-creator`'s `build_storage_provider()` and Gemini client factory already branch on
  `settings.e2e_test_mode` to select an existing fake — these only need one more `or` clause.
- `event-creator`'s notification-pipeline factory (`get_pipeline_notifier()`) has **no branch at
  all today** — it unconditionally returns the real Twilio/Resend-backed sender, even under
  `E2E_TEST_MODE` — so a new branch needs adding, not extending.
- `ha-dashboard`'s HA-transport selection is a bare constructor default
  (`transport_factory: HATransportFactory = WebSocketsHATransport`), not a settings-driven factory
  function at all, and its `FakeHATransport` currently lives only in that repo's own test suite —
  both need building/promoting before they can be a runtime-selectable option.
- `doc-library` has no third-party integration and needs nothing here.

## Decision

Add a new, independent boolean setting, `mock_integrations` (default `False`), to every hosted
app's `Settings` that has at least one such integration (`event-creator`, `ha-dashboard`). Each
app's real-vs-fake selection point ORs this flag alongside its existing (or newly-added)
`e2e_test_mode` check, so the two flags can be set together when a developer specifically wants
both effects (e.g. running the e2e suite locally with mocks on). No shared cross-repo abstraction
is introduced for this: the known call sites differ enough in shape — a multi-way provider-type
dispatch, a binary real/fake client swap, and a seam that doesn't exist as a branch yet — that
unifying them now would either be a no-op wrapper or force incompatible dispatch shapes into one
interface. Instead, the convention is written down once, in the platform's hosted-app-onboarding
documentation (`how-to-add-a-hosted-app.md`): *"add `mock_integrations: bool = False` to your own
Settings; OR it into your existing or newly-added real-vs-fake selection point."*

## Alternatives considered

- **Reuse `E2E_TEST_MODE` for this too.** Rejected: conflates "I'm running the Playwright e2e
  suite" with "I'm a developer clicking around locally," and would incidentally expose the
  reset-token endpoint outside CI just because a developer wanted mocked integrations.
- **A shared `organizeme_chrome`-level "integration mode" concept** every app's settings compose.
  Rejected for now: would be the first time that package reaches into runtime settings/DI territory
  (today scoped entirely to routing/nav data), forcing a version bump across every hosted app for
  behavior that's purely local-dev-only. Worth revisiting only if a future integration's shape
  turns out to genuinely match an existing one closely enough that sharing real code — not just a
  documented convention — actually pays for itself.

## Consequences

- Three of the (currently) two apps' integration points need real, differently-sized work, not a
  uniform one-line flag add: `event-creator`'s storage/Gemini factories need one clause each;
  `event-creator`'s notification-pipeline factory needs a new branch built; `ha-dashboard`'s HA
  transport needs a new settings-driven factory function built and its existing test-only
  `FakeHATransport` promoted into application code (mirroring where `event-creator`'s other fakes
  already live). These should be scoped and sized as separate WBS items per app, not folded into a
  single "add the flag" task.
- A future fifth hosted app's author follows the documented convention rather than
  reverse-engineering it from `event-creator`'s diff — enforced by documentation and code review,
  not by a shared type system.
