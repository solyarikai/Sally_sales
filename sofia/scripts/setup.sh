#!/bin/bash
# One-time setup for sales_engineer auto-sync on a new machine
# Run after cloning the repo: bash scripts/setup.sh
#
# What it does:
# 1. Installs fswatch (if missing)
# 2. Generates LaunchAgent plist for this machine's repo path
# 3. Loads the LaunchAgent (starts watching immediately)
#
# Works on: macOS (Homebrew required)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="com.sales-engineer.auto-sync"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== Sales Engineer Auto-Sync Setup ==="
echo "Repo: $REPO_DIR"
echo ""

# --- Step 1: Install fswatch ---
if command -v fswatch &>/dev/null; then
  echo "[OK] fswatch already installed"
else
  echo "[..] Installing fswatch..."
  if command -v brew &>/dev/null; then
    brew install fswatch
    echo "[OK] fswatch installed"
  else
    echo "[ERROR] Homebrew not found. Install it first: https://brew.sh"
    exit 1
  fi
fi

# --- Step 2: Make scripts executable ---
chmod +x "$SCRIPT_DIR/auto-sync.sh"
chmod +x "$SCRIPT_DIR/watch-sync.sh"
echo "[OK] Scripts made executable"

# --- Step 3: Unload old plist if exists ---
if launchctl list 2>/dev/null | grep -q "$PLIST_NAME"; then
  echo "[..] Stopping existing watcher..."
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# --- Step 4: Generate plist with correct paths ---
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/watch-sync.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/sales_engineer_watch.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/sales_engineer_watch.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST

echo "[OK] LaunchAgent created: $PLIST_PATH"

# --- Step 5: Load and start ---
launchctl load "$PLIST_PATH"
echo "[OK] Watcher started"

# --- Step 6: Verify ---
echo ""
if launchctl list 2>/dev/null | grep -q "$PLIST_NAME"; then
  echo "=== Setup complete ==="
  echo ""
  echo "Auto-sync is now active:"
  echo "  - Claude hook: commits after each Claude response (instant)"
  echo "  - File watcher: commits on any file change (30s debounce)"
  echo "  - Starts automatically on login"
  echo ""
  echo "Commands:"
  echo "  tail -f /tmp/sales_engineer_watch.log   # watch log"
  echo "  launchctl unload \"$PLIST_PATH\"           # stop"
  echo "  launchctl load \"$PLIST_PATH\"             # start"
else
  echo "[ERROR] LaunchAgent failed to start. Check:"
  echo "  cat /tmp/sales_engineer_watch.log"
  exit 1
fi
