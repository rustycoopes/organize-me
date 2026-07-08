@echo off
REM Claude Issue Loop Launcher
REM Runs /next-issue skill repeatedly to work through the GitHub project board
REM Each iteration picks the highest-priority remaining issue and updates you on progress

setlocal enabledelayedexpansion

REM Change to script directory
cd /d "%~dp0"

REM ======================================================================
REM CONFIGURATION - Customize as needed
REM ======================================================================

REM Use /next-issue skill - picks the highest-priority issue from the board
set PROMPT=/next-issue

REM How many times to run (once per hour)
set ITERATIONS=5

REM How long to wait between picks (minutes)
set INTERVAL_MINUTES=60

REM ======================================================================
REM Run the Claude loop
REM ======================================================================

echo.
echo ========================================
echo Claude Issue Loop Launcher
echo ========================================
echo.
echo This will run /next-issue %ITERATIONS% times
echo with %INTERVAL_MINUTES% minute intervals
echo.
echo Each iteration will:
echo   1. Pick the highest-priority unstarted issue
echo   2. Explain the choice
echo   3. Kick off implementation (or analysis)
echo   4. Report status
echo   5. Wait %INTERVAL_MINUTES% minutes for the next pick
echo.
echo Starting...
echo.

REM Run the PowerShell script
powershell -NoProfile -ExecutionPolicy Bypass -File "claude-loop.ps1" ^
  -Prompt "%PROMPT%" ^
  -Iterations %ITERATIONS% ^
  -IntervalMinutes %INTERVAL_MINUTES%

echo.
echo ========================================
echo Issue loop completed!
echo ========================================
echo.
echo Logs saved to: %%APPDATA%%\claude-sessions\logs\
echo.
echo To view logs:
echo   .\claude-control.ps1 -Action ViewLog
echo.
pause
