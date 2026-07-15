#!/usr/bin/env bash
# Slice R12 — provisions the production External HTTPS Load Balancer that fronts
# organizeme.russcoopersoftware.com. See docs/platform-restructure/WBS/slice-R12.md.
#
# Mirrors infra/gcp_lb/provision.sh (R5's QA setup) exactly, with every resource name suffixed
# `-prod` instead of `-qa` (GCP global resource names collide across environments, so QA's
# resources can't be reused) and its own static IPs / managed cert / DNS record for the prod host.
#
# This is a manual, one-time (re-runnable) operator script — not part of CI/CD. It creates real,
# billable GCP resources and a managed SSL cert whose validation can take up to ~24h once the
# DNS records below resolve. Run it from an authenticated gcloud session:
#
#   gcloud auth login
#   gcloud config set project gen-lang-client-0791944342
#   bash infra/gcp_lb/provision-prod.sh
#
# Idempotent: every step checks whether its resource already exists before creating it.
#
# Creating these resources and the DNS record below is non-disruptive: organizeme.russcoopersoftware.com
# is a brand-new hostname nothing currently points at (prod is reached today via the raw Cloud Run
# URLs), so nothing changes for existing users until GOOGLE_OAUTH_REDIRECT_URI/GOOGLE_DRIVE_REDIRECT_URI
# are deliberately flipped to it in a later, separate step.

set -euo pipefail

PROJECT_ID="gen-lang-client-0791944342"
REGION="northamerica-northeast1"
DNS_ZONE="russcoopersoftware-com"
PROD_HOST="organizeme.russcoopersoftware.com"

RUN_SERVICE="organizeme-prod"
NEG_NAME="organizeme-prod-neg"
BACKEND_HOST="host-backend-prod"
BACKEND_ORGANIZEME="organizeme-backend-prod"

EVENTCREATOR_RUN_SERVICE="event-creator-prod"
EVENTCREATOR_NEG_NAME="event-creator-prod-neg"
BACKEND_EVENTCREATOR="event-creator-backend-prod"

IP_V4_NAME="organizeme-prod-lb-ipv4"
IP_V6_NAME="organizeme-prod-lb-ipv6"
CERT_NAME="organizeme-prod-cert"
URL_MAP_NAME="organizeme-prod-url-map"
PROXY_NAME="organizeme-prod-https-proxy"
FWD_RULE_V4="organizeme-prod-fwd-v4"
FWD_RULE_V6="organizeme-prod-fwd-v6"

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
gcloud dns record-sets describe "$PROD_HOST." --zone="$DNS_ZONE" --type=A >/dev/null 2>&1 || \
  gcloud dns record-sets create "$PROD_HOST." --zone="$DNS_ZONE" --type=A --ttl=300 --rrdatas="$IPV4_ADDR"
gcloud dns record-sets describe "$PROD_HOST." --zone="$DNS_ZONE" --type=AAAA >/dev/null 2>&1 || \
  gcloud dns record-sets create "$PROD_HOST." --zone="$DNS_ZONE" --type=AAAA --ttl=300 --rrdatas="$IPV6_ADDR"

echo "== 3. Google-managed SSL certificate =="
gcloud compute ssl-certificates describe "$CERT_NAME" --global >/dev/null 2>&1 || \
  gcloud compute ssl-certificates create "$CERT_NAME" --global --domains="$PROD_HOST"
echo "NOTE: cert stays PROVISIONING until the A/AAAA records above resolve and Google validates them (can take up to ~24h)."

echo "== 4. Serverless NEGs (organizeme-prod + event-creator-prod) =="
gcloud compute network-endpoint-groups describe "$NEG_NAME" --region="$REGION" >/dev/null 2>&1 || \
  gcloud compute network-endpoint-groups create "$NEG_NAME" \
    --region="$REGION" \
    --network-endpoint-type=serverless \
    --cloud-run-service="$RUN_SERVICE"
if ! gcloud compute network-endpoint-groups describe "$EVENTCREATOR_NEG_NAME" --region="$REGION" >/dev/null 2>&1; then
  gcloud compute network-endpoint-groups create "$EVENTCREATOR_NEG_NAME" \
    --region="$REGION" \
    --network-endpoint-type=serverless \
    --cloud-run-service="$EVENTCREATOR_RUN_SERVICE"
fi

echo "== 5. Backend services =="
for BACKEND in "$BACKEND_HOST" "$BACKEND_ORGANIZEME"; do
  if ! gcloud compute backend-services describe "$BACKEND" --global >/dev/null 2>&1; then
    gcloud compute backend-services create "$BACKEND" --global --load-balancing-scheme=EXTERNAL_MANAGED
    gcloud compute backend-services add-backend "$BACKEND" --global \
      --network-endpoint-group="$NEG_NAME" --network-endpoint-group-region="$REGION"
  fi
done
if ! gcloud compute backend-services describe "$BACKEND_EVENTCREATOR" --global >/dev/null 2>&1; then
  gcloud compute backend-services create "$BACKEND_EVENTCREATOR" --global --load-balancing-scheme=EXTERNAL_MANAGED
  gcloud compute backend-services add-backend "$BACKEND_EVENTCREATOR" --global \
    --network-endpoint-group="$EVENTCREATOR_NEG_NAME" --network-endpoint-group-region="$REGION"
fi

echo "== 6. URL map, generated from the R3 app-registry =="
URL_MAP_FILE="$(mktemp)"
uv run python -m infra.gcp_lb.generate_url_map prod | sed "s/\$LB_HOST/$PROD_HOST/" > "$URL_MAP_FILE"
gcloud compute url-maps import "$URL_MAP_NAME" --global --source="$URL_MAP_FILE" --quiet
rm -f "$URL_MAP_FILE"

echo "== 7. Target HTTPS proxy =="
gcloud compute target-https-proxies describe "$PROXY_NAME" --global >/dev/null 2>&1 || \
  gcloud compute target-https-proxies create "$PROXY_NAME" \
    --url-map="$URL_MAP_NAME" --ssl-certificates="$CERT_NAME" --global

echo "== 8. Global forwarding rules (443, v4 + v6) =="
gcloud compute forwarding-rules describe "$FWD_RULE_V4" --global >/dev/null 2>&1 || \
  gcloud compute forwarding-rules create "$FWD_RULE_V4" \
    --global --load-balancing-scheme=EXTERNAL_MANAGED \
    --target-https-proxy="$PROXY_NAME" --address="$IP_V4_NAME" --ports=443
gcloud compute forwarding-rules describe "$FWD_RULE_V6" --global >/dev/null 2>&1 || \
  gcloud compute forwarding-rules create "$FWD_RULE_V6" \
    --global --load-balancing-scheme=EXTERNAL_MANAGED \
    --target-https-proxy="$PROXY_NAME" --address="$IP_V6_NAME" --ports=443

echo "Done. Once the cert shows ACTIVE (gcloud compute ssl-certificates describe $CERT_NAME --global),"
echo "verify with: curl https://$PROD_HOST/login"
echo "verify Event Creator routing with: curl https://$PROD_HOST/dashboard"
echo ""
echo "IMPORTANT: this only creates the prod domain — it does not redirect any existing traffic."
echo "GOOGLE_OAUTH_REDIRECT_URI / GOOGLE_DRIVE_REDIRECT_URI still point at the raw Cloud Run URLs"
echo "until that's deliberately flipped in a follow-up PR (register the new URLs on the Google"
echo "OAuth client in Google Cloud Console first, or login/Drive-connect will break)."
