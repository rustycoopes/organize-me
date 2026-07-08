# Claude Loop Setup - Complete Reference

## What's Been Created

A complete automated workflow system for running Claude sessions on schedule. Configured for the `/next-issue` skill by default.

### 📁 Files

```
C:\dev\organize-me\
├── claude-loop.ps1                  # Main loop script (primary)
├── claude-control.ps1               # Control panel & monitoring
├── run-next-issue-loop.bat          # Quick launcher for /next-issue
├── run-claude-loop.bat              # Generic launcher
├── claude-loop-config.example.ps1   # Config template
│
├── QUICK-START.md                   # ⭐ Start here (2 min read)
├── NEXT-ISSUE-LOOP-GUIDE.md         # Issue picking workflow
├── CLAUDE-LOOP-README.md            # Full reference & advanced
└── CLAUDE-LOOP-SETUP.md             # This file
```

## Which File to Use?

### 🎯 If you want to pick GitHub issues repeatedly:

```powershell
run-next-issue-loop.bat
# OR
.\claude-loop.ps1 -Prompt "/next-issue"
```

**See:** `NEXT-ISSUE-LOOP-GUIDE.md`

### 🎯 If you want to run a custom task repeatedly:

```powershell
.\claude-loop.ps1 -Prompt "Your task here"
```

**See:** `QUICK-START.md`

### 🎯 If you want to monitor a running session:

```powershell
.\claude-control.ps1 -Action Status
.\claude-control.ps1 -Action Logs
```

## File Purposes

| File | Purpose | When to Use |
|------|---------|------------|
| **claude-loop.ps1** | Core loop orchestrator | Always (via launchers) |
| **claude-control.ps1** | Status & log viewer | While script is running |
| **run-next-issue-loop.bat** | Quick `/next-issue` launcher | For GitHub issue picking |
| **run-claude-loop.bat** | Generic prompt launcher | For custom tasks |
| **claude-loop-config.example.ps1** | Configuration template | To set defaults |

## Default Behavior

✅ **Prompt:** `/next-issue` (pick from GitHub board)  
✅ **Iterations:** 5 (5 issues/tasks)  
✅ **Interval:** 60 minutes (1 hour between picks)  
✅ **Logging:** `%APPDATA%\claude-sessions\logs\`  
✅ **Remote Control:** Enabled via `/remote-control` skill  

## Starting Points

### Just Want to Try It?

```powershell
cd C:\dev\organize-me
run-next-issue-loop.bat
```

Picks 5 issues from your board, 1 hour apart.

### Want to Understand It First?

1. Read `QUICK-START.md` (2 minutes)
2. Read `NEXT-ISSUE-LOOP-GUIDE.md` (5 minutes)
3. Try it: `run-next-issue-loop.bat`

### Want Full Details?

Read `CLAUDE-LOOP-README.md` (15 minutes) for:
- All parameters and options
- Advanced usage
- Troubleshooting
- Task Scheduler setup
- Security notes

## Core Concepts

### The Loop

```
Iteration 1: Run Claude with prompt → Log output → Wait 1 hour
Iteration 2: Run Claude with prompt → Log output → Wait 1 hour
Iteration 3: Run Claude with prompt → Log output → Wait 1 hour
...
Iteration 5: Run Claude with prompt → Log output → Done
```

### Single Session Control

- Checks if Claude is already running
- Won't start a new session if one is active
- Waits (up to 30 minutes) for previous session to finish
- Prevents duplicate runs

### Remote Control

During any iteration, you can:

```powershell
claude
# Use /remote-control inside Claude to:
#   - Pause the main session
#   - Send feedback or corrections
#   - Change direction
#   - Resume the main session
```

### Logging

Everything is saved:
- **Console** — real-time as it runs
- **Master log** — `%APPDATA%\claude-sessions\logs\master.log`
- **Session logs** — individual file per iteration

View anytime:
```powershell
.\claude-control.ps1 -Action Logs
```

## Quick Reference

| Task | Command |
|------|---------|
| Pick 5 issues (hourly) | `run-next-issue-loop.bat` |
| Pick issues (custom) | `.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 10 -IntervalMinutes 30` |
| Run custom task | `.\claude-loop.ps1 -Prompt "Your task"` |
| Check status | `.\claude-control.ps1 -Action Status` |
| View logs | `.\claude-control.ps1 -Action Logs` |
| Open full log | `.\claude-control.ps1 -Action ViewLog` |

## Configuration

All scripts support parameters:

```powershell
.\claude-loop.ps1 `
  -Prompt "Your prompt or /skill" `
  -Iterations 5 `
  -IntervalMinutes 60 `
  -LogPath "C:\my-logs"
```

Or edit the batch files:
- `run-next-issue-loop.bat` — for /next-issue workflow
- `run-claude-loop.bat` — for generic tasks

## Architecture

```
┌─────────────────────────────────────────┐
│     User runs batch file or PS           │
│     (run-next-issue-loop.bat)            │
└──────────────┬──────────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │  claude-loop.ps1     │
    │                      │
    │  • Check if Claude   │
    │    is running        │
    │  • Start Claude CLI  │
    │    with prompt       │
    │  • Log output        │
    │  • Wait 1 hour       │
    │  • Repeat 5 times    │
    └──────────────────────┘
               │
        ┌──────┼──────┐
        │      │      │
        ▼      ▼      ▼
      CONSOLE LOG    STATUS FILE
                    (\claude_status.txt)
               │
               ▼
    ┌──────────────────────┐
    │  claude-control.ps1  │
    │  (separate terminal) │
    │                      │
    │  • Check status      │
    │  • View logs         │
    │  • Monitor progress  │
    └──────────────────────┘
```

## Testing

### Quick Test (No Waiting)

```powershell
.\claude-loop.ps1 -Prompt "Test" -Iterations 1 -IntervalMinutes 0
```

Runs one iteration, no wait. Should complete in ~10-30 seconds.

### Test with Delays

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 2 -IntervalMinutes 1
```

Runs 2 iterations, waits 1 minute between them. Good for quick testing.

## Common Workflows

### Workflow 1: Daily Issue Processing

Schedule this to run every morning at 9 AM:

```batch
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 8 -IntervalMinutes 60
```

Processes 8 issues, 1 per hour, takes 7-8 hours. Start at 9 AM, done by 4-5 PM.

### Workflow 2: Quick Sprint

```batch
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 3 -IntervalMinutes 0
```

Pick 3 issues immediately, one after another. Good for focused work.

### Workflow 3: Overnight Processing

```batch
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 12 -IntervalMinutes 30
```

Pick 12 issues every 30 minutes. Runs 6 hours overnight.

### Workflow 4: Custom Analysis

```batch
.\claude-loop.ps1 `
  -Prompt "Analyze recent commits and summarize changes" `
  -Iterations 5 `
  -IntervalMinutes 120
```

Custom task, every 2 hours, 5 times.

## Next Steps

1. **Read** `QUICK-START.md` (this takes 2 minutes)
2. **Run** `run-next-issue-loop.bat` (watch one iteration)
3. **Check logs** with `.\claude-control.ps1 -Action Logs`
4. **Adjust settings** for your workflow
5. **Schedule** (optional) with Windows Task Scheduler

## Troubleshooting Entry Points

- **General issues** → See `CLAUDE-LOOP-README.md` → Troubleshooting
- **Issue picking** → See `NEXT-ISSUE-LOOP-GUIDE.md` → Troubleshooting
- **Quick problems** → See `QUICK-START.md` → Troubleshooting

## Files You'll Interact With

### Most Common
- `run-next-issue-loop.bat` — Double-click to run
- `.\claude-control.ps1` — Check status/logs

### Customize If Needed
- `run-next-issue-loop.bat` — Edit the PROMPT/ITERATIONS/INTERVAL_MINUTES section
- `run-claude-loop.bat` — Same for custom tasks

### Read for Reference
- `QUICK-START.md` — Fast overview
- `NEXT-ISSUE-LOOP-GUIDE.md` — Issue workflow details
- `CLAUDE-LOOP-README.md` — Complete reference

## Support Commands

```powershell
# Check Claude is installed
claude --version

# Test simple Claude execution
claude "Hello"

# Check current status
.\claude-control.ps1 -Action Status

# View recent logs
.\claude-control.ps1 -Action Logs

# Kill any hanging Claude process
Get-Process claude | Stop-Process -Force
```

---

## Start Here 👇

**New to this?** Read `QUICK-START.md` (2 min) then run:
```powershell
run-next-issue-loop.bat
```

**Questions?** See the appropriate guide above or check logs with:
```powershell
.\claude-control.ps1 -Action ViewLog
```

**Ready to schedule?** See `CLAUDE-LOOP-README.md` → "Windows Task Scheduler Integration"
