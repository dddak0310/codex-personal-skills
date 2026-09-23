#!/usr/bin/env bash
# Install or remove the shared daily-work-log session hook for one agent.
#
#   ./install.sh --client claude
#   ./install.sh --client codex
#   ./install.sh --client codex --dry-run
#   ./install.sh --client codex --uninstall
#
# The hook records one row per (tool, session_id) at
# $DAILY_WORKLOG_ROOT/session-log/YYYYMMDD.jsonl (DAILY_WORKLOG_ROOT defaults
# to `$HOME/meeting`). Existing hooks and unrelated settings are preserved.

set -euo pipefail

HOOK_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/session-log.py"
CLIENT="claude"
MODE="install"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --client)
      [ "$#" -ge 2 ] || { echo "--client needs claude or codex" >&2; exit 2; }
      CLIENT="$2"
      shift 2
      ;;
    --uninstall) MODE="uninstall"; shift ;;
    --dry-run) MODE="dryrun"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

case "$CLIENT" in
  claude)
    SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
    ;;
  codex)
    SETTINGS="${CODEX_HOOKS:-$HOME/.codex/hooks.json}"
    ;;
  *) echo "--client must be claude or codex" >&2; exit 2 ;;
esac

[ -f "$HOOK_SCRIPT" ] || { echo "hook script not found: $HOOK_SCRIPT" >&2; exit 1; }
chmod +x "$HOOK_SCRIPT" 2>/dev/null || true

# One Codex config layer should use either hooks.json or inline [hooks], not
# both. Refuse to create a duplicate source that Codex would merge and warn on.
if [ "$CLIENT" = "codex" ]; then
  CODEX_CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
  if [ -f "$CODEX_CONFIG" ] && grep -Eq '^[[:space:]]*\[\[?hooks([.]|\])' "$CODEX_CONFIG"; then
    echo "$CODEX_CONFIG already contains inline [hooks]; keep one Codex hook source and migrate it before installing." >&2
    exit 1
  fi
fi

python3 - "$SETTINGS" "$HOOK_SCRIPT" "$CLIENT" "$MODE" <<'__INSTALL_PY__'
import json
import shlex
import shutil
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
hook_script = Path(sys.argv[2])
client = sys.argv[3]
mode = sys.argv[4]
events = ("SessionStart", "UserPromptSubmit")
command = f"{shlex.quote(str(hook_script))} --tool {client}"

settings = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{settings_path} is not valid JSON; repair it first: {exc}")
    if not isinstance(settings, dict):
        sys.exit(f"{settings_path} top level is not an object; refusing to modify it")

hooks = settings.setdefault("hooks", {})
if not isinstance(hooks, dict):
    sys.exit(f"{settings_path}.hooks is not an object; refusing to modify it")
changed = []


def entries(event: str) -> list[tuple[dict, dict]]:
    groups = hooks.get(event, [])
    if not isinstance(groups, list):
        sys.exit(f"{settings_path}.hooks.{event} is not a list; refusing to modify it")
    found = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks", [])
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if (
                isinstance(handler, dict)
                and handler.get("type") == "command"
                and "session-log.py" in str(handler.get("command", ""))
            ):
                found.append((group, handler))
    return found


for event in events:
    found = entries(event)
    if mode == "uninstall":
        groups = hooks.get(event, [])
        for group, handler in found:
            group["hooks"].remove(handler)
            if not group["hooks"]:
                groups.remove(group)
        if found:
            changed.append(f"removed {event}")
        if not groups:
            hooks.pop(event, None)
        continue

    if found:
        for _, handler in found:
            if handler.get("command") != command:
                handler["command"] = command
                handler["timeout"] = 3
                changed.append(f"updated {event}")
        continue

    hooks.setdefault(event, []).append({
        "hooks": [{"type": "command", "command": command, "timeout": 3}],
    })
    changed.append(f"added {event}")

if not hooks:
    settings.pop("hooks", None)
rendered = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"

if mode == "dryrun":
    print(rendered)
    print("[dry-run] " + (", ".join(changed) if changed else "no changes"), file=sys.stderr)
    raise SystemExit(0)
if not changed:
    print(f"already current: {settings_path}")
    raise SystemExit(0)

if settings_path.exists():
    backup = settings_path.with_suffix(".json.bak")
    shutil.copy2(settings_path, backup)
    print(f"backup: {backup}")
settings_path.parent.mkdir(parents=True, exist_ok=True)
tmp = settings_path.with_suffix(".json.tmp")
tmp.write_text(rendered, encoding="utf-8")
tmp.replace(settings_path)
print(", ".join(changed) + f" -> {settings_path}")
__INSTALL_PY__

if [ "$MODE" = "install" ]; then
  LOG_ROOT="${DAILY_WORKLOG_ROOT:-$HOME/meeting}"
  cat <<EOF

Installed $CLIENT session hooks in $SETTINGS.
They will write platform-tagged rows to:
  $LOG_ROOT/session-log/YYYYMMDD.jsonl

For Codex, run /hooks once and trust the reviewed hook definition. To backfill
sessions that existed before installation:
  $(dirname "$HOOK_SCRIPT")/backfill-session-log.py --tool $CLIENT
EOF
fi
