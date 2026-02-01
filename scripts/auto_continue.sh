#!/bin/bash
# Auto-continue script for Cursor CLI
# Reads first pending task from tasks.md and continues work every 5 minutes

WORKSPACE="/home/leadokol/magnum-opus-project/repo"
STATE_DIR="$WORKSPACE/state"
TASKS_FILE="$STATE_DIR/tasks.md"
CONTEXT_FILE="$STATE_DIR/session_context.json"
LOG_FILE="$STATE_DIR/auto_continue.log"
INTERVAL_MINUTES=5
CURSOR_TIMEOUT=900  # 15 minutes timeout for cursor-agent (Opus 4.5 needs time)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_first_pending_task() {
    # Find first task with unchecked subtasks
    local task_name=""
    local subtask=""
    local in_task=false
    local task_header=""
    
    while IFS= read -r line; do
        # Check for task header (### Task N: ...)
        if [[ "$line" =~ ^###[[:space:]]Task[[:space:]]([0-9]+):[[:space:]](.+) ]]; then
            # Skip if marked complete
            if [[ ! "$line" =~ "✅ COMPLETE" && ! "$line" =~ "COMPLETE" ]]; then
                task_header="$line"
                in_task=true
            else
                in_task=false
            fi
        fi
        
        # Find first unchecked subtask within active task
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

update_session_context() {
    local task_name="$1"
    local subtask="$2"
    local session_id=$(jq -r '.session_id // 0' "$CONTEXT_FILE" 2>/dev/null || echo "0")
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
}

build_prompt() {
    local task_name="$1"
    local subtask="$2"
    
    cat << EOF
Continue working on the project. 

CURRENT TASK: $task_name
CURRENT SUBTASK: $subtask

CONTEXT:
1. Read state/session_context.json for previous session state
2. Read state/tasks.md for full task list
3. Check state/response.txt for what was done last
4. Check state/blocker.txt for any blockers

INSTRUCTIONS:
1. Complete the current subtask: "$subtask"
2. Mark it done in tasks.md when complete
3. Update session_context.json with progress
4. Write summary to state/response.txt
5. If blocked, write to state/blocker.txt
6. If subtask complete, move to next subtask
7. Rebuild Docker if code changed: docker-compose down && docker-compose up -d --build

SAFETY: Never send messages via Smartlead API. Read-only!
EOF
}

run_cursor() {
    local prompt="$1"
    
    log "Starting Cursor CLI (timeout: ${CURSOR_TIMEOUT}s / $((CURSOR_TIMEOUT/60)) minutes)..."
    
    # Run cursor with the prompt and timeout
    cd "$WORKSPACE"
    
    # Use cursor-agent CLI with timeout to prevent hanging
    if [ -f "$HOME/.local/bin/cursor-agent" ]; then
        timeout $CURSOR_TIMEOUT "$HOME/.local/bin/cursor-agent" --message "$prompt" 2>&1 | tee -a "$LOG_FILE"
        local exit_code=$?
        if [ "$exit_code" -eq 124 ]; then
            log "${YELLOW}WARNING: cursor-agent timed out after $((CURSOR_TIMEOUT/60)) minutes${NC}"
            # Mark session as timed out
            if [ -f "$CONTEXT_FILE" ]; then
                jq '.status = "timed_out" | .timeout_at = "'"$(date -Iseconds)"'"' "$CONTEXT_FILE" > "${CONTEXT_FILE}.tmp" && mv "${CONTEXT_FILE}.tmp" "$CONTEXT_FILE"
            fi
        fi
        return $exit_code
    else
        log "ERROR: cursor-agent not found at ~/.local/bin/cursor-agent"
        return 1
    fi
}

main_loop() {
    log "=========================================="
    log "Auto-continue script started"
    log "Interval: ${INTERVAL_MINUTES} minutes"
    log "=========================================="
    
    while true; do
        log "---"
        log "Checking for pending tasks..."
        
        # Get first pending task and subtask
        result=$(get_first_pending_task)
        
        if [ -z "$result" ]; then
            log "${GREEN}All tasks complete!${NC}"
            log "Sleeping for $INTERVAL_MINUTES minutes before checking again..."
            sleep $((INTERVAL_MINUTES * 60))
            continue
        fi
        
        # Parse task and subtask
        task_name=$(echo "$result" | cut -d'|' -f1-3 | sed 's/|||.*//')
        subtask=$(echo "$result" | sed 's/.*|||//')
        
        log "Found pending task: $task_name"
        log "Subtask: $subtask"
        
        # Update session context
        update_session_context "$task_name" "$subtask"
        
        # Build prompt
        prompt=$(build_prompt "$task_name" "$subtask")
        
        # Run cursor
        run_cursor "$prompt"
        
        log "Cursor session complete. Waiting $INTERVAL_MINUTES minutes..."
        sleep $((INTERVAL_MINUTES * 60))
    done
}

# Single run mode (for testing or one-shot execution)
single_run() {
    log "Single run mode"
    
    result=$(get_first_pending_task)
    
    if [ -z "$result" ]; then
        log "All tasks complete!"
        exit 0
    fi
    
    task_name=$(echo "$result" | cut -d'|' -f1-3 | sed 's/|||.*//')
    subtask=$(echo "$result" | sed 's/.*|||//')
    
    log "Task: $task_name"
    log "Subtask: $subtask"
    
    update_session_context "$task_name" "$subtask"
    prompt=$(build_prompt "$task_name" "$subtask")
    
    echo ""
    echo "=== PROMPT FOR CURSOR ==="
    echo "$prompt"
    echo "========================="
}

# Parse arguments
case "${1:-loop}" in
    "loop")
        main_loop
        ;;
    "once"|"single")
        single_run
        ;;
    "prompt")
        # Just output the prompt, don't run cursor
        result=$(get_first_pending_task)
        if [ -n "$result" ]; then
            task_name=$(echo "$result" | cut -d'|' -f1-3 | sed 's/|||.*//')
            subtask=$(echo "$result" | sed 's/.*|||//')
            build_prompt "$task_name" "$subtask"
        else
            echo "No pending tasks"
        fi
        ;;
    *)
        echo "Usage: $0 [loop|once|prompt]"
        echo "  loop   - Run continuously every $INTERVAL_MINUTES minutes (default)"
        echo "  once   - Run once and exit"
        echo "  prompt - Just show the prompt without running cursor"
        exit 1
        ;;
esac
