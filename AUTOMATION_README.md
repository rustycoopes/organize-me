# Automated Sequential Issue Implementation

Orchestrate implementing multiple GitHub issues sequentially with fresh Claude Code sessions. Each session is fully interactive—you can respond to Claude, run additional skills, enable remote control, and work naturally.

## How It Works

1. **Spawn interactive Claude session** for each issue
2. **You work through it naturally** — respond to questions, run skills, enable features
3. **Script monitors GitHub** for issue closure
4. **Moves to next issue** once closed
5. **Fresh context** each time (new session = clean window)

## Prerequisites

- Claude Code installed with `claude` CLI available in PATH
- GitHub CLI (`gh`) installed and authenticated
- Python 3.7+ (for the Python script) OR PowerShell (for PS script)
- Appropriate GitHub permissions to view/manage issues

## Usage

### Option 1: Python Script (Recommended)

#### Using command-line arguments:
```bash
python automate_implementation.py --issues 123 124 125
```

#### Using config file:
```bash
python automate_implementation.py issues_config.json
```

#### With options:
```bash
# Enable auto mode
python automate_implementation.py --issues 123 124 --auto

# Different repository
python automate_implementation.py --issues 123 124 --repo event-creator

# Don't wait for closure (move to next immediately)
python automate_implementation.py --issues 123 124 --skip-wait

# Combine flags
python automate_implementation.py --issues 123 124 --auto --skip-wait
```

### Option 2: PowerShell Script

#### Using command-line arguments:
```powershell
.\automate_implementation.ps1 -IssueNumbers 123, 124, 125
```

#### Using config file:
```powershell
.\automate_implementation.ps1 -ConfigPath issues_config.json
```

#### With options:
```powershell
# Enable auto mode
.\automate_implementation.ps1 -IssueNumbers 123, 124 -Auto

# Different repository
.\automate_implementation.ps1 -IssueNumbers 123, 124 -Repo event-creator

# Don't wait for closure
.\automate_implementation.ps1 -IssueNumbers 123, 124 -SkipWait

# Combine flags
.\automate_implementation.ps1 -IssueNumbers 123, 124 -Auto -SkipWait
```

## Config File Format

Create a JSON file with your issue list:

```json
{
  "issues": [
    123,
    124,
    125
  ]
}
```

See `issues_config.json` for a template.

## What Happens in Each Session

For each issue, a new interactive Claude session opens with `/to-implementation <issue-number>` called automatically. You can:

- **Answer questions** Claude asks about requirements or decisions
- **Run additional skills** — e.g., `/grilling`, `/debug`, `/verify`
- **Enable features** — e.g., enable remote control, enable vision
- **Provide input** — review code, approve changes, etc.
- **Close when done** — exit the Claude session normally (ctrl+d, exit, etc.)

The script then:
1. Detects the session closed
2. Polls GitHub to verify the issue is closed
3. Moves to the next issue

## Monitoring & Polling

After you close a Claude session, the script waits up to **120 minutes** for GitHub to show the issue as closed.

If an issue isn't closed by the timeout:
- The script warns you and continues to the next issue
- You can verify closure manually and move forward

Use `--skip-wait` to disable this polling entirely (move to next issue immediately).

## Tips & Tricks

### Batch Multiple Lists

Process different issue batches by running the script multiple times:

```bash
python automate_implementation.py --issues 1 2 3
# ... complete those ...
python automate_implementation.py --issues 4 5 6
```

### Monitor Progress

The script logs:
- Each issue start time
- Session exit status
- GitHub closure checks
- Overall completion summary

Use this to track progress and identify bottlenecks.

### Interrupt Gracefully

Press **Ctrl+C** while the script is waiting for closure, or close the Claude session normally—the script will catch the interrupt and show a summary.

### Remote Control

During each Claude session, you can enable remote control:
- Say `enable remote control` or run `/remote`
- Script continues running; you can pair with teammates
- Close the session when done—script detects it and continues

### Inspect GitHub Status Manually

Check issue status directly:

```bash
gh issue view 123
```

## Troubleshooting

### "Claude CLI not found"

Make sure Claude Code is installed and the `claude` command is in your PATH.

Test with:
```bash
claude --version
```

### "Could not check issue status"

Ensure `gh` CLI is authenticated:
```bash
gh auth status
```

### Issue didn't close after 120 minutes

The script will warn and continue. Options:
- Use `--skip-wait` to disable polling altogether
- Manually verify the issue is closed and restart from the next issue
- Check GitHub directly to see what's blocking closure

### Session exits unexpectedly

If a Claude session crashes or closes unexpectedly:
- Python script logs the exit code
- PowerShell script shows the error
- The issue is marked as "failed" in the summary
- Script continues to the next issue

You can re-run the failed issue manually or restart with `--issues <number>`.

## Performance Notes

- **Network latency**: GitHub polling every 15 seconds is fairly conservative; adjust in the script if needed
- **Context freshness**: Each new session starts clean—no accumulated context from prior issues
- **Session startup**: First Claude session takes ~2-3s; subsequent sessions are similar
- **Typical flow**: ~5-10 minutes per issue (depends on implementation complexity)

## Examples

### Quick batch with auto mode:
```bash
python automate_implementation.py --issues 100 101 102 --auto
```

### PowerShell with auto mode:
```powershell
.\automate_implementation.ps1 -IssueNumbers 100, 101, 102 -Auto
```

### Slice-based workflow (Slice 2 issues):
```bash
python automate_implementation.py --issues 45 46 47 48 --auto
```

### One-off implementation with auto mode and no polling:
```bash
python automate_implementation.py --issues 200 --auto --skip-wait
```

### Use config file for repeatable batches:
Save issue lists to `slice1_issues.json`, `slice2_issues.json`, etc.
```bash
python automate_implementation.py slice1_issues.json --auto
python automate_implementation.py slice2_issues.json --auto
```

## Implementation Details

- **Python script**: Uses `subprocess` for session spawning, `gh` API for status checks, JSON for config
- **PowerShell script**: Uses `Start-Process` for session spawning, equivalent GitHub checks
- **Both**: Poll GitHub every 15 seconds, timeout after 120 minutes (configurable in code)
- **Interactivity**: Sessions run with full TTY—no output capture; you interact directly

## Editing the Scripts

Both scripts are self-contained and well-commented. Customize:
- **Poll interval**: Change `check_interval = 15` (seconds)
- **Timeout**: Change `timeout_minutes=120` parameter
- **Repository**: Default is `organize-me`; override with `--repo` flag
- **Session launch**: Modify the `claude` command (e.g., add flags)

---

**Created for**: Sequential batched issue implementation with fresh context and full interactivity.
