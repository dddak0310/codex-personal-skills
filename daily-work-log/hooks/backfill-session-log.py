#!/usr/bin/env python3
"""Backfill Claude Code and Codex sessions into the daily session index.

The live hook only sees sessions that receive an event after installation. This
script scans existing transcripts and upserts the same schema, keyed by
``(tool, session_id)``. It keeps live hook-only fields such as the historical
branch and lifecycle source when they are already known.

Usage: backfill-session-log.py [--date YYYY-MM-DD] [--tool claude|codex|all]
                               [--dry-run]
"""

import argparse
import json
import os
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude" / "projects"
CODEX_DIR = Path.home() / ".codex" / "sessions"


def local_ts(raw: str) -> str:
    """Convert UTC transcript timestamps to the local hook timestamp format."""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone().isoformat(timespec="seconds")
    except ValueError:
        return raw


def git_repo(cwd: str) -> dict:
    """Backfill only the repository path; a current branch is not historical data."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return {}
    if out.returncode != 0:
        return {}
    return {"git_repo": out.stdout.strip()}


def make_record(
    tool: str,
    session_id: str,
    cwd: str | None,
    first_ts: str,
    last_ts: str,
    prompts: int,
    transcript_path: Path,
) -> dict:
    return {
        "tool": tool,
        "session_id": session_id,
        "cwd": cwd,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "prompts": prompts,
        "source": "backfill",
        "transcript_path": str(transcript_path),
        **(git_repo(cwd) if cwd and Path(cwd).is_dir() else {}),
    }


def scan_claude(target: str) -> list[dict]:
    found = []
    if not CLAUDE_DIR.exists():
        return found
    for path in CLAUDE_DIR.rglob("*.jsonl"):
        first_ts = last_ts = cwd = None
        prompts = 0
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = obj.get("timestamp")
                    if not isinstance(ts, str):
                        continue
                    ts = local_ts(ts)
                    if ts[:10] != target:
                        continue
                    first_ts = first_ts or ts
                    last_ts = ts
                    cwd = cwd or obj.get("cwd")
                    if obj.get("type") == "user" and not obj.get("isMeta"):
                        prompts += 1
        except (OSError, UnicodeDecodeError):
            continue
        if first_ts:
            found.append(make_record(
                "claude", path.stem, cwd, first_ts, last_ts, prompts, path,
            ))
    return found


def codex_candidate_dirs(target: str) -> list[Path]:
    """Include neighbouring UTC directories for one local calendar day."""
    day = date.fromisoformat(target)
    return [
        CODEX_DIR / f"{candidate:%Y}" / f"{candidate:%m}" / f"{candidate:%d}"
        for candidate in (day - timedelta(days=1), day, day + timedelta(days=1))
    ]


def scan_codex(target: str) -> list[dict]:
    found = []
    paths = [
        path for directory in codex_candidate_dirs(target) if directory.exists()
        for path in directory.glob("*.jsonl")
    ]
    for path in paths:
        session_id = cwd = first_ts = last_ts = None
        prompts = 0
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = obj.get("payload", {})
                    if obj.get("type") == "session_meta":
                        session_id = session_id or payload.get("session_id") or payload.get("id")
                        cwd = cwd or payload.get("cwd")
                    raw_ts = obj.get("timestamp")
                    if not isinstance(raw_ts, str):
                        continue
                    ts = local_ts(raw_ts)
                    if ts[:10] != target:
                        continue
                    first_ts = first_ts or ts
                    last_ts = ts
                    if (
                        obj.get("type") == "response_item"
                        and payload.get("type") == "message"
                        and payload.get("role") == "user"
                    ):
                        prompts += 1
        except (OSError, UnicodeDecodeError):
            continue
        if first_ts and isinstance(session_id, str) and session_id:
            found.append(make_record(
                "codex", session_id, cwd, first_ts, last_ts, prompts, path,
            ))
    return found


def infer_tool(row: dict) -> str:
    if row.get("tool") in ("claude", "codex"):
        return row["tool"]
    return "codex" if "/.codex/" in str(row.get("transcript_path") or "") else "claude"


def load_rows(out_file: Path) -> list[dict]:
    rows = []
    if not out_file.exists():
        return rows
    with out_file.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                row["tool"] = infer_tool(row)
                rows.append(row)
    return rows


def merge_record(old: dict, rec: dict) -> None:
    old["first_ts"] = min(value for value in (old.get("first_ts"), rec["first_ts"]) if value)
    old["last_ts"] = max(value for value in (old.get("last_ts"), rec["last_ts"]) if value)
    old["prompts"] = rec["prompts"]
    old["tool"] = rec["tool"]
    for key, value in rec.items():
        if value is not None and old.get(key) in (None, "", "backfill", "in-progress") and key != "source":
            old[key] = value
    old.setdefault("source", "backfill")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--tool", choices=("claude", "codex", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true", help="print results without writing")
    args = parser.parse_args()
    date.fromisoformat(args.date)

    root = Path(os.environ.get("DAILY_WORKLOG_ROOT") or (Path.home() / "meeting"))
    out_file = root / "session-log" / f"{args.date.replace('-', '')}.jsonl"
    rows = load_rows(out_file)
    by_key = {(row.get("tool"), row.get("session_id")): row for row in rows}

    records = []
    if args.tool in ("claude", "all"):
        records.extend(scan_claude(args.date))
    if args.tool in ("codex", "all"):
        records.extend(scan_codex(args.date))

    added = updated = 0
    for rec in records:
        key = (rec["tool"], rec["session_id"])
        old = by_key.get(key)
        if old is None:
            rows.append(rec)
            by_key[key] = rec
            added += 1
        else:
            merge_record(old, rec)
            updated += 1

    rows.sort(key=lambda row: (row.get("first_ts") or "", row.get("tool") or ""))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    if args.dry_run:
        print(f"\n[dry-run] {args.date}: added {added}, updated {updated}; target {out_file}")
        return

    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(out_file)
    print(f"\n{args.date}: added {added}, updated {updated} -> {out_file}")


if __name__ == "__main__":
    main()
