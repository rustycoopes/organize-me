# Slice R5 — GCP HTTPS Load Balancer + Path Routing + Managed SSL

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** A GCP External HTTPS Load Balancer fronting `organize-me.app`, with a path-based URL
map routing requests to the correct Cloud Run service and a Google-managed SSL certificate — the
shared single origin the whole platform sits behind.

## What to build

There is **no IaC or Load Balancer today**; services are reached directly on their `*.run.app`
URLs. Provision the shared front door: one External HTTPS LB, a Serverless NEG per Cloud Run
service, a Google-managed cert for `organize-me.app`, and a URL map whose path rules come from the
app-registry authored in R3. At this slice there is still only the Host service to route to (Event
Creator arrives in R6); the LB is stood up so the boundary tracer bullet in R6 has a shared origin.

## Includes
- External HTTPS Load Balancer + global static IP.
- Google-managed SSL certificate for `organize-me.app`; DNS A/AAAA record pointed at the LB IP
  (uses R0's DNS access).
- Serverless NEG for the Host Cloud Run service (and a placeholder/second NEG ready for Event
  Creator in R6).
- URL map path rules generated from the R3 app-registry (Host paths: `/`, `/login`, `/register`,
  `/forgot-password`, `/reset-password`, `/profile`; hosted-app paths route to their service).
- **IaC tooling decision** (Terraform vs. a `gcloud` deploy script) — no IaC exists; pick and
  establish the pattern here. *(Open item carried from the plan.)*
- QA-first: stand up the LB against the QA services; production LB is provisioned at cutover
  (R11/R12).

## Relevant files
- New IaC directory (e.g. `infra/` — Terraform or `gcloud` scripts) — greenfield.
- R3 app-registry file — consumed at provision time to generate URL-map path rules.
- `.github/workflows/*` — optional step to regenerate the URL map from the app-registry.

## Design notes
- **No server-to-server calls** between Host and hosted apps at request time — the LB routes the
  browser directly to one service; SSO rides the shared-domain cookie, not a back-channel.
- The app-registry is the **single source** for both rendering (R3) and routing (here) — path
  rules must be generated from it, not hand-maintained separately.
- Managed cert issuance requires the DNS record to resolve to the LB — sequence DNS before cert
  validation.
- Keep `*.run.app` URLs alive in parallel until the QA/prod cutovers (R11/R12) flip the origin.

## Blocked by
- R0 (registered domain + DNS control).

## Acceptance criteria
- [ ] An External HTTPS LB with a global IP and a **valid** Google-managed cert serves
      `https://organize-me.app` (QA setup).
- [ ] The URL map routes Host paths to the Host Cloud Run service via a Serverless NEG.
- [ ] URL-map path rules are generated from the R3 app-registry (not hand-authored).
- [ ] IaC (Terraform or `gcloud` script) for the LB/URL-map/NEG/cert is committed and re-runnable.
- [ ] A second NEG slot is ready to attach Event Creator in R6.

## Testing
- `curl https://organize-me.app/login` returns the Host login page over a valid TLS cert.
- URL-map dry-run: assert generated path rules match the app-registry.
- Re-run the IaC on a clean state to confirm it is reproducible.
