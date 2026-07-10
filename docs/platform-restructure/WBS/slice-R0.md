# Slice R0 — Acquire `organize-me.app` Domain + DNS Control

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Type:** Prerequisite / manual-ops task (not a code change).

**Delivers:** A registered `organize-me.app` domain with DNS records the operator can edit —
the blocking prerequisite for provisioning the shared HTTPS Load Balancer (R5).

## What to build

Confirm or establish ownership and DNS control of `organize-me.app`. Today the domain is only
*referenced* in code (`app/core/config.py` `base_url` default, notification email links) — it
is not confirmed as registered, and no DNS/managed-cert config exists in the repo. Live traffic
currently runs on the raw `*.run.app` Cloud Run URLs.

This is an ops/setup task with no code deliverable. It exists as its own issue because the
design doc explicitly flags domain/DNS readiness as **blocking** for Load Balancer provisioning,
and the Google-managed SSL cert in R5 cannot validate until a DNS record points at the LB.

## Includes
- Register `organize-me.app` (or confirm existing registration) with a registrar the operator controls.
- Verify DNS zone access — ability to add/edit A/AAAA records for the apex and any subdomains.
- Decide apex vs. subdomain strategy for the shared platform origin (design assumes the apex `organize-me.app`).
- Note the nameserver / DNS provider for R5 (Google Cloud DNS vs. external registrar DNS).

## Design notes
- The final A/AAAA record cutover to the Load Balancer IP happens **in R5/R11/R12**, not here —
  R0 only guarantees the domain exists and DNS is editable so R5 isn't blocked.
- Keep today's `*.run.app` URLs live throughout; nothing about this task touches production traffic.

## Blocked by
- None — can start immediately.

## Acceptance criteria
- [ ] `organize-me.app` is registered to an account the operator controls.
- [ ] The operator can add/edit DNS records in its zone (verified with a throwaway TXT record).
- [ ] DNS provider / nameservers documented for R5.
- [ ] No production traffic change — existing `*.run.app` URLs still serve.

## Testing
- Manual: add and resolve a temporary TXT record to prove edit access, then remove it.
