<#
.SYNOPSIS
Slice R5 — provisions the shared External HTTPS Load Balancer that fronts
organizeme.qa.russcoopersoftware.com for QA. See docs/features/platform-restructure/WBS/slice-R5.md.

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

R6 introduces Event Creator as its own independent Cloud Run service (event-creator-qa), so it
gets its own Serverless NEG + backend service, distinct from the Host's. Re-running this script is
what wires that second backend into the URL map (which regenerates from the R3 app-registry and
now routes /dashboard to event-creator-backend). This requires event-creator-qa to already be
deployed (its own repo's CI/CD does that) — run this only after that first deploy.
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

$EventCreatorRunService = "event-creator-qa"
$EventCreatorNegName = "event-creator-qa-neg"
$BackendEventCreator = "event-creator-backend"

$DocLibraryRunService = "doc-library-qa"
$DocLibraryNegName = "doc-library-qa-neg"
$BackendDocLibrary = "doc-library-backend"

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

Write-Host "== 4. Serverless NEGs (organizeme-qa + event-creator-qa + doc-library-qa) =="
if (-not (Test-GcloudResource @("compute", "network-endpoint-groups", "describe", $NegName, "--region=$Region"))) {
    gcloud compute network-endpoint-groups create $NegName `
        --region=$Region `
        --network-endpoint-type=serverless `
        --cloud-run-service=$RunService
}
if (-not (Test-GcloudResource @("compute", "network-endpoint-groups", "describe", $EventCreatorNegName, "--region=$Region"))) {
    gcloud compute network-endpoint-groups create $EventCreatorNegName `
        --region=$Region `
        --network-endpoint-type=serverless `
        --cloud-run-service=$EventCreatorRunService
}
if (-not (Test-GcloudResource @("compute", "network-endpoint-groups", "describe", $DocLibraryNegName, "--region=$Region"))) {
    gcloud compute network-endpoint-groups create $DocLibraryNegName `
        --region=$Region `
        --network-endpoint-type=serverless `
        --cloud-run-service=$DocLibraryRunService
}

Write-Host "== 5. Backend services (host-backend, organizeme-backend -> organizeme NEG; event-creator-backend/doc-library-backend -> their own NEGs) =="
foreach ($Backend in @($BackendHost, $BackendOrganizeme)) {
    if (-not (Test-GcloudResource @("compute", "backend-services", "describe", $Backend, "--global"))) {
        gcloud compute backend-services create $Backend --global --load-balancing-scheme=EXTERNAL_MANAGED
        gcloud compute backend-services add-backend $Backend --global `
            --network-endpoint-group=$NegName --network-endpoint-group-region=$Region
    }
}
if (-not (Test-GcloudResource @("compute", "backend-services", "describe", $BackendEventCreator, "--global"))) {
    gcloud compute backend-services create $BackendEventCreator --global --load-balancing-scheme=EXTERNAL_MANAGED
    gcloud compute backend-services add-backend $BackendEventCreator --global `
        --network-endpoint-group=$EventCreatorNegName --network-endpoint-group-region=$Region
}
if (-not (Test-GcloudResource @("compute", "backend-services", "describe", $BackendDocLibrary, "--global"))) {
    gcloud compute backend-services create $BackendDocLibrary --global --load-balancing-scheme=EXTERNAL_MANAGED
    gcloud compute backend-services add-backend $BackendDocLibrary --global `
        --network-endpoint-group=$DocLibraryNegName --network-endpoint-group-region=$Region
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
Write-Host "verify Event Creator routing with: curl https://$QaHost/dashboard"
Write-Host "verify Doc Library routing with: curl https://$QaHost/doc-library"
