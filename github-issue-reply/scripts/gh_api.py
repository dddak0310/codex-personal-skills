#!/usr/bin/env python3
"""Thin GitHub REST API helper — stdlib only, no extra deps.

Token/repo resolution order:
  1. explicit --token / --repo CLI args (handled by the calling script)
  2. GITHUB_TOKEN / GITHUB_DEFAULT_REPO / GITHUB_LOGIN / ANTHROPIC_API_KEY /
     CLAUDE_CODE_OAUTH_TOKEN env vars
  3. this skill's own .env (same keys), same convention as apgpas-query's
     db_conn.py: tracked in the shared skills repo, but the bare ".env" name is
     repo-gitignored, so it never leaves this developer's own clone.

ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN here are unrelated to GitHub —
only used by dashboard_server.py to authenticate its `claude -p` calls
(generate-draft). They are NOT interchangeable: a real Anthropic Console API
key (starts `sk-ant-api...`) goes in ANTHROPIC_API_KEY; the long-lived token
`claude setup-token` prints (starts `sk-ant-oat...`) MUST go in
CLAUDE_CODE_OAUTH_TOKEN instead — passing an oat-token as ANTHROPIC_API_KEY
gets a clean "401 API key is invalid" from the API, verified empirically.
See SKILL.md ## 3.
"""
import datetime
import json
import os
import shutil
import urllib.error
import urllib.request

_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
API_ROOT = "https://api.github.com"

# Fixed local output root — one place per user, organized <repo>/<state>/<N>/issue.json.
OUTPUT_ROOT = os.path.expanduser("~/github-issue")

STATES = ("awaiting_reply", "replied", "closed")


def _load_env():
    """Parse this skill's .env into a dict. Shell env vars of the same name
    take precedence (same rule as apgpas-query's db_conn.py)."""
    values = {}
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    for key in (
        "GITHUB_TOKEN",
        "GITHUB_DEFAULT_REPO",
        "GITHUB_LOGIN",
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
    ):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def resolve_token(explicit=None):
    if explicit:
        return explicit
    token = _load_env().get("GITHUB_TOKEN")
    if not token:
        raise SystemExit(
            "No GitHub token found. Run scripts/install.sh first, "
            "or pass --token, or set GITHUB_TOKEN."
        )
    return token


def resolve_claude_cli_env():
    """Optional env overrides for dashboard_server.py's `claude -p` subprocess
    calls — {"ANTHROPIC_API_KEY": ...} and/or {"CLAUDE_CODE_OAUTH_TOKEN": ...},
    whichever are configured (empty dict if neither — that's fine, it just
    means `claude -p` falls back to `claude setup-token`'s stored credentials
    or the interactive login state). Only forwards these two specific keys;
    never leaks the rest of .env into the subprocess beyond what it already
    inherits from the parent process's own environment."""
    env = _load_env()
    return {
        k: env[k] for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN") if env.get(k)
    }


def resolve_login(token, explicit=None):
    """The authenticated GitHub username, used to tell 'awaiting my reply' from
    'I already replied'. Cached in .env (written by install.sh) to avoid an
    extra API call every run; falls back to a live /user lookup."""
    if explicit:
        return explicit
    login = _load_env().get("GITHUB_LOGIN")
    if login:
        return login
    return _request("GET", "/user", token)["login"]


def resolve_repo(explicit=None):
    if explicit:
        return explicit
    repo = _load_env().get("GITHUB_DEFAULT_REPO")
    if not repo:
        raise SystemExit(
            "No repo specified and no default repo configured. "
            "Pass --repo owner/name or run scripts/install.sh to set a default."
        )
    return repo


def _request(method, path, token, body=None):
    url = f"{API_ROOT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"GitHub API error {e.code} on {method} {path}: {detail}")


def list_issues(repo, token, state="open"):
    # Note: GitHub's issues endpoint also returns PRs; filter those out.
    issues = []
    page = 1
    while True:
        batch = _request(
            "GET",
            f"/repos/{repo}/issues?state={state}&per_page=100&page={page}",
            token,
        )
        if not batch:
            break
        issues.extend(i for i in batch if "pull_request" not in i)
        if len(batch) < 100:
            break
        page += 1
    return issues


def get_issue(repo, number, token):
    issue = _request("GET", f"/repos/{repo}/issues/{number}", token)
    comments = _request("GET", f"/repos/{repo}/issues/{number}/comments", token)
    issue["comments_detail"] = comments
    return issue


def post_comment(repo, number, body, token):
    return _request(
        "POST", f"/repos/{repo}/issues/{number}/comments", token, body={"body": body}
    )


def close_issue(repo, number, token):
    return _request(
        "PATCH", f"/repos/{repo}/issues/{number}", token, body={"state": "closed"}
    )


def reopen_issue(repo, number, token):
    return _request(
        "PATCH", f"/repos/{repo}/issues/{number}", token, body={"state": "open"}
    )


def classify_state(issue, login):
    """awaiting_reply = open and the last comment (or the issue itself, if no
    comments) is NOT from me -> I owe a reply.
    replied = open and I posted the last comment.
    closed = issue is closed, regardless of who spoke last."""
    if issue.get("state") == "closed":
        return "closed"
    comments = issue.get("comments_detail") or []
    last_author = comments[-1]["user"]["login"] if comments else issue["user"]["login"]
    return "replied" if last_author == login else "awaiting_reply"


def repo_dir(repo):
    return os.path.join(OUTPUT_ROOT, repo.replace("/", "-"))


def state_dir(repo, state):
    return os.path.join(repo_dir(repo), state)


def issue_dir(repo, state, number):
    """Everything about one issue lives under its own folder — <state>/<N>/
    — instead of flat <N>_* files in <state>/, so a directory listing for a
    repo/state with many issues stays short (one entry per issue), and
    reclassifying an issue to a different state is a single folder move
    instead of moving each file individually."""
    return os.path.join(state_dir(repo, state), str(number))


def issue_json_path(repo, state, number):
    return os.path.join(issue_dir(repo, state, number), "issue.json")


def draft_path(repo, state, number):
    return os.path.join(issue_dir(repo, state, number), "draft.md")


def assets_dir(repo, state, number):
    """Where images embedded in an issue's draft (via the dashboard's
    upload-image endpoint) are stored, alongside its issue.json."""
    return os.path.join(issue_dir(repo, state, number), "assets")


def questions_path(repo, state, number):
    """The issue's questions broken down into a numbered list — output of the
    dashboard's 拆解問題 step, kept separate from the draft reply itself so
    decomposing and drafting are two independent, independently-rerunnable
    generate-draft calls."""
    return os.path.join(issue_dir(repo, state, number), "questions.md")


def generate_log_path(repo, state, number):
    """ONE cumulative record per issue of every AI attempt of every kind —
    draft and questions alike — each entry carrying its own kind, the exact
    prompt that was sent, the hint (if any), model, exit code and raw
    stdout/stderr. Previously this was four files (generate.json,
    questions_generate.json, prompt.txt, questions_prompt.txt); folding them
    into one keeps an issue folder readable, and keeps every prompt (not just
    the most recent one, which is all a single prompt.txt could hold) next to
    the output it produced. A JSON array, oldest entry first;
    append_generate_log() is the only writer, so it stays a valid array."""
    return os.path.join(issue_dir(repo, state, number), "generate.json")


_LEGACY_LOGS = (("generate.json", "draft"), ("questions_generate.json", "questions"))
_LEGACY_PROMPTS = (("prompt.txt", "draft"), ("questions_prompt.txt", "questions"))


def _migrate_generate_files(repo, state, number):
    """Fold pre-merge folders into the single generate.json above: tag each
    old entry with its kind, attach each old prompt file to the newest entry
    of its kind that has no prompt recorded (those files only ever held the
    most recent prompt, so older entries genuinely have none to recover), then
    delete the leftovers. Idempotent — a folder with nothing legacy in it is
    untouched."""
    folder = issue_dir(repo, state, number)
    if not any(
        os.path.exists(os.path.join(folder, name))
        for name, _ in _LEGACY_PROMPTS
    ) and not os.path.exists(os.path.join(folder, "questions_generate.json")):
        return  # nothing legacy left, and generate.json (if any) is already merged

    entries = []
    for name, kind in _LEGACY_LOGS:
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for entry in existing if isinstance(existing, list) else [existing]:
            entry.setdefault("kind", kind)
            entries.append(entry)

    for name, kind in _LEGACY_PROMPTS:
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                prompt = f.read()
        except OSError:
            continue
        for entry in reversed(entries):
            if entry.get("kind") == kind and not entry.get("prompt"):
                entry["prompt"] = prompt
                break
        os.remove(path)

    entries.sort(key=lambda e: e.get("timestamp") or "")
    with open(os.path.join(folder, "generate.json"), "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    legacy_questions_log = os.path.join(folder, "questions_generate.json")
    if os.path.exists(legacy_questions_log):
        os.remove(legacy_questions_log)


def read_generate_log(repo, state, number):
    """Every attempt for this issue, oldest first. Migrates a pre-merge folder
    on the way past."""
    _migrate_generate_files(repo, state, number)
    path = generate_log_path(repo, state, number)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []  # unreadable/corrupt — treat as no history rather than crash
    return existing if isinstance(existing, list) else [existing]


def append_generate_log(repo, state, number, entry):
    """Append one AI attempt (entry["kind"] says which) to generate.json.
    Never drops prior entries."""
    history = read_generate_log(repo, state, number)
    history.append(entry)
    path = generate_log_path(repo, state, number)
    with open(path, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    return path


def last_draft_settings(repo, state, number):
    """What the last 生成草稿 for this issue was told to do — the 額外提示 and
    whether the questions list was set as the primary basis — read back out of
    the log so the dashboard's hint box and checkbox survive a reload without
    a file of their own. Each is taken from the most recent draft attempt that
    actually recorded it, so a later run that left one blank doesn't erase the
    other."""
    hint, questions_primary = "", None
    for entry in reversed(read_generate_log(repo, state, number)):
        if entry.get("kind", "draft") != "draft":
            continue
        if not hint and (entry.get("hint") or "").strip():
            hint = entry["hint"]
        if questions_primary is None and entry.get("questions_primary") is not None:
            questions_primary = entry["questions_primary"]
        if hint and questions_primary is not None:
            break
    return {"hint": hint, "questions_primary": bool(questions_primary)}


def manual_state_path(repo, state, number):
    """A state you set by hand in the dashboard (擱置成已回覆 / 丟回未回覆),
    overriding what classify_state would derive from who spoke last. Lives
    inside the issue's own folder, so it travels with a folder move like every
    other per-issue file."""
    return os.path.join(issue_dir(repo, state, number), "manual_state.json")


def last_comment_id(issue):
    """Identifies 'the conversation as it stood' when a manual state was set —
    a manual override only holds while this is unchanged. None = no comments
    yet (just the issue body)."""
    comments = issue.get("comments_detail") or []
    return comments[-1]["id"] if comments else None


def read_manual_state(repo, number):
    """(state, marker_dict) for the issue's manual override, or (None, None).
    Looks wherever the issue currently lives."""
    state = find_issue_state(repo, number)
    if not state:
        return None, None
    path = manual_state_path(repo, state, number)
    if not os.path.exists(path):
        return None, None
    try:
        with open(path) as f:
            marker = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None, None
    return marker.get("state"), marker


def clear_manual_state(repo, number):
    state = find_issue_state(repo, number)
    if not state:
        return
    path = manual_state_path(repo, state, number)
    if os.path.exists(path):
        os.remove(path)


def set_manual_state(repo, number, new_state, issue):
    """Pin an open issue to awaiting_reply/replied by hand and move its folder
    there. The marker records the comment the thread ended on, so the next sync
    drops the override as soon as someone says something new."""
    if new_state not in ("awaiting_reply", "replied"):
        raise ValueError(f"cannot manually set state to {new_state!r}")
    old_state = find_issue_state(repo, number)
    if not old_state:
        raise ValueError(f"issue #{number} not found locally")

    dest_dir = issue_dir(repo, new_state, number)
    if old_state != new_state:
        os.makedirs(state_dir(repo, new_state), exist_ok=True)
        shutil.move(issue_dir(repo, old_state, number), dest_dir)

    marker = {
        "state": new_state,
        "last_comment_id": last_comment_id(issue),
        "marked_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open(manual_state_path(repo, new_state, number), "w") as f:
        json.dump(marker, f, indent=2, ensure_ascii=False)
    return new_state


def find_issue_state(repo, number):
    """Which state dir an issue's <N>/issue.json currently lives under (it
    may have moved since the last sync). None if never synced."""
    for state in STATES:
        if os.path.exists(issue_json_path(repo, state, number)):
            return state
    return None


def file_issue(repo, issue, login):
    """Write/update an issue's issue.json under its classified state dir
    (<state>/<N>/issue.json). If it previously lived under a different
    state, MOVE the whole <N>/ folder in one go — draft.md, assets/,
    prompt.txt, generate.json, questions.md, everything travels together
    automatically, nothing to enumerate here.

    A manual override (manual_state.json, set from the dashboard) wins over
    classify_state while the thread hasn't moved on — as soon as there's a new
    last comment, or the issue closes, the marker is dropped and automatic
    classification takes over again."""
    state = classify_state(issue, login)
    number = issue["number"]

    manual, marker = read_manual_state(repo, number)
    if manual:
        if state == "closed" or marker.get("last_comment_id") != last_comment_id(issue):
            clear_manual_state(repo, number)  # stale — the conversation moved on
        else:
            state = manual

    dest_dir = issue_dir(repo, state, number)

    old_state = find_issue_state(repo, number)
    if old_state and old_state != state:
        old_dir = issue_dir(repo, old_state, number)
        os.makedirs(state_dir(repo, state), exist_ok=True)
        shutil.move(old_dir, dest_dir)
    else:
        os.makedirs(dest_dir, exist_ok=True)

    dest = issue_json_path(repo, state, number)
    with open(dest, "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)
    return state, dest
