#!/bin/bash
DIR="$(dirname "$0")"
cd "$DIR"
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
exec node server.js
