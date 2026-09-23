#!/usr/bin/env bash
# Stop a dashboard started with start_dashboard.sh.
set -e

STATE_DIR="$HOME/.cache/github-issue-reply"
PID_FILE="$STATE_DIR/dashboard.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "No PID file found ($PID_FILE) — nothing tracked to stop."
    echo "(If it was started manually, not via start_dashboard.sh, stop it with Ctrl-C in its terminal instead.)"
    exit 0
fi

IFS=: read -r PID PORT < "$PID_FILE"

if [[ -z "$PID" ]] || ! kill -0 "$PID" 2>/dev/null; then
    echo "Process $PID is not running (stale pid file) — removing it."
    rm -f "$PID_FILE"
    exit 0
fi

kill "$PID"
for _ in $(seq 1 10); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.2
done
if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
fi

rm -f "$PID_FILE"
echo "Stopped dashboard (was pid $PID, port $PORT)."
