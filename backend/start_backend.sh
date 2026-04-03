#!/bin/sh
cd /volume1/docker/docscool/backend || exit 1

if [ -f backend.pid ] && kill -0 "$(cat backend.pid)" 2>/dev/null; then
    echo "DocsCool backend is already running"
    exit 0
fi

nohup /volume1/docker/docscool/backend/.venv/bin/python /volume1/docker/docscool/backend/run.py \
    > /volume1/docker/docscool/backend/backend.log 2>&1 &

echo $! > /volume1/docker/docscool/backend/backend.pid
echo "DocsCool backend started with PID $(cat /volume1/docker/docscool/backend/backend.pid)"
