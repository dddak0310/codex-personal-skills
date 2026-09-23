#!/usr/bin/env python3
"""Map a GitHub issue back to the dev sessions behind the worklog page it cites.

Issues in a worklog repo almost always point at a specific daily-report page
(e.g. `20260820/05-pathogen-api-perf.html`). That page was written by the
daily-work-log skill from real Claude Code / Codex sessions, and that skill
keeps the provenance next to the report:

  ${DAILY_WORKLOG_ROOT:-~/meeting}/<YYYYMMDD>/
    data/page-sources.json      # page -> [source:session_id]   (best: per page)
    data/session-manifest.json  # every session of that day + its .jsonl path
    data/task-summaries.md      # task table, each row citing its session
    data/theme-map.md

So when an issue asks "why was it built this way / isn't this wrong", the
answer shouldn't be reconstructed from the rendered page alone — the original
session transcript says what was actually measured, tried, rejected and left
undone. This module finds those transcripts and hands them to whoever drafts
the reply.

Uses:
  # what sessions back the pages this issue cites (JSON)
  python3 worklog_sessions.py --repo owner/name --issue 1
  # same, as the prompt block the dashboard injects into 生成草稿
  python3 worklog_sessions.py --repo owner/name --issue 1 --format prompt
  # any free text instead of an issue
  python3 worklog_sessions.py --text-file some.md
  # readable dump of one session (jsonl -> user/assistant turns)
  python3 worklog_sessions.py --session e76918a4-5f84-4755-97b3-6570aae3c88d
  python3 worklog_sessions.py --session 417dbbc4 --grep worktree
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_api  # noqa: E402

CLAUDE_PROJECTS = os.path.expanduser("~/.claude/projects")
CODEX_SESSIONS = os.path.expanduser("~/.codex/sessions")

# A date-scan fallback can turn up dozens of sessions for one day; listing all
# of them would drown the draft prompt, so the prompt block shows this many and
# points at the CLI for the rest.
MAX_SESSIONS_IN_PROMPT = 12


def worklog_root():
    return os.path.expanduser(
        os.environ.get("DAILY_WORKLOG_ROOT") or "~/meeting"
    )


# `YYYYMMDD/05-pathogen-api-perf.html`, `~/meeting/YYYYMMDD/05-x.html`,
# or a bare `05-pathogen-api-perf.html` with the date mentioned elsewhere.
PAGE_RE = re.compile(r"(?:(\d{8})[/\\])?(\d{2}-[A-Za-z0-9._-]+\.html)")
# `20260820`, `2026-08-20`, `2026/08/20`
DATE_RE = re.compile(r"\b(20\d{2})[-/]?(\d{2})[-/]?(\d{2})\b")


def _date_dirs():
    root = worklog_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        d for d in os.listdir(root)
        if re.fullmatch(r"\d{8}", d) and os.path.isdir(os.path.join(root, d))
    )


def find_references(text):
    """-> [{"date": "20260820", "page": "05-x.html"|None}], deduped, in order.

    A page named without its date is matched against every date folder; a bare
    date with no page yields a whole-day reference (all that day's sessions)."""
    text = text or ""
    dirs = _date_dirs()
    refs = []
    seen = set()

    def add(date, page):
        key = (date, page)
        if date and key not in seen:
            seen.add(key)
            refs.append({"date": date, "page": page})

    for date, page in PAGE_RE.findall(text):
        if date:
            add(date, page)
            continue
        for d in dirs:  # undated page name: wherever that file actually exists
            if os.path.exists(os.path.join(worklog_root(), d, page)):
                add(d, page)

    for y, m, d in DATE_RE.findall(text):
        date = f"{y}{m}{d}"
        if date in dirs and not any(r["date"] == date for r in refs):
            add(date, None)
    return refs


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _find_transcript(source, session_id):
    """Locate a session's raw .jsonl, accepting a short id prefix."""
    if source == "codex":
        for root, _dirs, files in os.walk(CODEX_SESSIONS):
            for name in files:
                if name.endswith(".jsonl") and session_id in name:
                    return os.path.join(root, name)
        return None
    if not os.path.isdir(CLAUDE_PROJECTS):
        return None
    for proj in sorted(os.listdir(CLAUDE_PROJECTS)):
        pdir = os.path.join(CLAUDE_PROJECTS, proj)
        if not os.path.isdir(pdir):
            continue
        for name in sorted(os.listdir(pdir)):
            if name.endswith(".jsonl") and name.startswith(session_id):
                return os.path.join(pdir, name)
    return None


def _first_timestamp(path):
    try:
        with open(path, errors="replace") as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break
                try:
                    ts = json.loads(line).get("timestamp")
                except ValueError:
                    continue
                if ts:
                    return ts
    except OSError:
        pass
    return None


def _date_scan_sessions(date):
    """Fallback for reports written before session provenance existed: find
    sessions that were live on that date, by file window rather than by
    attribution. Cheap on purpose — first line's timestamp for the start,
    mtime for the end, no full parse."""
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    started, spanning = [], []

    day = os.path.join(CODEX_SESSIONS, date[:4], date[4:6], date[6:])
    if os.path.isdir(day):
        for name in sorted(os.listdir(day)):
            if name.endswith(".jsonl"):
                started.append({"source": "codex", "session_id": name[:-6],
                                "transcript": os.path.join(day, name),
                                "started_at": iso})

    if os.path.isdir(CLAUDE_PROJECTS):
        for proj in sorted(os.listdir(CLAUDE_PROJECTS)):
            pdir = os.path.join(CLAUDE_PROJECTS, proj)
            if not os.path.isdir(pdir):
                continue
            for name in sorted(os.listdir(pdir)):
                if not name.endswith(".jsonl"):
                    continue
                path = os.path.join(pdir, name)
                start = _first_timestamp(path)
                if not start:
                    continue
                end = datetime.datetime.fromtimestamp(
                    os.path.getmtime(path), datetime.timezone.utc
                ).strftime("%Y-%m-%d")
                rec = {"source": "claude", "session_id": name[:-6],
                       "transcript": path, "started_at": start, "ended_at": end}
                if start[:10] == iso:
                    started.append(rec)
                elif start[:10] < iso <= end:
                    spanning.append(rec)
    # A session that started that day is a far better candidate than one that
    # merely happened to still be open; only fall back to the latter.
    return started or spanning


def _sessions_for(date, page):
    """Sessions behind one page (or one whole day), best source first."""
    ddir = os.path.join(worklog_root(), date)
    data = os.path.join(ddir, "data")
    out = {"date": date, "page": page, "date_dir": ddir, "sessions": [],
           "provenance": None, "notes": []}
    if not os.path.isdir(ddir):
        out["notes"].append(f"{ddir} does not exist")
        return out

    if page and not os.path.exists(os.path.join(ddir, page)):
        out["notes"].append(f"page file {page} not found in {ddir}")

    manifest = _read_json(os.path.join(data, "session-manifest.json")) or {}
    by_id = {
        (s.get("source"), s.get("session_id")): s
        for s in manifest.get("sessions", [])
    }

    picked = []
    page_sources = _read_json(os.path.join(data, "page-sources.json"))
    if page and page_sources:
        pages = page_sources.get("pages", page_sources)
        entry = None
        if isinstance(pages, dict):
            entry = pages.get(page)
        elif isinstance(pages, list):
            for p in pages:
                if p.get("page") == page:
                    entry = p.get("sessions")
                    break
        if entry:
            out["provenance"] = "page-sources.json (this exact page)"
            for ref in entry:
                src, _, sid = str(ref).partition(":")
                picked.append((src or "claude", sid or src))

    if not picked and by_id:
        out["provenance"] = "session-manifest.json (all sessions of that day)"
        picked = list(by_id.keys())

    for src, sid in picked:
        meta = by_id.get((src, sid), {})
        path = meta.get("source_file")
        if not path or not os.path.exists(path):
            path = _find_transcript(src, sid)
        out["sessions"].append({
            "source": src,
            "session_id": sid,
            "transcript": path,
            "started_at": meta.get("started_at"),
            "ended_at": meta.get("ended_at"),
            "turn_count": meta.get("turn_count"),
            "cwd": meta.get("cwd"),
        })

    if not out["sessions"]:
        scanned = _date_scan_sessions(date)
        if scanned:
            out["provenance"] = (
                "date scan — this report predates session provenance, so these "
                "are the sessions that were merely LIVE on that date, not ones "
                "confirmed to back this page; check each before trusting it"
            )
            out["sessions"] = scanned
        else:
            out["notes"].append(
                "no page-sources.json / session-manifest.json for this date and "
                "no session files found for it"
            )

    out["digests"] = [
        os.path.join(data, name)
        for name in ("task-summaries.md", "theme-map.md")
        if os.path.exists(os.path.join(data, name))
    ]
    return out


def resolve(text):
    """Full lookup for a blob of issue text.

    Pages of the same date that end up resolving to the same session list
    (the usual case when the fallbacks kick in) are merged into one record, so
    citing three pages of one day doesn't repeat the same 50 sessions."""
    records = []
    for ref in find_references(text):
        rec = _sessions_for(ref["date"], ref["page"])
        ids = [(s["source"], s["session_id"]) for s in rec["sessions"]]
        for prev in records:
            prev_ids = [(s["source"], s["session_id"]) for s in prev["sessions"]]
            if prev["date"] == rec["date"] and prev_ids == ids:
                if rec["page"] and rec["page"] not in prev["pages"]:
                    prev["pages"].append(rec["page"])
                prev["notes"] += [n for n in rec["notes"] if n not in prev["notes"]]
                break
        else:
            rec["pages"] = [rec["page"]] if rec["page"] else []
            records.append(rec)
    for rec in records:
        rec.pop("page", None)
    return records


def issue_text(issue):
    parts = [issue.get("title") or "", issue.get("body") or ""]
    for c in issue.get("comments_detail") or []:
        parts.append(c.get("body") or "")
    return "\n".join(parts)


# ------------------------------------------------------------- prompt section

def build_prompt_lines(text, this_script=None):
    """Lines to inject into the 生成草稿 prompt; [] when nothing is traceable
    (so an issue that cites no worklog page is unaffected)."""
    records = [r for r in resolve(text) if r["sessions"] or r["digests"]]
    if not records:
        return []
    this_script = this_script or os.path.abspath(__file__)

    lines = [
        "DEVELOPMENT HISTORY IS AVAILABLE FOR THIS ISSUE. The worklog page(s) "
        "this issue cites were written from real development sessions, and "
        "those raw transcripts are on this machine:",
        "",
    ]
    for rec in records:
        pages = ", ".join(rec["pages"]) if rec["pages"] else "(whole day)"
        lines.append(f"- {rec['date']}: {pages}   [report dir: {rec['date_dir']}]")
        if rec["provenance"]:
            lines.append(f"  sessions via {rec['provenance']}:")
        for s in rec["sessions"][:MAX_SESSIONS_IN_PROMPT]:
            when = " ".join(str(x) for x in (s.get("started_at"), s.get("ended_at")) if x)
            turns = f", {s['turn_count']} turns" if s.get("turn_count") else ""
            lines.append(
                f"    - {s['source']} {s['session_id']}"
                + (f" ({when}{turns})" if when else "")
            )
            lines.append(f"      transcript: {s['transcript'] or 'NOT FOUND on disk'}")
        rest = rec["sessions"][MAX_SESSIONS_IN_PROMPT:]
        if rest:
            dirs = sorted({os.path.dirname(s["transcript"]) for s in rest
                           if s.get("transcript")})
            lines.append(
                f"    - …and {len(rest)} more session(s) that day, under "
                + ", ".join(dirs or ["(paths unresolved)"])
                + " — grep there to find the relevant ones"
            )
        for d in rec["digests"]:
            lines.append(f"  digest: {d}")
        for n in rec["notes"]:
            lines.append(f"  note: {n}")
    lines += [
        "",
        "Before writing the reply, reconstruct what actually happened during "
        "that development — do not answer from the rendered page alone, and do "
        "not guess. Read the page HTML, then the digests (task-summaries.md / "
        "theme-map.md are short — start there), then go into the raw session "
        "transcripts for the details that matter to this issue.",
        "",
        "The transcripts are large JSONL files. Do NOT read one end to end. "
        "When several sessions are listed, first narrow down which ones are "
        "even about this issue — grep the directory for the terms the issue "
        "uses (a file name, a function, a number) and only open the files that "
        "hit. Then dump a readable user/assistant view of one session with:",
        f"    python3 {this_script} --session <session_id> --grep <keyword>",
        "(omit --grep for the whole conversation; add --max-chars to trim long turns).",
        "",
        "Use that history to work out which of these the issue actually is, "
        "and let that decide what the reply says:",
        "  (a) the question is aimed at the wrong thing — the page's wording, "
        "or a number in it, led the reader somewhere the actual work didn't go "
        "(e.g. they're optimizing a step that wasn't the cost, or assuming a "
        "design that was already ruled out during development). Say what was "
        "really done and why, and correct the premise directly instead of "
        "answering the question as literally asked.",
        "  (b) it's a real gap — the transcript shows the thing genuinely "
        "wasn't handled, was deferred, was left as a known open item, or was "
        "done in a way that doesn't hold up under what the issue points out. "
        "Acknowledge it plainly, say what the current behavior is and what "
        "would have to change; do not defend it.",
        "  (c) the transcript doesn't settle it. Say which part is unclear and "
        "what would answer it — don't manufacture a confident answer.",
        "",
        "Ground the reply in specifics found there (measured numbers, commit "
        "hashes, file paths, options that were tried and dropped) rather than "
        "in general reasoning. But do NOT narrate your research, cite session "
        "ids, or mention transcripts/worklog data files in the reply — those "
        "are internal; the reader sees only the answer and its evidence.",
        "",
    ]
    return lines


# ------------------------------------------------------------ transcript dump

def _turns(path):
    out = []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                ts = obj.get("timestamp") or ""
                role = text = None
                if obj.get("type") in ("user", "assistant"):  # claude code
                    role = obj["type"]
                    content = (obj.get("message") or {}).get("content")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = "".join(
                            c.get("text", "") for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                elif obj.get("type") == "response_item":  # codex
                    payload = obj.get("payload") or {}
                    if payload.get("type") == "message" and payload.get("role") in (
                        "user", "assistant"
                    ):
                        role = payload["role"]
                        text = "".join(
                            c.get("text", "") for c in payload.get("content", [])
                            if isinstance(c, dict)
                            and c.get("type") in ("input_text", "text", "output_text")
                        )
                if not role or not text:
                    continue
                text = text.strip()
                if not text or text.startswith(("<", "Caveat:", "# AGENTS.md")):
                    continue
                out.append((ts, role, text))
    except OSError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
    return out


def dump_session(session_id, grep=None, max_chars=4000, context=1):
    path = _find_transcript("claude", session_id) or _find_transcript("codex", session_id)
    if not path:
        print(f"[ERROR] no transcript found for session id {session_id}", file=sys.stderr)
        return 1
    turns = _turns(path)
    print(f"# session {session_id}\n# file {path}\n# {len(turns)} text turns\n")
    keep = range(len(turns))
    if grep:
        rx = re.compile(grep, re.I)
        hits = [i for i, (_, _, t) in enumerate(turns) if rx.search(t)]
        if not hits:
            print(f"(no turn matches /{grep}/)")
            return 0
        wanted = sorted({j for i in hits for j in range(max(0, i - context),
                                                       min(len(turns), i + context + 1))})
        keep = wanted
    prev = None
    for i in keep:
        if prev is not None and i != prev + 1:
            print("...\n")
        ts, role, text = turns[i]
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n…[truncated, {len(text)} chars total]"
        print(f"[{ts}] {role}:\n{text}\n")
        prev = i
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo")
    ap.add_argument("--issue", type=int, help="issue number (looked up on disk)")
    ap.add_argument("--state", help="state folder of --issue; searched if omitted")
    ap.add_argument("--text-file", help="resolve references in this file instead")
    ap.add_argument("--format", choices=("json", "prompt"), default="json")
    ap.add_argument("--session", help="dump one session transcript, readable")
    ap.add_argument("--grep", help="with --session: only turns matching this regex")
    ap.add_argument("--context", type=int, default=1, help="turns around each --grep hit")
    ap.add_argument("--max-chars", type=int, default=4000, help="per-turn truncation")
    args = ap.parse_args()

    if args.session:
        return dump_session(args.session, args.grep, args.max_chars, args.context)

    if args.text_file:
        with open(args.text_file) as f:
            text = f.read()
    elif args.issue:
        repo = gh_api.resolve_repo(args.repo)
        state = args.state or gh_api.find_issue_state(repo, args.issue)
        if not state:
            print(f"[ERROR] issue #{args.issue} not found locally for {repo}",
                  file=sys.stderr)
            return 2
        with open(gh_api.issue_json_path(repo, state, args.issue)) as f:
            text = issue_text(json.load(f))
    else:
        text = sys.stdin.read()

    if args.format == "prompt":
        lines = build_prompt_lines(text)
        print("\n".join(lines) if lines
              else "(no worklog page reference found in this text)")
    else:
        print(json.dumps(resolve(text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
