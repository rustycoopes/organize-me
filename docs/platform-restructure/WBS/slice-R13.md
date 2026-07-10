# Slice R13 — Host Cleanup + "How to Add a Hosted App" Playbook (P1)

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The Host repo stripped of leftover event-extraction code, and a written playbook for
adding a future hosted app — closing out the restructure's P1 items once Event Creator is stable in
production.

## What to build

After Event Creator is verified stable in production (R12), remove the now-dead event-extraction
code from the Host (`organize-me`) repo, leaving a clean Host that owns only auth / profile /
settings-shell / nav-shell. Then document the repeatable pattern so a second app is a known process.

Note this is **cleanup, not repo retirement** — `organize-me` *is* the Host going forward.

## Includes
- Remove leftover event-extraction modules from the Host now that Event Creator owns them:
  `app/pages/{dashboard,upload,processing,logs,prompt}.py`, `app/api/v1/{upload,events,llm_prompt,
  processing_runs,storage_config,storage_google_drive,storage_dropbox,import_pending_files}.py`,
  `app/services/{pipeline,llm,storage,notifications}/*`, `app/core/{prompts,date_parser,
  calendar_url,message_filter,onboarding}.py`, `app/worker.py`, and their templates/models.
- Keep in the Host: auth, profile, settings-shell, nav-shell, JWT issuance, app-registry authoring,
  shared-chrome-package publishing.
- Write the **"How to add a hosted app" playbook**: the Host app-registry entry (nav heading/items
  + settings tabs + service name), the LB URL-map regeneration, the shared-chrome-package
  dependency, and the JWT-verify-helper usage — i.e. "new repo + Host config change" only.
- Update Host repo docs (README, technical-approach) to reflect the Host-only surface.

## Design notes
- Sequence after R12 so nothing is removed from the Host until Event Creator is proven in prod —
  the Host keeps serving today's routes until the cutover is stable.
- The playbook is the deliverable that makes the PRD's "repeatable pattern" goal real; validate it
  against what Event Creator actually did (it's the reference implementation).
- This validates the lagging Success Metric: adding a future app's nav entry + settings tab is a
  single Host config change + redeploy.

## Blocked by
- R12 (production cutover stable).

## Acceptance criteria
- [ ] Event-extraction code is removed from the Host repo; the Host builds/deploys and serves
      auth/profile/settings-shell/nav-shell with no dead event-extraction code.
- [ ] The Host repo's README + technical-approach docs reflect the Host-only surface.
- [ ] A "how to add a hosted app" playbook exists, documenting the Host config steps and the
      sidebar/settings contribution pattern Event Creator established.
- [ ] The playbook's steps are validated against the actual Event Creator integration.

## Testing
- Host CI (pytest + mypy + E2E) green after code removal — no references to removed modules remain.
- Playbook dry-run/review: trace each step against the real Event Creator app-registry entry + LB
  routing to confirm completeness.
