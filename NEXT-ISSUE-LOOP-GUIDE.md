# Claude Loop: Issue Picking Workflow

Run the `/next-issue` skill repeatedly to work through your GitHub project board systematically.

## What It Does

Each iteration:
1. **Picks the highest-priority issue** from the OrganizeMe project board
2. **Explains why it chose that issue** (slice number, urgency, dependencies)
3. **Starts implementation** or analysis of the chosen issue
4. **Reports status** - what was done, what's next
5. **Waits 1 hour** before picking the next issue

After 5 iterations (or your custom count), you'll have worked through 5 issues with clear progress tracking.

## Quick Start

### Simplest Way: Double-Click

```
run-next-issue-loop.bat
```

That's it. No configuration needed. Uses defaults: 5 issues, 1-hour intervals.

### Command Line

```powershell
cd C:\dev\organize-me
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 5 -IntervalMinutes 60
```

### Quick Test (2 issues, 1 minute apart)

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 2 -IntervalMinutes 1
```

## What You'll See

### Console Output

```
[2026-07-08 14:00:00] [INFO] Status: RUNNING (Iteration 1/5)
[2026-07-08 14:00:00] [INFO] ========================================
[2026-07-08 14:00:00] [INFO] Starting Claude Session #1
[2026-07-08 14:00:00] [INFO] Prompt: /next-issue
[2026-07-08 14:00:00] [INFO] ========================================

> Running /next-issue skill...

Selected: Issue #87 - "Implement email notification system"
Reason: Slice 7.1 feature, depends on issue #86 (completed)
Status: Starting implementation...

[Implementation details and progress...]

[2026-07-08 14:05:30] [INFO] Session completed successfully
[2026-07-08 14:05:30] [INFO] Waiting 60 minutes until next iteration...
```

### Logs

All output saved to:
```
%APPDATA%\claude-sessions\logs\master.log
%APPDATA%\claude-sessions\logs\session_2026-07-08_140000_iter1.log
%APPDATA%\claude-sessions\logs\session_2026-07-08_150000_iter2.log
...
```

View with:
```powershell
.\claude-control.ps1 -Action ViewLog
```

## Common Scenarios

### Scenario 1: Work Through Issues During Your Workday

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 3 -IntervalMinutes 30
```

Picks 3 issues, one every 30 minutes. Check progress between picks.

### Scenario 2: Overnight Issue Processing

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 8 -IntervalMinutes 60
```

8 issues × 1 hour = 8 hours of issue picking and work. Start at 5 PM, done by 1 AM.

### Scenario 3: Focused Sprint (No Waiting)

```powershell
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 5 -IntervalMinutes 0
```

Picks 5 issues back-to-back with no waiting. Good for intensive work sessions.

### Scenario 4: Scheduled Daily (via Task Scheduler)

Edit `run-next-issue-loop.bat` to set 5 issues, then schedule it to run at 9 AM daily.

## How to Interact

### While It's Running

Open a new PowerShell window:

```powershell
# Check current status
.\claude-control.ps1 -Action Status

# View recent logs
.\claude-control.ps1 -Action Logs -Lines 50
```

### Pause Between Picks

During the 1-hour wait, you can:
- Press Ctrl+C to stop (and restart later)
- Open another Claude session: `claude`
- Use `/remote-control` to interact with the running session
- Check the logs to review what was done

### Resume Later

If you press Ctrl+C:
1. The script stops
2. Logs are saved
3. You can run the script again to continue
4. It will pick where it left off in the iteration count

## Customization

### Change Issue Selection Logic

If you want Claude to use a different issue-picking strategy, modify the prompt:

```powershell
$prompt = "/next-issue --priority critical-only"
.\claude-loop.ps1 -Prompt $prompt -Iterations 5
```

Or provide your own strategy:

```powershell
$prompt = @"
Pick the highest-priority issue from the OrganizeMe GitHub board.
Focus on: backend issues first, then frontend, then docs.
Report: issue number, title, why chosen, estimated effort.
"@

.\claude-loop.ps1 -Prompt $prompt -Iterations 5
```

### Different Wait Times

```powershell
# Pick one every 30 minutes
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 10 -IntervalMinutes 30

# Pick one every 2 hours
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 4 -IntervalMinutes 120

# No wait - continuous
.\claude-loop.ps1 -Prompt "/next-issue" -Iterations 5 -IntervalMinutes 0
```

## Understanding `/next-issue`

The `/next-issue` skill:
- Reads your OrganizeMe GitHub project board
- Identifies all issues in the "Todo" column
- Applies project priorities (Slice numbers, dependencies)
- Selects the single highest-priority issue
- Explains the choice
- Kicks off implementation or analysis

Output typically includes:
- **Issue #** and title
- **Why selected** (priority reasoning)
- **What it does** (feature/bug/refactor)
- **Estimated effort**
- **Next steps** or kickoff of work

## Monitoring Progress

### After Each Iteration

Check the logs:
```powershell
.\claude-control.ps1 -Action Logs
```

### After All Iterations

Review full work session:
```powershell
.\claude-control.ps1 -Action ViewLog
```

Look for:
- Which issues were selected and why
- How much work was done per issue
- Any blockers or dependencies identified
- Status at completion

## Troubleshooting

### "/next-issue not recognized"

**Problem:** Claude doesn't understand `/next-issue`

**Solution:** 
- Ensure the skill is available in your Claude Code installation
- Try running `/next-issue` manually first: `claude /next-issue`
- Check that you're in the right project directory
- Verify GitHub access (for reading the project board)

### GitHub access issues

**Problem:** Claude can't read the project board

**Solution:**
- Ensure you're logged into your GitHub account
- Check that OrganizeMe repo is accessible
- Verify the GitHub project board exists and has issues

### Want to stop and resume later

```powershell
# Press Ctrl+C in the script window (stops after current iteration)
# Your logs are saved
# Run again later - it will continue from where iteration left off
```

### Issues aren't being picked as expected

**Possible causes:**
- All issues are already assigned or in progress
- No issues in "Todo" column
- Different priority rules than expected

**Solution:**
- Check the board manually: `gh project view --web`
- Review logs to see what Claude is seeing: `.\claude-control.ps1 -Action Logs`
- Clarify issue selection criteria if needed

## Integration with Workflow

### Before You Run

1. Ensure your GitHub project board is updated
2. Review the Todo column - make sure issues are in the right state
3. Verify GitHub credentials are active

### While It Runs

1. Monitor logs periodically
2. Note any blockers Claude identifies
3. Be available if `/remote-control` interaction needed

### After It Completes

1. Review what was done: `.\claude-control.ps1 -Action ViewLog`
2. Check which issues advanced
3. Update the board manually if needed
4. Plan next session based on progress

## Example Full Session

```
Iteration 1 (14:00):
  Selected: Issue #92 - "Add email template customization"
  Action: Started implementation, created PR draft
  
[Wait 1 hour]

Iteration 2 (15:00):
  Selected: Issue #88 - "Fix search highlighting on mobile"
  Action: Identified bug in CSS media query, proposed fix
  
[Wait 1 hour]

Iteration 3 (16:00):
  Selected: Issue #95 - "Update security dependencies"
  Action: Ran audit, identified 2 critical packages, created updates
  
[Completed - 3 issues processed in 2 hours]
```

## Next Steps

1. Run the quick start: `run-next-issue-loop.bat`
2. Watch the first iteration complete
3. Check logs: `.\claude-control.ps1 -Action ViewLog`
4. Adjust settings (iterations, wait times) for your workflow
5. Consider scheduling with Task Scheduler for daily runs

---

See **CLAUDE-LOOP-README.md** for advanced topics and full reference.
