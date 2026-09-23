#!/usr/bin/env bash

set -euo pipefail

# Resolution order:
# 1. Explicit environment override for one command/session.
# 2. A per-user config file for a persistent personal report repository.
# 3. The current user's worklog repository beside the shared skills checkout.
if [[ -n "${WEEKLY_DECK_ROOT:-}" ]]; then
    printf '%s\n' "${WEEKLY_DECK_ROOT}"
    exit 0
fi

root_file="${WEEKLY_DECK_ROOT_FILE:-${HOME}/.config/presentation-builder/root}"
if [[ -f "${root_file}" ]]; then
    configured_root="$(sed -n '1p' "${root_file}" | sed 's/[[:space:]]*$//')"
    if [[ -n "${configured_root}" ]]; then
        printf '%s\n' "${configured_root}"
        exit 0
    fi
fi

user_name="${USER:-$(id -un)}"
if [[ -n "${WORKLOGS_PROJECTS_ROOT:-}" ]]; then
    projects_root="${WORKLOGS_PROJECTS_ROOT}"
else
   # The shared skills checkout lives beside each developer's other repos.
   # Resolve through symlinks so calls via ~/.claude or ~/.codex still work.
   script_dir="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    skills_repo_root="$(cd "${script_dir}/../../.." && pwd)"
    projects_root="$(cd "${skills_repo_root}/.." && pwd)"
fi

worklog_repo="${projects_root}/${user_name}-worklogs"
if [[ -d "${worklog_repo}" ]]; then
    printf '%s\n' "${worklog_repo}"
    exit 0
fi

printf '[錯誤] 找不到同層工作日誌 repo：%s\n' "${user_name}-worklogs" >&2
printf '       請設定 WEEKLY_DECK_ROOT、WEEKLY_DECK_ROOT_FILE 或 WORKLOGS_PROJECTS_ROOT。\n' >&2
exit 1
