#!/usr/bin/env python3
"""Record the active Claude Code or Codex session in the daily session index.

Configured on both ``SessionStart`` and ``UserPromptSubmit``. The first event
records the lifecycle source; the second keeps an already-open session visible
and increments its user-prompt count. Output is one upserted record per
``(tool, session_id)`` in
``$DAILY_WORKLOG_ROOT/session-log/YYYYMMDD.jsonl`` (``DAILY_WORKLOG_ROOT``
defaults to ``$HOME/meeting``).

This is a lifecycle hook: it must never write to stdout or stop a chat when
logging fails.
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TOOLS = ("claude", "codex")


def git_info(cwd: str) -> dict:
    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", cwd, *args],
                capture_output=True, text=True, timeout=3,
            )
            return out.stdout.strip() if out.returncode == 0 else None
        except Exception:
            return None

    top = run("rev-parse", "--show-toplevel")
    if not top:
        return {}
    return {"git_repo": top, "git_branch": run("rev-parse", "--abbrev-ref", "HEAD")}


def infer_tool(transcript_path: object, fallback: str = "claude") -> str:
    """Infer legacy rows without a platform field from their transcript path."""
    path = str(transcript_path or "")
    if "/.codex/" in path:
        return "codex"
    if "/.claude/" in path:
        return "claude"
    return fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tool", choices=(*TOOLS, "auto"), default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return

    tool = (
        infer_tool(payload.get("transcript_path"))
        if args.tool == "auto"
        else args.tool
    )
    cwd = payload.get("cwd") or os.getcwd()
    event = payload.get("hook_event_name")
    now = datetime.now().astimezone()
    ts = now.isoformat(timespec="seconds")

    root = Path(os.environ.get("DAILY_WORKLOG_ROOT") or (Path.home() / "meeting"))
    out_dir = root / "session-log"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{now:%Y%m%d}.jsonl"

    # Several sessions can update one day concurrently. Keep read-modify-write
    # inside the same advisory lock and replace atomically after writing.
    with (out_dir / f".{now:%Y%m%d}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows: list[dict] = []
        if out_file.exists():
            with out_file.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        # Migrate a legacy Claude-only row on its next update.
                        row.setdefault("tool", infer_tool(row.get("transcript_path")))
                        rows.append(row)

        row = next(
            (
                candidate for candidate in rows
                if candidate.get("tool") == tool
                and candidate.get("session_id") == session_id
            ),
            None,
        )
        if row is None:
            row = {
                "tool": tool,
                "session_id": session_id,
                "cwd": cwd,
                "first_ts": ts,
                "last_ts": ts,
                "prompts": 0,
                "source": payload.get("source") if event == "SessionStart" else "in-progress",
                "transcript_path": payload.get("transcript_path"),
                **git_info(cwd),
            }
            rows.append(row)
        else:
            row["last_ts"] = ts
            row["cwd"] = cwd
            if event == "SessionStart" and payload.get("source"):
                row["source"] = payload["source"]
            if payload.get("transcript_path"):
                row["transcript_path"] = payload["transcript_path"]

        if event == "UserPromptSubmit":
            row["prompts"] = int(row.get("prompts") or 0) + 1

        tmp = out_file.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for item in sorted(rows, key=lambda item: item.get("first_ts") or ""):
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        tmp.replace(out_file)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
