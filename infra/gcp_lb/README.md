# Slice R5 — GCP HTTPS Load Balancer

Provisions the shared External HTTPS Load Balancer that fronts
`organizeme.qa.russcoopersoftware.com` for QA — the single origin the platform sits behind, per
[`docs/platform-restructure/WBS/slice-R5.md`](../../docs/platform-restructure/WBS/slice-R5.md).

## IaC choice

A `gcloud` shell script (`provision.sh`), not Terraform — this repo has no existing IaC and
`ci.yml`/`deploy.yml` already manage Cloud Run entirely via plain `gcloud` commands. This keeps
the same tooling pattern rather than introducing a new toolchain (state file, provider config,
backend storage) for a single Load Balancer.

## What this provisions

- Two global static IPs (IPv4 + IPv6).
- `organizeme.qa.russcoopersoftware.com` A/AAAA records in the Cloud DNS zone `russcoopersoftware-com`
  (the zone R0 established editable control over).
- A Google-managed SSL certificate for that host.
- A Serverless NEG against the `organizeme-qa` Cloud Run service.
- Two backend services — `host-backend` and `organizeme-backend` — both currently pointing at the
  same NEG, since the Host shell and the "organizeme" app are one Cloud Run service until R6
  splits Event Creator out.
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

The script is idempotent — every step checks whether its resource already exists first, so it's
safe to re-run (e.g. after R6 adds Event Creator's own NEG/backend).

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
      `https://organizeme.qa.russcoopersoftware.com` — run `provision.sh`, wait for cert `ACTIVE`.
- [x] URL map routes Host paths to the Host Cloud Run service via a Serverless NEG.
- [x] URL-map path rules are generated from the R3 app-registry (`generate_url_map.py`).
- [x] IaC (`provision.sh`) for the LB/URL-map/NEG/cert is committed and re-runnable.
- [x] A second NEG slot is ready to attach Event Creator in R6 (see the "R6" comment block at the
      bottom of `provision.sh`).

The first item is a live-infrastructure outcome of running the script, not something this PR's CI
can verify — it depends on real DNS propagation and Google's cert validation, both of which
happen after merge when the operator runs `provision.sh`.

## Keeping `*.run.app` alive

Nothing here touches the existing Cloud Run service or its direct `*.run.app` URL — both continue
to work in parallel until the QA/prod cutovers (R11/R12) flip the origin.
