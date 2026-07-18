<#
.SYNOPSIS
Orchestrate sequential issue implementation using Claude Code.

.DESCRIPTION
Process a list of GitHub issues sequentially. Each issue gets a fresh,
fully interactive Claude Code session where you can respond to questions,
run additional skills, enable remote control, and work through naturally.

The script monitors GitHub for closure and moves to the next issue.

.PARAMETER IssueNumbers
Array of GitHub issue numbers to process.

.PARAMETER ConfigPath
Path to JSON config file with issue list (alternative to -IssueNumbers).

.PARAMETER Repo
GitHub repository name (default: organize-me)

.PARAMETER SkipWait
Don't wait for issue closure before moving to next.

.PARAMETER Auto
Enable auto mode for Claude (runs without requiring manual interaction).

.EXAMPLE
.\automate_implementation.ps1 -IssueNumbers 123, 124, 125
.\automate_implementation.ps1 -ConfigPath issues_config.json
.\automate_implementation.ps1 -IssueNumbers 123, 124 -Auto
.\automate_implementation.ps1 -IssueNumbers 123, 124 -Auto -SkipWait
#>

param(
    [Parameter(Position = 0)]
    [int[]]$IssueNumbers,

    [Parameter()]
    [string]$ConfigPath,

    [Parameter()]
    [string]$Repo = "organize-me",

    [Parameter()]
    [switch]$SkipWait,

    [Parameter()]
    [switch]$Auto
)

function Get-IssueStatus {
    param(
        [int]$IssueNumber,
        [string]$Repository
    )

    try {
        $json = gh issue view $IssueNumber -R "rustycoopes/$Repository" --json state
        if ($LASTEXITCODE -eq 0) {
            $data = $json | ConvertFrom-Json
            return $data.state -eq "CLOSED"
        }
    } catch {
        Write-Warning "Could not check issue status: $_"
    }
    return $false
}

function Wait-ForIssueClosure {
    param(
        [int]$IssueNumber,
        [string]$Repository,
        [int]$TimeoutMinutes = 120
    )

    Write-Host ""
    Write-Host "[INFO] Monitoring issue #$IssueNumber for closure..."

    $startTime = Get-Date
    $timeout = [timespan]::FromMinutes($TimeoutMinutes)
    $checkInterval = 15

    while (((Get-Date) - $startTime) -lt $timeout) {
        if (Get-IssueStatus -IssueNumber $IssueNumber -Repository $Repository) {
            Write-Host "[CLOSED] Issue #$IssueNumber is closed"
            return $true
        }

        $elapsed = [int]((Get-Date) - $startTime).TotalSeconds
        Write-Host "  ($elapsed seconds elapsed, still open...)" -NoNewline
        Start-Sleep -Seconds $checkInterval
    }

    Write-Host ""
    Write-Host "[TIMEOUT] Waiting for issue #$IssueNumber after $TimeoutMinutes minutes"
    return $false
}

function Start-Implementation {
    param(
        [int]$IssueNumber,
        [bool]$AutoMode = $false
    )

    Write-Host ""
    Write-Host "================================================================"
    Write-Host "STARTING: Issue #$IssueNumber"
    if ($AutoMode) {
        Write-Host "(Auto Mode Enabled)"
    }
    Write-Host "================================================================"
    Write-Host ""

    try {
        # Use & (call operator) to properly invoke claude with arguments
        if ($AutoMode) {
            & claude /auto /to-implementation $IssueNumber
        } else {
            & claude /to-implementation $IssueNumber
        }
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0 -or $exitCode -eq $null) {
            Write-Host ""
            Write-Host "[OK] Session for issue #$IssueNumber completed"
            return $true
        } else {
            Write-Host ""
            Write-Host "[FAIL] Session for issue #$IssueNumber exited with code $exitCode"
            return $false
        }
    } catch {
        Write-Host ""
        Write-Host "[ERROR] Failed to spawn Claude session: $_"
        Write-Host "[ERROR] Make sure Claude CLI is installed and in PATH"
        return $false
    }
}

function Process-Issues {
    param(
        [int[]]$Issues,
        [string]$Repository,
        [bool]$SkipWaitFlag,
        [bool]$AutoMode = $false
    )

    $total = $Issues.Count
    $issueList = $Issues -join ", "

    Write-Host ""
    Write-Host "================================================================"
    Write-Host "AUTOMATION: Sequential Issue Implementation"
    Write-Host "================================================================"
    Write-Host "Processing $total issue(s): $issueList"
    Write-Host "Repository: rustycoopes/$Repository"
    if ($AutoMode) {
        Write-Host "Mode: AUTO"
    }
    Write-Host "Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "================================================================"
    Write-Host ""

    $completed = @()
    $failed = @()

    for ($idx = 0; $idx -lt $total; $idx++) {
        $issueNum = $Issues[$idx]
        $progress = $idx + 1

        Write-Host ""
        Write-Host "[$progress/$total] Processing issue #$issueNum..."

        $sessionOk = Start-Implementation -IssueNumber $issueNum -AutoMode $AutoMode

        if (-not $sessionOk) {
            Write-Host "[FAIL] Session failed for issue #$issueNum"
            $failed += $issueNum
            continue
        }

        if ($SkipWaitFlag) {
            Write-Host "[INFO] Skipping closure check"
            $completed += $issueNum
        } else {
            if (Wait-ForIssueClosure -IssueNumber $issueNum -Repository $Repository) {
                $completed += $issueNum
            } else {
                $completed += $issueNum
                Write-Host "(Verify closure manually if needed)"
            }
        }

        if ($idx -lt ($total - 1)) {
            Write-Host ""
            Write-Host "[INFO] Moving to next issue in 5 seconds..."
            Start-Sleep -Seconds 5
        }
    }

    Write-Host ""
    Write-Host ""
    Write-Host "================================================================"
    Write-Host "SUMMARY"
    Write-Host "================================================================"
    Write-Host "Completed: $($completed.Count)/$total"
    if ($completed.Count -gt 0) {
        $completedStr = $completed | ForEach-Object { "#$_" }
        Write-Host "  OK Issues: $($completedStr -join ', ')"
    }
    if ($failed.Count -gt 0) {
        Write-Host "Failed: $($failed.Count)/$total"
        $failedStr = $failed | ForEach-Object { "#$_" }
        Write-Host "  FAIL Issues: $($failedStr -join ', ')"
    }
    Write-Host "Finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "================================================================"
    Write-Host ""
}

try {
    $issues = $null

    if ($IssueNumbers.Count -gt 0) {
        $issues = $IssueNumbers
    } elseif ($ConfigPath) {
        if (-not (Test-Path $ConfigPath)) {
            Write-Host "Error: Config file not found: $ConfigPath"
            exit 1
        }
        $config = Get-Content $ConfigPath | ConvertFrom-Json
        $issues = $config.issues
    } else {
        Write-Host "Usage:"
        Write-Host "  .\automate_implementation.ps1 -IssueNumbers 123, 124, 125"
        Write-Host "  .\automate_implementation.ps1 -ConfigPath issues_config.json"
        exit 1
    }

    if (-not $issues -or $issues.Count -eq 0) {
        Write-Host "Error: No issues to process"
        exit 1
    }

    Process-Issues -Issues $issues -Repository $Repo -SkipWaitFlag $SkipWait -AutoMode $Auto
} catch {
    Write-Host ""
    Write-Host "[ERROR] $($_)"
    exit 1
}
