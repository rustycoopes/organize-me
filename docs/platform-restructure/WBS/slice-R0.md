# Slice R0 — Establish DNS Control for `organizeme.russcoopersoftware.com` (Squarespace subdomain)

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Type:** Prerequisite / manual-ops task (not a code change).

**Delivers:** Editable DNS for the platform subdomains on the existing, operator-owned
`russcoopersoftware.com` domain (managed at Squarespace) — the blocking prerequisite for
provisioning the shared HTTPS Load Balancer (R5) and its Google-managed SSL cert.

The shared platform origins are:
- **Production:** `organizeme.russcoopersoftware.com`
- **QA:** `organizeme.qa.russcoopersoftware.com`

## What to build

No domain purchase is required — `russcoopersoftware.com` is already registered and managed at
Squarespace. This slice confirms the operator can add/edit **Custom DNS Records** for the two
subdomains above, so R5 can point them at the Load Balancer IP and issue managed certs.

Today the platform domain is only *referenced* in code (`app/core/config.py` `base_url` default,
notification email links, previously `organize-me.app`) — no DNS/managed-cert config exists in the
repo and live traffic runs on the raw `*.run.app` Cloud Run URLs.

This is an ops/setup task with no code deliverable. It exists as its own issue because the design
doc flags domain/DNS readiness as **blocking** for Load Balancer provisioning: the Google-managed
SSL cert in R5 cannot validate until an A/AAAA record for the subdomain resolves to the LB.

## Includes
- Confirm access to Squarespace's DNS panel for `russcoopersoftware.com` → **Custom Records**.
- Verify you can add/edit **A, AAAA, and TXT** records for the `organizeme` and `organizeme.qa`
  hosts (the LB cutover records land in R5/R11/R12; here we only prove edit access).
- Record which DNS provider is authoritative (Squarespace-managed nameservers vs. delegating the
  zone to Google Cloud DNS) and note it for R5.

## Design notes
- **Use Custom DNS Records (A/AAAA), _not_ Squarespace "Domain Forwarding".** Forwarding issues an
  HTTP 301/302 redirect (or an iframe-masked one) from Squarespace's servers — it never points at
  the LB, so (a) the Google-managed cert can't validate, and (b) the browser never lands on the
  shared origin, which breaks the domain-scoped SSO cookie (R4) and the LB path routing (R5). The
  subdomain must resolve *directly* to the LB IP via an A (IPv4) / AAAA (IPv6) record.
- A subdomain is simpler than an apex here: no apex-CNAME/flattening constraints, and it keeps the
  auth cookie isolated from the main `russcoopersoftware.com` site (see R4 — scope to the exact
  host, never to `.russcoopersoftware.com`).
- The actual A/AAAA record cutover to the Load Balancer IP happens **in R5 (QA) and R11/R12
  (prod)**, not here — R0 only guarantees DNS is editable so R5 isn't blocked.
- Keep today's `*.run.app` URLs live throughout; nothing about this task touches production traffic.

## Blocked by
- None — can start immediately.

## Acceptance criteria
- [ ] Operator can add/edit Custom A/AAAA/TXT records for `organizeme.russcoopersoftware.com` and
      `organizeme.qa.russcoopersoftware.com` in Squarespace DNS (verified with a throwaway TXT record).
- [ ] Confirmed the plan uses Custom DNS Records, not Domain Forwarding.
- [ ] Authoritative DNS provider / nameservers documented for R5.
- [ ] No production traffic change — existing `*.run.app` URLs still serve.

## Testing
- Manual: add and resolve a temporary TXT record on one of the subdomains to prove edit access,
  then remove it.
