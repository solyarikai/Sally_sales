#!/bin/bash
DIR="$(dirname "$0")"
cd "$DIR"

# Load local env overrides (not committed to git — each user sets their own tokens)
REPO_ROOT="$(cd "$DIR/../../../.." && pwd)"
if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a
  source "$REPO_ROOT/.env.local"
  set +a
fi

if [ ! -d "node_modules" ]; then
  npm install --silent
fi
exec node server.js
