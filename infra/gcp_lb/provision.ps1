<#
.SYNOPSIS
Slice R5 — provisions the shared External HTTPS Load Balancer that fronts
organizeme.qa.russcoopersoftware.com for QA. See docs/platform-restructure/WBS/slice-R5.md.

.DESCRIPTION
Windows PowerShell equivalent of provision.sh — same steps, same idempotency pattern (each
resource is describe-checked before create), same resource names. Keep both scripts in sync;
provision.sh is the canonical version (this repo's CI/CD runs on Linux), this one exists so an
operator on Windows doesn't need WSL/Git Bash just to run a one-time manual step.

This is a manual, one-time (re-runnable) operator script — not part of CI/CD. It creates real,
billable GCP resources and a managed SSL cert whose validation can take up to ~24h once the DNS
records below resolve. Run it from an authenticated gcloud session:

    gcloud auth login
    gcloud config set project gen-lang-client-0791944342
    .\infra\gcp_lb\provision.ps1

Today there is only one Cloud Run service (organizeme-qa) — it serves both the Host shell and the
"organizeme" app, so host-backend and organizeme-backend both point at the same Serverless NEG
until R6 introduces Event Creator as its own service (see the "R6" notes at the bottom).
#>

$ErrorActionPreference = "Stop"

$ProjectId = "gen-lang-client-0791944342"
$Region = "northamerica-northeast1"
$DnsZone = "russcoopersoftware-com"
$QaHost = "organizeme.qa.russcoopersoftware.com"

$RunService = "organizeme-qa"
$NegName = "organizeme-qa-neg"
$BackendHost = "host-backend"
$BackendOrganizeme = "organizeme-backend"
$IpV4Name = "organizeme-lb-ipv4"
$IpV6Name = "organizeme-lb-ipv6"
$CertName = "organizeme-qa-cert"
$UrlMapName = "organizeme-qa-url-map"
$ProxyName = "organizeme-qa-https-proxy"
$FwdRuleV4 = "organizeme-qa-fwd-v4"
$FwdRuleV6 = "organizeme-qa-fwd-v6"

function Test-GcloudResource {
    param([string[]]$DescribeArgs)
    try {
        & gcloud @DescribeArgs *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

gcloud config set project $ProjectId | Out-Null

Write-Host "== 1. Global static IPs =="
if (-not (Test-GcloudResource @("compute", "addresses", "describe", $IpV4Name, "--global"))) {
    gcloud compute addresses create $IpV4Name --global --ip-version=IPV4
}
if (-not (Test-GcloudResource @("compute", "addresses", "describe", $IpV6Name, "--global"))) {
    gcloud compute addresses create $IpV6Name --global --ip-version=IPV6
}

$Ipv4Addr = gcloud compute addresses describe $IpV4Name --global --format="value(address)"
$Ipv6Addr = gcloud compute addresses describe $IpV6Name --global --format="value(address)"
Write-Host "IPv4: $Ipv4Addr"
Write-Host "IPv6: $Ipv6Addr"

Write-Host "== 2. Cloud DNS A/AAAA records ($DnsZone) =="
if (-not (Test-GcloudResource @("dns", "record-sets", "describe", "$QaHost.", "--zone=$DnsZone", "--type=A"))) {
    gcloud dns record-sets create "$QaHost." --zone=$DnsZone --type=A --ttl=300 --rrdatas=$Ipv4Addr
}
if (-not (Test-GcloudResource @("dns", "record-sets", "describe", "$QaHost.", "--zone=$DnsZone", "--type=AAAA"))) {
    gcloud dns record-sets create "$QaHost." --zone=$DnsZone --type=AAAA --ttl=300 --rrdatas=$Ipv6Addr
}

Write-Host "== 3. Google-managed SSL certificate =="
if (-not (Test-GcloudResource @("compute", "ssl-certificates", "describe", $CertName, "--global"))) {
    gcloud compute ssl-certificates create $CertName --global --domains=$QaHost
}
Write-Host "NOTE: cert stays PROVISIONING until the A/AAAA records above resolve and Google validates them (can take up to ~24h)."

Write-Host "== 4. Serverless NEG for $RunService =="
if (-not (Test-GcloudResource @("compute", "network-endpoint-groups", "describe", $NegName, "--region=$Region"))) {
    gcloud compute network-endpoint-groups create $NegName `
        --region=$Region `
        --network-endpoint-type=serverless `
        --cloud-run-service=$RunService
}

Write-Host "== 5. Backend services (host-backend + organizeme-backend, same NEG for now) =="
foreach ($Backend in @($BackendHost, $BackendOrganizeme)) {
    if (-not (Test-GcloudResource @("compute", "backend-services", "describe", $Backend, "--global"))) {
        gcloud compute backend-services create $Backend --global --load-balancing-scheme=EXTERNAL_MANAGED
        gcloud compute backend-services add-backend $Backend --global `
            --network-endpoint-group=$NegName --network-endpoint-group-region=$Region
    }
}

Write-Host "== 6. URL map, generated from the R3 app-registry =="
$UrlMapFile = New-TemporaryFile
try {
    (uv run python -m infra.gcp_lb.generate_url_map) -replace '\$LB_HOST', $QaHost |
        Set-Content -Path $UrlMapFile -Encoding utf8
    # `import` creates the URL map if it doesn't exist yet, or updates it in place if it does —
    # idempotent either way, so no existence check is needed here (unlike the resources above).
    gcloud compute url-maps import $UrlMapName --global --source=$UrlMapFile --quiet
} finally {
    Remove-Item -Path $UrlMapFile -Force -ErrorAction SilentlyContinue
}

Write-Host "== 7. Target HTTPS proxy =="
if (-not (Test-GcloudResource @("compute", "target-https-proxies", "describe", $ProxyName, "--global"))) {
    gcloud compute target-https-proxies create $ProxyName `
        --url-map=$UrlMapName --ssl-certificates=$CertName --global
}

Write-Host "== 8. Global forwarding rules (443, v4 + v6) =="
# --load-balancing-scheme must match the backend services' EXTERNAL_MANAGED (step 5) — global
# forwarding rules default to the classic EXTERNAL scheme otherwise, which GCP rejects as a
# scheme mismatch against the url-map/backend-services chain.
if (-not (Test-GcloudResource @("compute", "forwarding-rules", "describe", $FwdRuleV4, "--global"))) {
    gcloud compute forwarding-rules create $FwdRuleV4 `
        --global --load-balancing-scheme=EXTERNAL_MANAGED `
        --target-https-proxy=$ProxyName --address=$IpV4Name --ports=443
}
if (-not (Test-GcloudResource @("compute", "forwarding-rules", "describe", $FwdRuleV6, "--global"))) {
    gcloud compute forwarding-rules create $FwdRuleV6 `
        --global --load-balancing-scheme=EXTERNAL_MANAGED `
        --target-https-proxy=$ProxyName --address=$IpV6Name --ports=443
}

Write-Host "Done. Once the cert shows ACTIVE (gcloud compute ssl-certificates describe $CertName --global),"
Write-Host "verify with: curl https://$QaHost/login"

# --- R6 (adding Event Creator as a second hosted app) ---
# 1. Deploy the Event Creator Cloud Run service (e.g. "event-creator-qa").
# 2. Add an entry for it in packages/chrome/src/organizeme_chrome/registry.py (APPS list).
# 3. Create its own Serverless NEG + backend service (e.g. "event-creator-backend"), mirroring
#    steps 4-5 above with RunService=event-creator-qa, NegName=event-creator-qa-neg.
# 4. Re-run this script (or just steps 6-7) — the URL map regenerates from the updated registry
#    and automatically adds a path rule routing Event Creator's nav paths to its own backend.
