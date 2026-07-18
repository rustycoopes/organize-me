# App-level OIDC verification (not Cloud Run IAM invoker) for the registry endpoint

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`registry-decoupling`](../features/registry-decoupling/TDD.md)

## Context

The Host's new `GET /internal/app-registry.json` endpoint needs to reject anything but a request
from one of the platform's own consumer services. Two real mechanisms exist on Cloud Run:

1. **App-level verification**, mirroring the existing `POST /internal/pipeline/run` pattern
   (event-creator): the service stays `--allow-unauthenticated` overall, and the one internal
   route verifies a Google-signed OIDC token's `aud`+`email` claims in application code
   (`google.oauth2.id_token.verify_oauth2_token`).
2. **Cloud Run's built-in IAM invoker gate**: mark the Host service (or just this route, via a
   second Cloud Run service/ingress rule) as requiring `roles/run.invoker`, granted to the shared
   runtime service account every service already runs as. Cloud Run rejects unauthorized calls at
   the platform level, before any application code runs.

The existing `/internal/pipeline/run` endpoint uses (1) out of necessity — it must stay
`--allow-unauthenticated` because real user-facing routes share the same Cloud Run service. But
this platform's design review flagged that (2) is actually the mechanism Cloud Run's IAM-based
invoker auth was built for: a consumer service *pulling* from another service, both already
running as the same identity, with a one-line no-op grant (the SA already exists) rather than a
new-SA-per-consumer proliferation.

## Decision

Use app-level OIDC verification (option 1), consistent with the existing
`/internal/pipeline/run` pattern — copy its verification shape (check `aud` against the Host's own
audience URL, `email` against the shared runtime service account) into a new dependency on the
registry endpoint.

This is a **consistency choice, not a forced one.** The IAM grant needed for option 2 would be
identical in cost to what option 1 already assumes (the shared SA has zero new grants to make
either way) — so anyone revisiting this decision later should not assume IAM was infeasible or
expensive. The reason to prefer app-level verification here is that it keeps exactly one mental
model and one code pattern for "internal route" across the platform, rather than two different
protection mechanisms for what are conceptually the same kind of endpoint (an internal,
non-public, service-to-service route).

## Alternatives considered

- **Cloud Run IAM invoker gate.** Rejected for consistency reasons above, not cost or feasibility.
  Would mean the registry endpoint can no longer be curled directly with a hand-minted token for
  local debugging without also configuring IAM-aware tooling (`gcloud auth print-identity-token`
  + invoker grant) — a minor developer-experience regression traded against removing a whole class
  of app-level token-verification bugs. If a future internal endpoint doesn't need to coexist with
  public routes on the same service, this alternative is worth revisiting rather than defaulting
  to app-level verification out of habit.
- **Secret Manager-sourced Host URL, mirroring how OAuth client secrets are stored.** Rejected: the
  Host's per-environment `*.run.app` URL isn't confidential — it's effectively public
  infrastructure topology (Cloud Run URLs aren't secret even today, they're just not linked from
  anywhere). Adding a `--set-secrets` entry for it would be needless Secret Manager overhead for a
  non-secret value. It's set as a plain env var in each consumer's `deploy.yml`/CI config instead,
  alongside other already-plain values like `GOOGLE_DRIVE_REDIRECT_URI`.
- **Self-referential Host URL discovery**, mirroring `PIPELINE_ENDPOINT_URL`'s pattern (captured
  from `gcloud run services describe` in a follow-up deploy step, since a service can't know its
  own URL before its first deploy). Rejected: that pattern exists because a service needs to know
  *its own* just-deployed URL. Here, a consumer needs the *Host's* URL, and the Host already
  exists and has a stable URL in both environments before any consumer's registry-fetch migration
  ships — no self-referential bootstrapping problem exists, so the extra deploy-step complexity
  buys nothing.

## Consequences

- The registry endpoint and `/internal/pipeline/run` share one verification code shape,
  duplicated (not centralized) across the organize-me and event-creator repos today — a real,
  flagged-but-not-blocking duplication. Factoring a shared `oidc.py`-style helper is left as a
  follow-up, not part of this feature (see TDD Open Questions).
- If the Host's Cloud Run service is ever recreated (not just redeployed) under a new random
  `*.run.app` suffix, every consumer's hardcoded `HOST_INTERNAL_URL` constant goes stale silently
  — no automatic re-discovery exists under this decision. Worth a code comment at the constant's
  definition site; not worth building a discovery mechanism for an event that hasn't happened on
  this platform to date.
- Debugging the registry endpoint directly (e.g. `curl`) requires hand-minting a matching OIDC
  token, same friction the existing `/internal/pipeline/run` endpoint already has — no new
  debugging burden introduced beyond what's already accepted platform-wide.
