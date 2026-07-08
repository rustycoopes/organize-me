@echo off
REM Claude Loop Launcher
REM A simple batch file to run the Claude loop script with your settings

setlocal enabledelayedexpansion

REM Change to script directory
cd /d "%~dp0"

REM ======================================================================
REM CUSTOMIZE THESE SETTINGS
REM ======================================================================

set PROMPT=Please analyze the current state and provide a summary.
set ITERATIONS=5
set INTERVAL_MINUTES=60

REM ======================================================================
REM Run the PowerShell script
REM ======================================================================

echo.
echo ========================================
echo Claude Loop Launcher
echo ========================================
echo.
echo Prompt:    %PROMPT%
echo Iterations: %ITERATIONS%
echo Interval:   %INTERVAL_MINUTES% minutes
echo.
echo Starting Claude loop...
echo.

REM Run with no profile to avoid user startup scripts, and allow script execution
powershell -NoProfile -ExecutionPolicy Bypass -File "claude-loop.ps1" ^
  -Prompt "%PROMPT%" ^
  -Iterations %ITERATIONS% ^
  -IntervalMinutes %INTERVAL_MINUTES%

echo.
echo Script completed. Logs are saved to %%APPDATA%%\claude-sessions\logs\
echo.
pause
