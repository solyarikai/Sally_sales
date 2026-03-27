#!/bin/bash
# File watcher: triggers auto-sync.sh when files change in the repo
# Uses fswatch to monitor the working directory
# Runs independently of Claude — catches manual edits, Finder changes, etc.
#
# Usage:
#   ./scripts/watch-sync.sh          # foreground (for testing)
#   launchctl load ~/Library/LaunchAgents/com.sales-engineer.auto-sync.plist  # as service

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/auto-sync.sh"
LOG_FILE="/tmp/sales_engineer_watch.log"
DEBOUNCE_SECONDS=30

echo "[$(date)] watch-sync started for: $REPO_DIR" >> "$LOG_FILE"

# Exclude patterns that shouldn't trigger sync
EXCLUDES=(
  "\.git/"
  "\.DS_Store"
  "__pycache__"
  "node_modules"
  "\.pyc$"
)

EXCLUDE_ARGS=""
for pattern in "${EXCLUDES[@]}"; do
  EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$pattern"
done

# Watch for file changes and batch them
fswatch \
  --recursive \
  --latency "$DEBOUNCE_SECONDS" \
  --batch-marker \
  $EXCLUDE_ARGS \
  "$REPO_DIR" | while read -r line; do
    if [ "$line" = "NoOp" ]; then
      # Batch marker received — run sync
      echo "[$(date)] Changes detected, syncing..." >> "$LOG_FILE"
      CLAUDE_PROJECT_DIR="$REPO_DIR" bash "$SYNC_SCRIPT" >> "$LOG_FILE" 2>&1 || true
      echo "[$(date)] Sync complete" >> "$LOG_FILE"
    fi
  done
