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
  `app/services/{pipeline,llm,storage}/*`, the pipeline-only parts of `app/services/notifications/`
  (kept `email.py` — still used for the Host's own password-reset emails), `app/core/{prompts,
  date_parser,calendar_url,message_filter,onboarding}.py`, `app/worker.py`, the now-unused
  `[program:worker]` block in `supervisord.conf`, and their templates/models/schemas.
  `app/api/v1/users.py`'s `UserRead`/`UserUpdate` also drop `notification_email`/`notification_sms`
  — that data lived on the now-removed `event_creator.user_settings` model (R7 had already moved
  the Notifications Settings tab UI to `event-creator`).
- Remove the parallel **test files** for all of the above from `organize-me/tests/` — code removal
  without test removal leaves stale tests importing deleted modules. Requires verifying
  equivalent, passing coverage exists in `event-creator/tests/` first (not assumed from filename
  match alone) before deleting a Host-side test.
- Port the event-extraction **Playwright specs** out of `organize-me/e2e/tests/` into
  `event-creator`'s own Playwright suite (which didn't exist before this slice) — e.g.
  `upload.spec.ts`, `processing.spec.ts`, `storage.spec.ts`, `prompt.spec.ts`, `logs.spec.ts`,
  `import-pending-files.spec.ts`, `dashboard.spec.ts`, `notifications.spec.ts`.
- Keep `e2e/tests/host-event-creator-boundary.spec.ts` in the Host permanently — it asserts the
  *seam* between the two apps (JWT cookie flow, logout propagation, tampered-token rejection), not
  either app's internals, so it doesn't move with the rest.
- Keep in the Host: auth, profile, settings-shell, nav-shell, JWT issuance, app-registry authoring,
  shared-chrome-package publishing — and their existing tests, unaffected.
- Write the **"How to add a hosted app" playbook**
  ([`how-to-add-a-hosted-app.md`](../how-to-add-a-hosted-app.md)): the Host app-registry entry (nav
  heading/items + settings tabs + service name), the LB URL-map regeneration, the shared-chrome-
  package dependency, and the JWT-verify-helper usage — i.e. "new repo + Host config change" only.
  Include the test-ownership rule (unit + e2e tests live with the code they exercise; only
  cross-repo boundary tests stay in the Host) as part of the repeatable pattern, not a one-off
  cleanup note.
- Update Host repo docs (README, technical-approach) to reflect the Host-only surface, and add this
  slice's section to `host-integration-guide.md`.

## Design notes
- Sequence after R12 so nothing is removed from the Host until Event Creator is proven in prod —
  the Host keeps serving today's routes until the cutover is stable.
- The playbook is the deliverable that makes the PRD's "repeatable pattern" goal real; validate it
  against what Event Creator actually did (it's the reference implementation).
- This validates the lagging Success Metric: adding a future app's nav entry + settings tab is a
  single Host config change + redeploy.
- Before deleting any Host-side test, confirm equivalent coverage actually exists in
  `event-creator` — don't assume from filename match alone.

## Blocked by
- R12 (production cutover stable).

## Acceptance criteria
- [ ] Event-extraction code is removed from the Host repo; the Host builds/deploys and serves
      auth/profile/settings-shell/nav-shell with no dead event-extraction code.
- [ ] All event-extraction unit tests are removed from `organize-me/tests/` with verified
      equivalent coverage in `event-creator/tests/`.
- [ ] `event-creator` has its own Playwright config + e2e suite; the event-extraction specs
      migrated out of `organize-me/e2e/tests/` run and pass there.
- [ ] `organize-me/e2e/tests/` contains only Host-surface specs plus
      `host-event-creator-boundary.spec.ts`.
- [ ] The Host repo's README + technical-approach docs reflect the Host-only surface.
- [ ] A "how to add a hosted app" playbook exists, documenting the Host config steps, the
      sidebar/settings contribution pattern Event Creator established, and the test-ownership rule.
- [ ] The playbook's steps are validated against the actual Event Creator integration.

## Testing
- Host CI (pytest + mypy + E2E) green after code removal — no references to removed modules remain,
  and no test in either repo imports across the repo boundary.
- `event-creator` CI green with its new Playwright suite included.
- Playbook dry-run/review: trace each step against the real Event Creator app-registry entry + LB
  routing to confirm completeness.

## Delivered (2026-07-16, issue #168, branch `restructure/r13-host-cleanup`)

Also removed one item not anticipated above: a Host-only DB-schema regression test
(`test_host_users_no_longer_has_moved_columns`) was moved into `tests/test_schema_separation.py`
rather than deleted, since it exercises the Host's own schema, not event-extraction code.
`notifications.spec.ts` was found missing from the original test-removal list during review and
ported to `event-creator` (PR #17) before its Host copy was deleted. See
`docs/features/platform-restructure/host-integration-guide.md`'s R13 section for the integrator-facing
summary.
