#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 [--date YYYYMMDD]" >&2
  exit 2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(bash "${SCRIPT_DIR}/report_root.sh")"

# An explicit CLI date takes precedence over WEEKLY_DECK_DATE; otherwise default
# to the Friday of the current week.
if [[ $# -eq 0 ]]; then
  if [[ -n "${WEEKLY_DECK_DATE:-}" ]]; then
    target_date="${WEEKLY_DECK_DATE}"
  else
    today_weekday="$(date +%u)"
    days_until_friday="$((5 - today_weekday))"
    target_date="$(date -d "${days_until_friday} day" +%Y%m%d)"
  fi
elif [[ $# -eq 2 && $1 == "--date" ]]; then
  target_date="$2"
else
  usage
fi

if [[ ! "${target_date}" =~ ^[0-9]{8}$ ]] || [[ "$(date -d "${target_date}" +%Y%m%d 2>/dev/null || true)" != "${target_date}" ]]; then
  printf '[錯誤] report date 必須是有效的 YYYYMMDD：%s\n' "${target_date}" >&2
  exit 1
fi

target_dir="${BASE_DIR}/${target_date}-w"
mkdir -p "${target_dir}/data"

# 單頁 HTML 用 assets/slides.css 連樣式表。預覽 server 的根目錄是報告資料夾的上一層，
# 所以爬到 ~/.claude 的相對路徑會落在根目錄外面而 404；用資料夾內的 symlink 讓 URL
# 留在根目錄裡。serve_preview.py 也會補建這個連結（舊資料夾用得到）。
asset_target="$(realpath --relative-to="${target_dir}" "${HOME}/.codex/skills/presentation-builder/assets")"
ln -sfn "${asset_target}" "${target_dir}/assets"

printf 'Created weekly report: %s\n' "${target_dir}"
