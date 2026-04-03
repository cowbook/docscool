#!/bin/sh
PID_FILE=/volume1/docker/docscool/backend/backend.pid

if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found"
    exit 1
fi

PID="$(cat "$PID_FILE")"

if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "DocsCool backend stopped"
else
    rm -f "$PID_FILE"
    echo "Process not running, PID file removed"
fi

