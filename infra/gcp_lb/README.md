# Slice R5 — GCP HTTPS Load Balancer

Provisions the shared External HTTPS Load Balancer that fronts
`organizeme.qa.russcoopersoftware.com` for QA — the single origin the platform sits behind, per
[`docs/features/platform-restructure/WBS/slice-R5.md`](../../docs/features/platform-restructure/WBS/slice-R5.md).

## IaC choice

A `gcloud` shell script (`provision.sh`), not Terraform — this repo has no existing IaC and
`ci.yml`/`deploy.yml` already manage Cloud Run entirely via plain `gcloud` commands. This keeps
the same tooling pattern rather than introducing a new toolchain (state file, provider config,
backend storage) for a single Load Balancer. `provision.ps1` is a PowerShell port of the same
script (same steps, same resource names, same idempotency pattern) for an operator running from
Windows without WSL/Git Bash; `provision.sh` is canonical — keep both in sync if you edit either.

## What this provisions

- Two global static IPs (IPv4 + IPv6).
- `organizeme.qa.russcoopersoftware.com` A/AAAA records in the Cloud DNS zone `russcoopersoftware-com`
  (the zone R0 established editable control over).
- A Google-managed SSL certificate for that host.
- Serverless NEGs against the `organizeme-qa` and `event-creator-qa` Cloud Run services.
- Three backend services — `host-backend` and `organizeme-backend` (pointing at the `organizeme-qa`
  NEG) and `event-creator-backend` (pointing at its own `event-creator-qa` NEG, added in R6).
- A URL map generated from the app-registry (`infra/gcp_lb/generate_url_map.py`), not hand-authored.
- A target HTTPS proxy + global forwarding rules (443, v4 + v6).

## Running it

Requires an authenticated `gcloud` session with permissions to manage Compute Engine (Load
Balancer resources) and Cloud DNS in project `gen-lang-client-0791944342`:

```bash
gcloud auth login
gcloud config set project gen-lang-client-0791944342
bash infra/gcp_lb/provision.sh
```

On Windows, run the PowerShell equivalent instead (no bash/WSL needed):

```powershell
gcloud auth login
gcloud config set project gen-lang-client-0791944342
.\infra\gcp_lb\provision.ps1
```

Both scripts are idempotent — every step checks whether its resource already exists first, so
either is safe to re-run (e.g. once `event-creator-qa` has its first deploy, to attach its NEG).

**This is a manual, one-time operator step, not wired into CI/CD.** It creates real, billable GCP
resources, and the managed cert cannot go `ACTIVE` until the DNS records it creates propagate and
Google validates them — that can take up to ~24h. Running it inside a CI job would either time
out waiting on that validation or leave the job "done" while the cert is still provisioning; a
one-time manual run (mirroring how R0's DNS cutover was done) avoids both.

## Verifying

```bash
# Cert status — wait for ACTIVE before the LB actually serves valid HTTPS.
gcloud compute ssl-certificates describe organizeme-qa-cert --global

# Once ACTIVE:
curl https://organizeme.qa.russcoopersoftware.com/login
```

To confirm the URL map is generated (not hand-maintained), regenerate and diff against the live map:

```bash
uv run python -m infra.gcp_lb.generate_url_map
gcloud compute url-maps describe organizeme-qa-url-map --global
```

`tests/test_url_map_generator.py` covers the generator itself — it asserts path rules derive from
the app-registry (`organizeme_chrome.registry`), including that Event Creator (R6) can be added
without changing this generator's code.

## Acceptance criteria (slice-R5.md)

- [ ] External HTTPS LB with a global IP and a valid Google-managed cert serves
      `https://organizeme.qa.russcoopersoftware.com` — run `provision.sh` (or `provision.ps1` on
      Windows), wait for cert `ACTIVE`.
- [x] URL map routes Host paths to the Host Cloud Run service via a Serverless NEG.
- [x] URL-map path rules are generated from the R3 app-registry (`generate_url_map.py`).
- [x] IaC (`provision.sh` / `provision.ps1`) for the LB/URL-map/NEG/cert is committed and re-runnable.
- [x] Event Creator's own NEG/backend (`event-creator-qa-neg` / `event-creator-backend`, R6) is
      wired into the same script — re-run it once `event-creator-qa` has deployed.

The first item is a live-infrastructure outcome of running the script, not something this PR's CI
can verify — it depends on real DNS propagation and Google's cert validation, both of which
happen after merge when the operator runs `provision.sh`.

## Keeping `*.run.app` alive

Nothing here touches the existing Cloud Run service or its direct `*.run.app` URL — both continue
to work in parallel until the QA/prod cutovers (R11/R12) flip the origin.

## Production (Slice R12)

`provision-prod.sh` / `provision-prod.ps1` are the prod equivalents — same steps, same idempotency
pattern, fronting `organizeme.russcoopersoftware.com` instead. Every resource name is suffixed
`-prod` instead of `-qa` (GCP global resource names — static IPs, backend services, NEGs, cert,
URL map, proxy, forwarding rules — can't be shared across environments, so prod needs its own full
set, not a reuse of QA's). `generate_url_map.py` takes an optional environment argument
(`uv run python -m infra.gcp_lb.generate_url_map prod`) that renames every backend service in the
generated URL map to match (`host-backend-prod`, `organizeme-backend-prod`,
`event-creator-backend-prod`); omitting it keeps the original QA behavior (`host-backend`, etc.).

```bash
gcloud auth login
gcloud config set project gen-lang-client-0791944342
bash infra/gcp_lb/provision-prod.sh
```

Running this is non-disruptive: `organizeme.russcoopersoftware.com` is a brand-new hostname that
nothing currently points at (prod is reached today via the raw Cloud Run URLs), so no existing
traffic is affected until `GOOGLE_OAUTH_REDIRECT_URI`/`GOOGLE_DRIVE_REDIRECT_URI` are deliberately
flipped to it in a separate, reviewed PR — see the R12 slice doc and
[`host-integration-guide.md`](../../docs/host-integration-guide.md) for that
follow-up.
