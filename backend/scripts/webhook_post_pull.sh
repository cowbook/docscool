#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_PY="$BACKEND_DIR/.venv/bin/python"
BACKEND_RUN="$BACKEND_DIR/run.py"
LOG_DIR="$BACKEND_DIR/instance"
BUILD_LOG="$LOG_DIR/webhook_frontend_build.log"
BACKEND_LOG="$LOG_DIR/webhook_backend_restart.log"

mkdir -p "$LOG_DIR"

# Rebuild frontend first. Keep logs for troubleshooting on DSM.
if [ -d "$FRONTEND_DIR" ]; then
  (
    cd "$FRONTEND_DIR"
    npm run build
  ) >"$BUILD_LOG" 2>&1 || exit 1
fi

# Stop existing backend process started by run.py if present.
if command -v pkill >/dev/null 2>&1; then
  pkill -f "$BACKEND_RUN" >/dev/null 2>&1 || true
fi

# Start backend in background detached from webhook request lifecycle.
nohup "$BACKEND_PY" "$BACKEND_RUN" >"$BACKEND_LOG" 2>&1 &
