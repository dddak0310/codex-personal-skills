#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 [--month YYYY-MM]" >&2
  exit 2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(bash "${SCRIPT_DIR}/report_root.sh")"

if [[ $# -eq 0 ]]; then
  # 月會預設報告上個月；用該月最後一天作為資料夾日期。
  reporting_month="$(date -d "$(date +%Y-%m-01) -1 month" +%Y-%m)"
elif [[ $# -eq 2 && $1 == "--month" && $2 =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
  reporting_month="$2"
  date -d "${reporting_month}-01" +%Y-%m >/dev/null
else
  usage
fi

target_date="$(date -d "${reporting_month}-01 +1 month -1 day" +%Y%m%d)"
target_dir="${BASE_DIR}/${target_date}-m"
mkdir -p "${target_dir}/data"

asset_target="$(realpath --relative-to="${target_dir}" "${HOME}/.codex/skills/presentation-builder/assets")"
ln -sfn "${asset_target}" "${target_dir}/assets"

printf 'Created monthly report: %s\n' "${target_dir}"
