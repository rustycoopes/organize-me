#!/usr/bin/env bash
# Slice R5 — provisions the shared External HTTPS Load Balancer that fronts
# organizeme.qa.russcoopersoftware.com for QA. See docs/platform-restructure/WBS/slice-R5.md.
#
# This is a manual, one-time (re-runnable) operator script — not part of CI/CD. It creates real,
# billable GCP resources and a managed SSL cert whose validation can take up to ~24h once the
# DNS records below resolve. Run it from an authenticated gcloud session:
#
#   gcloud auth login
#   gcloud config set project gen-lang-client-0791944342
#   bash infra/gcp_lb/provision.sh
#
# Idempotent: every step checks whether its resource already exists before creating it, so this
# is safe to re-run (e.g. after adding Event Creator's NEG in R6, or if a step fails partway).
#
# Today there is only one Cloud Run service (organizeme-qa) — it serves both the Host shell and
# the "organizeme" app, so host-backend and organizeme-backend both point at the same Serverless
# NEG until R6 introduces Event Creator as its own service (see the "R6" section at the bottom).

set -euo pipefail

PROJECT_ID="gen-lang-client-0791944342"
REGION="northamerica-northeast1"
DNS_ZONE="russcoopersoftware-com"
QA_HOST="organizeme.qa.russcoopersoftware.com"

RUN_SERVICE="organizeme-qa"
NEG_NAME="organizeme-qa-neg"
BACKEND_HOST="host-backend"
BACKEND_ORGANIZEME="organizeme-backend"
IP_V4_NAME="organizeme-lb-ipv4"
IP_V6_NAME="organizeme-lb-ipv6"
CERT_NAME="organizeme-qa-cert"
URL_MAP_NAME="organizeme-qa-url-map"
PROXY_NAME="organizeme-qa-https-proxy"
FWD_RULE_V4="organizeme-qa-fwd-v4"
FWD_RULE_V6="organizeme-qa-fwd-v6"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "== 1. Global static IPs =="
gcloud compute addresses describe "$IP_V4_NAME" --global >/dev/null 2>&1 || \
  gcloud compute addresses create "$IP_V4_NAME" --global --ip-version=IPV4
gcloud compute addresses describe "$IP_V6_NAME" --global >/dev/null 2>&1 || \
  gcloud compute addresses create "$IP_V6_NAME" --global --ip-version=IPV6

IPV4_ADDR=$(gcloud compute addresses describe "$IP_V4_NAME" --global --format="value(address)")
IPV6_ADDR=$(gcloud compute addresses describe "$IP_V6_NAME" --global --format="value(address)")
echo "IPv4: $IPV4_ADDR"
echo "IPv6: $IPV6_ADDR"

echo "== 2. Cloud DNS A/AAAA records ($DNS_ZONE) =="
gcloud dns record-sets describe "$QA_HOST." --zone="$DNS_ZONE" --type=A >/dev/null 2>&1 || \
  gcloud dns record-sets create "$QA_HOST." --zone="$DNS_ZONE" --type=A --ttl=300 --rrdatas="$IPV4_ADDR"
gcloud dns record-sets describe "$QA_HOST." --zone="$DNS_ZONE" --type=AAAA >/dev/null 2>&1 || \
  gcloud dns record-sets create "$QA_HOST." --zone="$DNS_ZONE" --type=AAAA --ttl=300 --rrdatas="$IPV6_ADDR"

echo "== 3. Google-managed SSL certificate =="
gcloud compute ssl-certificates describe "$CERT_NAME" --global >/dev/null 2>&1 || \
  gcloud compute ssl-certificates create "$CERT_NAME" --global --domains="$QA_HOST"
echo "NOTE: cert stays PROVISIONING until the A/AAAA records above resolve and Google validates them (can take up to ~24h)."

echo "== 4. Serverless NEG for $RUN_SERVICE =="
gcloud compute network-endpoint-groups describe "$NEG_NAME" --region="$REGION" >/dev/null 2>&1 || \
  gcloud compute network-endpoint-groups create "$NEG_NAME" \
    --region="$REGION" \
    --network-endpoint-type=serverless \
    --cloud-run-service="$RUN_SERVICE"

echo "== 5. Backend services (host-backend + organizeme-backend, same NEG for now) =="
# NOTE: bash's errexit exemption on the RHS of `||` cascades into a whole `{ ...; }` block used
# there (BashFAQ/105) — an `if` is used instead so a failing `add-backend` (after `create`
# already succeeded) still aborts the script under `set -e`, rather than silently leaving a
# backend service with no NEG attached.
for BACKEND in "$BACKEND_HOST" "$BACKEND_ORGANIZEME"; do
  if ! gcloud compute backend-services describe "$BACKEND" --global >/dev/null 2>&1; then
    gcloud compute backend-services create "$BACKEND" --global --load-balancing-scheme=EXTERNAL_MANAGED
    gcloud compute backend-services add-backend "$BACKEND" --global \
      --network-endpoint-group="$NEG_NAME" --network-endpoint-group-region="$REGION"
  fi
done

echo "== 6. URL map, generated from the R3 app-registry =="
URL_MAP_FILE="$(mktemp)"
uv run python -m infra.gcp_lb.generate_url_map | sed "s/\$LB_HOST/$QA_HOST/" > "$URL_MAP_FILE"
# `import` creates the URL map if it doesn't exist yet, or updates it in place if it does —
# idempotent either way, so no existence check is needed here (unlike the other resources above).
gcloud compute url-maps import "$URL_MAP_NAME" --global --source="$URL_MAP_FILE" --quiet
rm -f "$URL_MAP_FILE"

echo "== 7. Target HTTPS proxy =="
gcloud compute target-https-proxies describe "$PROXY_NAME" --global >/dev/null 2>&1 || \
  gcloud compute target-https-proxies create "$PROXY_NAME" \
    --url-map="$URL_MAP_NAME" --ssl-certificates="$CERT_NAME" --global

echo "== 8. Global forwarding rules (443, v4 + v6) =="
# --load-balancing-scheme must match the backend services' EXTERNAL_MANAGED (step 5) — global
# forwarding rules default to the classic EXTERNAL scheme otherwise, which GCP rejects as a
# scheme mismatch against the url-map/backend-services chain.
gcloud compute forwarding-rules describe "$FWD_RULE_V4" --global >/dev/null 2>&1 || \
  gcloud compute forwarding-rules create "$FWD_RULE_V4" \
    --global --load-balancing-scheme=EXTERNAL_MANAGED \
    --target-https-proxy="$PROXY_NAME" --address="$IP_V4_NAME" --ports=443
gcloud compute forwarding-rules describe "$FWD_RULE_V6" --global >/dev/null 2>&1 || \
  gcloud compute forwarding-rules create "$FWD_RULE_V6" \
    --global --load-balancing-scheme=EXTERNAL_MANAGED \
    --target-https-proxy="$PROXY_NAME" --address="$IP_V6_NAME" --ports=443

echo "Done. Once the cert shows ACTIVE (gcloud compute ssl-certificates describe $CERT_NAME --global),"
echo "verify with: curl https://$QA_HOST/login"

# --- R6 (adding Event Creator as a second hosted app) ---
# 1. Deploy the Event Creator Cloud Run service (e.g. "event-creator-qa").
# 2. Add an entry for it in packages/chrome/src/organizeme_chrome/registry.py (APPS list).
# 3. Create its own Serverless NEG + backend service (e.g. "event-creator-backend"), mirroring
#    steps 4-5 above with RUN_SERVICE=event-creator-qa, NEG_NAME=event-creator-qa-neg.
# 4. Re-run this script (or just steps 6-7) — the URL map regenerates from the updated registry
#    and automatically adds a path rule routing Event Creator's nav paths to its own backend.
