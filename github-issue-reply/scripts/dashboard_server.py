#!/usr/bin/env python3
"""Local dashboard for github-issue-reply: browse awaiting_reply/replied/closed
issues for one repo, generate/edit/send drafts, and close replied issues —
all from a single-repo local web UI. stdlib only (http.server), no framework.

THIS IS THE ONLY PART OF THE SKILL WHERE A CLICK, NOT A CHAT CONFIRMATION,
SENDS SOMETHING TO GITHUB: checking boxes + pressing "發送回覆" / "Close"
IS the confirmation in this UI — same weight as the verbal confirmation the
chat-driven workflow (SKILL.md ## 2) requires, just a different surface.
There is no second prompt once you click.

Binds 127.0.0.1 by default. This server has NO authentication of its own —
its POST endpoints really do post comments / close issues using your GitHub
token — so exposing it beyond localhost lets anyone who can reach the port
do that with your identity. Pass --bind 0.0.0.0 only if you accept that.

"生成草稿"/"拆解問題" call one of two AI backends, chosen with --ai-backend
(default "claude"):

  claude — shells out to the local `claude` CLI in one-shot print mode
    (`claude -p --model <model> ... --output-format text`), which needs its
    own authentication independent of this skill's GitHub token — set ONE
    of these in this skill's own .env (same file as GITHUB_TOKEN) or as a
    shell env var:
      ANTHROPIC_API_KEY=sk-ant-api...    a real Anthropic Console API key
      CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...   what `claude setup-token` prints
    These are NOT interchangeable — an oat-token passed as ANTHROPIC_API_KEY
    fails with a clean "401 API key is invalid", verified empirically.
    Gets a read-only tool allowlist by default (--allowedTools "Read Grep
    Glob Skill") so it can ground replies in real files/skills instead of
    only the prompt text.

  codex — shells out to `codex exec` (OpenAI Codex CLI), with
    `--sandbox read-only` (override via --codex-sandbox) for the same
    unattended-safety reason, and `--output-last-message <tmpfile>` to get
    a clean response instead of parsing its verbose transcript stdout.
    Needs its own separate auth (`codex login`) — unrelated to both the
    GitHub token and whatever authenticates the claude backend. No
    Read/Grep/Glob/Skill-style tool allowlist exists for codex (its
    permission model is sandbox-mode based, not per-tool), so it has no
    access to this skill's other skills the way the claude backend does.

If the chosen backend isn't authenticated, generate-draft/拆解問題 fails
per-issue with whatever error it reports — the rest of the batch still
proceeds. Every attempt of either kind (success or failure) is appended to
the issue's single <N>/generate.json — a JSON array, one entry per attempt:
timestamp, kind ("draft"/"questions"), backend, model, hint, the exact prompt
sent, exit_code, success, stdout, stderr — so you can see exactly what was
asked and what came back without a separate prompt file per step.

When an issue cites a daily worklog page, 生成草稿's prompt also carries the
dev sessions that page was written from (worklog_sessions.py: page-sources.json
-> session-manifest.json -> date scan) plus the instruction to judge, against
that history, whether the issue is aimed at the wrong thing or found a real
gap. Disable with --no-session-context.

Usage:
  dashboard_server.py [--repo owner/name] [--port 8765] [--bind 127.0.0.1]
    [--ai-backend claude|codex] [--model sonnet]
    [--allowed-tools "Read Grep Glob Skill"] [--codex-sandbox read-only]
    [--claude-cwd ~] [--worklog-root ~/meeting] [--no-session-context]
"""
import argparse
import base64
import datetime
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_issues  # noqa: E402
import gh_api  # noqa: E402
import worklog_sessions  # noqa: E402

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "dashboard.html",
)

# Set once in main() — this dashboard serves exactly one repo per process.
REPO = None
TOKEN = None
LOGIN = None
MODEL = None  # None means "let the backend pick its own default" (only claude forces one)
CLAUDE_CLI_ENV = {}  # optional {"ANTHROPIC_API_KEY": ...} / {"CLAUDE_CODE_OAUTH_TOKEN": ...}
ALLOWED_TOOLS = "Read Grep Glob Skill"  # read-only allowlist for the unattended claude -p call
CLAUDE_CWD = os.path.expanduser("~")  # where the AI backend looks for repo/worklog files
CLAUDE_TIMEOUT = 300  # seconds; tool use + a longer questions list can genuinely take a while
AI_BACKEND = "claude"  # "claude" (claude -p) or "codex" (codex exec)
SESSION_CONTEXT = True  # look the cited worklog page's dev sessions up for 生成草稿
CODEX_SANDBOX = "read-only"  # codex exec --sandbox; same unattended-safety intent as ALLOWED_TOOLS

# A full sync walks every issue; serialize it so a double-clicked 重新抓取
# (or a click racing the hourly cron's own run) can't have two passes moving
# the same <N>/ folders between state dirs at once.
FETCH_LOCK = threading.Lock()


def _read_if_exists(path):
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def _resolve_backend_model(payload):
    """backend/model default to the server's --ai-backend/--model unless a
    request explicitly overrides them (the dashboard's per-click AI/model
    picker); an explicit backend switch without an explicit model gets that
    backend's own sensible default, not the other backend's."""
    backend = payload.get("backend") or AI_BACKEND
    model = payload.get("model")
    if not model:
        model = MODEL if backend == AI_BACKEND else ("sonnet" if backend == "claude" else None)
    return backend, model


def _issue_summary(state, number):
    with open(gh_api.issue_json_path(REPO, state, number)) as f:
        issue = json.load(f)
    last = gh_api.last_draft_settings(REPO, state, number)
    draft = _read_if_exists(gh_api.draft_path(REPO, state, number))
    questions = _read_if_exists(gh_api.questions_path(REPO, state, number))
    return {
        "number": issue["number"],
        "title": issue["title"],
        "html_url": issue["html_url"],
        "body": issue.get("body") or "",
        "comments": [
            {"login": c["user"]["login"], "body": c["body"]}
            for c in issue.get("comments_detail") or []
        ],
        "draft": draft,
        "has_draft": bool(draft.strip()),
        "questions": questions,
        "has_questions": bool(questions.strip()),
        # what the last draft run here was told to do, recovered from
        # generate.json so these survive a reload without files of their own
        "hint": last["hint"],
        "questions_primary": last["questions_primary"],
        # true = this pile was chosen by hand, not derived from who spoke last
        "manual_state": os.path.exists(gh_api.manual_state_path(REPO, state, number)),
    }


def _numbers_in(state):
    """Issue numbers filed under this state — one subfolder per issue
    (<state>/<N>/issue.json), so this lists subfolder names, not filenames."""
    d = gh_api.state_dir(REPO, state)
    if not os.path.isdir(d):
        return []
    numbers = []
    for name in os.listdir(d):
        if name.isdigit() and os.path.exists(os.path.join(d, name, "issue.json")):
            numbers.append(int(name))
    return sorted(numbers)


def _collect_data():
    return {
        "repo": REPO,
        "states": {
            state: [_issue_summary(state, n) for n in _numbers_in(state)]
            for state in gh_api.STATES
        },
    }


def _issue_context_lines(issue, task, include_title=True):
    """Header shared by both prompts: task framing + title/body/comment thread."""
    lines = [f"{task} GitHub issue #{issue['number']} in {REPO}."]
    if include_title:
        lines.append(f"Title: {issue['title']}")
    lines += [
        "",
        "Issue body:",
        issue.get("body") or "(no body)",
    ]
    comments = issue.get("comments_detail") or []
    if comments:
        lines.append("")
        lines.append("Existing comments:")
        for c in comments:
            lines.append(f"- {c['user']['login']}: {c['body']}")
    return lines


def _tool_reading_note():
    if not ALLOWED_TOOLS:
        return []
    return [
        "If the issue references specific files, code, or docs (e.g. a worklog "
        "page, a source path) and you have file-reading tools available, read "
        "them for grounding before answering instead of guessing at their "
        "content. Don't speculate about what a referenced file says if you can "
        "just read it.",
        "",
    ]


def _can_read_files():
    """Both backends can read local files — claude only if its allowlist wasn't
    emptied, codex under its read-only sandbox."""
    return AI_BACKEND != "claude" or bool(ALLOWED_TOOLS)


def _session_context_lines(issue):
    """Worklog pages cited by this issue -> the dev sessions behind them, plus
    the instruction to judge the issue against what actually happened. Empty
    when the issue cites no page, when the lookup finds nothing, or when the
    backend can't read files anyway."""
    if not SESSION_CONTEXT or not _can_read_files():
        return []
    try:
        return worklog_sessions.build_prompt_lines(worklog_sessions.issue_text(issue))
    except Exception as exc:  # never let provenance lookup break drafting
        sys.stderr.write(f"[worklog_sessions] lookup failed: {exc}\n")
        return []


def _build_questions_prompt(issue):
    """拆解問題 step: just the breakdown, not an answer."""
    lines = _issue_context_lines(
        issue, "You are breaking down the question(s) in", include_title=False
    )
    lines.append("")
    lines += _tool_reading_note()
    lines.append(
        "Break down the distinct question(s)/request(s) this issue is actually "
        "raising. Err on the side of splitting rather than merging: when a "
        "sentence bundles multiple clauses, sub-points, or asks together (e.g. "
        "\"why is X so large, and can it be filtered\"), treat each clause as "
        "its own item unless they are unmistakably restating the same single "
        "ask. You can't know in advance which clause is the one that actually "
        "needs a careful answer or where the reply is most likely to go wrong, "
        "so don't fold a clause into another item just because it looks like "
        "'supporting detail' or context — surface it as its own item so it "
        "can't be silently skipped. This applies even when a clause is phrased "
        "as a declarative statement rather than a question — a claim, "
        "expectation, or objection (e.g. \"the amount being processed shouldn't "
        "be at this scale\") is its own answerable item if someone could confirm "
        "or refute it on its own, even though it isn't phrased with a question "
        "mark and even if it reads like it's just building up to the next "
        "sentence's question. Don't fold it in as 'context' or 'the reason for' "
        "another item just because it precedes or motivates that item in the "
        "text. Only merge two clauses into one item when they are clearly the "
        "same request phrased twice, not merely related or sitting in the same "
        "sentence — the narrow case for this is when answering one clause "
        "would already fully answer the other, with literally nothing left "
        "for the second item to add (e.g. one clause states an expectation "
        "and the very next clause just asks to confirm that exact same "
        "expectation). This is a narrow exception, not a license to "
        "second-guess the split-by-default rule above — when it's not that "
        "clear-cut, keep them separate. When in doubt, split rather than "
        "merge. List them in the SAME ORDER "
        "they appear in the issue body, top to bottom — do not regroup or reorder "
        "by topic/logical relatedness; whoever wrote the issue will reply following "
        "the list in order, so the order must match how they laid out their own "
        "points, not a reorganized version of it. Your ENTIRE final text output "
        "must be ONLY a numbered Markdown list, one item per question/request, "
        "phrased concretely enough that someone could answer each item without "
        "re-reading the issue. Do not write/save the list to any file — output it "
        "directly as your response. No preamble, no answers, no meta-commentary, no "
        "description of what you did — just the list itself."
    )
    return "\n".join(lines)


def _build_prompt(issue, hint=None, questions=None, questions_primary=False):
    """questions_primary flips which side leads when both a hint and a
    questions list exist: False (default) = the hint drives the reply and the
    list is background; True = every item in the list must be answered and the
    hint only steers how."""
    has_hint = bool(hint and hint.strip())
    has_questions = bool(questions and questions.strip())
    lines = _issue_context_lines(issue, "You are drafting a reply to")
    lines.append("")
    lines += _tool_reading_note()
    lines += _session_context_lines(issue)

    if has_questions:
        lines.append("The issue's questions/requests have already been broken down:")
        lines.append(questions.strip())
        lines.append("")

    if has_questions and questions_primary:
        lines.append(
            "Address every item in that list in turn — don't skip or merge any of "
            "them into a vague general answer. The list is what this reply must "
            "cover; it is not optional background."
        )
        if has_hint:
            lines.append("")
            lines.append(
                "The user also left this instruction. Treat it as guidance on HOW to "
                "answer (angle, emphasis, tone, what to include or leave out), not as "
                "a replacement for the list — every item above still has to be "
                "answered:"
            )
            lines.append(hint.strip())
    elif has_hint:
        # The hint is the primary basis for this reply when given — the issue
        # body/comments/questions above are background the user may or may not
        # want drawn on, not a checklist that must be worked through.
        lines.append(
            "The reply's content and direction must be driven PRIMARILY by this "
            "instruction from the user:"
        )
        lines.append(hint.strip())
        lines.append("")
        lines.append(
            "Everything above (issue body, comments, the broken-down questions list "
            "if present) is supporting background only. You do NOT need to address "
            "every item in that list, or even use it at all, if it isn't relevant to "
            "what the instruction above asks for — follow the instruction above as "
            "the main basis for what you write, and draw on the background only "
            "where it actually helps."
        )
    elif has_questions:
        lines.append(
            "Address every item in that list in turn — don't skip or merge any of "
            "them into a vague general answer."
        )
    else:
        lines.append(
            "First break down the question(s)/request(s) the issue is actually raising "
            "(an issue often bundles more than one), then address each one in turn — "
            "don't skip or merge any of them into a vague general answer."
        )
    lines.append("")
    lines.append(
        "Write a reply comment that directly addresses the question/issue above. "
        "Your ENTIRE final text output must be nothing but that comment's literal "
        "Markdown body — GitHub posts it as-is. Do not write, save, or create any "
        "file with the reply text; do not describe what you did or plan to do; do "
        "not say things like \"I've read X\" / \"drafted a reply\" / \"saved at\" / "
        "\"let me know if\" / \"I have not posted it\" — none of that is part of the "
        "comment and none of it belongs in your output. If your research turned up "
        "findings, weave them directly into the answer's content, don't report on "
        "having done the research. Output raw Markdown directly — do NOT wrap the "
        "whole reply in a ``` code fence; GitHub renders the comment body as "
        "Markdown already, so a wrapping fence would make the whole thing display "
        "as literal unformatted text."
    )
    return "\n".join(lines)


_WRAPPING_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```\s*$", re.S)


def _strip_wrapping_fence(text):
    """Defensive cleanup: some models wrap the whole reply in a ``` fence
    despite being told not to. If the ENTIRE draft is one fenced block (not
    just a fence somewhere inside real content), unwrap it — otherwise GitHub
    would render the whole comment as literal text instead of Markdown."""
    match = _WRAPPING_FENCE_RE.match(text.strip())
    return match.group(1) if match else text


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep stdout quiet; exceptions still surface via _send_json errors

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def _serve_file(self, path, content_type):
        if not os.path.exists(path):
            self.send_error(404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_asset(self, path):
        # path is "/assets/<state>/<number>/<filename>" ->
        # split("/") = ["", "assets", "<state>", "<number>", "<filename>"]
        parts = path.split("/")
        if len(parts) != 5 or parts[2] not in gh_api.STATES or not parts[3].isdigit():
            self.send_error(404)
            return
        state, number = parts[2], int(parts[3])
        filename = os.path.basename(urllib.parse.unquote(parts[4]))
        full = os.path.join(gh_api.assets_dir(REPO, state, number), filename)
        ctype = "image/png"
        lower = filename.lower()
        for ext, mime in (
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/gif"),
            (".webp", "image/webp"),
            (".svg", "image/svg+xml"),
        ):
            if lower.endswith(ext):
                ctype = mime
                break
        self._serve_file(full, ctype)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(TEMPLATE_PATH, "text/html; charset=utf-8")
        elif parsed.path == "/api/data":
            self._send_json(_collect_data())
        elif parsed.path.startswith("/assets/"):
            self._serve_asset(parsed.path)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        routes = {
            "/api/decompose-questions": self._decompose_questions,
            "/api/generate-draft": self._generate_draft,
            "/api/save-draft": self._save_draft,
            "/api/save-questions": self._save_questions,
            "/api/send-reply": self._send_reply,
            "/api/close-issue": self._close_issue,
            "/api/upload-image": self._upload_image,
            "/api/fetch": self._fetch,
            "/api/mark-state": self._mark_state,
        }
        handler = routes.get(parsed.path)
        if not handler:
            self.send_error(404)
            return
        try:
            self._send_json(handler(self._read_json()))
        except Exception as e:  # one bad request shouldn't kill the server
            self._send_json({"error": str(e)}, status=500)

    def _exec_claude(self, prompt, model):
        """Returns a subprocess.CompletedProcess-like object with .stdout
        holding the response text — claude -p prints it straight to stdout
        with --output-format text."""
        claude_env = {**os.environ, **CLAUDE_CLI_ENV}
        claude_cmd = ["claude", "-p", prompt, "--output-format", "text"]
        if model:
            claude_cmd += ["--model", model]
        if ALLOWED_TOOLS:
            claude_cmd += ["--allowedTools", ALLOWED_TOOLS]
        # Defense-in-depth alongside the allowlist above: explicitly block
        # anything that writes/executes, since a real run showed the model
        # can otherwise try to "helpfully" save its answer to a scratch file
        # and report on that instead of just returning the text.
        claude_cmd += ["--disallowedTools", "Write Edit NotebookEdit Bash"]
        return subprocess.run(
            claude_cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
            env=claude_env,
            cwd=CLAUDE_CWD,
        )

    def _exec_codex(self, prompt, model):
        """Returns a subprocess.CompletedProcess-like object with .stdout
        holding the response text. codex exec's own stdout is a verbose,
        noisy transcript (workdir/model/session banner, tool-use log, token
        count, THEN the response) — not something to parse directly, so we
        use --output-last-message to get just the clean final text and
        splice it into .stdout so callers don't need to know the backend."""
        codex_cmd = ["codex", "exec", prompt, "--sandbox", CODEX_SANDBOX, "--cd", CLAUDE_CWD]
        if model:
            codex_cmd += ["--model", model]
        out_fd, out_path = tempfile.mkstemp(suffix=".txt", prefix="codex-out-")
        os.close(out_fd)
        codex_cmd += ["--output-last-message", out_path]
        try:
            proc = subprocess.run(
                codex_cmd,
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT,
                cwd=CLAUDE_CWD,
                stdin=subprocess.DEVNULL,
            )
            response_text = ""
            if os.path.exists(out_path):
                with open(out_path) as f:
                    response_text = f.read()
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass
        # Keep the raw transcript in .stderr for diagnostics (it's genuinely
        # useful there — e.g. shows which tools it tried to use), and put
        # just the clean response in .stdout so both backends look the same
        # to the callers below.
        return subprocess.CompletedProcess(
            codex_cmd,
            returncode=proc.returncode,
            stdout=response_text,
            stderr=proc.stdout + proc.stderr,
        )

    def _run_ai(self, state, number, prompt, kind, backend, model, hint=None,
                questions_primary=None):
        """Shared by generate-draft and decompose-questions: run the given AI
        backend/model and append the attempt — prompt included — to the issue's
        single cumulative generate.json. Returns (proc, success, message,
        file_refs) — proc.stdout is always the clean response text,
        regardless of backend. Callers resolve backend/model up front with
        _resolve_backend_model()."""
        exec_fn = self._exec_codex if backend == "codex" else self._exec_claude
        try:
            proc = exec_fn(prompt, model)
        except subprocess.TimeoutExpired as e:
            # A real outcome, not a server bug — still log it and return a
            # proper result instead of a raw exception, since with tool use
            # (or a longer questions list to address) this can legitimately
            # take longer than expected, especially on a busy shared machine.
            proc = subprocess.CompletedProcess(
                e.cmd,
                returncode=-1,
                stdout=(e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=(e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""),
            )
        success = proc.returncode == 0 and bool(proc.stdout.strip())
        # Both CLIs can print some failures (e.g. auth errors) to stdout
        # rather than stderr, so check both rather than assume stderr always
        # carries the useful message.
        message = (
            proc.stderr.strip()
            or proc.stdout.strip()
            or (f"timed out after {CLAUDE_TIMEOUT}s" if proc.returncode == -1 else f"{backend} exec failed")
        )

        gh_api.append_generate_log(
            REPO,
            state,
            number,
            {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "kind": kind,
                "backend": backend,
                "model": model,
                "hint": hint,
                "questions_primary": questions_primary,
                "prompt": prompt,
                "exit_code": proc.returncode,
                "success": success,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )

        file_refs = {"log_file": gh_api.generate_log_path(REPO, state, number)}
        return proc, success, message, file_refs

    def _generate_draft(self, payload):
        # hints: {"<number>": "extra instructions for just this issue"} — optional,
        # keyed by string since that's what JSON object keys deserialize to.
        hints = payload.get("hints") or {}
        # {"<number>": true} — this issue's 生成草稿 should lead with the
        # questions list instead of the hint (see _build_prompt).
        questions_first = payload.get("questions_primary") or {}
        overwrite = bool(payload.get("overwrite"))
        backend, model = _resolve_backend_model(payload)
        results = []
        for number in payload.get("numbers", []):
            state = gh_api.find_issue_state(REPO, number)
            if not state:
                results.append({"number": number, "error": "not found locally"})
                continue
            draft_file = gh_api.draft_path(REPO, state, number)
            if not overwrite and os.path.exists(draft_file):
                with open(draft_file) as f:
                    existing = f.read()
                if existing.strip():
                    results.append({"number": number, "skipped": "already has a draft"})
                    continue
            with open(gh_api.issue_json_path(REPO, state, number)) as f:
                issue = json.load(f)
            hint = hints.get(str(number))
            questions = _read_if_exists(gh_api.questions_path(REPO, state, number))
            questions_primary = bool(questions_first.get(str(number)))
            prompt = _build_prompt(issue, hint, questions, questions_primary)

            proc, success, message, file_refs = self._run_ai(
                state, number, prompt, kind="draft", backend=backend, model=model,
                hint=hint, questions_primary=questions_primary,
            )
            if not success:
                results.append(
                    {"number": number, "error": message, "exit_code": proc.returncode, **file_refs}
                )
                continue
            draft = _strip_wrapping_fence(proc.stdout.strip()) + "\n"
            with open(draft_file, "w") as f:
                f.write(draft)
            results.append({"number": number, "draft": draft, "ok": True, **file_refs})
        return {"results": results, "model": model, "backend": backend}

    def _decompose_questions(self, payload):
        overwrite = bool(payload.get("overwrite"))
        backend, model = _resolve_backend_model(payload)
        results = []
        for number in payload.get("numbers", []):
            state = gh_api.find_issue_state(REPO, number)
            if not state:
                results.append({"number": number, "error": "not found locally"})
                continue
            questions_file = gh_api.questions_path(REPO, state, number)
            if not overwrite and os.path.exists(questions_file):
                with open(questions_file) as f:
                    existing = f.read()
                if existing.strip():
                    results.append({"number": number, "skipped": "already broken down"})
                    continue
            with open(gh_api.issue_json_path(REPO, state, number)) as f:
                issue = json.load(f)
            prompt = _build_questions_prompt(issue)

            proc, success, message, file_refs = self._run_ai(
                state, number, prompt, kind="questions", backend=backend, model=model,
            )
            if not success:
                results.append(
                    {"number": number, "error": message, "exit_code": proc.returncode, **file_refs}
                )
                continue
            questions = _strip_wrapping_fence(proc.stdout.strip()) + "\n"
            with open(questions_file, "w") as f:
                f.write(questions)
            results.append({"number": number, "questions": questions, "ok": True, **file_refs})
        return {"results": results, "model": model, "backend": backend}

    def _save_draft(self, payload):
        number = payload["number"]
        state = gh_api.find_issue_state(REPO, number)
        if not state:
            return {"error": f"issue #{number} not found locally"}
        with open(gh_api.draft_path(REPO, state, number), "w") as f:
            f.write(payload.get("content", ""))
        return {"ok": True}

    def _save_questions(self, payload):
        """Hand-edited 問題清單. Same file 拆解問題 writes, so a later 生成草稿
        answers exactly the list you left there."""
        number = payload["number"]
        state = gh_api.find_issue_state(REPO, number)
        if not state:
            return {"error": f"issue #{number} not found locally"}
        with open(gh_api.questions_path(REPO, state, number), "w") as f:
            f.write(payload.get("content", ""))
        return {"ok": True}

    def _send_reply(self, payload):
        results = []
        for number in payload.get("numbers", []):
            state = gh_api.find_issue_state(REPO, number)
            if not state:
                results.append({"number": number, "error": "not found locally"})
                continue
            draft_file = gh_api.draft_path(REPO, state, number)
            body = ""
            if os.path.exists(draft_file):
                with open(draft_file) as f:
                    body = f.read()
            if not body.strip():
                results.append({"number": number, "error": "draft is empty"})
                continue
            try:
                gh_api.post_comment(REPO, number, body, TOKEN)
            except SystemExit as e:
                results.append({"number": number, "error": str(e)})
                continue
            issue = gh_api.get_issue(REPO, number, TOKEN)
            new_state, _ = gh_api.file_issue(REPO, issue, LOGIN)
            results.append({"number": number, "ok": True, "new_state": new_state})
        return {"results": results}

    def _close_issue(self, payload):
        results = []
        for number in payload.get("numbers", []):
            try:
                gh_api.close_issue(REPO, number, TOKEN)
            except SystemExit as e:
                results.append({"number": number, "error": str(e)})
                continue
            issue = gh_api.get_issue(REPO, number, TOKEN)
            new_state, _ = gh_api.file_issue(REPO, issue, LOGIN)
            results.append({"number": number, "ok": True, "new_state": new_state})
        return {"results": results}

    def _mark_state(self, payload):
        """Move issues between awaiting_reply and replied by hand — nothing is
        posted to GitHub, this only changes which pile they sit in locally.
        The override lasts until someone comments again (see gh_api.file_issue)."""
        target = payload.get("state")
        if target not in ("awaiting_reply", "replied"):
            return {"error": f"bad target state: {target!r}"}
        results = []
        for number in payload.get("numbers", []):
            state = gh_api.find_issue_state(REPO, number)
            if not state:
                results.append({"number": number, "error": "not found locally"})
                continue
            if state == "closed":
                results.append({"number": number, "error": "issue 已關閉，不能改狀態"})
                continue
            try:
                with open(gh_api.issue_json_path(REPO, state, number)) as f:
                    issue = json.load(f)
                new_state = gh_api.set_manual_state(REPO, number, target, issue)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                results.append({"number": number, "error": str(e)})
                continue
            results.append({"number": number, "ok": True, "new_state": new_state})
        return {"results": results}

    def _fetch(self, payload):
        """Re-sync from GitHub — same read-only pass fetch_issues.py's CLI (and
        the hourly cron) runs: refile every issue by state, rewrite summary.md.
        Never drafts or posts anything. Drafts survive because file_issue moves
        the whole <N>/ folder when an issue changes state."""
        if not FETCH_LOCK.acquire(blocking=False):
            return {"error": "已經有一個抓取在進行中，請稍候"}
        try:
            counts, summary_path = fetch_issues.sync_repo(REPO, TOKEN, LOGIN)
        finally:
            FETCH_LOCK.release()
        return {"counts": counts, "summary": summary_path}

    def _upload_image(self, payload):
        number = payload["number"]
        state = gh_api.find_issue_state(REPO, number)
        if not state:
            return {"error": f"issue #{number} not found locally"}
        filename = os.path.basename(payload["filename"])
        data = base64.b64decode(payload["data_base64"])
        dest_dir = gh_api.assets_dir(REPO, state, number)
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, filename), "wb") as f:
            f.write(data)
        return {"url": f"/assets/{state}/{number}/{filename}"}


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    global REPO, TOKEN, LOGIN, MODEL, CLAUDE_CLI_ENV, ALLOWED_TOOLS, CLAUDE_CWD
    global CLAUDE_TIMEOUT, AI_BACKEND, CODEX_SANDBOX, SESSION_CONTEXT
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="owner/name; defaults to config's default_repo")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument(
        "--ai-backend",
        default="claude",
        choices=["claude", "codex"],
        help="which AI CLI 生成草稿/拆解問題 shells out to: 'claude' (claude -p, default) "
        "or 'codex' (codex exec). Separate auth per backend — see module docstring.",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="model name/alias passed to the backend's --model flag. Default: 'sonnet' "
        "if --ai-backend=claude (kept explicit rather than relying on claude -p's "
        "undocumented default); unset (backend picks its own default) if "
        "--ai-backend=codex.",
    )
    ap.add_argument(
        "--allowed-tools",
        default="Read Grep Glob Skill",
        help=(
            "space-separated tool allowlist passed to `claude -p --allowedTools` "
            "(claude backend only) for 生成草稿, so it can ground replies in real "
            "files/skills instead of only the prompt text. Read-only by default (no "
            "Bash/Write) since this runs unattended. Pass '' to disable tool use "
            "entirely."
        ),
    )
    ap.add_argument(
        "--codex-sandbox",
        default="read-only",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="sandbox mode passed to `codex exec --sandbox` (codex backend only). "
        "Read-only by default for the same unattended-safety reason as "
        "--allowed-tools.",
    )
    ap.add_argument(
        "--claude-cwd",
        default=os.path.expanduser("~"),
        help="working directory the AI backend subprocess runs in (default: $HOME), "
        "so it can find repo/worklog files when using its tools",
    )
    ap.add_argument(
        "--claude-timeout",
        type=int,
        default=300,
        help="seconds to wait for one backend call before giving up (default: 300). "
        "Tool use and longer questions lists can genuinely take a while, especially "
        "on a busy shared machine.",
    )
    ap.add_argument(
        "--worklog-root",
        default=None,
        help="where the daily-work-log reports live (default: $DAILY_WORKLOG_ROOT "
        "or ~/meeting). Used to trace a cited worklog page back to the dev "
        "sessions it was written from.",
    )
    ap.add_argument(
        "--no-session-context",
        action="store_true",
        help="don't look up the dev sessions behind worklog pages an issue cites; "
        "生成草稿 then answers from the issue text and whatever it reads itself.",
    )
    args = ap.parse_args()

    TOKEN = gh_api.resolve_token()
    REPO = gh_api.resolve_repo(args.repo)
    LOGIN = gh_api.resolve_login(TOKEN)
    AI_BACKEND = args.ai_backend
    MODEL = args.model if args.model is not None else ("sonnet" if AI_BACKEND == "claude" else None)
    CODEX_SANDBOX = args.codex_sandbox
    CLAUDE_CLI_ENV = gh_api.resolve_claude_cli_env()
    ALLOWED_TOOLS = args.allowed_tools
    CLAUDE_CWD = args.claude_cwd
    CLAUDE_TIMEOUT = args.claude_timeout
    SESSION_CONTEXT = not args.no_session_context
    if args.worklog_root:
        os.environ["DAILY_WORKLOG_ROOT"] = os.path.expanduser(args.worklog_root)

    if args.bind != "127.0.0.1":
        print(
            f"WARNING: binding to {args.bind} exposes GitHub write access (this "
            "server has no auth of its own) to anyone who can reach this port.",
            file=sys.stderr,
        )

    server = Server((args.bind, args.port), Handler)
    print(f"github-issue-reply dashboard for {REPO} (backend: {AI_BACKEND}, model: {MODEL or '(default)'}, "
          f"session context: {'on, ' + worklog_sessions.worklog_root() if SESSION_CONTEXT else 'off'})")
    print(f"http://{args.bind}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
