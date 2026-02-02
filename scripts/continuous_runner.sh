#!/bin/bash
# Continuous Cursor Runner with Auto Git Commit/Push
# Follows architecture.md principles

WORKSPACE="/home/leadokol/magnum-opus-project/repo"
STATE_DIR="$WORKSPACE/state"
TASKS_FILE="$STATE_DIR/tasks.md"
LOG_FILE="$STATE_DIR/continuous_runner.log"
LOCK_FILE="/tmp/continuous_runner.lock"
GIT_SCRIPT="/home/leadokol/scripts/utils/git_commit_push.sh"
CURSOR_TIMEOUT=600  # 10 minutes per task
LOOP_INTERVAL=30    # seconds between tasks
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
    curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
        -d "chat_id=$TG_CHAT" -d "text=$1" > /dev/null 2>&1
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
    # Escape special regex characters
    local escaped_subtask=$(echo "$subtask" | sed 's/[[\\.\*\^\{}|+?]/\\&/g')
    # Mark the subtask as done
    sed -i "s/- \[ \] $escaped_subtask/- [x] $subtask (done $(date '+%Y-%m-%d %H:%M'))/" "$TASKS_FILE"
    log "Marked done: $subtask"
}

git_commit_push() {
    local msg="$1"
    cd "$WORKSPACE"
    
    # Check for changes
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
        notify "📦 Committed: $msg ($changed files)"
    else
        log "Git: push failed, trying with -u"
        git push -u origin replies310126 2>&1 | tail -2 >> "$LOG_FILE"
    fi
}

log "=== Continuous Runner Started (PID $$) ==="
notify "🤖 Autocoding started - continuous mode"

while true; do
    # Check if cursor-agent is already running
    if pgrep -f 'cursor-agent.*-p' > /dev/null; then
        log "cursor-agent already running, waiting..."
        sleep 30
        continue
    fi
    
    result=$(get_first_pending_task)
    
    if [ -z "$result" ]; then
        log "All tasks complete! Sleeping 60s..."
        sleep 60
        continue
    fi
    
    task_name=$(echo "$result" | sed 's/|||.*//')
    subtask=$(echo "$result" | sed 's/.*|||//')
    
    log "Starting: $subtask"
    notify "🚀 Task: $subtask"
    
    start_time=$(date +%s)
    cd "$WORKSPACE"
    
    PROMPT="You are autocoding on Hetzner server. Complete ONE subtask then stop.

CURRENT SUBTASK: $subtask

INSTRUCTIONS:
1. Complete ONLY this subtask: \"$subtask\"
2. Run necessary commands (docker logs, curl, etc.)
3. If code changes needed, make them
4. Write result summary to state/response.txt
5. If blocked, write to state/blocker.txt
6. DO NOT mark tasks done - the script will do it
7. DO NOT commit/push - the script will do it

SAFETY: Never send messages via Smartlead API!"

    timeout $CURSOR_TIMEOUT ~/.local/bin/cursor-agent -p "$PROMPT" 2>&1 | tee -a "$LOG_FILE"
    exit_code=$?
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    if [ "$exit_code" -eq 124 ]; then
        log "TIMEOUT after $((CURSOR_TIMEOUT/60)) minutes"
        notify "⏰ Timeout: $subtask"
    elif [ "$exit_code" -ne 0 ]; then
        log "ERROR: exit code $exit_code"
        notify "❌ Error: $subtask (exit $exit_code)"
    else
        log "COMPLETED in ${duration}s"
        # Mark subtask done via SCRIPT (not AI)
        mark_subtask_done "$subtask"
        # Git commit/push via SCRIPT (not AI)
        git_commit_push "Completed: $subtask"
        notify "✅ Done: $subtask (${duration}s)"
    fi
    
    log "Waiting ${LOOP_INTERVAL}s before next task..."
    sleep $LOOP_INTERVAL
done
