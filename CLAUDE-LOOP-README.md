# Claude Loop Script

A Windows PowerShell script that executes Claude sessions on a schedule with remote control support.

## Overview

**What it does:**
- Runs a Claude prompt repeatedly (default: 5 times)
- Waits between iterations (default: 1 hour)
- Only allows one Claude session at a time
- Logs all output to file and console
- Enables `/remote-control` for interactive feedback during sessions

**Use cases:**
- Scheduled monitoring or reporting tasks
- Recurring analysis or checks
- Automated workflows that need Claude's reasoning
- Testing Claude behavior over multiple iterations

## Quick Start

### 1. Basic Usage

```powershell
cd C:\dev\organize-me
.\claude-loop.ps1 -Prompt "Your task here"
```

This will run 5 iterations with 1-hour intervals.

### 2. Custom Configuration

```powershell
.\claude-loop.ps1 `
  -Prompt "Check system status" `
  -Iterations 3 `
  -IntervalMinutes 5
```

### 3. Using a Config File

Copy and customize the example:

```powershell
Copy-Item claude-loop-config.example.ps1 claude-loop-config.ps1
# Edit claude-loop-config.ps1 with your settings
```

Then run with the config:

```powershell
.\claude-loop.ps1 -Prompt $YOUR_PROMPT -Iterations 5 -IntervalMinutes 60
```

## Features

### Single Session Control

The script ensures only one Claude session runs at a time:
- Checks if Claude is already running before starting a new session
- Waits up to 30 minutes for a previous session to finish
- Never starts duplicate sessions

### Logging

All output is saved to:
- **Console** — real-time display as Claude runs
- **Session logs** — individual file per iteration
  - Location: `%APPDATA%\claude-sessions\logs\session_[date]_iter[N].log`
- **Master log** — all iterations combined
  - Location: `%APPDATA%\claude-sessions\logs\master.log`

### Remote Control

During a running session, you can interact with Claude:

1. **In a new terminal**, open another Claude session:
   ```powershell
   claude
   ```

2. **Inside Claude**, use `/remote-control` to:
   - Pause the running session
   - Send feedback or corrections
   - Modify the task or prompt
   - Resume automatically after interaction

3. **Back in the main window**, the loop resumes where it left off

### Status Monitoring

Check the status of your running loop:

```powershell
.\claude-control.ps1 -Action Status
```

This shows:
- Current iteration and status
- Whether Claude is running
- Recent log files
- Next iteration time

### View Logs

```powershell
# Show last 20 lines
.\claude-control.ps1 -Action Logs

# Show last 50 lines
.\claude-control.ps1 -Action Logs -Lines 50

# Open full log in text editor
.\claude-control.ps1 -Action ViewLog
```

## Parameters

### claude-loop.ps1

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Prompt` | "Please analyze the current state..." | Claude prompt to execute |
| `-Iterations` | 5 | Number of times to run |
| `-IntervalMinutes` | 60 | Minutes to wait between iterations |
| `-LogPath` | `%APPDATA%\claude-sessions\logs` | Where to save logs |

### Examples

**Test run (quick feedback loop):**
```powershell
.\claude-loop.ps1 -Prompt "Test" -Iterations 2 -IntervalMinutes 1
```

**Overnight monitoring (hourly for 8 hours):**
```powershell
.\claude-loop.ps1 `
  -Prompt "Check system logs and report any errors" `
  -Iterations 8 `
  -IntervalMinutes 60
```

**Extended task (every 30 minutes):**
```powershell
.\claude-loop.ps1 `
  -Prompt "Analyze daily metrics" `
  -Iterations 12 `
  -IntervalMinutes 30
```

## Output Format

Each session produces output like:

```
[2026-07-08 14:00:00] [INFO] Status: RUNNING (Iteration 1/5)
[2026-07-08 14:00:00] [INFO] ========================================
[2026-07-08 14:00:00] [INFO] Starting Claude Session #1
[2026-07-08 14:00:00] [INFO] Prompt: Your task here
[2026-07-08 14:00:00] [INFO] ========================================
[Claude's response here...]
[2026-07-08 14:05:30] [INFO] Claude session #1 completed successfully
[2026-07-08 14:05:30] [INFO] Status: IDLE
[2026-07-08 14:05:30] [INFO] Waiting 60 minutes until next iteration
```

## Troubleshooting

### Script won't start

**Problem:** `The term 'claude' is not recognized`

**Solution:** Ensure Claude CLI is installed and in your PATH:
```powershell
claude --version
```

If not installed, follow the Claude Code setup instructions.

### Script hangs or takes too long

**Problem:** Session takes longer than expected

**Possible causes:**
- Claude is processing (normal for complex tasks)
- Claude is waiting for user input
- Network connection issue

**Solution:**
- Press Ctrl+C to interrupt and check logs
- Use `/remote-control` to interact during the session
- View logs with `.\claude-control.ps1 -Action Logs`

### Sessions not starting after first iteration

**Problem:** Second iteration doesn't start

**Possible cause:** Previous Claude process didn't fully exit

**Solution:**
- Check Task Manager for lingering `claude` processes
- Kill manually if needed: `Get-Process claude | Stop-Process -Force`
- Restart the script

### Can't interact with running session

**Problem:** `/remote-control` isn't working

**Solution:**
- Ensure you're running Claude with the `--remote-control` flag (script does this automatically)
- Try opening a new Claude terminal window and using `/remote-control` from there
- Check logs for any errors

## Windows Task Scheduler Integration (Optional)

To run this script automatically on a schedule:

### Step 1: Create a batch file launcher

Create `run-claude-loop.bat`:

```batch
@echo off
REM Run Claude loop with your settings
REM Customize the prompt and timing as needed

cd /d "C:\dev\organize-me"
powershell -NoProfile -ExecutionPolicy Bypass -File "claude-loop.ps1" ^
  -Prompt "Your prompt here" ^
  -Iterations 5 ^
  -IntervalMinutes 60

pause
```

### Step 2: Create scheduled task

1. Open **Task Scheduler** (Win+X → Task Scheduler)
2. Click **Create Task**
3. **General tab:**
   - Name: "Claude Loop - YourTask"
   - Check: "Run whether user is logged in or not"
4. **Triggers tab:**
   - New Trigger → Select your schedule
   - Example: Daily at 9:00 AM
5. **Actions tab:**
   - Action: Start a program
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c C:\dev\organize-me\run-claude-loop.bat`
6. Click **OK**

### Step 3: Monitor execution

Logs will be saved to `%APPDATA%\claude-sessions\logs\` and can be reviewed anytime:

```powershell
.\claude-control.ps1 -Action Logs
```

## Advanced Usage

### Custom log directory

```powershell
.\claude-loop.ps1 -Prompt "Task" -LogPath "D:\my-logs\claude"
```

### Programmatic status checking

Check the status file in PowerShell:

```powershell
$status = Get-Content "$env:APPDATA\claude-sessions\session_status.txt"
Write-Host $status
```

Possible values: `IDLE`, `RUNNING`, `WAITING_INPUT`, `FAILED`, `COMPLETED`

### Redirect to custom log file

```powershell
.\claude-loop.ps1 -Prompt "Task" 2>&1 | Tee-Object "my-log.txt"
```

## Files Created

```
%APPDATA%\claude-sessions\
├── session_status.txt              # Current status
├── logs/
│   ├── master.log                  # All iterations combined
│   ├── session_2026-07-08_140000_iter1.log
│   ├── session_2026-07-08_150000_iter2.log
│   └── ...
```

## Security Notes

- The script logs all Claude interactions (in plaintext) to disk
- Keep logs directory secure if sensitive data is involved
- Status file is world-readable by default (runs as current user)
- No credentials are stored in the script

## Support

If you encounter issues:

1. Check logs: `.\claude-control.ps1 -Action Logs`
2. Try a test run: `.\claude-loop.ps1 -Prompt "Test" -Iterations 1 -IntervalMinutes 0`
3. Check Claude CLI: `claude --version`
4. Review event logs in Windows Event Viewer

## License

This script is provided as-is for use with Claude Code.
