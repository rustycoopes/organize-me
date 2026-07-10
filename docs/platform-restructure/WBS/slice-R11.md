# Slice R11 — QA Cutover + Full Verification (P0 Gate)

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The full platform verified end-to-end in QA — Host + Event Creator behind the shared
Load Balancer, all functionality passing — the go/no-go gate for the production cutover.

## What to build

Bring everything together in the QA environment and prove parity + boundary integrity before
touching production. Point the QA Load Balancer's URL map at **both** services, then run the whole
verification battery.

## Includes
- Point the QA LB URL map at both `organize-me-qa` (Host) and `event-creator-qa` per the
  app-registry path rules.
- Run the full verification battery in QA:
  - The R10 Host↔Event Creator boundary E2E suite (must be green).
  - `docs/prd.md` user stories **13–52** against the new structure (functional parity).
  - Independent-deploy proof: Event Creator builds/deploys to QA with **zero** Host
    build/redeploy (and vice versa) — a Success-Metric leading indicator.
- Fix any regressions surfaced; re-run until fully green.

## Design notes
- This is the PRD's **P0 gate**: no production step (R12) proceeds until QA is fully green.
- No data migration is involved even in QA — schemas were separated in place (R1); this is routing
  + verification, not data movement.
- Verifies the Success-Metric leading indicators: 100% of stories 13–52 pass; boundary suite
  green; Event Creator deploys with zero Host changes.

## Blocked by
- R10 (boundary suite). Implicitly gathers R5–R9 into one verified QA whole.

## Acceptance criteria
- [ ] The QA LB routes to both Host and Event Creator per the app-registry path rules.
- [ ] The R10 boundary E2E suite is green in QA.
- [ ] 100% of `docs/prd.md` stories 13–52 pass against the new structure in QA.
- [ ] Event Creator deploys to QA with zero Host build/redeploy (and vice versa), demonstrated.
- [ ] No open regressions against previously-working functionality.

## Testing
- Full E2E battery + the stories-13–52 checklist executed in QA and recorded as the go/no-go
  evidence for R12.
