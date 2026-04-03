#!/bin/bash
# Continuous Cursor Runner with Anti-Loop Protection
# Auto git commit/push via script (not AI)

WORKSPACE="/home/leadokol/magnum-opus-project/repo"
STATE_DIR="$WORKSPACE/state"
TASKS_FILE="$STATE_DIR/tasks.md"
LOG_FILE="$STATE_DIR/continuous_runner.log"
LOCK_FILE="/tmp/continuous_runner.lock"
LAST_TASK_FILE="/tmp/last_completed_task.txt"
CURSOR_TIMEOUT=300
LOOP_INTERVAL=15
TG_TOKEN="8543996153:AAHnqBM52tK2zUUMUEM4fLUA4tozufXoOss"
TG_CHAT="57344339"

# Single instance check
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "Already running (PID $pid)"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify() {
    # Only send notification if message is different from last one
    local msg="$1"
    local last_msg_file="/tmp/last_tg_msg.txt"
    local last_msg=""
    [ -f "$last_msg_file" ] && last_msg=$(cat "$last_msg_file")
    
    if [ "$msg" != "$last_msg" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
            -d "chat_id=$TG_CHAT" -d "text=$msg" > /dev/null 2>&1
        echo "$msg" > "$last_msg_file"
    fi
}

get_first_pending_task() {
    local in_task=false
    local task_header=""
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^###[[:space:]]Task[[:space:]]([0-9]+):[[:space:]](.+) ]]; then
            if [[ ! "$line" =~ "✅" && ! "$line" =~ "COMPLETE" ]]; then
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

mark_subtask_done() {
    local subtask="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M')
    
    # Use Python for reliable text replacement
    python3 << PYTHON
import re
with open('$TASKS_FILE', 'r') as f:
    content = f.read()
# Escape special regex characters in subtask
escaped = re.escape("""$subtask""")
# Replace unchecked with checked
pattern = r'- \[ \] ' + escaped
replacement = '- [x] $subtask (done $timestamp)'
new_content = re.sub(pattern, replacement, content, count=1)
if new_content != content:
    with open('$TASKS_FILE', 'w') as f:
        f.write(new_content)
    print('Marked done successfully')
else:
    print('WARNING: Pattern not found, task may already be done')
PYTHON
    log "Marked done: $subtask"
}

git_commit_push() {
    local msg="$1"
    cd "$WORKSPACE"
    
    if git diff --quiet && git diff --cached --quiet; then
        log "No git changes to commit"
        return 0
    fi
    
    local changed=$(git status --porcelain | wc -l)
    log "Git: $changed files changed"
    
    git add -A
    git commit -m "$msg

Auto-committed at $(date '+%Y-%m-%d %H:%M')" 2>&1 | tail -3 >> "$LOG_FILE"
    
    git push origin replies310126 2>&1 | tail -2 >> "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        log "Git: committed and pushed"
        # Only notify for commits, not for every task start
        notify "📦 Committed: $msg ($changed files)"
    else
        log "Git: push failed"
    fi
}

log "=== Continuous Runner Started (PID $$) ==="

while true; do
    # Check if cursor-agent is already running
    if pgrep -f 'cursor-agent.*-p' > /dev/null; then
        sleep 10
        continue
    fi
    
    result=$(get_first_pending_task)
    
    if [ -z "$result" ]; then
        log "All tasks complete! Sleeping 120s..."
        sleep 60
        continue
    fi
    
    task_name=$(echo "$result" | sed 's/|||.*//')
    subtask=$(echo "$result" | sed 's/.*|||//')
    
    # Anti-loop: Check if this is the same task we just completed
    last_task=""
    [ -f "$LAST_TASK_FILE" ] && last_task=$(cat "$LAST_TASK_FILE")
    
    if [ "$subtask" = "$last_task" ]; then
        log "WARNING: Same task detected, possible loop. Skipping and marking done."
        mark_subtask_done "$subtask"
        sleep 5
        continue
    fi
    
    log "Starting: $subtask"
    # Don't spam TG for every task start - only notify on completion
    
    start_time=$(date +%s)
    cd "$WORKSPACE"
    
    PROMPT="You are autocoding on Hetzner. Complete ONE subtask then stop.

SUBTASK: $subtask

RULES:
1. Complete ONLY this subtask
2. Make code changes if needed
3. Write summary to state/response.txt
4. DO NOT mark tasks done - script handles it
5. DO NOT commit/push - script handles it
6. NEVER send Smartlead messages!"

    timeout $CURSOR_TIMEOUT ~/.local/bin/cursor-agent -p "$PROMPT" 2>&1 | tee -a "$LOG_FILE"
    exit_code=$?
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    # Save last completed task to prevent loops
    echo "$subtask" > "$LAST_TASK_FILE"
    
    if [ "$exit_code" -eq 124 ]; then
        log "TIMEOUT after $((CURSOR_TIMEOUT/60)) minutes"
    elif [ "$exit_code" -ne 0 ]; then
        log "ERROR: exit code $exit_code"
    else
        log "COMPLETED in ${duration}s"
        mark_subtask_done "$subtask"
        git_commit_push "Completed: $subtask"
        notify "✅ Done: $subtask (${duration}s)"
    fi
    
    log "Waiting ${LOOP_INTERVAL}s..."
    sleep $LOOP_INTERVAL
done
