#!/usr/bin/env python3
"""Dump raw Claude Code + Codex conversation turns for a given date.

Two ways to find which sessions touched the target date (--source):
  - scan (default): walk the raw transcript trees directly —
      ~/.claude/projects/*/*.jsonl   (not date-sharded, so every file is
        opened and filtered by each line's timestamp)
      ~/.codex/sessions/YYYY/MM/DD/*.jsonl   (already date-sharded)
  - hook: read the day's session index that the SessionStart/UserPromptSubmit
      hook (and its backfill script) maintains at
      $DAILY_WORKLOG_ROOT/session-log/YYYYMMDD.jsonl, and open only the
      transcript_path files it lists. Cheaper, but only as complete as that
      index (Claude Code only unless backfilled; misses anything the hook
      hasn't recorded yet).
  - both: union of the two (deduplicated by tool+session id).

For each session touched on the target date, prints the ordered user/assistant
text turns (system-injected wrapper content — environment_context, plugin
lists, AGENTS.md boilerplate, tool_result/tool_use payloads, thinking blocks —
is filtered out). This is raw material for a human/LLM to write a daily report
from; it does not summarize or judge relevance itself.

Usage:
  python3 extract_transcripts.py [--date YYYY-MM-DD] [--tool claude|codex|all]
                                  [--source scan|hook|both]
                                  [--max-chars N] [--manifest-out PATH]
"""
import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude" / "projects"
CODEX_DIR = Path.home() / ".codex" / "sessions"
DAILY_ROOT = Path(os.environ.get("DAILY_WORKLOG_ROOT", str(Path.home() / "meeting")))
SESSION_LOG_DIR = DAILY_ROOT / "session-log"

NOISE_PREFIXES = (
    "<", "Caveat:", "# AGENTS.md",
    "Base directory for this skill:", "[Request interrupted",
)
NOISE_MARKERS = (
    "<recommended_plugins>", "<environment_context>", "<system-reminder>",
)


def is_noise(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if t.startswith(NOISE_PREFIXES):
        return True
    if any(m in t[:200] for m in NOISE_MARKERS):
        return True
    return False


def truncate(text: str, max_chars: int) -> str:
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + f"\n…[截斷，原長 {len(t)} 字元]"


# ---------------------------------------------------------------- Claude Code

def extract_claude_session(path: Path, target: str, max_chars: int,
                            session_id: str | None = None) -> dict | None:
    """Parse one Claude Code transcript file; return its session dict for
    `target`, or None if it has no turns on that date."""
    turns = []
    cwd = None
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("timestamp")
                if not ts or not ts.startswith(target):
                    continue
                if cwd is None:
                    cwd = obj.get("cwd")
                role = obj.get("type")
                if role not in ("user", "assistant"):
                    continue
                msg = obj.get("message", {})
                content = msg.get("content")
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text += c.get("text", "")
                text = text.strip()
                if role == "user" and is_noise(text):
                    continue
                if not text:
                    continue
                turns.append((ts, role, truncate(text, max_chars)))
    except (OSError, UnicodeDecodeError):
        return None
    if not turns:
        return None
    return {
        "tool": "claude",
        "id": session_id or path.stem,
        "cwd": cwd,
        "source_file": str(path),
        "turns": turns,
    }


def scan_claude_sessions(target: str, max_chars: int) -> list[dict]:
    if not CLAUDE_DIR.exists():
        return []
    sessions = []
    for proj_dir in CLAUDE_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        for path in proj_dir.glob("*.jsonl"):
            session = extract_claude_session(path, target, max_chars)
            if session:
                sessions.append(session)
    return sessions


# --------------------------------------------------------------------- Codex

def extract_codex_session(path: Path, target: str, max_chars: int,
                           session_id: str | None = None) -> dict | None:
    """Parse one Codex rollout file; return its session dict for `target`,
    or None if it has no turns on that date."""
    turns = []
    cwd = None
    found_id = None
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("timestamp")
                if obj.get("type") == "session_meta":
                    meta = obj.get("payload", {})
                    if cwd is None:
                        cwd = meta.get("cwd")
                    found_id = found_id or meta.get("session_id") or meta.get("id")
                if obj.get("type") != "response_item":
                    continue
                if not ts or not ts.startswith(target):
                    continue
                payload = obj.get("payload", {})
                if payload.get("type") != "message":
                    continue
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue
                text = ""
                for c in payload.get("content", []):
                    if isinstance(c, dict) and c.get("type") in (
                        "input_text", "text", "output_text",
                    ):
                        text += c.get("text", "")
                text = text.strip()
                if role == "user" and is_noise(text):
                    continue
                if not text:
                    continue
                turns.append((ts, role, truncate(text, max_chars)))
    except (OSError, UnicodeDecodeError):
        return None
    if not turns:
        return None
    return {
        "tool": "codex",
        # The filename also includes a rollout timestamp; prefer the live
        # hook's actual Codex session identifier when known.
        "id": session_id or found_id or path.stem,
        "cwd": cwd,
        "source_file": str(path),
        "turns": turns,
    }


def scan_codex_sessions(target: str, max_chars: int) -> list[dict]:
    try:
        y, m, d = target.split("-")
    except ValueError:
        return []
    day_dir = CODEX_DIR / y / m / d
    if not day_dir.exists():
        return []
    sessions = []
    for path in day_dir.glob("*.jsonl"):
        session = extract_codex_session(path, target, max_chars)
        if session:
            sessions.append(session)
    return sessions


# ---------------------------------------------------------------- hook index

def load_hook_sessions(target: str, tool_filter: str, max_chars: int) -> list[dict]:
    """Use the session-log hook's daily index to find which transcript files
    to open, instead of walking the raw transcript trees. Cheaper, but only
    as complete as the index (see module docstring)."""
    log_path = SESSION_LOG_DIR / f"{target.replace('-', '')}.jsonl"
    if not log_path.exists():
        print(f"[hook-index] not found: {log_path}", file=sys.stderr)
        return []
    sessions = []
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            tool = entry.get("tool", "claude")
            if tool_filter != "all" and tool != tool_filter:
                continue
            transcript_path = entry.get("transcript_path")
            if not transcript_path:
                continue
            path = Path(transcript_path)
            if not path.exists():
                continue
            session_id = entry.get("session_id")
            if tool == "codex":
                session = extract_codex_session(path, target, max_chars, session_id)
            else:
                session = extract_claude_session(path, target, max_chars, session_id)
            if session:
                sessions.append(session)
    return sessions


# ------------------------------------------------------------------- output

def default_manifest_path(target: str) -> Path:
    """Return the daily report's default local session-index location."""
    return DAILY_ROOT / target.replace("-", "") / "data" / "session-manifest.json"


def write_manifest(path: Path, target: str, selected_tool: str, source_mode: str,
                    sessions: list[dict]) -> None:
    """Write session metadata for later task/page provenance; never include transcript text."""
    payload = {
        "schema_version": 1,
        "report_kind": "daily",
        "report_date": target,
        "selected_tool": selected_tool,
        "source_mode": source_mode,
        "sessions": [
            {
                "source": session["tool"],
                "session_id": session["id"],
                "source_file": session["source_file"],
                "cwd": session["cwd"],
                "started_at": session["turns"][0][0],
                "ended_at": session["turns"][-1][0],
                "turn_count": len(session["turns"]),
            }
            for session in sessions
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat(),
                    help="YYYY-MM-DD, default today")
    ap.add_argument("--tool", choices=["claude", "codex", "all"], default="all")
    ap.add_argument("--source", choices=["scan", "hook", "both"], default="scan",
                    help="scan: walk ~/.claude and ~/.codex directly (default). "
                         "hook: use the session-log hook's daily index instead. "
                         "both: union of the two.")
    ap.add_argument("--max-chars", type=int, default=4000,
                    help="truncate each turn's text to this many chars")
    ap.add_argument("--manifest-out", type=Path, default=None,
                    help="override the default daily JSON session metadata path")
    args = ap.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid --date {args.date!r}, expected YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    manifest_path = args.manifest_out or default_manifest_path(args.date)

    scanned = []
    if args.source in ("scan", "both"):
        if args.tool in ("claude", "all"):
            scanned += scan_claude_sessions(args.date, args.max_chars)
        if args.tool in ("codex", "all"):
            scanned += scan_codex_sessions(args.date, args.max_chars)

    hooked = []
    if args.source in ("hook", "both"):
        hooked = load_hook_sessions(args.date, args.tool, args.max_chars)

    if args.source == "both":
        # De-dupe by (tool, id); a scan-found session wins since it re-parses
        # the live file directly rather than trusting the index's path.
        by_key = {(s["tool"], s["id"]): s for s in hooked}
        by_key.update({(s["tool"], s["id"]): s for s in scanned})
        sessions = list(by_key.values())
    else:
        sessions = scanned or hooked

    if not sessions:
        write_manifest(manifest_path, args.date, args.tool, args.source, sessions)
        print(f"[session-manifest] {manifest_path}", file=sys.stderr)
        print(f"No sessions found for {args.date}.")
        return

    sessions.sort(key=lambda s: s["turns"][0][0])
    write_manifest(manifest_path, args.date, args.tool, args.source, sessions)
    print(f"[session-manifest] {manifest_path}", file=sys.stderr)

    print(f"# Raw transcript dump — {args.date}")
    print(f"# {len(sessions)} session(s) found\n")
    for s in sessions:
        first_ts = s["turns"][0][0]
        last_ts = s["turns"][-1][0]
        print(f"\n{'=' * 80}")
        print(f"## [{s['tool']}] session {s['id']}  cwd={s['cwd']}  "
              f"{first_ts} → {last_ts}  ({len(s['turns'])} turns)")
        print("=" * 80)
        for ts, role, text in s["turns"]:
            tag = "🧑 USER" if role == "user" else "🤖 ASSISTANT"
            print(f"\n--- {tag} [{ts}] ---")
            print(text)


if __name__ == "__main__":
    main()
