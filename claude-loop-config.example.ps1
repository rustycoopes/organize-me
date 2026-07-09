# Claude Loop Configuration Example
# Copy this file to claude-loop-config.ps1 and customize the values below

# ============================================================================
# MAIN CONFIGURATION
# ============================================================================

# The prompt Claude will execute in each iteration
# This should be a clear, actionable task that Claude can complete
$Prompt = @"
You are a scheduled automation task. Please:
1. Check for any critical issues or alerts
2. Summarize the current state
3. Recommend any immediate actions
4. Report back with findings

Keep your response concise and actionable.
"@

# Number of times the loop will execute
$Iterations = 5

# Wait time between iterations (in minutes)
$IntervalMinutes = 60

# Where to store logs
$LogPath = "$env:APPDATA\claude-sessions\logs"

# ============================================================================
# USAGE
# ============================================================================

# After configuring this file, run:
#
#   .\claude-loop.ps1 -Prompt $Prompt -Iterations $Iterations -IntervalMinutes $IntervalMinutes
#
# Or create a shortcut batch file (see SETUP.md) to run it with saved settings

# ============================================================================
# EXAMPLES
# ============================================================================

# Example 1: Quick test (5 minute intervals, 2 iterations)
# $Iterations = 2
# $IntervalMinutes = 5
# $Prompt = "Test prompt"

# Example 2: Overnight job (hourly checks for 12 hours)
# $Iterations = 12
# $IntervalMinutes = 60
# $Prompt = "Check system health and report any issues"

# Example 3: Monitoring task (every 30 minutes, all day)
# $Iterations = 48  # 24 hours / 30 min intervals
# $IntervalMinutes = 30
# $Prompt = "Monitor service status and alert on failures"
