---
name: github-issue-reply
description: >
  Fetch GitHub issues from a repo (each user configures their own token/default repo
  independently) into a local ~/github-issue/<repo>/<state>/ folder tree classified by
  whether the issue is closed, awaiting my reply, or already replied to — then, the main
  point, actually draft a real reply for each issue awaiting a response, saved as a file
  for the user to review, only posting it to GitHub via API after the user explicitly
  confirms out loud. When an issue cites a daily worklog page, the draft is grounded in
  the actual development sessions behind that page (traced via ~/meeting/<date>/data/),
  so the reply can say whether the question is aimed at the wrong thing or found a real
  gap. Also answers general questions about the fetched issues in
  conversation, and can launch a local checkbox-driven dashboard (collapsible
  awaiting_reply/replied/closed groups, generate/edit/send drafts, close replied
  issues) as an alternative to the chat flow. Never posts a comment without explicit
  confirmation (verbal in chat, or a checkbox+button click in the dashboard). Trigger
  on: 抓取 issue, 抓 repo 的 issue, 幫我看一下這個 repo 的 issue, 這些 issue 有哪些是 bug,
  哪些 issue 還沒回, 幫我回這個 issue, 起草回覆, 回覆 issue #N, fetch github issues, list
  issues for owner/repo, draft a reply to issue #N, answer questions about these
  issues, reply to this GitHub issue, sync my github issues, open the issue dashboard,
  打開 issue 面板/dashboard.
---

# github-issue-reply skill

Scripts live at `~/.claude/skills/github-issue-reply/scripts/`. Pure Python stdlib +
bash — no venv/install step beyond the one-time per-user config below.

## Setup (first time per user)

Per-user config (GitHub token, optional default repo, cached login) lives in this
skill's own `.env` — `~/.claude/skills/github-issue-reply/.env`, i.e.
`skills/github-issue-reply/.env` in the shared skills repo. Same convention as
`apgpas-query/.env`: tracked in the shared repo *directory*, but the bare `.env`
filename is repo-gitignored, so the file itself never leaves this developer's own
clone — no other user's `sync.sh` ever sees or overwrites it.

Check if already configured:
```bash
cat ~/.claude/skills/github-issue-reply/.env 2>/dev/null
```

If missing, run the setup script — it walks through creating a fine-grained token
(github.com/settings/personal-access-tokens/new: pick Resource owner -> Repository
access -> Only select repositories -> Add permissions -> Issues -> Read and write)
and an optional default repo (`owner/name`), verifies it, and writes `GITHUB_TOKEN` /
`GITHUB_DEFAULT_REPO` / `GITHUB_LOGIN` to `.env` (chmod 600):
```bash
bash ~/.claude/skills/github-issue-reply/scripts/install.sh
```

Shell env vars of the same name (`GITHUB_TOKEN`, `GITHUB_DEFAULT_REPO`, `GITHUB_LOGIN`,
`ANTHROPIC_API_KEY`) override the `.env` file if set. `ANTHROPIC_API_KEY` is unrelated
to the GitHub setup above — see ## 3 for what it's for.

## 1. Sync issues into ~/github-issue/

```bash
FETCH=~/.claude/skills/github-issue-reply/scripts/fetch_issues.py

# full sync: fetch open+closed issues, classify, write per-issue folders + summary.md
python3 $FETCH --repo owner/name

# a single issue + its full comment thread (also files/refiles it locally)
python3 $FETCH --repo owner/name --number 42
```

Everything lands under a fixed local path, keyed by repo/state/issue number, **one
subfolder per issue** — `<state>/<N>/` — so a directory listing stays short (one entry
per issue) even once a few generated files pile up per issue, and reclassifying an
issue to a different state is a single folder move (`gh_api.file_issue()`), not moving
each file individually:
```
~/github-issue/<owner>-<name>/
  summary.md                          # awaiting_reply only, see below
  awaiting_reply/
    <N>/
      issue.json
      draft.md                        # only once a draft has been written
      questions.md                    # 拆解問題 output, hand-editable in the dashboard
      generate.json                   # every AI attempt: kind, prompt, hint, output
      manual_state.json               # only when the state was set by hand
      assets/                         # only when images were pasted into a draft
  replied/
    <N>/issue.json
  closed/
    <N>/issue.json
```

States (see `gh_api.classify_state`):
- **awaiting_reply** — issue is open and the last comment (or the issue body itself,
  if no comments yet) is NOT from the configured user → a reply is owed.
- **replied** — issue is open and the configured user posted the last comment.
- **closed** — issue is closed, regardless of who spoke last.

A **manual override** beats that classification: the dashboard's 標記為已回覆 /
丟回未回覆 buttons write `manual_state.json` into the issue's folder (target state +
the id of the comment the thread ended on) and move the folder there. Nothing is
posted to GitHub. `file_issue` honors the marker on later syncs, and drops it
automatically once there's a newer last comment or the issue closes — so a manually
parked issue reappears in `awaiting_reply` the moment someone says something new.

`replied` and `closed` issues are filed to disk (for lookup/Q&A) but **not** listed in
`summary.md` — that file only covers `awaiting_reply` (title + URL + a `[draft ready]`
marker once drafted), since that's the actionable queue. **It's an aid, not the
deliverable** — see step 2.

If the user just says "抓這個 repo 的 issue" without naming one and no default_repo is
configured, ask which `owner/name` to use (or suggest running `install.sh` to set a
default for next time).

**Optional automation:** `fetch_issues.py` is read-only (no GitHub writes), so it's safe
to run unattended. `scripts/setup_cron.sh` installs (or `--remove`s) an hourly cron job
that runs it for the configured default repo, logging to
`~/github-issue/<user>-fetch.log`. It resolves its own path and `python3` at run time,
so it's portable across developers — each person runs it after their own `install.sh`,
no path editing needed:
```bash
bash ~/.claude/skills/github-issue-reply/scripts/setup_cron.sh            # install
bash ~/.claude/skills/github-issue-reply/scripts/setup_cron.sh --remove   # remove
```
Only offer/run this when the user asks for scheduled/automatic syncing — never install a
cron job unprompted.

## 2. The actual point: draft real replies for awaiting_reply issues

Classifying is just bookkeeping — what the user actually wants is a real, ready-to-send
draft reply for each issue that's awaiting one, based on that issue's title/body/comment
thread (read its `issue.json` for full context).

For each `awaiting_reply` issue you're asked to handle (one, several, or "all of them"):

1. Read `~/github-issue/<owner>-<name>/awaiting_reply/<N>/issue.json` for context.
1b. **If the issue cites a worklog page, go back to the sessions that page was
   written from before drafting** — see ## 2b. Skip only when the issue cites no
   page and asks nothing about how something was built.
2. Write an actual drafted reply (not a placeholder) to
   `~/github-issue/<owner>-<name>/awaiting_reply/<N>/draft.md`.
3. Paste the full draft content into the conversation and ask explicitly whether it's
   OK to post — do this per issue, don't bulk-approve silently.
4. **Do not call `post_comment.py` until the user explicitly confirms that specific
   draft out loud** (e.g. "可以發", "發吧", "OK send it"). If they ask for changes, edit
   the draft file and ask again — a general "these look fine" about the topic is not
   approval to post any one of them.
5. Only after confirmation:
   ```bash
   python3 ~/.claude/skills/github-issue-reply/scripts/post_comment.py \
     --repo owner/name --issue 42
   ```
   (it defaults `--body-file` to that issue's `draft.md`; pass `--body-file`
   explicitly only if the confirmed text lives elsewhere). On success it posts the
   comment, prints the URL, and automatically re-files the issue's whole folder under
   `replied/` — re-run step 1's sync only if you want summary.md's list refreshed.

`post_comment.py` is the only CLI script in this skill that writes to GitHub —
everything else (`fetch_issues.py`, reading `issue.json`/`summary.md`) is
read-only. (The dashboard below is the other thing that writes to GitHub — see its
own confirmation model.)

**A stray file left in `<N>/` (e.g. a manual copy someone made while browsing) is
harmless** — it just sits there, nothing in this skill scans for or depends on an
exact file list inside an issue's folder beyond the specific names above.

## 2b. Trace a cited worklog page back to the sessions it came from

Issues in a worklog repo almost always point at one daily-report page (e.g.
`20260820/05-pathogen-api-perf.html`). That page is a *summary* — it's what made
the reader ask the question in the first place, so answering from it just
re-serves the same partial picture. The development it summarizes happened in
real Claude Code / Codex sessions, and daily-work-log keeps the provenance next
to the report under `${DAILY_WORKLOG_ROOT:-~/meeting}/<YYYYMMDD>/data/`:
`page-sources.json` (page → sessions, the precise one), `session-manifest.json`
(that day's sessions + each transcript path), plus the `task-summaries.md` /
`theme-map.md` digests.

`scripts/worklog_sessions.py` does that lookup and the transcript reading:

```bash
WS=~/.claude/skills/github-issue-reply/scripts/worklog_sessions.py

# which sessions back the pages this issue cites (JSON: ids + transcript paths)
python3 $WS --repo owner/name --issue 1

# the same as the instruction block the dashboard injects into 生成草稿
python3 $WS --repo owner/name --issue 1 --format prompt

# read one session as plain user/assistant turns instead of raw JSONL
python3 $WS --session e76918a4 --grep "clinical_class" --context 2
```

Resolution degrades in three steps, and each result says which one it used:
`page-sources.json` (this exact page) → `session-manifest.json` (all of that
day's sessions) → a **date scan** of `~/.claude/projects` + `~/.codex/sessions`
for reports written before provenance existed. A date-scan result is *candidates,
not attribution* — those sessions were merely live that day, so grep them for the
issue's own terms and keep only what actually hits.

**What the session is for**: reconstruct what was actually measured, tried,
rejected and left undone, then decide which of these the issue is — and let that
decide the reply:

- **問題聚焦錯了** — the page's wording or one of its numbers pointed the reader
  at something the real work didn't hinge on (they're optimizing a step that
  wasn't the cost, or assuming a design that was ruled out during development).
  Correct the premise directly instead of answering the question as asked.
- **真的有紕漏** — the transcript shows it genuinely wasn't handled, was
  deferred, was left as a known open item, or doesn't hold up under what the
  issue points out. Say so plainly, state the current behavior and what would
  have to change. Don't defend it.
- **講不清楚** — the transcript doesn't settle it. Say which part is unclear and
  what would answer it, rather than inventing a confident answer.

Ground the reply in what you found (measured numbers, commit hashes, file paths,
options tried and dropped) — but **don't narrate the research or cite session ids
in the reply**; the sessions are internal, the reader sees only the answer and
its evidence.

Transcripts are large JSONL — never read one end to end. Grep the directory for
the issue's terms first, then `--session ... --grep ...` on the files that hit.

## 3. Optional: visual dashboard (checkbox-driven, same repo/state/N/ folders)

`scripts/dashboard_server.py` serves `templates/dashboard.html` — a single local page
per repo with a collapsible group per state (awaiting_reply/replied/closed), checkboxes
+ "全選", a collapsible "顯示 issue 內容" per row rendered as GitHub-flavored Markdown —
not raw text with literal backticks (issue body + full comment thread, so you don't
have to open GitHub to see what you're replying to), and per-issue draft editors with
an explicit 編輯/預覽 toggle (Markdown, with image paste/upload; preview also renders
GFM, not raw source). Each awaiting_reply row also has an
optional hint field ("生成草稿時的額外提示") — when filled in, it becomes the PRIMARY
basis for the reply's content and direction; the issue body/comments/decomposed
questions list become supporting background only, not a checklist the model must work
through — it doesn't have to address every item, or use them at all, if they aren't
relevant to what the hint asks for. Leaving it blank keeps the default behavior
(address the issue/questions list directly, as described above).

**Which side leads is a per-issue choice**, via the "以問題清單為主（逐條回答；不勾則
以額外提示為主）" checkbox on the questions box:
- **unchecked (default)** — hint-led, exactly as described above: the hint drives
  content and direction, the questions list is background the model may skip.
- **checked** — list-led: every item in the questions list must be answered, and the
  hint is demoted to guidance on *how* (angle, emphasis, tone, what to leave out)
  rather than *what*.
It rides in `generate-draft`'s `questions_primary` payload and is recorded per attempt
in `generate.json`, so the checkbox comes back the way you left it after a reload
(`gh_api.last_draft_settings()`). With no hint at all, both settings behave the same —
answer the list item by item. "生成草稿" only
generates for selected issues that don't already have a draft — a checked box
already-drafted issue is silently left alone — unless the "覆蓋已有草稿" checkbox next
to the button is checked, in which case selected issues are regenerated regardless. It
reads and
writes the exact same `~/github-issue/<owner>-<name>/<state>/<N>/*` files as the CLI
flow above, so the two are always in sync — nothing about the dashboard is a separate
data model.

**Page header: 重新抓取** runs the same read-only sync as `fetch_issues.py`
(`POST /api/fetch` → `fetch_issues.sync_repo`, serialized by a lock so two clicks can't
overlap), then reloads the page data — so you don't need the hourly cron or a terminal
just to see new issues/comments. It never drafts or posts anything.

**Moving issues between piles by hand** (nothing is sent to GitHub): awaiting_reply has
"標記為已回覆", replied has "丟回未回覆" — both `POST /api/mark-state`, see the manual
override note in ## 1. Rows in a hand-set pile show a "手動標記" badge. "Close 選中項目"
is available in **both** open groups (it does close on GitHub); in awaiting_reply it
asks for confirmation first, since that closes something you never answered.

**拆解問題 is a separate step from 生成草稿, run first if you want it.** It's its own
button (with its own "覆蓋已拆解" checkbox, same skip-unless-overwrite behavior) that
calls `claude -p` to break the issue into a numbered list of its distinct
questions/requests, saved to `<N>/questions.md` (shown per row as "拆解出的問題清單",
badge "questions ready"/"not decomposed"). If that file exists when you later click
"生成草稿", its content is included in the draft prompt and the model is told to
address every item in it in turn; if it doesn't exist, 生成草稿 falls back to breaking
the issue down itself in the same call (the original one-step behavior — decomposing
first is an optional quality improvement, not a requirement). Both steps log into the
same `<N>/generate.json`, each attempt tagged with its `kind` ("draft"/"questions") —
one file per issue, not one per step.

**The questions list is editable in the page**, not just rendered: the box under each
awaiting_reply row is a textarea over `<N>/questions.md`, saved on blur (`POST
/api/save-questions`) and flushed again right before 生成草稿 runs. So you can fix a bad
breakdown by hand, or write the list yourself without ever clicking 拆解問題 — whatever
is in that box is what the draft will answer.

Foreground (blocks the terminal, Ctrl-C to stop):
```bash
python3 ~/.claude/skills/github-issue-reply/scripts/dashboard_server.py [--repo owner/name] [--port 8765] [--ai-backend claude|codex] [--model ...]
```
Background, with a proper stop command (no manual PID hunting) — `start_dashboard.sh`
auto-picks a free port if `--port` is omitted, writes the pid+port to
`~/.cache/github-issue-reply/dashboard.pid`, and refuses to double-start if one's
already running; `stop_dashboard.sh` reads that file and kills it cleanly. All args
(including `--ai-backend`) are forwarded to `dashboard_server.py`:
```bash
bash ~/.claude/skills/github-issue-reply/scripts/start_dashboard.sh [--repo owner/name] [--port N] [--ai-backend codex]
bash ~/.claude/skills/github-issue-reply/scripts/stop_dashboard.sh
```
Either way it prints `http://127.0.0.1:<port>/` to open. Binds `127.0.0.1` only by
default — this server has no auth of its own, and its POST endpoints really do post
comments / close issues with the configured token, so don't suggest `--bind 0.0.0.0`
unless the user explicitly wants LAN access and understands that trade-off.

**Confirmation model is different from ## 2, not weaker than it**: in the dashboard,
checking a box and pressing "發送回覆" / "Close 選中項目" **is** the user's explicit
confirmation — equivalent in weight to the verbal "可以發" required in the chat flow,
just a different surface. Don't add a second confirmation step there and don't treat
clicks in the dashboard as needing a follow-up chat confirmation either.

**Two interchangeable AI backends** — pick with `--ai-backend claude` (default) or
`--ai-backend codex`:
- `claude` — `claude -p`, see auth details below.
- `codex` — `codex exec --sandbox <mode> --output-last-message <tmpfile>`. Needs its
  own separate auth via `codex login`, unrelated to both the GitHub token and the
  claude backend's auth. No Read/Grep/Glob/Skill-style tool allowlist exists for
  codex (its permission model is sandbox-mode based: `read-only` default, override
  with `--codex-sandbox`), so it can't load this skill's other skills as context the
  way the claude backend can — but it can still read local files under that sandbox.
  Verified end-to-end: both backends produced clean, narration-free, well-grounded
  replies for the same issue; codex even caught a SQL detail (IN-list pairing
  producing unwanted cross-combinations) the claude backend's answer didn't mention
  — neither backend is strictly better, they're just different models/tools.

`--model` is passed to whichever backend's own `--model` flag; unset by default for
codex (it picks its own default), defaults to `sonnet` for claude (kept explicit
rather than relying on claude -p's undocumented default). Every log entry
(`<N>/generate.json`) records which `backend` produced it.

**Also selectable per click, right in the dashboard** — no restart needed. The
awaiting_reply toolbar has an "AI: 預設/claude/codex" dropdown and a "model（選填）"
text box next to 拆解問題/生成草稿; leaving both at their default uses whatever
`--ai-backend`/`--model` the server was started with, picking either overrides just
that one click's batch (verified: overriding to codex on a server started with the
claude default worked and was recorded correctly in the log). There's no such
per-click picker for a fixed `--allowed-tools`/`--codex-sandbox`/`--claude-cwd` — those
stay server-wide, set at startup.

**"生成草稿" needs its own auth, separate from the GitHub token**: (claude backend) it
shells out to the
local `claude` CLI (`claude -p "..." --model <model> --output-format text`) as a brand
new OS process — this is a *different* authentication channel from whatever session
you're reading this in, even on the same machine, because a freshly started `claude`
process re-authenticates from scratch instead of reusing a running session's already-
established login. If that fresh process's stored credentials are stale, every
`claude -p` call fails with something like `Failed to authenticate: OAuth session
expired and could not be refreshed`, regardless of who or what invoked it (the
dashboard's subprocess call and you typing `claude -p` directly in a terminal hit the
exact same failure — it is not specific to how the dashboard calls it).

Fix with **one** of:
```bash
claude setup-token
```
Walks through a one-time browser login and prints a long-lived token starting
`sk-ant-oat...`. **This token is NOT an `ANTHROPIC_API_KEY`** — passing it as one fails
with a clean `401 API key is invalid` from the API (verified empirically, not a guess).
Put it in this skill's own `.env` instead, under its own name:
```bash
# in ~/.claude/skills/github-issue-reply/.env (same file as GITHUB_TOKEN)
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...
```

```bash
# in ~/.claude/skills/github-issue-reply/.env
ANTHROPIC_API_KEY=sk-ant-api...
```
If you have an actual Anthropic Console API key instead (from
console.anthropic.com/settings/keys, starts `sk-ant-api...`), that one *does* go in
`ANTHROPIC_API_KEY`. The two env vars are for two genuinely different credential types
and are not interchangeable — set the one matching what you actually have.

Either can also be a shell env var instead of a `.env` line (same override precedence
as `GITHUB_TOKEN`/etc.). `dashboard_server.py` reads whichever is set via
`gh_api.resolve_claude_cli_env()` and passes it into the `claude -p` subprocess's
environment — this is otherwise unrelated to anything else in this skill (GitHub auth
is untouched by it).

If neither is configured, the button surfaces whatever error `claude -p` reports
per-issue (the rest of a multi-select batch still proceeds) rather than failing
silently.

**生成草稿 can read files/use skills to ground its answer, read-only by default**:
`claude -p` runs with `--allowedTools "Read Grep Glob Skill"` (override via
`dashboard_server.py --allowed-tools "..."`, empty string disables tool use entirely),
`--disallowedTools "Write Edit NotebookEdit Bash"` as defense-in-depth on top
of the allowlist, and `cwd=$HOME` (override via `--claude-cwd <path>`) — since this is
an unattended process nobody is watching to approve permissions for. Timeout defaults
to 300s (`--claude-timeout`), not 180s — tool use and a longer 拆解問題 list can
genuinely take a while, especially on a busy shared machine; a timeout is caught and
logged as a normal (if unsuccessful) attempt, not a crash. The prompt explicitly tells
it to read referenced files instead of guessing at their content, and — this needed a
real failure to discover — explicitly forbids narrating its own process ("I've read
X... saved at...") instead of just outputting the raw comment text, because a run with
tool access enabled did exactly that once before this instruction was added. Verified
end-to-end after each fix: for an issue whose body referenced a worklog page under
`~/meeting/`, the generated reply actually read that file (and, in one run, related
source files too) and quoted/cited it directly rather than paraphrasing the issue text,
with clean output — no narration, no wrapping fence.

**生成草稿 traces the issue's worklog page back to its dev sessions by itself**:
before the prompt is built, the issue's title/body/comments are scanned for
worklog page references and resolved exactly as ## 2b describes; when anything is
found, the prompt gains a block listing those sessions' transcript paths, the
`--session` reading recipe, and the 聚焦錯誤／真的紕漏／講不清楚 judgement it has
to make. An issue citing no page is unaffected — the block is simply empty. The
lookup is wrapped so a failure logs to stderr and drafting continues without it.
It's on by default; `--no-session-context` turns it off, and `--worklog-root`
points at a report root other than `$DAILY_WORKLOG_ROOT`/`~/meeting`. Since the
whole prompt is recorded per attempt in `<N>/generate.json`, whether a given
draft actually got the session block (and which sessions) is answerable after the
fact. It's skipped automatically when the backend can't read files anyway
(claude with `--allowed-tools ''`), since the block is only instructions to go
read them.

**Model and prompt/response are never a black box**: the model is explicit, not
whatever `claude -p`'s undocumented default happens to be — `--model sonnet` unless the
dashboard was started with `--model <alias>` (`start_dashboard.sh`/`dashboard_server.py
--model opus`, etc.), and the model actually used is echoed back in the status line and
in every result. Every attempt of either kind, success or failure, is appended to ONE
file next to the issue so nothing about it is a mystery:
- `<N>/generate.json` — JSON array, one entry appended per attempt (oldest first):
  timestamp, kind ("draft"/"questions"), backend, model, the 額外提示 used,
  questions_primary, **the exact prompt that was sent**, exit_code, success, raw stdout, raw stderr — nothing is
  overwritten, so past attempts (and the prompt each one used, not just the most recent)
  stay visible after a regeneration

`gh_api.read_generate_log()` folds a pre-merge folder (`questions_generate.json`,
`prompt.txt`, `questions_prompt.txt`) into this format on first access and deletes the
leftovers — no manual migration step. The hint box and the 以問題清單為主 checkbox are
repopulated from the newest draft entry that recorded each (`gh_api.last_draft_settings()`),
so what you last told it survives a reload without files of their own.

The dashboard's status line after clicking "生成草稿" reports that path per issue, so
"did this actually work" is answerable by opening the log file, not by guessing.

The prompt explicitly tells the model not to wrap its reply in a ``` fence (GitHub
already renders the comment body as Markdown, so a wrapping fence makes the whole thing
display as literal unformatted text). Models don't always obey that, so
`_strip_wrapping_fence()` also strips one defensively if the *entire* response turns out
to be a single fenced block — verified against a real generation that came back fenced.
