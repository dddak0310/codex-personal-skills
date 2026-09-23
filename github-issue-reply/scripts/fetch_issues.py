#!/usr/bin/env python3
"""Fetch GitHub issues and organize them locally under ~/github-issue/.

Two modes:

  --number N   Fetch ONE issue + its full comment thread, file it into
               ~/github-issue/<owner>-<name>/<state>/<N>/issue.json, and print
               the JSON to stdout (for reading straight into conversation).

  (default)    Sync ALL issues (open + closed) for the repo: classify each
               into awaiting_reply / replied / closed, write each one to
               ~/github-issue/<owner>-<name>/<state>/<N>/issue.json (one
               subfolder per issue, so a directory listing stays short even
               with many generated files per issue), and (re)write
               ~/github-issue/<owner>-<name>/summary.md — which only lists the
               awaiting_reply ones (the actionable queue).

Classification (see gh_api.classify_state):
  closed          - issue is closed
  awaiting_reply  - open, and the last word belongs to someone else (I owe a reply)
  replied         - open, and I posted the last comment

Usage:
  fetch_issues.py --repo owner/name              # full sync + summary
  fetch_issues.py --repo owner/name --number 42   # single issue
  fetch_issues.py --number 42                     # uses default_repo from config
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_api  # noqa: E402


def _write_summary(repo, by_state):
    """summary.md only covers awaiting_reply — that's the actionable queue.
    replied/closed are filed on disk but not summarized here."""
    awaiting = sorted(by_state.get("awaiting_reply", []), key=lambda i: i["number"])
    lines = [f"# {repo} — 未回覆 issue ({len(awaiting)})", ""]
    for issue in awaiting:
        draft = gh_api.draft_path(repo, "awaiting_reply", issue["number"])
        draft_marker = " [draft ready]" if os.path.exists(draft) else ""
        lines.append(
            f"- #{issue['number']} {issue['title']}{draft_marker}\n"
            f"  {issue['html_url']}"
        )
    lines.append("")

    summary_path = os.path.join(gh_api.repo_dir(repo), "summary.md")
    os.makedirs(gh_api.repo_dir(repo), exist_ok=True)
    with open(summary_path, "w") as f:
        f.write("\n".join(lines))
    return summary_path


def sync_repo(repo, token, login):
    """Full sync: refile every issue under its current state and rewrite
    summary.md. Returns {state: count} plus the summary path — shared by the
    CLI below and the dashboard's 重新抓取 button, so both go through exactly
    the same classification path."""
    by_state = {s: [] for s in gh_api.STATES}
    for issue in gh_api.list_issues(repo, token, state="all"):
        full = gh_api.get_issue(repo, issue["number"], token)
        state, _ = gh_api.file_issue(repo, full, login)
        by_state[state].append(full)

    summary_path = _write_summary(repo, by_state)
    return {s: len(by_state[s]) for s in gh_api.STATES}, summary_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="owner/name; defaults to config's default_repo")
    ap.add_argument("--number", type=int, help="fetch a single issue + its comments")
    ap.add_argument("--token", help="override token (else GITHUB_TOKEN / config file)")
    args = ap.parse_args()

    token = gh_api.resolve_token(args.token)
    repo = gh_api.resolve_repo(args.repo)
    login = gh_api.resolve_login(token)

    if args.number:
        issue = gh_api.get_issue(repo, args.number, token)
        state, dest = gh_api.file_issue(repo, issue, login)
        print(json.dumps(issue, indent=2, ensure_ascii=False))
        print(f"\n(state={state}, filed at {dest})", file=sys.stderr)
        return

    counts, summary_path = sync_repo(repo, token, login)

    print(f"Synced {repo} to {gh_api.repo_dir(repo)}")
    for state in gh_api.STATES:
        print(f"  {state}: {counts[state]}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
