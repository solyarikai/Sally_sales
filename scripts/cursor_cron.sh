#!/bin/bash
# Cron-compatible script to invoke Cursor CLI for one task iteration
# Handles Opus 4.5 thinking timeouts with auto-recovery
# Add to crontab: */5 * * * * /home/leadokol/magnum-opus-project/repo/scripts/cursor_cron.sh

WORKSPACE="/home/leadokol/magnum-opus-project/repo"
STATE_DIR="$WORKSPACE/state"
TASKS_FILE="$STATE_DIR/tasks.md"
CONTEXT_FILE="$STATE_DIR/session_context.json"
LOG_FILE="$STATE_DIR/cursor_cron.log"
LOCK_FILE="/tmp/cursor_cron.lock"
TIMEOUT_FILE="$STATE_DIR/timeout_history.json"
TIMEOUT_MINUTES=15  # If session active for longer, consider it timed out
CURSOR_TIMEOUT=900  # 15 minutes for cursor-agent (Opus 4.5 needs more time)

# Prevent overlapping runs
LOCK_TIMEOUT_MINUTES=20  # Kill stale lock after 20 minutes
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        # Check if it's been running too long (possible timeout)
        lock_age_minutes=$(( ($(date +%s) - $(stat -c %Y "$LOCK_FILE")) / 60 ))
        if [ "$lock_age_minutes" -gt "$LOCK_TIMEOUT_MINUTES" ]; then
            echo "[$(date)] Stale lock detected (${lock_age_minutes}min old). Killing PID $pid" >> "$LOG_FILE"
            kill -9 "$pid" 2>/dev/null
            rm -f "$LOCK_FILE"
        else
            echo "[$(date)] Previous run still active (PID $pid, ${lock_age_minutes}min), skipping" >> "$LOG_FILE"
            exit 0
        fi
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_and_recover_timeout() {
    # Check if previous session timed out
    if [ ! -f "$CONTEXT_FILE" ]; then
        return 0
    fi
    
    local status=$(jq -r '.status // "unknown"' "$CONTEXT_FILE" 2>/dev/null)
    local last_updated=$(jq -r '.last_updated // ""' "$CONTEXT_FILE" 2>/dev/null)
    
    if [ "$status" = "active" ] && [ -n "$last_updated" ]; then
        local last_ts=$(date -d "$last_updated" +%s 2>/dev/null || echo 0)
        local now_ts=$(date +%s)
        local diff_minutes=$(( (now_ts - last_ts) / 60 ))
        
        if [ "$diff_minutes" -gt "$TIMEOUT_MINUTES" ]; then
            log "TIMEOUT DETECTED: Session was active for ${diff_minutes} minutes"
            
            local task_name=$(jq -r '.current_task.name // "unknown"' "$CONTEXT_FILE")
            local subtask=$(jq -r '.current_task.current_subtask // "unknown"' "$CONTEXT_FILE")
            
            # Log timeout for tracking
            local timeout_entry="{\"timestamp\":\"$(date -Iseconds)\",\"task\":\"$task_name\",\"subtask\":\"$subtask\",\"duration_minutes\":$diff_minutes}"
            
            if [ -f "$TIMEOUT_FILE" ]; then
                jq ". + [$timeout_entry]" "$TIMEOUT_FILE" > "${TIMEOUT_FILE}.tmp" && mv "${TIMEOUT_FILE}.tmp" "$TIMEOUT_FILE"
            else
                echo "[$timeout_entry]" > "$TIMEOUT_FILE"
            fi
            
            # Mark session as recovered
            jq '.status = "recovered_from_timeout" | .recovery_timestamp = "'"$(date -Iseconds)"'"' "$CONTEXT_FILE" > "${CONTEXT_FILE}.tmp" && mv "${CONTEXT_FILE}.tmp" "$CONTEXT_FILE"
            
            log "Logged timeout and marked for recovery. Will continue same task."
            return 1  # Indicates timeout was detected
        fi
    fi
    return 0
}

get_first_pending_task() {
    local task_name=""
    local subtask=""
    local in_task=false
    local task_header=""
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^###[[:space:]]Task[[:space:]]([0-9]+):[[:space:]](.+) ]]; then
            if [[ ! "$line" =~ "✅ COMPLETE" && ! "$line" =~ "COMPLETE" ]]; then
                task_header="$line"
                in_task=true
            else
                in_task=false
            fi
        fi
        
        if $in_task && [[ "$line" =~ ^-[[:space:]]\[[[:space:]]\][[:space:]](.+) ]]; then
            subtask="${BASH_REMATCH[1]}"
            task_name=$(echo "$task_header" | sed 's/^### //')
            echo "$task_name|||$subtask"
            return 0
        fi
    done < "$TASKS_FILE"
    
    echo ""
    return 1
}

log "=== Cron job started ==="

# Check for timeout recovery
check_and_recover_timeout
timeout_recovered=$?

result=$(get_first_pending_task)

if [ -z "$result" ]; then
    log "All tasks complete!"
    exit 0
fi

task_name=$(echo "$result" | cut -d'|' -f1-3 | sed 's/|||.*//')
subtask=$(echo "$result" | sed 's/.*|||//')

log "Task: $task_name"
log "Subtask: $subtask"

# Update session context
session_id=$(jq -r '.session_id // 0' "$CONTEXT_FILE" 2>/dev/null || echo "0")
session_id=$((session_id + 1))

cat > "$CONTEXT_FILE" << EOF
{
  "session_id": $session_id,
  "started_at": "$(date -Iseconds)",
  "last_updated": "$(date -Iseconds)",
  "status": "active",
  "current_task": {
    "name": "$task_name",
    "current_subtask": "$subtask"
  },
  "auto_continue": true,
  "recovery_notes": "Auto-continue session. Working on: $task_name - $subtask"
}
EOF

# Build the prompt with timeout recovery context if applicable
TIMEOUT_CONTEXT=""
if [ "$timeout_recovered" -eq 1 ]; then
    TIMEOUT_CONTEXT="
TIMEOUT RECOVERY: Previous session timed out (Opus 4.5 thinking limit).
- Check state/response.txt for partial progress
- Check git diff to see what code was already changed
- DO NOT repeat work already done - continue from where it stopped
- Update session_context.json status to 'active' when starting
"
fi

PROMPT="Continue working on the project.

CURRENT TASK: $task_name
CURRENT SUBTASK: $subtask
$TIMEOUT_CONTEXT
CONTEXT:
1. Read state/session_context.json for previous session state
2. Read state/tasks.md for full task list  
3. Check state/response.txt for what was done last
4. Check state/blocker.txt for any blockers
5. If recovering from timeout, run 'git diff' to see uncommitted changes

INSTRUCTIONS:
1. Complete the current subtask: \"$subtask\"
2. Mark it done in tasks.md when complete
3. Update session_context.json with progress (status='active' while working, 'completed' when done)
4. Write summary to state/response.txt
5. If blocked, write to state/blocker.txt
6. If subtask complete, move to next subtask
7. Rebuild Docker if code changed: docker-compose down && docker-compose up -d --build
8. ALWAYS update session_context.json last_updated timestamp before finishing

SAFETY: Never send messages via Smartlead API. Read-only!"

cd "$WORKSPACE"

# Run cursor-agent CLI with timeout
log "Invoking cursor-agent (timeout: ${CURSOR_TIMEOUT}s / $((CURSOR_TIMEOUT/60)) minutes)..."
timeout $CURSOR_TIMEOUT ~/.local/bin/cursor-agent -p "$PROMPT" 2>&1 >> "$LOG_FILE"
exit_code=$?

if [ "$exit_code" -eq 124 ]; then
    log "WARNING: cursor-agent timed out after $((CURSOR_TIMEOUT/60)) minutes"
    # Mark session for timeout recovery
    jq '.status = "timed_out" | .timeout_at = "'"$(date -Iseconds)"'"' "$CONTEXT_FILE" > "${CONTEXT_FILE}.tmp" && mv "${CONTEXT_FILE}.tmp" "$CONTEXT_FILE"
elif [ "$exit_code" -ne 0 ]; then
    log "ERROR: cursor-agent exited with code $exit_code"
else
    log "cursor-agent completed successfully"
fi

log "=== Cron job finished (exit: $exit_code) ==="
