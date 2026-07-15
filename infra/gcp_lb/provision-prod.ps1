<#
.SYNOPSIS
Slice R12 — provisions the production External HTTPS Load Balancer that fronts
organizeme.russcoopersoftware.com. See docs/platform-restructure/WBS/slice-R12.md.

.DESCRIPTION
Windows PowerShell equivalent of provision-prod.sh — same steps, same idempotency pattern (each
resource is describe-checked before create), same resource names. Keep both scripts in sync;
provision-prod.sh is the canonical version (this repo's CI/CD runs on Linux), this one exists so an
operator on Windows doesn't need WSL/Git Bash just to run a one-time manual step.

This is a manual, one-time (re-runnable) operator script — not part of CI/CD. It creates real,
billable GCP resources and a managed SSL cert whose validation can take up to ~24h once the DNS
records below resolve. Run it from an authenticated gcloud session:

    gcloud auth login
    gcloud config set project gen-lang-client-0791944342
    .\infra\gcp_lb\provision-prod.ps1

Creating these resources and the DNS record below is non-disruptive: organizeme.russcoopersoftware.com
is a brand-new hostname nothing currently points at (prod is reached today via the raw Cloud Run
URLs), so nothing changes for existing users until GOOGLE_OAUTH_REDIRECT_URI/GOOGLE_DRIVE_REDIRECT_URI
are deliberately flipped to it in a later, separate step.
#>

$ErrorActionPreference = "Stop"

$ProjectId = "gen-lang-client-0791944342"
$Region = "northamerica-northeast1"
$DnsZone = "russcoopersoftware-com"
$ProdHost = "organizeme.russcoopersoftware.com"

$RunService = "organizeme-prod"
$NegName = "organizeme-prod-neg"
$BackendHost = "host-backend-prod"
$BackendOrganizeme = "organizeme-backend-prod"

$EventCreatorRunService = "event-creator-prod"
$EventCreatorNegName = "event-creator-prod-neg"
$BackendEventCreator = "event-creator-backend-prod"

$IpV4Name = "organizeme-prod-lb-ipv4"
$IpV6Name = "organizeme-prod-lb-ipv6"
$CertName = "organizeme-prod-cert"
$UrlMapName = "organizeme-prod-url-map"
$ProxyName = "organizeme-prod-https-proxy"
$FwdRuleV4 = "organizeme-prod-fwd-v4"
$FwdRuleV6 = "organizeme-prod-fwd-v6"

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
if (-not (Test-GcloudResource @("dns", "record-sets", "describe", "$ProdHost.", "--zone=$DnsZone", "--type=A"))) {
    gcloud dns record-sets create "$ProdHost." --zone=$DnsZone --type=A --ttl=300 --rrdatas=$Ipv4Addr
}
if (-not (Test-GcloudResource @("dns", "record-sets", "describe", "$ProdHost.", "--zone=$DnsZone", "--type=AAAA"))) {
    gcloud dns record-sets create "$ProdHost." --zone=$DnsZone --type=AAAA --ttl=300 --rrdatas=$Ipv6Addr
}

Write-Host "== 3. Google-managed SSL certificate =="
if (-not (Test-GcloudResource @("compute", "ssl-certificates", "describe", $CertName, "--global"))) {
    gcloud compute ssl-certificates create $CertName --global --domains=$ProdHost
}
Write-Host "NOTE: cert stays PROVISIONING until the A/AAAA records above resolve and Google validates them (can take up to ~24h)."

Write-Host "== 4. Serverless NEGs (organizeme-prod + event-creator-prod) =="
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

Write-Host "== 5. Backend services =="
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

Write-Host "== 6. URL map, generated from the R3 app-registry =="
$UrlMapFile = New-TemporaryFile
try {
    (uv run python -m infra.gcp_lb.generate_url_map prod) -replace '\$LB_HOST', $ProdHost |
        Set-Content -Path $UrlMapFile -Encoding utf8
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
Write-Host "verify with: curl https://$ProdHost/login"
Write-Host "verify Event Creator routing with: curl https://$ProdHost/dashboard"
Write-Host ""
Write-Host "IMPORTANT: this only creates the prod domain — it does not redirect any existing traffic."
Write-Host "GOOGLE_OAUTH_REDIRECT_URI / GOOGLE_DRIVE_REDIRECT_URI still point at the raw Cloud Run URLs"
Write-Host "until that's deliberately flipped in a follow-up PR (register the new URLs on the Google"
Write-Host "OAuth client in Google Cloud Console first, or login/Drive-connect will break)."
