#!/usr/bin/env bash
# Start the github-issue-reply dashboard in the background, tracked in a PID
# file so stop_dashboard.sh can shut it down cleanly — no manual pgrep/kill.
# All args are forwarded to dashboard_server.py (--repo, --bind, ...); --port
# is auto-picked (scanning for a free one) if you don't pass it yourself.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$HOME/.cache/github-issue-reply"
PID_FILE="$STATE_DIR/dashboard.pid"
LOG_FILE="$STATE_DIR/dashboard.log"
mkdir -p "$STATE_DIR"

if [[ -f "$PID_FILE" ]]; then
    IFS=: read -r OLD_PID OLD_PORT < "$PID_FILE"
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Already running: http://127.0.0.1:${OLD_PORT}/  (pid $OLD_PID)"
        echo "Stop it first with: bash $SCRIPT_DIR/stop_dashboard.sh"
        exit 0
    fi
    rm -f "$PID_FILE"  # stale — process from a prior run is gone
fi

ARGS=("$@")
PORT=""
for ((i = 0; i < ${#ARGS[@]}; i++)); do
    if [[ "${ARGS[$i]}" == "--port" ]]; then
        PORT="${ARGS[$((i + 1))]}"
    fi
done

if [[ -z "$PORT" ]]; then
    PORT=$(python3 -c "
import socket
for p in range(8765, 8865):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', p))
        print(p)
        break
    except OSError:
        pass
    finally:
        s.close()
")
    if [[ -z "$PORT" ]]; then
        echo "No free port found in 8765-8864 — pass --port explicitly." >&2
        exit 1
    fi
    ARGS+=(--port "$PORT")
fi

nohup python3 "$SCRIPT_DIR/dashboard_server.py" "${ARGS[@]}" > "$LOG_FILE" 2>&1 &
PID=$!
disown

sleep 1
if ! kill -0 "$PID" 2>/dev/null; then
    echo "Failed to start — last lines of $LOG_FILE:" >&2
    tail -n 20 "$LOG_FILE" >&2
    exit 1
fi

echo "${PID}:${PORT}" > "$PID_FILE"
echo "Dashboard running: http://127.0.0.1:${PORT}/"
echo "Log: $LOG_FILE"
echo "Stop with: bash $SCRIPT_DIR/stop_dashboard.sh"
