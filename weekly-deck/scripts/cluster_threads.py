#!/usr/bin/env python3
"""layer1 的機械聚類：用日誌的 artifacts 路徑把一週的 item 分群。

為什麼要機械聚類（而不是讓 LLM 讀 materials.md 憑感覺歸群）：
  純 LLM 歸群的失敗方式是**把時間順序讀成因果**——十幾個 item 按日期排下來
  看起來很像一條線，串起來還很順，所以特別危險（上一版實跑的 plan.feedback
  就有這一條：「硬串 A→B→C→D→E」，使用者改成四個互不相關的主角）。

  `artifacts.files` / `artifacts.outputs` 是**物證**：碰過同一批檔案的 item，
  多半真的是同一件事。本腳本只負責把物證整理出來，**不命名、不下結論**——
  命名與補孤兒是 LLM 的工作，判定是使用者的工作（關卡①）。

限制（一定要知道）：
  · 只碰得到「有動到檔案」的 item。純討論、純量測、純閱讀論文不會有 artifacts，
    一律落進 orphans，要靠 LLM 補。**orphans 不是雜訊，是本腳本看不見的那一半。**
  · v1 舊日誌沒有 artifacts 欄位 → 退回從 details 正則撈路徑（同 build_deck.py）。

用法：
  cluster_threads.py --days 2024-03-04 2024-03-07 [--data <.data>] [--json out.json]
"""
import argparse, datetime, json, os, re, sys
from collections import defaultdict

import _range
import paths

# 路徑一律由 paths.py 解析（環境變數 → ~/.config/weekly-deck/ → 慣例），
# 日誌 repo 的部分再轉發給 daily-log 自己的 paths.py。
# ⛔ 不要寫死 —— 這兩個 skill 是配套的，路徑規則只該有一份，而且要能在別人的機器上跑。
# ⛔ 也不要 try/except 退回預設值：找不到 daily-log 就該直接報錯，
#    靜默用一個猜出來的路徑只會產出一份空週報。
DATA_DEFAULT = paths.data_dir()

# v1 退路：從自由文字撈看起來像專案內路徑的東西。
# 目錄名與 daily-log 的 config source-dirs 對齊。
SRC_DIRS = r"docs|pipeline|results|data|config|\.claude|\.scratch|scripts|weekly_reports|weekly"
PATH_RE = re.compile(rf"(?:^|[\s`（(])((?:{SRC_DIRS})/[\w./\-]+)")

# 這些前綴太籠統，單獨成群沒有意義（幾乎每個 item 都會碰到）。
# 它們仍然參與更深一層的前綴（docs/03_snv_detect 就有意義）。
TOO_BROAD = {"docs", "data", "results", "config", "pipeline", "scripts"}


def daterange(a, b):
    d0 = datetime.date.fromisoformat(a)
    d1 = datetime.date.fromisoformat(b)
    if d1 < d0:
        sys.exit("[cluster] 起日晚於迄日")
    out, d = [], d0
    while d <= d1:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def entry_paths(entry):
    """一個 item／record 碰過的路徑集合。artifacts 優先，v1 舊檔退回正則。"""
    art = entry.get("artifacts") or {}
    paths = list(art.get("files") or []) + list(art.get("outputs") or [])
    if not paths:
        blob = " ".join(str(entry.get(k) or "") for k in
                        ("details", "approach", "result", "what"))
        paths = PATH_RE.findall(blob)
    # 正規化：去掉開頭的 ./ 與結尾的 /
    # ⚠️ 不可用 lstrip("./") —— 那是字元集合，會把 `.claude` 的開頭點一起吃掉。
    out = set()
    for p in paths:
        p = (p or "").strip().rstrip("/")
        while p.startswith("./"):
            p = p[2:]
        if p:
            out.add(p)
    return out


def prefixes(path, max_depth=3):
    """一條路徑貢獻的候選群鍵：前 1~3 層。

    深度 3 是實測值：`.claude/skills/daily-log` 與 `.claude/skills/weekly-deck`
    要到第三層才分得開，而第四層（`.claude/skills/weekly-deck/scripts`）
    會把同一件事拆成好幾群。
    """
    parts = [x for x in path.split("/") if x]
    return ["/".join(parts[:d]) for d in range(1, min(max_depth, len(parts)) + 1)]


def load_entries(data_dir, days):
    """把一週的 item 與 record 攤平成統一結構。

    record 也要進來：記錄層存在的理由就是「被 5 項上限擠掉的那幾項，
    常常正是週報缺的料」（daily-log README）。編號帶 R 以便回查。
    """
    out, missing = [], []
    for d in days:
        fp = os.path.join(data_dir, f"{d}.json")
        if not os.path.isfile(fp):
            missing.append(d)
            continue
        j = json.load(open(fp, encoding="utf-8"))
        for i, it in enumerate(j.get("items", []), 1):
            out.append({"sid": f"{d}#{i}", "layer": "item", "date": d,
                        "title": it.get("title", ""),
                        "summary": it.get("summary") or it.get("result", ""),
                        "status": it.get("status", ""),
                        "paths": entry_paths(it)})
        for i, r in enumerate(j.get("record", []), 1):
            out.append({"sid": f"{d}#R{i}", "layer": "record", "date": d,
                        "title": r.get("title", ""),
                        "summary": r.get("what", ""),
                        "status": r.get("status", ""),
                        "paths": entry_paths(r)})
    return out, missing


def load_advisor(data_dir, days):
    """教授的提問與方針 —— 排序的第一順位（editorial_policy §3）。

    ⚠️ 這是日誌裡**唯一沒有自動來源**的欄位（daily-log log_schema.md 明寫）。
    掃不到就是真的沒有，不要編。
    """
    out = []
    for d in days:
        fp = os.path.join(data_dir, f"{d}.json")
        if not os.path.isfile(fp):
            continue
        j = json.load(open(fp, encoding="utf-8"))
        for a in (j.get("advisor") or []):
            out.append({"date": d, **a})
        # v1 舊欄位
        for q in (j.get("questions_for_advisor") or []):
            out.append({"date": d, "kind": "question", "text": str(q),
                        "answered": False, "_v1": True})
    return out


def cluster(entries, min_size=2):
    """貪婪聚類：每個 entry 指派給「涵蓋它、且成員數 ≥ min_size」的**最深**前綴。

    最深優先的理由：`.claude/skills` 會把 daily-log 與 weekly-deck 併成一群，
    而那正是本週要分開的兩條主線。深的前綴先搶，淺的只撿剩下的。
    """
    by_prefix = defaultdict(set)
    for e in entries:
        for p in e["paths"]:
            for pre in prefixes(p):
                if pre in TOO_BROAD:
                    continue
                by_prefix[pre].add(e["sid"])

    # 深 → 淺；同深度時成員多的優先
    order = sorted(by_prefix, key=lambda k: (-k.count("/"), -len(by_prefix[k]), k))
    assigned, clusters = {}, []
    for pre in order:
        members = [s for s in by_prefix[pre] if s not in assigned]
        if len(members) < min_size:
            continue
        cid = f"T{len(clusters) + 1}"
        for s in members:
            assigned[s] = cid
        clusters.append({"id": cid, "key": pre, "members": sorted(members)})

    orphans = [e["sid"] for e in entries if e["sid"] not in assigned]
    return clusters, orphans


def render_md(clusters, orphans, entries, advisor, days, missing):
    idx = {e["sid"]: e for e in entries}
    L = ["# layer1 聚類結果（機械產出，未命名）", "",
         f"區間 {days[0]} ~ {days[-1]}，"
         f"{len(entries)} 個項目（item + record），"
         f"{len(clusters)} 個候選群，{len(orphans)} 個孤兒。", ""]
    if missing:
        L += [f"⚠️ 缺日誌：{'、'.join(missing)}", ""]

    L += ["> ⚠️ **這份不是主線清單。** 群 = 碰過同一批檔案的項目，是物證不是判斷。",
          "> 命名、合併、補孤兒由 LLM 做；**切法與名字由使用者定案**（關卡①）。", ""]

    if advisor:
        L += ["## ⚑ 教授交代（排序第一順位）", ""]
        for a in advisor:
            mark = "未答" if a.get("kind") == "question" and not a.get("answered") else a.get("kind", "")
            L.append(f"- [{a['date']}][{mark}] {a.get('text', '')}")
        L.append("")
    else:
        L += ["## ⚑ 教授交代", "",
              "本週日誌的 `advisor` 欄位是空的。**這不代表沒有** —— 那一欄只有使用者補得了，",
              "掃不到就要在關卡① 直接問他：上次問了什麼還沒回答、哪些是他指定的方向。", ""]

    L += ["## 候選群", ""]
    for c in clusters:
        L += [f"### {c['id']}　共同路徑 `{c['key']}`　（{len(c['members'])} 項）", ""]
        for s in c["members"]:
            e = idx[s]
            tag = "" if e["layer"] == "item" else "〔記錄層〕"
            L.append(f"- `{s}` {tag}**{e['title']}** — {e['summary'][:80]}")
        L.append("")

    L += ["## 孤兒（沒有共用路徑，或根本沒碰檔案）", "",
          "⚠️ **孤兒不是雜訊**。純討論、純量測、純讀論文都不會留下 artifacts，",
          "但它們可能正是本週最該講的東西。LLM 要逐項判斷該掛哪一群或獨立成線，",
          "**而且要說出它跟那一群共用了什麼**（共用的東西不是檔案就要講得出是什麼）。", ""]
    for s in orphans:
        e = idx[s]
        tag = "" if e["layer"] == "item" else "〔記錄層〕"
        paths = "、".join(sorted(e["paths"])[:3]) or "（無 artifacts）"
        L.append(f"- `{s}` {tag}**{e['title']}** — {e['summary'][:80]}　〔{paths}〕")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    _range.add_args(ap)          # --days / --since-last-deck / --last
    ap.add_argument("--data", default=DATA_DEFAULT)
    ap.add_argument("--out", help="週報的日期目錄（產物寫進 _work/1_materials/）")
    ap.add_argument("--min-size", type=int, default=2)
    a = ap.parse_args()

    start, end = _range.from_args(a)
    days = daterange(start, end)
    entries, missing = load_entries(a.data, days)
    if not entries:
        sys.exit(f"[cluster] {a.data} 在 {days[0]}~{days[-1]} 沒有任何日誌項目")
    advisor = load_advisor(a.data, days)
    clusters, orphans = cluster(entries, a.min_size)

    md = render_md(clusters, orphans, entries, advisor, days, missing)
    payload = {"range": [days[0], days[-1]], "clusters": clusters,
               "orphans": orphans, "advisor": advisor,
               "entries": [{k: (sorted(v) if isinstance(v, set) else v)
                            for k, v in e.items()} for e in entries]}

    if a.out:
        # 過程產物 → `_work/1_materials/`
        d = paths.work_dir(a.out, "materials", create=True)
        open(os.path.join(d, "threads.md"), "w", encoding="utf-8").write(md)
        json.dump(payload, open(os.path.join(d, "threads.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[cluster] {len(entries)} 項 → {len(clusters)} 群 + {len(orphans)} 孤兒 "
              f"→ {d}/threads.md")
    else:
        print(md)


if __name__ == "__main__":
    main()
