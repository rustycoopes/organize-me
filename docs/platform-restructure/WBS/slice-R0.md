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

## Step-by-Step: Squarespace DNS Console

Squarespace has **two different DNS-adjacent features** — this task only ever uses the second one.

- ❌ **Domain Forwarding** (under a domain's *"Forwarding"* tab) — issues an HTTP redirect. Do not
  use this for anything in R0/R5/R12.
- ✅ **DNS Settings → Custom Records** (under a domain's *"DNS Settings"* tab) — real DNS records
  (A/AAAA/CNAME/TXT/MX) that resolve independently of any redirect. This is what R0 verifies access
  to, and what R5/R12 will use for the real A/AAAA cutover.

### 1. Confirm you're in the right account and find the domain

1. Sign in at [squarespace.com](https://www.squarespace.com) (or `account.squarespace.com`) with
   the account that owns `russcoopersoftware.com`.
2. Open the **Home Menu** (top-left) → **Domains**. (If Squarespace's newer unified account view is
   active instead, go to **account.squarespace.com → Domains**.)
3. Click **`russcoopersoftware.com`** in the domain list to open its domain overview page.

### 2. Check who's authoritative for DNS

1. On the domain overview page, click **DNS Settings** (sometimes labeled **DNS**).
2. Scroll to the **Nameservers** section at the top of that page.
   - If it shows Squarespace's own nameservers (`ns1.squarespace.com`, `ns2.squarespace.com`, …),
     Squarespace's DNS panel is authoritative — the Custom Records you add here are what the
     internet actually sees. This is the expected case.
   - If it shows a **different** provider's nameservers, the zone has been delegated elsewhere
     (e.g. to Google Cloud DNS or a registrar) and Squarespace's Custom Records panel would be
     inert — records would need adding at the actual authoritative provider instead. Note whichever
     is true; that's the "DNS provider" this issue's acceptance criteria asks you to record.

### 3. Add the throwaway TXT verification record

1. Still on **DNS Settings**, scroll to **Custom Records**.
2. Click **Add Record** (or **Add Preset** → choose a blank/custom entry, depending on the current
   UI — look for a row with editable **Host / Type / Priority / Data / TTL** fields).
3. Fill in:
   - **Host:** `organizeme-dns-check` (any throwaway label works — this proves edit access, it
     doesn't need to match the real subdomains yet)
   - **Type:** `TXT`
   - **Data:** any short string, e.g. `r0-dns-access-verified-2026-07-10`
   - **TTL:** leave default (Squarespace typically defaults to 4 hrs / 14400s — fine for a test)
4. Click the checkmark / **Save** to commit the record.

### 4. Verify it resolves

DNS changes at Squarespace usually propagate within a few minutes, occasionally up to an hour.
Check from a terminal:

```powershell
# PowerShell
Resolve-DnsName -Type TXT organizeme-dns-check.russcoopersoftware.com
```

```bash
# bash / WSL
nslookup -type=TXT organizeme-dns-check.russcoopersoftware.com
# or
dig TXT organizeme-dns-check.russcoopersoftware.com +short
```

You should see the exact string you entered come back. If it doesn't resolve after ~15–20 minutes,
double-check the Host field (Squarespace wants just the subdomain label, not the full FQDN — don't
type `organizeme-dns-check.russcoopersoftware.com` into the Host box, just `organizeme-dns-check`)
and confirm nameservers from step 2 actually point at Squarespace.

### 5. Clean up

1. Back on **DNS Settings → Custom Records**, find the `organizeme-dns-check` TXT row.
2. Click its delete/trash icon and confirm removal.
3. Re-run the `Resolve-DnsName`/`dig` check above — it should now fail to resolve (NXDOMAIN or empty).

### 6. Document for R5

Note in the R5 issue/PR (or just carry forward mentally — R5 will restate it) which nameservers are
authoritative (step 2) and confirm both subdomains will need their own Custom Records in this same
panel:
- **Host `organizeme`** → will get an A + AAAA record pointed at the LB IP (prod, R12).
- **Host `organizeme.qa`** → will get an A + AAAA record pointed at the LB IP (QA, R5).

Nothing else needs adding yet — R0's job stops at proving edit access.

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
