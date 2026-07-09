# Claude Loop - Quick Start Guide

## What You've Got

Four files to automate Claude sessions on a schedule:

| File | Purpose |
|------|---------|
| **claude-loop.ps1** | Main loop script (5 iterations, 1 hour apart) |
| **claude-control.ps1** | Control panel - check status, view logs, interact |
| **run-claude-loop.bat** | Easy launcher (double-click to run) |
| **CLAUDE-LOOP-README.md** | Full documentation |

## 30-Second Start

### Option 1: Pick Next Issue from Board (Recommended)

```powershell
cd C:\dev\organize-me
run-next-issue-loop.bat
```

OR from PowerShell:

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 5 -IntervalMinutes 60
```

→ See **NEXT-ISSUE-LOOP-GUIDE.md** for details

### Option 2: Custom Task (Command Line)

```powershell
cd C:\dev\organize-me
.\claude-loop.ps1 -Prompt "Your task here"
```

That's it. Ctrl+C to stop.

### Option 3: Batch File (Double-Click)

1. Edit `run-claude-loop.bat` — change the `PROMPT` line to your task
2. Double-click `run-claude-loop.bat` 
3. PowerShell window opens and runs your loop
4. Close window when done

### Option 4: Scheduled Task (Automated)

See **CLAUDE-LOOP-README.md** → "Windows Task Scheduler Integration"

## How It Works

```
Loop 5 times:
  1. Check if Claude is already running
  2. Start Claude with your prompt
  3. Show output in console AND save to log file
  4. Wait 1 hour
  5. Repeat
```

## While It's Running

### Check Status (New PowerShell Window)

```powershell
cd C:\dev\organize-me
.\claude-control.ps1 -Action Status
```

Shows: Current iteration, whether Claude is running, recent logs

### Interact with Running Session

During any iteration, you can open a new terminal and type:

```powershell
claude
```

Use `/remote-control` inside Claude to pause the main session and send feedback. When done, the main loop resumes automatically.

### View Logs

```powershell
# Last 20 lines
.\claude-control.ps1 -Action Logs

# Open in text editor
.\claude-control.ps1 -Action ViewLog
```

## Common Examples

### Quick Test (2 minutes, 2 iterations)

```powershell
.\claude-loop.ps1 -Prompt "Test" -Iterations 2 -IntervalMinutes 1
```

### Hourly Monitoring (24 hours)

```powershell
.\claude-loop.ps1 `
  -Prompt "Check system status and report issues" `
  -Iterations 24 `
  -IntervalMinutes 60
```

### Every 30 Minutes (All Day)

```powershell
.\claude-loop.ps1 `
  -Prompt "Analyze metrics and summarize" `
  -Iterations 48 `
  -IntervalMinutes 30
```

## Key Features

✅ **Single session control** — Never runs Claude twice at once  
✅ **Logging** — Everything saved to `%APPDATA%\claude-sessions\logs\`  
✅ **Remote control** — Pause and interact via `/remote-control`  
✅ **Real-time console** — See output as it happens  
✅ **Status monitoring** — Check progress anytime  
✅ **Error handling** — Graceful recovery from failures  

## Troubleshooting

**"Claude not found"**
- Ensure Claude CLI is installed: `claude --version`

**"Script says it's waiting forever"**
- Previous Claude session didn't finish
- Use Task Manager to kill `claude.exe`
- Restart the script

**"Want to stop the loop"**
- Press Ctrl+C in the PowerShell window

## Next Steps

1. **Edit your prompt** in the command or `run-claude-loop.bat`
2. **Run** it and watch the first iteration
3. **Check logs** with `.\claude-control.ps1 -Action Logs`
4. **Use /remote-control** to interact during a session (optional)
5. **Schedule it** with Task Scheduler if you want it to run automatically

## Full Documentation

See **CLAUDE-LOOP-README.md** for:
- Complete parameter reference
- Advanced usage
- Task Scheduler setup
- Troubleshooting details
- Security notes

---

**Questions?** Check CLAUDE-LOOP-README.md for answers.
