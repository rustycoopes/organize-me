# Slice R0 — Establish DNS Control for `organizeme.russcoopersoftware.com` (Cloud DNS zone cutover)

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Type:** Prerequisite / manual-ops task (not a code change).

**Delivers:** Editable DNS for the platform subdomains on the existing, operator-owned
`russcoopersoftware.com` domain (registered at Squarespace, but — as determined below —
**authoritative on Google Cloud DNS**) — the blocking prerequisite for provisioning the shared
HTTPS Load Balancer (R5) and its Google-managed SSL cert.

The shared platform origins are:
- **Production:** `organizeme.russcoopersoftware.com`
- **QA:** `organizeme.qa.russcoopersoftware.com`

## What to build

No domain purchase is required — `russcoopersoftware.com` is already registered at Squarespace.
**Investigation finding (2026-07-11):** the domain's nameservers are
`ns-cloud-b1..b4.googledomains.com` — a legacy Google Domains free-DNS zone, not Squarespace's own
DNS — and there is **no GCP project under our control that owns that zone**. Squarespace's Custom
Records panel is inert for this domain (it isn't the authoritative provider); editing DNS there
would have no effect on live resolution.

**Resolved plan:** create a new Cloud DNS public zone in GCP project
**`gen-lang-client-0791944342`**, replicate the records currently live on the legacy zone into it,
then repoint the registrar's nameservers (at Squarespace) from the old legacy zone to the new one.
Once cut over, this project-owned zone is what R5/R11/R12 add the LB's A/AAAA records to.

Today the platform domain is only *referenced* in code (`app/core/config.py` `base_url` default,
notification email links, previously `organize-me.app`) — no DNS/managed-cert config exists in the
repo and live traffic runs on the raw `*.run.app` Cloud Run URLs.

This is an ops/setup task with no code deliverable. It exists as its own issue because the design
doc flags domain/DNS readiness as **blocking** for Load Balancer provisioning: the Google-managed
SSL cert in R5 cannot validate until an A/AAAA record for the subdomain resolves to the LB.

## Investigation findings (queried directly against the legacy authoritative nameserver)

Querying `ns-cloud-b1.googledomains.com` directly (not the cached/default resolver) turned up what
must survive the cutover — **this is the record set the new zone must be seeded with before
nameservers are repointed**, or the live Squarespace website goes down mid-migration:

| Host | Type | Value |
|---|---|---|
| `russcoopersoftware.com` | A | `198.185.159.144` (Squarespace website hosting IP) |
| `www.russcoopersoftware.com` | CNAME | `ghs.googlehosted.com.` |
| — | MX | none |
| — | TXT | none |

`organizeme` and `organizeme.qa` do not exist yet in the legacy zone — nothing to migrate for those;
R5/R12 create them fresh in the new zone.

## Includes
- Create a public Cloud DNS managed zone for `russcoopersoftware.com` in project
  `gen-lang-client-0791944342`.
- Seed the new zone with the two records above so the live site/CNAME survive cutover.
- Repoint Squarespace's registrar-level nameservers from the legacy `ns-cloud-b*` zone to the new
  zone's assigned nameservers.
- Verify you can add/edit **A, AAAA, and TXT** records for the `organizeme` and `organizeme.qa`
  hosts in the new zone (the LB cutover records land in R5/R11/R12; here we only prove edit access).
- Record which DNS provider is authoritative (now: Cloud DNS zone in `gen-lang-client-0791944342`)
  and note it for R5.

## Step-by-Step: Google Cloud DNS zone creation & nameserver cutover

This is the actual path for this domain (see Investigation findings above) — Squarespace's own DNS
panel is skipped entirely since it isn't authoritative. The Appendix below covers the
Squarespace-panel path only for reference, in case a future domain really does use Squarespace's
own nameservers.

### 1. Create the zone in `gen-lang-client-0791944342`

**Console:**
1. Sign in at [console.cloud.google.com](https://console.cloud.google.com), select project
   `gen-lang-client-0791944342`.
2. Go to **Network Services → Cloud DNS** → **Create Zone**.
3. **Zone type:** Public. **Zone name:** `russcoopersoftware-com`. **DNS name:**
   `russcoopersoftware.com` (console appends the trailing dot).
4. **DNSSEC:** leave **Off** (avoids an extra DS-record step at the registrar; not needed here).
5. Click **Create**.

**gcloud CLI:**
```bash
gcloud auth login
gcloud config set project gen-lang-client-0791944342
gcloud services enable dns.googleapis.com
gcloud dns managed-zones create russcoopersoftware-com \
  --dns-name="russcoopersoftware.com." \
  --description="Authoritative zone for russcoopersoftware.com" \
  --visibility=public
```

### 2. Seed the zone with the records that must survive cutover

**Console:** open the new zone → **Add Standard** for each row:
- `russcoopersoftware.com.` — Type `A` — TTL `300` — data `198.185.159.144`
- `www.russcoopersoftware.com.` — Type `CNAME` — TTL `300` — data `ghs.googlehosted.com.`

**gcloud:**
```bash
gcloud dns record-sets create russcoopersoftware.com. \
  --zone=russcoopersoftware-com --type=A --ttl=300 \
  --rrdatas="198.185.159.144"

gcloud dns record-sets create www.russcoopersoftware.com. \
  --zone=russcoopersoftware-com --type=CNAME --ttl=300 \
  --rrdatas="ghs.googlehosted.com."
```

### 3. Get the new zone's assigned nameservers

```bash
gcloud dns managed-zones describe russcoopersoftware-com --format="value(nameServers)"
```
Or in Console, click the zone name — the 4 `ns-cloud-XX.googledomains.com` values are listed under
"Registrar setup." These will differ from the legacy zone's (`ns-cloud-b1..b4`) — could be any
other letter group.

### 4. Repoint Squarespace's registrar nameservers

1. Squarespace → **Domains** → `russcoopersoftware.com` → **DNS Settings**.
2. Under **Nameservers**, switch to (or edit) **Custom Nameservers**.
3. Replace the current 4 values (`ns-cloud-b1..b4.googledomains.com`) with the **new** zone's 4
   nameservers from step 3.
4. Save.

### 5. Wait for propagation and verify

NS-level changes propagate slower than record changes — often a few hours, occasionally up to
24-48h.

```powershell
Resolve-DnsName -Type NS russcoopersoftware.com
```
Once this shows the new zone's nameservers, confirm `https://russcoopersoftware.com` still loads
and `www` still resolves — that proves the seeded records (step 2) carried over correctly and the
live site never went down.

### 6. Add the throwaway TXT verification record (now in the new zone)

**Console:** new zone → **Add Standard** — Host `organizeme-dns-check` — Type `TXT` — TTL `300` —
data `"r0-dns-access-verified-2026-07-11"` (Cloud DNS requires TXT data in quotes).

**gcloud:**
```bash
gcloud dns record-sets create organizeme-dns-check.russcoopersoftware.com. \
  --zone=russcoopersoftware-com --type=TXT --ttl=300 \
  --rrdatas='"r0-dns-access-verified-2026-07-11"'
```

Verify:
```powershell
Resolve-DnsName -Type TXT organizeme-dns-check.russcoopersoftware.com
```

Then delete it:
```bash
gcloud dns record-sets delete organizeme-dns-check.russcoopersoftware.com. \
  --zone=russcoopersoftware-com --type=TXT
```

### 7. Document for R5

Both subdomains will get their own record sets in this same zone
(`russcoopersoftware-com` in `gen-lang-client-0791944342`):
- **Host `organizeme`** → A + AAAA pointed at the LB IP (prod, R12).
- **Host `organizeme.qa`** → A + AAAA pointed at the LB IP (QA, R5).

Nothing else needs adding yet — R0's job stops at proving edit access on the new zone.

## Appendix: Squarespace DNS Console (reference only — not this domain's path)

Squarespace has **two different DNS-adjacent features**, relevant only if a domain's nameservers
are Squarespace's own (`ns1.squarespace.com`, `ns2.squarespace.com`, …) rather than delegated
elsewhere:

- ❌ **Domain Forwarding** (under a domain's *"Forwarding"* tab) — issues an HTTP redirect. Never
  use this for R0/R5/R12 — it doesn't point at the LB and breaks the managed cert and SSO cookie.
- ✅ **DNS Settings → Custom Records** (under a domain's *"DNS Settings"* tab) — real DNS records.
  Only actually authoritative if the Nameservers section on that page shows Squarespace's own
  nameservers — check that before trusting edits made here.

## Design notes
- **Use DNS A/AAAA records, _not_ Squarespace "Domain Forwarding".** Forwarding issues an HTTP
  301/302 redirect (or an iframe-masked one) — it never points at the LB, so (a) the Google-managed
  cert can't validate, and (b) the browser never lands on the shared origin, which breaks the
  domain-scoped SSO cookie (R4) and the LB path routing (R5). The subdomain must resolve *directly*
  to the LB IP via an A (IPv4) / AAAA (IPv6) record. Moot here anyway since the zone lives in Cloud
  DNS, not Squarespace, but the same principle would apply if it didn't.
- **The zone must be seeded with the legacy zone's existing records before the nameserver cutover**
  (see Investigation findings) — otherwise the live Squarespace-hosted site at the apex and the
  `www` CNAME go dark the moment the registrar's nameservers flip.
- A subdomain is simpler than an apex here for the *platform* origin: no apex-CNAME/flattening
  constraints, and it keeps the auth cookie isolated from the main `russcoopersoftware.com` site
  (see R4 — scope to the exact host, never to `.russcoopersoftware.com`). The apex itself keeps
  serving the existing Squarespace website unrelated to this project.
- The actual A/AAAA record cutover to the Load Balancer IP happens **in R5 (QA) and R11/R12
  (prod)**, not here — R0 only guarantees DNS is editable (via the new Cloud DNS zone) so R5 isn't
  blocked.
- Keep today's `*.run.app` URLs live throughout; nothing about this task touches production traffic.

## Blocked by
- None — can start immediately.

## Acceptance criteria
- [ ] Public Cloud DNS zone for `russcoopersoftware.com` created in project
      `gen-lang-client-0791944342`.
- [ ] Zone seeded with the pre-existing apex `A 198.185.159.144` and `www CNAME
      ghs.googlehosted.com.` records before cutover.
- [ ] Squarespace registrar nameservers repointed from the legacy `ns-cloud-b1..b4` zone to the new
      zone's nameservers; `russcoopersoftware.com` and `www` still resolve/load correctly after
      propagation.
- [ ] Operator can add/edit A/AAAA/TXT records for `organizeme.russcoopersoftware.com` and
      `organizeme.qa.russcoopersoftware.com` in the new zone (verified with a throwaway TXT record).
- [ ] Authoritative DNS provider (Cloud DNS zone `russcoopersoftware-com` in
      `gen-lang-client-0791944342`) documented for R5.
- [ ] No production traffic change — existing `*.run.app` URLs still serve.

## Testing
- Manual: after cutover, confirm the apex site and `www` still resolve/load.
- Manual: add and resolve a temporary TXT record on the new zone to prove edit access, then remove it.
