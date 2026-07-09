<#
.SYNOPSIS
Remote control interface for the Claude loop script.

.DESCRIPTION
Provides utilities to interact with the running Claude loop:
- Check current status
- View recent logs
- Manually pause/resume
- See session information

.PARAMETER Action
Action to perform: Status, Logs, ViewLog, Pause

.EXAMPLE
.\claude-control.ps1 -Action Status
.\claude-control.ps1 -Action Logs
.\claude-control.ps1 -Action ViewLog -Lines 50
#>

param(
    [Parameter(Mandatory = $true, HelpMessage = "Action to perform")]
    [ValidateSet("Status", "Logs", "ViewLog", "Pause")]
    [string]$Action,

    [Parameter(Mandatory = $false, HelpMessage = "Number of log lines to display")]
    [int]$Lines = 20
)

$sessionDir = ".\ralph\claude-sessions"
$statusFile = ".\ralph\session_status.txt"
$logDir = ".\ralph\logs"
$masterLog = ".\ralph\master.log"

function Show-Status {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Claude Loop Status" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    if (Test-Path $statusFile) {
        $status = Get-Content $statusFile -Raw
        Write-Host "`nCurrent Status:`n$status`n"
    }
    else {
        Write-Host "`nNo status file found. Script may not be running.`n" -ForegroundColor Yellow
    }

    if (Get-Process -Name "claude" -ErrorAction SilentlyContinue) {
        Write-Host "Claude Process: " -NoNewline -ForegroundColor Green
        Write-Host "RUNNING" -ForegroundColor Green
    }
    else {
        Write-Host "Claude Process: " -NoNewline -ForegroundColor Gray
        Write-Host "IDLE" -ForegroundColor Gray
    }

    Write-Host "`nLog Directory: $logDir"
    if (Test-Path $logDir) {
        $logFiles = Get-ChildItem $logDir -File | Sort-Object LastWriteTime -Descending
        Write-Host "Recent logs: $(($logFiles | Measure-Object).Count) files"
        $logFiles | Select-Object -First 3 | ForEach-Object {
            Write-Host "  - $($_.Name) ($($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')))"
        }
    }

    Write-Host "`nTo interact with the running session, use:"
    Write-Host "  - Close the main claude-loop.ps1 window and run it again (restart)"
    Write-Host "  - Use /remote-control inside Claude during a session"
    Write-Host "  - View logs with: .\claude-control.ps1 -Action ViewLog -Lines 50"
}

function Show-Logs {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Recent Log Lines (Last $Lines)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    if (Test-Path $masterLog) {
        $logContent = Get-Content $masterLog -Tail $Lines
        $logContent | ForEach-Object {
            if ($_ -like "*ERROR*") {
                Write-Host $_ -ForegroundColor Red
            }
            elseif ($_ -like "*WARN*") {
                Write-Host $_ -ForegroundColor Yellow
            }
            else {
                Write-Host $_
            }
        }
    }
    else {
        Write-Host "No log file found yet." -ForegroundColor Yellow
    }
}

function Show-FullLog {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Master Log" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    if (Test-Path $masterLog) {
        Write-Host "`nOpening in default text editor...`n"
        & $masterLog
    }
    else {
        Write-Host "No master log file found." -ForegroundColor Yellow
    }
}

function Pause-Session {
    Write-Host "To pause the Claude loop script:" -ForegroundColor Yellow
    Write-Host "  1. Switch to the claude-loop.ps1 window"
    Write-Host "  2. Press Ctrl+C to interrupt"
    Write-Host "  3. Run it again later to resume (it tracks iteration count)"
    Write-Host "`nTo interact during a running session:"
    Write-Host "  1. Open another PowerShell window"
    Write-Host "  2. Type 'claude' to open a new Claude session"
    Write-Host "  3. Use /remote-control to pause the running session and send feedback"
}

# Execute requested action
switch ($Action) {
    "Status" { Show-Status }
    "Logs" { Show-Logs }
    "ViewLog" { Show-FullLog }
    "Pause" { Pause-Session }
}
