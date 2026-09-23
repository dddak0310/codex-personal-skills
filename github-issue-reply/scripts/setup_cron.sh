#!/usr/bin/env bash
# Add (or remove) an hourly cron job that runs fetch_issues.py — read-only
# sync (fetch + classify + summary.md), never drafts or posts anything.
# Portable: resolves its own path and python3 at run time, so any developer
# can just `bash setup_cron.sh` after their own install.sh and get a cron
# line that matches their machine, not a hardcoded path.
#
# Usage:
#   bash setup_cron.sh            # install/update the hourly job
#   bash setup_cron.sh --remove   # remove it
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCH="$SCRIPT_DIR/fetch_issues.py"
PYTHON3="$(command -v python3)"
LOG_FILE="$HOME/github-issue/${USER}-fetch.log"
MARKER="# github-issue-reply: hourly fetch_issues.py sync"
CRON_LINE="0 * * * * $PYTHON3 $FETCH >> $LOG_FILE 2>&1 $MARKER"

if [[ -z "$PYTHON3" ]]; then
    echo "python3 not found on PATH — install it first." >&2
    exit 1
fi

mkdir -p "$HOME/github-issue"

if [[ "$1" == "--remove" ]]; then
    crontab -l 2>/dev/null | grep -vF "$MARKER" | crontab -
    echo "Removed the hourly github-issue-reply cron job (if it was installed)."
    exit 0
fi

# Idempotent: drop any previous line with our marker, then re-add the current one.
( crontab -l 2>/dev/null | grep -vF "$MARKER"; echo "$CRON_LINE" ) | crontab -

echo "Installed cron job:"
echo "  $CRON_LINE"
echo ""
echo "Runs every hour on the hour. Log: $LOG_FILE"
echo "Remove later with: bash $SCRIPT_DIR/setup_cron.sh --remove"
