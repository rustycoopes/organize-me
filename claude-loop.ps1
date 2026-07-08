<#
.SYNOPSIS
Executes Claude CLI sessions in a loop with remote control support.

.DESCRIPTION
Runs Claude with a fixed prompt 5 times with 1-hour intervals between iterations.
- Only one Claude session runs at a time
- All output is logged to file and displayed in console
- Supports /remote-control for interactive feedback during sessions
- Tracks session state to prevent duplicate runs

.PARAMETER Prompt
The Claude prompt to execute (same for all iterations)

.PARAMETER IntervalMinutes
Wait time between iterations in minutes (default: 60)

.PARAMETER Iterations
Number of times to run the loop (default: 5)

.PARAMETER LogPath
Directory to store logs (default: $env:APPDATA\claude-sessions\logs)

.EXAMPLE
.\claude-loop.ps1 -Prompt "Your Claude task here"
.\claude-loop.ps1 -Prompt "Check logs" -IntervalMinutes 5 -Iterations 3
#>

param(
    [Parameter(Mandatory=$false, HelpMessage="Claude prompt or skill to execute")]
    [string]$Prompt = "/next-issue",

    [Parameter(Mandatory=$false, HelpMessage="Minutes to wait between iterations")]
    [int]$IntervalMinutes = 60,

    [Parameter(Mandatory=$false, HelpMessage="Number of iterations to run")]
    [int]$Iterations = 5,

    [Parameter(Mandatory=$false, HelpMessage="Log directory path")]
    [string]$LogPath = ".ralph\claude-sessions\logs"
)

# ============================================================================
# INITIALIZATION
# ============================================================================

$ErrorActionPreference = "Stop"

# Create directories if they don't exist
$sessionDir = ".\ralph\claude-sessions"
$statusFile = ".\ralph\session_status.txt"
$masterLogFile = ".\ralph\master.log"

@($sessionDir, $LogPath) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR", "DEBUG")]
        [string]$Level = "INFO"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"

    Write-Host $logMessage
    Add-Content -Path $masterLogFile -Value $logMessage -Encoding UTF8
}

function Update-Status {
    param([string]$Status)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $statusMessage = "[$timestamp] $Status"
    Set-Content -Path $statusFile -Value $statusMessage -Encoding UTF8
    Write-Log "Status: $Status"
}

function Get-Status {
    if (Test-Path $statusFile) {
        return (Get-Content -Path $statusFile -Raw).Trim()
    }
    return "UNKNOWN"
}

function Is-ClaudeRunning {
    $claudeProcess = Get-Process -Name "claude" -ErrorAction SilentlyContinue
    return $null -ne $claudeProcess
}

function Wait-ForClaudeAvailable {
    param([int]$MaxRetries = 60, [int]$DelaySeconds = 30)

    $retries = 0
    while ($retries -lt $MaxRetries) {
        if (-not (Is-ClaudeRunning)) {
            Write-Log "Claude process is available."
            return $true
        }

        $retries++
        $timeRemaining = ($MaxRetries - $retries) * $DelaySeconds
        Write-Log "Claude still running. Retry $retries/$MaxRetries. Waiting ${DelaySeconds}s (${timeRemaining}s remaining)..." -Level "WARN"
        Start-Sleep -Seconds $DelaySeconds
    }

    Write-Log "Timeout waiting for Claude to finish after $($MaxRetries * $DelaySeconds) seconds" -Level "ERROR"
    return $false
}

function Start-ClaudeSession {
    param(
        [int]$IterationNumber,
        [string]$SessionLogFile
    )

    Update-Status "RUNNING (Iteration $IterationNumber/$Iterations)"

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Log "========================================"
    Write-Log "Starting Claude Session #$IterationNumber at $timestamp"
    Write-Log "Prompt: $Prompt"
    Write-Log "========================================"

    try {
        # Invoke Claude CLI with remote-control enabled
        # Captures output to both console and log file
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = "claude"
        $processInfo.Arguments = @(
            $Prompt
            "--remote-control"
        ) -join " "
        $processInfo.UseShellExecute = $false
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.CreateNoWindow = $false

        $process = [System.Diagnostics.Process]::Start($processInfo)

        # Read output while the process runs
        while (-not $process.HasExited) {
            $line = $process.StandardOutput.ReadLine()
            if ($line) {
                Write-Host $line
                Add-Content -Path $sessionLogFile -Value $line -Encoding UTF8
                Add-Content -Path $masterLogFile -Value $line -Encoding UTF8
            }
        }

        # Read remaining output
        $remainingOutput = $process.StandardOutput.ReadToEnd()
        if ($remainingOutput) {
            Write-Host $remainingOutput
            Add-Content -Path $sessionLogFile -Value $remainingOutput -Encoding UTF8
            Add-Content -Path $masterLogFile -Value $remainingOutput -Encoding UTF8
        }

        # Handle errors
        $errorOutput = $process.StandardError.ReadToEnd()
        if ($errorOutput) {
            Write-Log $errorOutput -Level "ERROR"
            Add-Content -Path $sessionLogFile -Value "[ERROR] $errorOutput" -Encoding UTF8
            Add-Content -Path $masterLogFile -Value "[ERROR] $errorOutput" -Encoding UTF8
        }

        $exitCode = $process.ExitCode
        $process.Dispose()

        if ($exitCode -eq 0) {
            Write-Log "Claude session #$IterationNumber completed successfully (exit code: $exitCode)"
            Update-Status "IDLE"
            return $true
        } else {
            Write-Log "Claude session #$IterationNumber failed with exit code: $exitCode" -Level "ERROR"
            Update-Status "FAILED"
            return $false
        }
    }
    catch {
        Write-Log "Error running Claude session: $($_.Exception.Message)" -Level "ERROR"
        Update-Status "FAILED"
        return $false
    }
}

# ============================================================================
# MAIN LOOP
# ============================================================================

function Main {
    Write-Log "Claude Loop Script Started"
    Write-Log "Configuration: Iterations=$Iterations, Interval=${IntervalMinutes}min, LogPath=$LogPath"
    Write-Log "Prompt: $Prompt"

    Update-Status "INITIALIZED"

    for ($i = 1; $i -le $Iterations; $i++) {
        Write-Log "====== ITERATION $i/$Iterations ======"

        # Wait for any existing Claude process to complete
        Write-Log "Checking for existing Claude processes..."
        if (-not (Wait-ForClaudeAvailable)) {
            Write-Log "Could not acquire Claude. Skipping iteration $i" -Level "ERROR"
            continue
        }

        # Create session log file
        $sessionTimestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $sessionLogFile = "$LogPath\session_${sessionTimestamp}_iter${i}.log"

        # Run Claude session
        $success = Start-ClaudeSession -IterationNumber $i -SessionLogFile $sessionLogFile

        # Wait before next iteration
        if ($i -lt $Iterations) {
            $nextIterationTime = (Get-Date).AddMinutes($IntervalMinutes)
            Write-Log "Waiting $IntervalMinutes minutes until next iteration (resume at $nextIterationTime)"
            Write-Log "To interrupt: Close this PowerShell window or use Ctrl+C"
            Write-Log "To interact: Open another terminal and use /remote-control during the wait"

            Update-Status "IDLE - Waiting for next iteration (due $nextIterationTime)"

            Start-Sleep -Seconds ($IntervalMinutes * 60)
        }
    }

    Write-Log "====== LOOP COMPLETE ======"
    Write-Log "All $Iterations iterations finished."
    Write-Log "Logs saved to: $LogPath"

    Update-Status "COMPLETED"
}

# ============================================================================
# RUN
# ============================================================================

try {
    Main
}
catch {
    Write-Log "Fatal error: $($_.Exception.Message)" -Level "ERROR"
    Write-Log $_.ScriptStackTrace -Level "ERROR"
    Update-Status "FATAL_ERROR"
    exit 1
}
