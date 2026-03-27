#!/bin/bash
# Auto-sync: smart git commit + push for Sofia inside magnum-opus
# Triggered by Claude Code Stop hook after each response
#
# Features:
# - Stages only sofia/
# - Skips if no Sofia changes
# - Generates meaningful commit messages based on changed files
# - Pre-push safety check for secrets
# - Pulls before push to avoid conflicts
# - Batches rapid changes (debounce 10s)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "$CLAUDE_PROJECT_DIR/magnum-opus/.git" ]; then
  REPO_DIR="$CLAUDE_PROJECT_DIR/magnum-opus"
elif [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "$CLAUDE_PROJECT_DIR/.git" ] && [ -d "$CLAUDE_PROJECT_DIR/sofia" ]; then
  REPO_DIR="$CLAUDE_PROJECT_DIR"
else
  REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

LOCK_FILE="/tmp/sales_engineer_sync.lock"
DEBOUNCE_SECONDS=10

cd "$REPO_DIR"

# --- Guard: not a git repo ---
if [ ! -d .git ]; then
  exit 0
fi

# --- Debounce: skip if synced recently ---
if [ -f "$LOCK_FILE" ]; then
  last_sync=$(cat "$LOCK_FILE" 2>/dev/null || echo 0)
  now=$(date +%s)
  elapsed=$((now - last_sync))
  if [ "$elapsed" -lt "$DEBOUNCE_SECONDS" ]; then
    exit 0
  fi
fi

# --- Stage only Sofia changes ---
git add -A -- sofia

# --- Skip if nothing to commit ---
if git diff --cached --quiet 2>/dev/null -- sofia; then
  exit 0
fi

# --- Safety: check for secrets in staged files ---
FORBIDDEN_PATTERNS="credentials\.json|token\.json|\.env$|\.mcp\.json|api[_-]?key|secret[_-]?key"
leaked=$(git diff --cached --name-only -- sofia | grep -iE "$FORBIDDEN_PATTERNS" || true)
if [ -n "$leaked" ]; then
  echo "AUTO-SYNC BLOCKED: potential secrets detected in staged files:"
  echo "$leaked"
  git reset HEAD -- $leaked 2>/dev/null
  # Re-check if anything left to commit
  if git diff --cached --quiet 2>/dev/null -- sofia; then
    exit 0
  fi
fi

# --- Generate smart commit message ---
changed_files=$(git diff --cached --name-only -- sofia)
file_count=$(echo "$changed_files" | wc -l | tr -d ' ')

# Detect what areas changed
areas=""
echo "$changed_files" | grep -q "^sofia/projects/OnSocial/" && areas="${areas}OnSocial, "
echo "$changed_files" | grep -q "^sofia/projects/ArchiStruct/" && areas="${areas}ArchiStruct, "
echo "$changed_files" | grep -q "^sofia/\\.claude/memory/" && areas="${areas}memory, "
echo "$changed_files" | grep -q "^sofia/skills/" && areas="${areas}skills, "
echo "$changed_files" | grep -q "^sofia/mcp/" && areas="${areas}MCP, "
echo "$changed_files" | grep -Eq "^sofia/(Outreach full guide|outreach_ful_ guide)/" && areas="${areas}outreach-guide, "
echo "$changed_files" | grep -q "^sofia/\\.claude/" && areas="${areas}config, "
echo "$changed_files" | grep -q "^sofia/scripts/" && areas="${areas}scripts, "

# Remove trailing ", "
areas=$(echo "$areas" | sed 's/, $//')

# Detect action type
has_new=$(git diff --cached --diff-filter=A --name-only | head -1)
has_modified=$(git diff --cached --diff-filter=M --name-only | head -1)
has_deleted=$(git diff --cached --diff-filter=D --name-only | head -1)

action=""
[ -n "$has_new" ] && [ -n "$has_modified" ] && action="update"
[ -n "$has_new" ] && [ -z "$has_modified" ] && action="add"
[ -z "$has_new" ] && [ -n "$has_modified" ] && action="update"
[ -n "$has_deleted" ] && action="refactor"
[ -z "$action" ] && action="sync"

# Build message
if [ "$file_count" -eq 1 ]; then
  filename=$(basename "$changed_files")
  msg="${action}: ${filename}"
  [ -n "$areas" ] && msg="${msg} (${areas})"
else
  if [ -n "$areas" ]; then
    msg="${action}: ${areas} (${file_count} files)"
  else
    msg="${action}: ${file_count} files"
  fi
fi

# --- Commit ---
git commit -m "$msg" --quiet

# --- Pull before push (rebase to keep history clean) ---
git pull --rebase --quiet origin main 2>/dev/null || true

# --- Push ---
git push origin main --quiet 2>/dev/null || true

# --- Update debounce lock ---
date +%s > "$LOCK_FILE"
