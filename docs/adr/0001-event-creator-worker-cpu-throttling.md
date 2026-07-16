# ADR-0001: Event Creator's Celery worker needs CPU-always-allocated on Cloud Run

**Status:** Resolved — option 3 (below) implemented: Celery/Redis replaced with Cloud Tasks
push-based dispatch. QA's `--no-cpu-throttling` experiment reverted; both QA and prod stay on
request-based billing. `event-creator`'s `app.worker` (Celery) removed entirely, replaced by
`app.services.pipeline.dispatch` + `POST /internal/pipeline/run`.

**Date:** 2026-07-14 (opened) / 2026-07-14 (resolved, same design-review pass)

**Context:** Slice R11 (QA Cutover + Full Verification, issue #166)

## Context

Event Creator (R7–R8) runs its 7-step upload/processing pipeline as a Celery task, dispatched by
the API process (`app.api.v1.upload`, `app.api.v1.import_pending_files`) and executed by a worker
process that `supervisord` starts alongside the web process in the same Cloud Run container
(`app/worker.py`, `supervisord.conf`). This is a deliberate departure from the organize-me
monolith, where the equivalent pipeline ran in-process as a plain `asyncio` background task tied
directly to the request — no separate worker, no broker, no queue.

R11 is the first slice to route real traffic (organize-me's Playwright e2e suite, run live against
QA) to Event Creator's `/upload` → `/processing` → `/dashboard`/`/logs` flow. Every prior test of
this pipeline (R7–R10) exercised the pipeline logic directly (fakes, in-process calls, unit tests)
or the API layer without waiting for a real Celery task to complete against a live Redis broker on
a live Cloud Run instance. R10's boundary suite tested auth/cookie behaviour only, never a real
upload. So this is the first point at which the deployed worker was ever asked to actually finish a
job.

### The failure

Post-cutover, the full e2e suite showed every pipeline-completion assertion time out
(`dashboard.spec.ts`, `logs.spec.ts`, `processing.spec.ts` — 8 of 9 total failures; the 9th,
`notifications.spec.ts`, is unrelated flakiness in an untouched area). Runs got created and stayed
stuck at `PENDING` — "Waiting to start…" — indefinitely.

Cloud Run logs for `event-creator-qa` showed the Celery worker process cycling every ~10–20
seconds:

```
INFO spawned: 'worker' with pid 3
INFO stopped: worker (exit status 0)
```

### Root cause

Cloud Run's default billing/execution model (**request-based billing**) only allocates CPU to a
container while it is actively handling an HTTP request. `app/worker.py`'s Celery worker is a
background process inside that same container, with no request of its own — the instant there is
no in-flight HTTP request on that particular instance, its CPU gets throttled to near-zero and the
worker process stalls and is restarted by `supervisord`. The ~10–20 second cycle is consistent with
CPU throttling, not Cloud Run's (much slower, usually minutes) scale-to-zero idle timeout — so a
longer scale-down grace period would not fix this on its own; a throttled-but-not-yet-killed
instance still cannot run the worker.

This has been a latent gap in Event Creator's Cloud Run config since R7/R8. It had no way to
surface until a slice actually routed real traffic there and waited for a run to finish — which is
exactly what R11 exists to do.

## Options considered

1. **`--no-cpu-throttling`** ("CPU always allocated"). Directly fixes the crash-loop: the container
   gets continuous CPU regardless of in-flight requests. Cloud Run does not allow this alongside
   request-based billing — setting it automatically switches the service to **instance-based
   billing**: you pay for the full time an instance is warm, not just per-request slices. With
   `--min-instances=0` (current setting), an idle instance still eventually scales to zero, so this
   is not equivalent to paying for 24/7 uptime — but every warm-idle window between bursts of
   traffic is now billed in full, not throttled/near-free as under request-based billing.

   **Known cost data point:** the user has previously run a Cloud Run service with instance-based
   billing and `min-instances=0` and observed roughly **$70/month** — this is a real prior
   observation, not a rough estimate, and should anchor any further sizing discussion rather than
   theoretical per-second pricing math.

2. **`--no-cpu-throttling` + `--min-instances=1`**. Same fix, plus guarantees a warm instance at all
   times (no cold-start latency, no risk of an idle-instance race right after scale-down). Adds a
   materially larger, continuous fixed cost on top of option 1 (a permanently-billed instance,
   24/7) for a QA-only service that does not need to be always warm.

3. **Move background processing off Cloud Run's request/CPU model entirely** — e.g. a push-based
   design (Cloud Tasks or Pub/Sub triggering a Cloud Run Job or Cloud Function per task) instead of
   a long-lived Celery worker process. Pay-per-invocation instead of pay-for-idle-time; no
   persistent background process to babysit. Meaningfully more re-architecture effort than a
   deploy-flag change — a candidate for a future slice, not a quick QA fix.

4. **Run the worker somewhere that isn't Cloud Run's request-scoped CPU model** (small GCE VM,
   GKE, etc.). Removes the throttling problem structurally, but adds an ops footprint (patching,
   scaling, monitoring a non-serverless component) that the platform has deliberately avoided so
   far — a bigger structural change than this ADR's scope.

5. **Drop Celery/Redis and run the pipeline in-process**, matching how the organize-me monolith
   always did it (tied to the request/SSE connection, no separate worker). Eliminates the
   background-worker/CPU-throttling problem entirely, but loses whatever durability/retry value the
   task queue was meant to provide, and ties pipeline execution to the lifetime of the initiating
   request — a real architectural reversal of R7/R8's design, not something to decide inside an
   infra-config ADR.

## Decision (short-term)

Apply `--no-cpu-throttling` to `event-creator-qa` **only**, as a validation experiment:

- Confirm it resolves the e2e pipeline-completion failures.
- Do **not** carry this into `event-creator`'s `deploy.yml` (i.e. do not apply to `prod`) until
  the cost profile has been reviewed against the known ~$70/month data point from option 1 and a
  decision is made on whether options 2–5 are worth pursuing instead or in addition.
- This ADR is the artefact for that follow-up design review — no rollout past QA should happen
  without revisiting it.

## Consequences

- QA's pipeline should start completing runs once this is applied; the e2e suite will be re-run to
  confirm.
- QA's Cloud Run cost for `event-creator-qa` will increase from request-based to instance-based
  billing. Expect a non-trivial idle-tail cost per warm period, informed by the ~$70/month prior
  data point (that observation used `min-instances=0`, the same setting QA will have here).
- Prod (`event-creator-prod`) is **unaffected** by this change and remains on request-based
  billing — meaning prod's pipeline has the same underlying bug and would fail in production
  exactly the same way once traffic is ever routed there (i.e. before R12's prod cutover, this must
  be resolved one way or another).
- This is tracked as an open decision, not a closed one — options 3–5 remain on the table pending
  review.

## Resolution

**Option 3 chosen: Cloud Tasks push-based dispatch**, replacing Celery/Redis entirely rather than
tuning the CPU-throttling flag. `event-creator`'s `POST /api/v1/upload` and
`/api/v1/import-pending-files` now enqueue a Cloud Tasks task targeting a new
`POST /internal/pipeline/run` endpoint on the same service, OIDC-verified. Each pipeline run is
therefore a genuine inbound HTTP request, so Cloud Run allocates CPU for exactly its duration —
true pay-per-run under request-based billing, no idle cost, no `min-instances`. Full design in
`docs/host-integration-guide.md`'s Cloud Tasks section; implementation in the
`event-creator` repo (`app/services/pipeline/dispatch.py`, `app/api/v1/internal_pipeline.py`,
`infra/cloud_tasks/provision.{sh,ps1}`).

**A design-review correction worth recording**: the initial instinct was option 5 (revert to the
monolith's in-process `asyncio.create_task()`, no Celery/Redis at all). That turned out to *not*
actually solve the cost problem — the monolith's own `BackgroundPipelineScheduler` required
`--no-cpu-throttling` too (see `app/api/v1/upload.py`'s `BackgroundPipelineScheduler` docstring
and PR #80 in this repo), and that flag was only removed during R6's tracer bullet per an explicit
ask to keep both services request-based-only. Plain in-process asyncio has the identical root
issue Celery does — detached background work with no HTTP request of its own to justify CPU
allocation — it just hadn't been load-tested since R6. Cloud Tasks avoids this because it's not
background work at all from Cloud Run's perspective: it's a normal request.

QA's `--no-cpu-throttling` experiment (this ADR's short-term validation) is reverted as part of
this change — nothing on either service needs CPU-always-allocated anymore.

**A code-review pass before merge caught real correctness gaps in the first implementation**,
fixed before this branch was committed: (1) the idempotency guard was a plain `SELECT`-then-act
check with a real TOCTOU race under Cloud Tasks' at-least-once delivery — closed by making the
run-pickup step an atomic `UPDATE ... WHERE status = 'pending'` (`dispatch._claim_run`); (2) the
initial design assumed a batch's strict "sequential, in order" requirement (#110) fell out of the
queue's `max-concurrent-dispatches=1` setting, which is false — Cloud Tasks only guarantees
non-concurrency, not order — fixed via explicit chaining (each item's payload carries the rest of
the batch, and the push endpoint enqueues the next item itself); (3) `verify_oauth2_token` was
re-fetching Google's public certs on every single push with no caching — fixed with a
`cachecontrol`-wrapped session; (4) a Cloud Tasks enqueue failure after the `processing_runs` row
was already committed left it orphaned at `PENDING` forever with nothing to recover it — fixed by
catching that failure and marking the run(s) `FAILED`. A fifth finding — the OIDC push
authentication only proves the request came from the shared default compute service account every
Cloud Run service in this GCP project already runs as, not specifically from Cloud Tasks — was
judged a pre-existing platform-wide identity decision this change inherits rather than introduces,
and is tracked as a follow-up rather than blocking this branch.
