#!/usr/bin/env python3
"""Post a comment to a GitHub issue. THIS IS THE ONLY SCRIPT THAT ACTUALLY
SENDS ANYTHING TO GITHUB — only run it after the user has explicitly
confirmed the draft file's content out loud.

By convention the draft lives at
  ~/github-issue/<owner>-<name>/<state>/<issue-number>/draft.md
and --body-file defaults to that path if omitted.

After a successful post, the issue is re-fetched and re-filed into the
"replied" state automatically (its draft file moves along with it).

Usage:
  post_comment.py --repo owner/name --issue 42
  post_comment.py --repo owner/name --issue 42 --body-file /some/other/draft.md
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_api  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="owner/name; defaults to config's default_repo")
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument(
        "--body-file",
        help="path to the confirmed draft; defaults to the issue's draft.md",
    )
    ap.add_argument("--token", help="override token (else GITHUB_TOKEN / config file)")
    args = ap.parse_args()

    token = gh_api.resolve_token(args.token)
    repo = gh_api.resolve_repo(args.repo)
    login = gh_api.resolve_login(token)

    body_file = args.body_file
    if not body_file:
        found_state = gh_api.find_issue_state(repo, args.issue)
        if not found_state:
            raise SystemExit(
                f"No local record found for {repo}#{args.issue} and no --body-file "
                "given. Run fetch_issues.py first, or pass --body-file explicitly."
            )
        body_file = gh_api.draft_path(repo, found_state, args.issue)

    if not os.path.exists(body_file):
        raise SystemExit(f"Draft file not found: {body_file}")

    with open(body_file) as f:
        body = f.read()

    result = gh_api.post_comment(repo, args.issue, body, token)
    print(f"Posted: {result.get('html_url')}")

    # Re-file the issue locally so it now shows up under replied/ (draft.md
    # moves with the folder).
    issue = gh_api.get_issue(repo, args.issue, token)
    state, dest = gh_api.file_issue(repo, issue, login)
    print(f"Local state updated: {repo}#{args.issue} -> {state} ({dest})")


if __name__ == "__main__":
    main()
