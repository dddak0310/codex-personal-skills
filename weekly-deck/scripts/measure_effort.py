#!/usr/bin/env python3
"""量測一段區間內「實際動手」了多久。

從 session transcript 的訊息時間戳算：把訊息切成活動段，
**超過 GAP 分鐘的空檔不計入**（那是去做別的事、或在等 agent 跑長工作）。

用途：知道這輪週報實際花了多少時間，跟歷史基準比較，
判斷這套系統到底有沒有省到時間——而不是靠感覺。

**Claude Code 與 Codex 都吃**：session 目錄依內容辨識，
Codex 的解析轉發給 `daily-log` 的 adapter（見同目錄 `_transcripts.py`）。
原本只認 Claude Code，只用 Codex 的人會拿到「0 小時 0 分」——
那跟「這段區間真的沒動手」分不出來，正是本專案明令避免的失效形態。

用法：
  measure_effort.py <since> [until]           # 只印結果
  measure_effort.py <since> [until] --log      # 並附加到 _effort_log.md
"""

import glob
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402  ../paths.py
import _transcripts  # noqa: E402  目錄形狀辨識 + Codex 轉發

GAP = 30          # 分鐘；超過這個空檔就視為中斷，不計入
# ⛔ session 目錄與紀錄檔的位置都不寫死：目錄名由專案路徑推導
#    （Claude Code 把 `/` 與 `_` 都換成 `-`），紀錄檔跟著週報輸出根走。
PROJECT_DIRS = paths.transcript_dirs()
LOG = paths.effort_log()


def user_times(since, until):
    """回傳區間內所有使用者訊息的時間，已排序。兩種工具的 session 都算進來。"""
    by_tool = _transcripts.classify(PROJECT_DIRS)
    ts = []
    for d in by_tool["claude"]:
        for f in glob.glob(os.path.join(d, "*.jsonl")):
            for line in open(f, errors="replace"):
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = e.get("message") or {}
                if m.get("role") != "user" or not e.get("timestamp"):
                    continue
                t = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
                if not (since <= t <= until):
                    continue
                c = m.get("content")
                txt = c if isinstance(c, str) else "".join(
                    b.get("text", "") for b in c
                    if isinstance(b, dict) and b.get("type") == "text")
                if txt.strip() and not txt.lstrip().startswith("<"):
                    ts.append(t)
    for d in by_tool["codex"]:
        for _sid, msgs in _transcripts.codex_sessions(d, since, until).items():
            ts.extend(t for t, kind, _txt, _side in msgs if kind == "user")
    return sorted(ts)


def active_minutes(times):
    """把時間點切成活動段，回傳 (總分鐘, 段數)。"""
    if not times:
        return 0, 0
    total, segs, start, prev = 0.0, 1, times[0], times[0]
    for t in times[1:]:
        if (t - prev).total_seconds() / 60 > GAP:
            total += (prev - start).total_seconds() / 60
            start, segs = t, segs + 1
        prev = t
    total += (prev - start).total_seconds() / 60
    return round(total), segs


def main():
    args = [a for a in sys.argv[1:] if a != "--log"]
    do_log = "--log" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(2)

    since = datetime.fromisoformat(args[0]).astimezone()
    until = datetime.fromisoformat(args[1]).astimezone() if len(args) > 1 else datetime.now().astimezone()

    times = user_times(since, until)
    mins, segs = active_minutes(times)
    days = len({t.date() for t in times})

    print(f"區間：{since:%Y-%m-%d %H:%M} ~ {until:%Y-%m-%d %H:%M}")
    print(f"實際動手：{mins // 60} 小時 {mins % 60} 分"
          f"　／　{len(times)} 則對話　／　{segs} 個活動段　／　橫跨 {days} 天")
    print(f"（超過 {GAP} 分鐘的空檔不計入）")

    if do_log and times:
        new = not os.path.exists(LOG)
        with open(LOG, "a") as fh:
            if new:
                fh.write("# 週報耗時紀錄\n\n"
                         "> 每份週報做完後手動附加一筆。\n"
                         "> 計法：使用者訊息的時間戳，超過 30 分鐘的空檔不計入。\n"
                         "> **參考基準：建立這套系統之前，手工做一份週報實測是 6~10 小時**\n\n"
                         "| 報告日 | 實際動手 | 對話則數 | 活動段 | 橫跨天數 |\n"
                         "|---|---|---|---|---|\n")
            fh.write(f"| {until:%Y-%m-%d} | {mins//60}h{mins%60:02d}m | {len(times)} | {segs} | {days} |\n")
        print(f"\n已記錄到 {LOG}")


if __name__ == "__main__":
    main()
