#!/usr/bin/env python3
"""週報的掃描區間：從**上一份 deck** 推導，不另開游標檔。

為什麼不新增一個 `_cursor.json`：
  `docs/STATE.md §4` 坑 #13——同一事實寫在兩個地方，必定分岔。
  而上一份 `deck.json` 的 `meta.range` 本來就記著「上次涵蓋到哪一天」，
  deck 又不會刪。所以起日直接從那裡推，不需要第二份狀態。

  ⚠️ 曾經有一份獨立的游標檔，但**沒有任何腳本讀過它** —— 於是它停在某一天之後
  再也沒被推進，而週報照樣一份一份出，**沒有人發現**。
  ⛔ **不要再開第二份游標檔**：狀態只該有一份，而 deck 本身就是那一份。

三種來源，優先序由高到低：
  1. `--days <起> <迄>`      使用者明講（會與推導值比對，有落差就警告）
  2. `--since-last-deck`     從上一份 deck 推（起 = 上次迄日 + 1 天，迄 = 今天）
  3. `--last N`              最近 N 天（⚠️ 會漏，見下）

⚠️ **`--last N` 為什麼不可靠**：實際週報間隔是 5、7、8、7、8、**13**、8、7 天，
很不規則。固定 7 天在那個 13 天的間隔上會**漏掉 6 天**。
它只保留給「還沒有任何一份 deck」的第一次。
"""
import datetime, glob, json, os, re

import paths

# ⛔ 不寫死輸出根目錄。寫死的後果不是報錯，是**無聲失效**：
#    別人的機器上沒有那個目錄 → 找不到上一份 deck → 區間推導默默失效、
#    退回手填日期，而「區間一直是手填的」正是這支腳本要修掉的毛病。
#    解析規則（環境變數 → ~/.config/weekly-deck/ → 慣例）在 paths.py，只有一份。
#    各函式的 root 預設 None，到真的要用時才解析——載入本模組不該因為
#    設定沒設好就整支掛掉。
DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _deck_candidates(root):
    """所有可能的 `deck.json`，回傳 [(週報日期, 路徑)]，**新路徑優先**。

    現行結構是 `<root>/YYYY-MM-DD/deck.json`（改版後，⭐ 交付物直接放在
    日期目錄，過程產物才進 `_work/`）。
    舊結構是 `<root>/YYYY-MM-DD/deck/deck.json`（多一層 `deck/`）。

    **舊路徑仍然認**，理由：本機有 10 份舊結構的週報且刻意不搬移，
    而 `--since-last-deck` 的失敗方式是**靜默的** —— 找不到上一份就推不出區間、
    退回手填日期，正是這支腳本存在的目的要修掉的毛病（見上方 ⚠️）。
    多這一條分支的成本是兩行，漏認的成本是每次都要手填一次區間。
    ⚠️ 同一週兩種結構都在時，**新的贏**（舊的是搬移前的殘留）。

    ⚠️ 底線開頭的目錄（`_archive`、`_replay_*`、`_blind_test_*`）一律排除——
    那些是演練與存檔，不是真的報告過的週。
    """
    seen = {}
    for pat, depth in ((os.path.join(root, "*", "deck.json"), 1),          # 新
                       (os.path.join(root, "*", "deck", "deck.json"), 2)):  # 舊
        for d in sorted(glob.glob(pat)):
            wk = d
            for _ in range(depth):
                wk = os.path.dirname(wk)
            wk = os.path.basename(wk)
            if DATE_DIR.match(wk):
                seen.setdefault(wk, d)      # 新路徑先掃 → 同一週不會被舊的蓋掉
    return sorted(seen.items())


def find_last_deck(root=None, before=None):
    """回傳 (週報日期, deck.json 路徑, meta.range) —— 日期最大的那一份正式週報。"""
    root = root or paths.reports_root()
    best = None
    for wk, d in _deck_candidates(root):
        if before and wk >= before:
            continue
        try:
            meta = (json.load(open(d, encoding="utf-8")).get("meta") or {})
        except (OSError, json.JSONDecodeError):
            continue
        rng = meta.get("range")
        if not (isinstance(rng, list) and len(rng) == 2):
            continue
        if best is None or wk > best[0]:
            best = (wk, d, rng)
    return best  # None 或 (週報日期, 路徑, [起, 迄])


def resolve(args_days=None, since_last_deck=False, last_n=None,
            root=None, today=None):
    """決定區間，並回報它是怎麼來的與有沒有缺口／重疊。

    回傳 (起, 迄, notes[])。notes 是要印給人看的警告，**不要吞掉**。
    """
    root = root or paths.reports_root()
    today = today or datetime.date.today().isoformat()
    # ⚠️ `before=today`：**排除今天這一份**。本週的輸出目錄
    # `<週報輸出根>/<今天>/deck.json` 可能已經先建好骨架（例如先寫
    # meta.range_note），若不排除就會把自己當成「上一份」，推出起日 = 明天。
    # 首次實跑實際踩過一次。
    notes, prev = [], find_last_deck(root, before=today)

    derived = None
    if prev:
        wk, path, rng = prev
        nxt = (datetime.date.fromisoformat(rng[1]) +
               datetime.timedelta(days=1)).isoformat()
        derived = (nxt, today)
        notes.append(f"上一份週報 {wk}（{os.path.relpath(path, root)}）涵蓋 "
                     f"{rng[0]} ~ {rng[1]} → 推導起日 {nxt}")
    else:
        notes.append("找不到任何既有 deck.json —— 這是第一份週報")

    if args_days:
        start, end = args_days
        src = "使用者指定"
        if derived and start != derived[0]:
            d0 = datetime.date.fromisoformat(derived[0])
            d1 = datetime.date.fromisoformat(start)
            gap = (d1 - d0).days
            if gap > 0:
                notes.append(
                    f"⚠️ **缺口 {gap} 天**：{derived[0]} ~ "
                    f"{(d1 - datetime.timedelta(days=1)).isoformat()} "
                    f"不在任何一份週報的區間內。\n"
                    f"   若那幾天已經口頭報過就沒問題；否則那些工作會無聲消失。\n"
                    f"   **刻意跳過的話，把理由寫進 deck.json 的 meta.range_note。**")
            else:
                notes.append(
                    f"⚠️ **與上一份重疊 {-gap} 天**：{start} ~ {derived[0]} 講過了，"
                    f"重複會變成雜訊。確認是刻意的再往下。")
    elif since_last_deck:
        if not derived:
            raise SystemExit("[range] 沒有既有 deck，無法用 --since-last-deck；"
                             "請用 --days 或 --last")
        start, end = derived
        src = "從上一份 deck 推導"
    elif last_n:
        end = today
        start = (datetime.date.fromisoformat(today) -
                 datetime.timedelta(days=last_n - 1)).isoformat()
        src = f"最近 {last_n} 天"
        notes.append("⚠️ `--last N` 不可靠：實際週報間隔是 5~13 天，固定天數會漏。"
                     "有既有 deck 時請改用 --since-last-deck 或 --days")
    else:
        raise SystemExit("[range] 要指定 --days / --since-last-deck / --last")

    if start > end:
        raise SystemExit(f"[range] 起日 {start} 晚於迄日 {end}")
    notes.insert(0, f"區間 {start} ~ {end}（{src}）")
    return start, end, notes


def add_args(ap):
    """把三個互斥選項掛上任何一個 argparse parser。"""
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--days", nargs=2, metavar=("FROM", "TO"))
    g.add_argument("--since-last-deck", action="store_true",
                   help="起日 = 上一份 deck 的 meta.range[1] + 1 天（建議）")
    g.add_argument("--last", type=int, metavar="N",
                   help="最近 N 天（⚠️ 會漏，只給第一份週報用）")


def from_args(a, root=None):
    start, end, notes = resolve(a.days, a.since_last_deck, a.last, root)
    for n in notes:
        print(f"[range] {n}")
    return start, end


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    add_args(ap)
    print(from_args(ap.parse_args()))
