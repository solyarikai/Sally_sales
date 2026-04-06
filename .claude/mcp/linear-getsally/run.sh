#!/bin/bash
DIR="$(dirname "$0")"
cd "$DIR"
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
exec node node_modules/linear-mcp/build/index.js
