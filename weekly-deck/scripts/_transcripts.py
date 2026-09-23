#!/usr/bin/env python3
"""逐字稿來源的分派層：一個目錄是 Claude Code 的還是 Codex 的，以及怎麼讀它。

## 為什麼有這支

`measure_effort.py` 原本**只認得 Claude Code 的 `.jsonl`**
（`entry["message"]["content"]`）。Codex 的存檔是另一種形狀
（`payload.type` + `content[].input_text`），餵進去的結果**不是報錯，是回空集合**：

    $ measure_effort.py 2024-03-18T00:00:00 2024-03-19T00:00:00
    實際動手：0 小時 0 分　／　0 則對話　／　0 個活動段　／　橫跨 0 天

這跟「這週真的沒做事」長得一模一樣。本專案明令避免這種失效
（`docs/STATE.md §4` 坑 #10：工具讀不了某種格式、錯誤被吞掉 → 假的「0 個命中」）。

## 兩條紀律

1. **不寫第二份 Codex adapter。** `daily-log/scripts/extract_transcript.py` 已經有一份
   （`read_codex_session` / `collect_codex`），這裡**按檔案路徑載入它並轉發**。
   同一件事寫在兩個地方必定分岔（`docs/STATE.md §4` 坑 #13）。
   ⛔ 要改 Codex 的解析規則，一律改 daily-log 那一份。
2. **空集合要有理由。** 掃過的目錄底下如果連一個 `.jsonl` 都沒有，
   或某個目錄的格式認不出來，一律報錯，不讓它混進「這週沒對話」的結論裡。

## 兩種工具的目錄形狀

| | Claude Code | Codex |
|---|---|---|
| 目錄 | 一個專案一個（路徑的 `/`、`_` 換成 `-`） | 沒有專案概念，按 `YYYY/MM/DD` 分 |
| session id | 檔名前 8 碼 | `session_meta.payload.id` 前 8 碼 |
| 訊息形狀 | `message.content[].text` | `payload.content[].input_text` 等 |
"""

import glob
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import paths  # noqa: E402  ../paths.py

_cache = {}


# --------------------------------------------------------------------------
# 轉發：載入 daily-log 的 Codex adapter
# --------------------------------------------------------------------------

def _daily_log_extract():
    """載入 `daily-log/scripts/extract_transcript.py`（Codex adapter 的唯一實作）。"""
    if "mod" in _cache:
        return _cache["mod"]
    d = paths._daily_log_dir()
    src = os.path.join(d, "scripts", "extract_transcript.py") if d else None
    if not (src and os.path.isfile(src)):
        sys.exit(
            "[錯誤] 找不到 daily-log 的 scripts/extract_transcript.py，"
            "無法讀 Codex 的 session。\n"
            "        Codex 的解析只有 daily-log 有一份（刻意不在這裡再寫一份），\n"
            "        兩個 skill 必須成對安裝。設定方式見 weekly-deck 的 README。")
    # ⚠️ 掛成別的模組名：daily-log 底下那支也叫 extract_transcript.py，
    #    用 `import extract_transcript` 會命中自己，變成自己呼叫自己。
    spec = importlib.util.spec_from_file_location("daily_log_extract", src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["daily_log_extract"] = mod
    spec.loader.exec_module(mod)
    _cache["mod"] = mod
    return mod


# --------------------------------------------------------------------------
# 目錄形狀的辨識
# --------------------------------------------------------------------------

def jsonl_files(d, limit=None):
    """目錄底下的 `.jsonl`（含子目錄——Codex 按 YYYY/MM/DD 分層）。"""
    out = sorted(glob.glob(os.path.join(d, "*.jsonl")))
    out += sorted(glob.glob(os.path.join(d, "**", "*.jsonl"), recursive=True))
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:limit] if limit else uniq


def detect_tool(d):
    """這個目錄是哪個工具的存檔：`claude` / `codex` / `empty` / `unknown`。

    判準用**檔案內容**，不用目錄名 —— 目錄可以被搬到任何地方，
    而「猜錯就靜默回空」正是這支要修的毛病。
    """
    files = jsonl_files(d, limit=20)
    if not files:
        return "empty"
    for path in files:
        with open(path, errors="replace") as fh:
            for _ in range(40):
                line = fh.readline()
                if not line:
                    break
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(e.get("message"), dict):
                    return "claude"
                if e.get("type") in ("session_meta", "response_item", "event_msg"):
                    return "codex"
    return "unknown"


def classify(dirs):
    """把目錄清單分成 {claude: [...], codex: [...]}；認不得就**報錯**。"""
    out = {"claude": [], "codex": []}
    bad = []
    for d in dirs:
        d = os.path.expanduser(d)
        if not os.path.isdir(d):
            print(f"  [略過] 找不到目錄：{d}", file=sys.stderr)
            continue
        kind = detect_tool(d)
        if kind in ("claude", "codex"):
            out[kind].append(d)
        else:
            bad.append((d, kind))
    if bad and not (out["claude"] or out["codex"]):
        detail = "\n".join(
            f"          {d}　（{'底下沒有任何 .jsonl' if k == 'empty' else '格式認不出來'}）"
            for d, k in bad)
        sys.exit(
            "[錯誤] 給定的逐字稿目錄裡沒有任何看得懂的 session：\n" + detail + "\n"
            "        支援的格式只有 Claude Code（`message.content`）與 "
            "Codex（`payload` + `session_meta`）。\n"
            "        ⛔ 不會靜默回 0 則 —— 那跟「這段區間真的沒做事」分不出來。")
    for d, k in bad:
        print(f"  [警告] {d} 認不出格式（{k}），已跳過", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# 讀 Codex：一律轉發給 daily-log 的 adapter
# --------------------------------------------------------------------------

# daily-log 的 adapter 會把工具呼叫壓成一行 ```\n[name] args\n```。
# 契約是「剝除工具輸出」（實測約佔 transcript 體積 95%），所以要濾掉它們。
_TOOLCALL_MARK = "```\n["


def codex_sessions(root, since, until, exclude=(), text_only=True):
    """讀一個 Codex 目錄，回 `{session_id: [(時間, role, 文字, False), ...]}`。

    `text_only=True`（預設）只留使用者與 assistant 的**純文字**，
    丟掉工具呼叫與工具結果 —— 剝除工具輸出。

    ⛔ 解析邏輯完全來自 daily-log，這裡只做「挑哪些留下」。
    """
    mod = _daily_log_extract()
    # 先走 daily-log 的日期視窗（`YYYY/MM/DD` 之下，效率好、與它一致）。
    sessions, _scanned = mod.collect_codex(root, since, until, exclude)
    got = {sid: msgs for (_proj, sid), msgs in sessions.items()}
    if not got:
        # 傳進來的可能不是 sessions 根，而是某一天的目錄（回放、測試常這樣給）。
        # 那時日期視窗那條路徑找不到檔案，改成直接掃底下所有 .jsonl。
        for path in jsonl_files(root):
            sid, _proj, msgs = mod.read_codex_session(path, since, until)
            if not (sid and msgs) or sid in exclude:
                continue
            got.setdefault(sid, []).extend(msgs)
    out = {}
    for sid, msgs in got.items():
        kept = []
        for t, kind, text, side in msgs:
            if text_only:
                if kind == "result" or text.startswith(_TOOLCALL_MARK):
                    continue
            kept.append((t, kind, text, side))
        if kept:
            out[sid] = sorted(kept, key=lambda x: x[0])
    return out
