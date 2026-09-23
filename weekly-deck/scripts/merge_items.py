#!/usr/bin/env python3
"""跨日合併提名 + 週層級排序信號。**機械只提名，不裁決。**

## 為什麼有這支

`daily-log` 的合併判準（`references/selection-signals.md` Step 2-2）**只在單日內生效**。
同一件事做三天，就會產生三個獨立 item —— 週報端**沒有任何一步**會把它們併回去。
實測首次實跑那份週報：4 天 16 個 item，其中「daily-log 改版」一件事佔了 4~5 項。
關卡① 要在十幾個看起來平行的候選裡挑重點，於是**重點很雜** —— 根因不是選材判準不好，
是**選材之前沒有先合併**。

`cluster_threads.py` 做的是**分群成主線**（路徑前綴、粒度粗），不是「這兩項是同一件事」。
兩者互補，不重疊：本支往下切到 item 對 item。

## 兩件事，分得很開

1. **合併提名**（Q1）：哪幾項其實是同一件事。判準沿用 daily-log 的四條
   （推進同一目標／同一依賴鏈／同一交付物或決定／會被寫進週報的同一頁），
   但那四條是**語意的**，機械驗不了。機械能驗的只有三種**物證**（見 `EVIDENCE`），
   湊滿兩種才提名 —— 對應「符合兩條以上才合併」的形狀。
   ⛔ **不自動併掉。** 藏起來使用者就沒有東西可以推翻，那正是「agent 抓的重點和使用者不一樣」的根因。

2. **排序信號**（Q2）：只排序，**不設門檻、不決定上不上台**。
   上不上台由關卡① 的使用者決定（`SKILL.md` 的 `user_points` 那條已經把決定權給他了）。

## ⚠️ 為什麼不直接搬 daily-log 的公式

那套是 `3×參與度 + 2×落地 + 1×延續 + 類別加權`，而**權重最高的參與度來自 transcript**
（使用者訊息數）—— 週報端拿不到，`SKILL.md` 也明文禁止重讀 transcript（太貴）。
硬搬會是一條缺了主項、又沒在週層級校準過的公式，只會製造假精確。

所以這裡重定一套**只用週報看得到的東西**算的信號，並沿用它的兩條紀律：
**印原始信號不只印分數**（看得出為什麼，才推翻得了）、**分數不寫回日誌 JSON**。

用法：
  merge_items.py --out <週報目錄> [--days 起 迄 | --since-last-deck]
"""
import argparse, json, os, re, sys
from collections import Counter, defaultdict

import _range
import paths

# 路徑一律由 paths.py 解析（環境變數 → ~/.config/weekly-deck/ → 慣例），
# 日誌 repo 的部分再轉發給 daily-log 自己的 paths.py。
# ⛔ 不要寫死 —— 這兩個 skill 是配套的，路徑規則只該有一份，而且要能在別人的機器上跑。
# ⛔ 也不要 try/except 退回預設值：找不到 daily-log 就該直接報錯，
#    靜默用一個猜出來的路徑只會產出一份空週報。
DEF_DATA = paths.data_dir()

# 與 cluster_threads.py 同一份定義：這些前綴太籠統，共用它不構成證據。
TOO_BROAD = {"docs", "data", "results", "config", "pipeline", "scripts",
             "weekly_reports", "weekly", ".claude", ".scratch"}

SRC_DIRS = r"docs|pipeline|results|data|config|\.claude|\.scratch|scripts|weekly_reports|weekly"
PATH_RE = re.compile(rf"(?:^|[\s`（(])((?:{SRC_DIRS})/[\w./\-]+)")

# 提名要**同時**滿足下面兩條。⚠️ 它們必須是**互相獨立**的證據 ——
# 第一版用「路徑交集」＋「共用前綴」當兩條，實跑當場失效：路徑有交集時前綴必然也有，
# 兩條其實是同一條，於是 27 項被併成一組 15 項的巨無霸（daily-log 與 weekly-deck
# 因為「某一項順手改了對方一個檔」而被串在一起）。
EVIDENCE = {
    "name":   "共用同一個主線名字（被反覆提到的那個專有名字）",
    "module": "主要模組相同（artifacts 裡出現最多的深度-3 目錄）",
    "files":  "改的是同一批檔（artifacts 路徑 Jaccard ≥ %.2f）",
}

# ── 主判準：主線的名字 ───────────────────────────────────────────────
# 事前理由（在看資料之前就講得出來，這是它唯一乾淨的辯護）：
#   **一條主線的名字，一定會被反覆提到。**
# 原本的兩條判準（同模組 ＋ 改同一批檔）測的是「碰過同一批檔案」＝同一次
# **動作**的特徵，不是同一條**主線**的特徵 —— 同一條線的工作散在很多目錄，
# 碰不到同一批檔就併不起來。實測五個區間有四個是 0 合併。
# 兩種形狀都算「專有名字」，⚠️ **只有這兩種**：
#   ⓐ kebab/snake 命名：daily-log、weekly-deck、bam-and-data
#   ⓑ 字母＋數字混的識別字：CL771、DB2024、batch7（樣本編號、版本代號那種）
# ⛔ **不要放寬成「所有拉丁詞」** —— 實測過，`claude`／`json`／`skill`
#    這種通用技術詞會變成主線鍵，把不相關的東西併成一組 10 項的東西。
#    那是**誤合**，比漏合嚴重（見檔尾方向性）。
#    代價是像 `pipeline`、`throughput` 這種「沒有數字的專業單字」抓不到 —— 已知，接受。
NAME_KEBAB = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+")
NAME_IDENT = re.compile(r"[A-Za-z]{2,}[0-9]+[A-Za-z0-9]*|[A-Za-z]+[0-9]+")
# ⚠️ **兩種名字用不同門檻**（獨立驗證抓到的誤合）：
#   · kebab／snake 複合名（`order-service`、`ingest-pipeline`）是**人造的**，
#     撞名機率極低 → df ≥ 2 就可信。
#   · 字母＋數字（`utf8`、`v2`、`k8s`、`python3`）常常是**版本號或通用標準**，
#     任何專案都會出現 → 要多一次重複才算數，df ≥ 3。
# 實測（合成資料，演算法沒看過）：5 個誤合**全部**是 df=2 的字母+數字
# （utf8／k8／pandas2／ffmpeg6／v2），4 條真主線**全部** df≥3
# （order-service 4、ingest-pipeline 5、batch7 3、ds2024 4）。分界乾淨、無邊界案例。
# ⛔ 這是「所有拉丁詞會誤合」那條的**同一個病、帶了數字的版本** ——
#    當初擋掉 `claude`／`json`／`skill`，但 `utf8`／`v2` 從 NAME_IDENT 溜進來了。
NAME_MIN_DF_KEBAB = 2
NAME_MIN_DF_IDENT = 3
NAME_MAX_DF = 0.85    # 超過這個比例的項目都提到 → 太籠統，當雜訊濾掉

PATH_JACCARD = 0.15   # ⚠️ 未校準，見檔尾「怎麼校準」。
MOD_DEPTH = 3         # 主要模組的目錄深度。與 cluster_threads.py 的 max_depth 一致。
BIG_GROUP = 6         # 超過這個大小就警告「這可能是整條主線，不是一件事」


# ---------- 讀日誌 ----------

def entry_paths(entry):
    """一個 item／record 碰過的路徑。artifacts 優先，v1 舊檔退回正則。"""
    art = entry.get("artifacts") or {}
    paths = list(art.get("files") or []) + list(art.get("outputs") or [])
    if not paths:
        blob = " ".join(str(entry.get(k) or "") for k in
                        ("details", "approach", "result", "what"))
        paths = PATH_RE.findall(blob)
    out = set()
    for p in paths:
        p = (p or "").strip().rstrip("/")
        while p.startswith("./"):
            p = p[2:]
        # 絕對路徑收斂成專案內相對路徑，否則同一個檔會因寫法不同而對不起來
        p = re.sub(r"^/[^\s]*?/(?=(?:%s)/)" % SRC_DIRS, "", p)
        if p:
            out.add(p)
    return out


def dominant_module(paths):
    """這一項「主要在改哪個模組」—— artifacts 裡出現最多的深度-3 目錄。

    深度 3 是 cluster_threads.py 實測出來的：`.claude/skills/daily-log` 與
    `.claude/skills/weekly-deck` 要到第三層才分得開，第四層又會把同一件事拆散。

    ⚠️ 用「**最多**的那一個」而不是「有沒有碰過」，是為了擋掉順手改的一個檔 ——
    「daily-log 改版順便讓週報讀新欄位」會碰到 weekly-deck 一個檔，
    但它的主要模組仍然是 daily-log。
    """
    cnt = defaultdict(int)
    for p in paths:
        parts = [x for x in p.split("/") if x]
        if len(parts) < MOD_DEPTH:
            continue
        key = "/".join(parts[:MOD_DEPTH])
        if key in TOO_BROAD:
            continue
        cnt[key] += 1
    if not cnt:
        return None
    return max(sorted(cnt), key=lambda k: cnt[k])


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def names_in(entry):
    """這一項提到的**專有名字**（kebab/snake 命名）。

    來源分兩種，⚠️ 分開記是為了濾雜訊（見 `thread_names`）：
      · 文字（`title`／`summary`／`concepts[].term`）—— 人真的在講它
      · 路徑（`artifacts`）—— 可能只是它剛好住在那個目錄下

    ⛔ 三種失敗的抽法，不要重走（實測）：
      ① 檔案路徑交集 → 五個區間有四個是 0 合併
      ② 稀有中文詞（idf 加權 bigram）→ **全是雜訊**，命中的是記錄層四段式結構的
         樣板詞（「做完」「狀態」「為什麼做」「做了什麼」「結果與狀態」）
      ③ 取**最罕見**的名字 → 方向取反，併到「順手碰到同一個檔」
    """
    text = " ".join(str(entry.get(k) or "") for k in ("title", "summary"))
    text += " " + " ".join(str(c.get("term") or "")
                           for c in (entry.get("concepts") or []))
    from_text = {m.group(0).lower() for m in NAME_KEBAB.finditer(text)} \
        | {m.group(0).lower() for m in NAME_IDENT.finditer(text)}
    from_path = set()
    for p in entry.get("paths") or ():
        for seg in re.split(r"[/.]", p.lower()):
            if seg and (NAME_KEBAB.fullmatch(seg) or NAME_IDENT.fullmatch(seg)):
                from_path.add(seg)
    return from_text, from_path


def canon_names(all_names):
    """別名歸併：一個名字若是另一個的**token 邊界前綴**，歸到較短的那個。

    例：`cl771_alt` → `cl771`、`order-service-v2` → `order-service`。

    ⚠️ **這是通用規則，不是本專案的別名表** —— 這個 skill 要給別人用，
    ⛔ 不得寫死任何專案專屬的名字對應。
    邊界條件（下一個字元必須是 `-` 或 `_`）是必要的，否則 `deck` 會吃掉 `decktop`。
    """
    out = {}
    for a in all_names:
        base = a
        for b in all_names:
            if b != a and a.startswith(b) and len(a) > len(b) \
                    and a[len(b)] in "-_" and len(b) < len(base):
                base = b
        out[a] = base
    return out


def thread_names(entries):
    """替每一項挑一個「主線鍵」，並回傳 (名字→項數) 供輸出說明用。

    規則：取這一項提到的名字裡 **df 最高**的那個（df = 有幾項提到它）。

    ⚠️ **雜訊靠規則濾，不靠名單** —— 這是要給別人用的公版 skill，
    ⛔ 不得寫死帳號名、磁碟名這種本機專屬的字。
    兩條通用規則：
      · **只出現在路徑、從來沒被人寫進 title/summary 的名字**不算主線名。
        路徑前綴（帳號名、磁碟名、家目錄）全部落在這一類 —— 人不會在
        標題裡寫磁碟名或帳號名，但每個路徑都帶著它。
      · **幾乎每一項都提到的名字**（≥ NAME_MAX_DF）太籠統，也濾掉。
    """
    for e in entries:
        e["_names_text"], e["_names_path"] = names_in(e)
    cm = canon_names({t for e in entries
                      for t in e["_names_text"] | e["_names_path"]})
    text_df, df = Counter(), Counter()
    for e in entries:
        e["_names_text"] = {cm[t] for t in e["_names_text"]}
        e["_names_path"] = {cm[t] for t in e["_names_path"]}
        text_df.update(e["_names_text"])       # 只數「被人寫進文字」的次數
        df.update(e["_names_text"] | e["_names_path"])
    n = len(entries)
    def _min_df(tok):
        """複合名（有連字號／底線）門檻低，字母+數字門檻高。見上方常數的說明。"""
        return NAME_MIN_DF_KEBAB if ("-" in tok or "_" in tok) else NAME_MIN_DF_IDENT
    ok = {t for t, c in df.items()
          if c >= _min_df(t) and c <= n * NAME_MAX_DF and text_df[t] > 0}
    for e in entries:
        cand = [t for t in (e["_names_text"] | e["_names_path"]) if t in ok]
        e["name"] = max(cand, key=lambda t: (df[t], t)) if cand else None
    return df, ok


def tokens(text):
    """中文 bigram + 英文詞。用來判「講的是不是同一批東西」。"""
    t = str(text or "").lower()
    out = set(re.findall(r"[a-z][a-z0-9_\-]{2,}", t))
    cjk = re.findall(r"[一-鿿]+", t)
    for run in cjk:
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def dice(a, b):
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def load_entries(data_dir, days):
    """攤平成統一結構。record 也要進來 —— 被 5 項上限擠掉的常常正是週報缺的料。"""
    out, missing, advisor = [], [], []
    for d in days:
        fp = os.path.join(data_dir, f"{d}.json")
        if not os.path.isfile(fp):
            missing.append(d)
            continue
        j = json.load(open(fp, encoding="utf-8"))
        for a in (j.get("advisor") or []):
            advisor.append({"date": d, **a})
        for i, it in enumerate(j.get("items", []), 1):
            out.append({
                "sid": f"{d}#{i}", "layer": "item", "date": d, "rank": i,
                "title": it.get("title", ""),
                "summary": it.get("summary") or it.get("result", ""),
                "kind": it.get("kind") or "research",
                "status": it.get("status", ""),
                "paths": entry_paths(it),
                "concepts": it.get("concepts") or [],
            })
        for i, r in enumerate(j.get("record", []), 1):
            out.append({
                "sid": f"{d}#R{i}", "layer": "record", "date": d, "rank": None,
                "title": r.get("title", ""),
                "summary": r.get("what", ""),
                "kind": r.get("kind") or "research",
                "status": r.get("status", ""),
                "paths": entry_paths(r),
                "concepts": r.get("concepts") or [],
            })
    for e in out:
        # tok 目前**不參與提名**（實測詞彙重疊在這個尺度上反向：真的同一件事的
        # 兩項 dice 只有 0.02，不同主線的反而 0.12）。保留是為了校準時可以量。
        e["tok"] = tokens(e["title"] + " " + e["summary"])
        e["mod"] = dominant_module(e["paths"])
    thread_names(out)          # 填 e["name"]（主判準）
    return out, missing, advisor


# ---------- 合併提名 ----------

def pair_evidence(a, b):
    """提名的**兩條路**，任一條成立即可。回傳 (證據 list, jaccard)。

    ⓐ **共用同一個主線名字**（主判準）
    ⓑ **同模組 ＋ 改同一批檔**（原本的路徑物證，保留當第二條路）

    ⚠️ **為什麼是「任一條」而不是「都要」**：主線名字抓不到「沒有名字但明顯是
    同一次動作」的情況（例如兩項都只改了 `docs/` 底下同一批檔、標題裡沒有任何
    專有名字）；反過來路徑物證抓不到「同一條線但散在不同目錄」。兩條互補。
    ⛔ 改成「都要成立」會退回早期版本的弱版（五個區間四個 0 合併）。
    """
    ev = []
    if a.get("name") and a["name"] == b.get("name"):
        ev.append("name")
    j = jaccard(a["paths"], b["paths"])
    if a["mod"] and a["mod"] == b["mod"] and j >= PATH_JACCARD:
        ev += ["module", "files"]
    return ev, j


def nominate(entries):
    """湊滿兩種物證才提名 —— 對應 daily-log「符合兩條以上才合併」的形狀。

    ⚠️ union-find 是**傳遞的**：A-B 與 B-C 各自成立，A 與 C 就會進同一組，
    即使 A 與 C 之間沒有直接證據。這是刻意的（一條依賴鏈本來就是這樣串起來的），
    但也是這支最可能誤合的地方 —— 所以輸出一定要列出**每一對的證據**，
    讓 LLM 與使用者看得到「A 跟 C 其實沒有直接關係」。

    ⚠️ **沒有 artifacts 的項目一定落單**（`mod` 是 None）。純討論、純量測、
    純讀論文都不會留下檔案 —— 那不是雜訊，是這支看不見的那一半，
    要由 LLM 在關卡① 前補掛（做法與 `cluster_threads.py` 的孤兒相同）。
    """
    parent = {e["sid"]: e["sid"] for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    links = []
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            ev, j = pair_evidence(a, b)
            if ev:
                links.append((a["sid"], b["sid"], ev, round(j, 2)))
                ra, rb = find(a["sid"]), find(b["sid"])
                if ra != rb:
                    parent[ra] = rb

    buckets = defaultdict(list)
    for e in entries:
        buckets[find(e["sid"])].append(e)

    groups, singles = [], []
    for members in buckets.values():
        members.sort(key=lambda e: (e["date"], e["layer"] != "item", e["sid"]))
        if len(members) == 1:
            singles.append(members[0])
        else:
            groups.append(members)
    groups.sort(key=lambda g: (-len(g), g[0]["date"]))
    return groups, singles, links


# ---------- 週層級排序信號 ----------

def _grade(n, hi, mid, lo, none_):
    return hi if n >= 10 else mid if n >= 4 else lo if n >= 1 else none_


def signals(members):
    """只用週報看得到的東西算。**分數不寫回日誌 JSON**（沿用 daily-log 的紀律）。

    | 信號 | 為什麼 | 權重 |
    |---|---|---|
    | 當日排名 | `items[]` 已照當天分數由高到低排序（daily-log SKILL Step 4-1），
    |          | **順序本身就把日層級的分數帶過來了** —— 這是週報端唯一拿得到的殘跡 | 3 |
    | 跨日天數 | 週報要的正是跨日的線；一次性嘗試通常不是 | 3 |
    | 落地規模 | 合併組去重後的檔案數。沿用 daily-log 的分級（0 是**扣分**不是 0 分） | 2 |

    ⛔ **`kind` 不計分。** `editorial_policy §1b` 明訂研究基礎建設（研究紀錄怎麼產、
    報告方法怎麼定）可以上主線 —— **工具的名字不決定去處，產物的效果決定**。
    日誌那套的 `infra −3` 是**日層級**的判準，搬到週層級會把該講的工具線直接壓掉。
    照印不計分。

    ⛔ **教授交代不計分**，因為它不可數（要語意比對才知道哪一組回應了哪一條）。
    它是排序的**第一順位**（`editorial_policy §3`），做法是印在最上面、
    由關卡① 手動置頂，不是塞進一個分數裡稀釋掉。
    """
    ranks = [m["rank"] for m in members if m["rank"]]
    best = min(ranks) if ranks else None
    s_rank = 0 if best is None else 3 if best == 1 else 2 if best <= 3 else 1
    span = len({m["date"] for m in members})
    s_span = 3 if span >= 3 else span
    files = set().union(*[m["paths"] for m in members]) if members else set()
    s_files = _grade(len(files), 3, 2, 1, -1)
    return {
        "best_rank": best, "span_days": span, "files": len(files),
        "n_item": sum(1 for m in members if m["layer"] == "item"),
        "n_record": sum(1 for m in members if m["layer"] == "record"),
        "kinds": sorted({m["kind"] for m in members}),
        "score": 3 * s_rank + 3 * s_span + 2 * s_files,
    }


def signal_line(sg):
    r = f"當日最佳排名 {sg['best_rank']}" if sg["best_rank"] else "只在記錄層"
    return (f"{r}・跨 {sg['span_days']} 天・改 {sg['files']} 檔"
            f"・{sg['n_item']} 項呈現層+{sg['n_record']} 項記錄層"
            f"・{'/'.join(sg['kinds'])}")


# ---------- 輸出 ----------

def build(entries):
    groups, singles, links = nominate(entries)
    ev_by_pair = {(a, b): (ev, j) for a, b, ev, j in links}
    out = []
    for n, members in enumerate(groups, 1):
        sids = [m["sid"] for m in members]
        pairs = [{"a": a, "b": b, "evidence": ev, "jaccard": j}
                 for (a, b), (ev, j) in ev_by_pair.items()
                 if a in sids and b in sids]
        out.append({"gid": f"G{n}", "members": sids, "pairs": pairs,
                    "signals": signals(members), "_members": members})
    for n, e in enumerate(singles, len(groups) + 1):
        out.append({"gid": f"G{n}", "members": [e["sid"]], "pairs": [],
                    "signals": signals([e]), "_members": [e]})
    out.sort(key=lambda g: (-g["signals"]["score"], g["_members"][0]["date"]))
    return out


def coverage_note(entries):
    """機械看得見多少。⚠️ 沒有這一句，「0 組合併」會被讀成「本週沒有可合併的」。

    v1 舊日誌沒有 `artifacts` 欄位（BACKLOG B7），退回正則從自由文字撈路徑 ——
    撈得到是巧合。實測區間A：18 項有 12 項撈不到任何模組，
    於是提名 0 組。那不是「這週的事都各自獨立」，是**這支看不見**。
    """
    blind = [e["sid"] for e in entries if not e["mod"]]
    if len(blind) * 2 <= len(entries):
        return None
    return (f"⚠️ **{len(blind)}/{len(entries)} 項沒有可用的 artifacts，這支看不見它們**"
            "（v1 舊日誌沒有 `artifacts` 欄位，見 `BACKLOG.md` B7）。\n"
            "> **「0 組合併」不代表本週的事都各自獨立** —— 合併要靠 LLM 讀內容自己判，"
            "判準見 `editorial_policy.md §5a`。")


def render_md(groups, advisor, days, missing, n_entries, note=None):
    n_merged = sum(1 for g in groups if len(g["members"]) > 1)
    L = ["# 合併提名與排序信號（機械產出，未裁決）", "",
         f"區間 {days[0]} ~ {days[-1]}，{n_entries} 個項目（item + record）"
         f" → {len(groups)} 組，其中 {n_merged} 組是跨項合併的提名。", ""]
    if missing:
        L += [f"⚠️ 缺日誌：{'、'.join(missing)}", ""]
    if note:
        L += ["> " + note, ""]
    L += ["> ⚠️ **這是提名，不是判斷。** 機械只驗得了三種物證"
          "（同檔案／同模組／同一批詞），",
          "> 而 daily-log 的合併判準是語意的（推進同一目標／同一依賴鏈／同一交付物"
          "／會被寫進週報的同一頁）。",
          "> **逐組確認：寫得出一個說得出共同目標的標題嗎？寫不出來就拆回去。**", "",
          "> ⚠️ 分數只用來**排序**，不決定上不上台 —— 那是關卡① 使用者的事。",
          "> 分數看不出為什麼，所以每組都印原始信號；一句話就推翻得了。", ""]

    if advisor:
        L += ["## ⚑ 教授交代（排序第一順位，不計分）", ""]
        for a in advisor:
            mark = "未答" if a.get("kind") == "question" and not a.get("answered") \
                   else a.get("kind", "")
            L.append(f"- [{a['date']}][{mark}] {a.get('text','')}")
        L += ["", "**哪一組回應了上面哪一條，機械判不出來 —— 由 LLM 標出來，"
              "並在排序時置頂。**", ""]
    else:
        L += ["## ⚑ 教授交代（排序第一順位，不計分）", "",
              "本週 `advisor` 欄位是空的。**這不代表教授沒有交代** —— 那一欄只有"
              "使用者補得了，關卡① 一定要問。", ""]

    L += ["## 合併提名（分數高 → 低）", ""]
    for g in groups:
        m = g["_members"]
        head = f"### {g['gid']}　{len(m)} 項　score {g['signals']['score']}"
        if len(m) == 1:
            head += "　（未提名合併）"
        L += [head, "", f"信號：{signal_line(g['signals'])}", ""]
        if len(m) > BIG_GROUP:
            L += [f"⚠️ **這組有 {len(m)} 項，可能是整條主線而不是一件事。**"
                  "　主線層級由 `threads.md` 負責；這裡該問的是"
                  "「這幾項寫得出**一個**說得出共同目標的標題嗎」，寫不出來就拆。", ""]
        for e in m:
            tag = "" if e["layer"] == "item" else "〔記錄層〕"
            mod = e["mod"] or "（無 artifacts）"
            L.append(f"- `{e['sid']}` {tag}**{e['title']}** — {e['summary'][:80]}"
                     f"　〔{mod}〕")
        if g["pairs"]:
            # ⚠️ 後修（獨立驗證抓到）：這裡原本寫死「同模組 ＋ 改同一批檔」
            # 並只印 Jaccard —— 但主判準換成「主線的名字」之後，名字路線提名的那些對
            # 會被印成「同模組 ＋ 改同一批檔……Jaccard 0.0」，**說的跟做的不是同一件事**。
            # `evidence` 早就在 JSON 裡了，只是從來沒被渲染出來。
            # 這一段是**誤合唯一看得見的地方**（合成資料實測：`utf8`／`k8s`／`v2`
            # 這種帶數字的通用技術詞會變成主線鍵），印錯等於把它藏起來。
            nm = {e["sid"]: e.get("name") for e in m}
            # B17-1：逐對列印是 O(n²) —— 16 項的一組印了 120 對，其中 115 對的理由
            #    逐字相同（「共用主線名字 X」）。這份檔同時進協調者的 context 與
            #    thread_finder 的派遣包，而且真正帶資訊的強物證（同模組＋同一批檔）
            #    被埋在裡面。⭐ 只靠名字成立的對**摺疊成一列**（列出涉及的成員），
            #    強物證照舊逐對列、Jaccard 由高到低。
            strong = [p for p in g["pairs"] if "files" in p["evidence"]]
            weak = [p for p in g["pairs"] if "files" not in p["evidence"]]
            L += ["", f"  提名依據（{len(g['pairs'])} 對；強物證逐對列、只靠名字的摺疊）："]
            for p in sorted(strong, key=lambda x: -x["jaccard"]):
                why = [f"同模組 ＋ 改同一批檔（Jaccard {p['jaccard']}）"]
                if "name" in p["evidence"]:
                    why.insert(0, f"共用主線名字 `{nm.get(p['a']) or '?'}`")
                L.append(f"  - `{p['a']}` ↔ `{p['b']}`：{'、'.join(why)}")
            by_name = {}
            for p in weak:
                key = nm.get(p["a"]) or nm.get(p["b"]) or "?"
                by_name.setdefault(key, set()).update((p["a"], p["b"]))
            for key, sids_ in sorted(by_name.items(), key=lambda kv: -len(kv[1])):
                n_pairs = sum(1 for p in weak if (nm.get(p["a"]) or nm.get(p["b"]) or "?") == key)
                L.append(f"  - **只靠共用名字 `{key}`**：{n_pairs} 對，涉及 {len(sids_)} 項 —— "
                         + "、".join(f"`{x}`" for x in sorted(sids_)))
            L.append("")
            L.append("  ⚠️ 只靠**共用名字**成立的對，要確認那個名字是不是"
                     "「一條主線的名字」——`utf8`／`k8s`／`v2`／`pandas2` 這種"
                     "帶數字的通用技術詞也會通過正則，把不相關的兩件事串起來。")
            L.append("")
            L.append("  ⚠️ 沒有出現在上面的成員，是被**傳遞**併進來的"
                     "（A-B、B-C 成立就會把 A 與 C 放同一組）——"
                     "那幾項要特別確認是不是同一件事。")
        L.append("")

    L += ["## 對帳（不可省）", "",
          "`check_deck.py` 要求日誌裡的每一項不是上投影片就是寫進 `plan.dropped`。",
          "**合併不豁免對帳** —— 一組上台時，`source` 要列出組內**全部**成員的 sid；",
          "一組被篩掉時，`plan.dropped` 也要逐個 sid 記，不能只記組。", ""]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="週報的日期目錄（產物寫進 _work/1_materials/）")
    ap.add_argument("--data", default=DEF_DATA)
    _range.add_args(ap)
    a = ap.parse_args()

    start, end = _range.from_args(a)
    import datetime as dt
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    days = [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]

    entries, missing, advisor = load_entries(a.data, days)
    if not entries:
        sys.exit(f"[merge] {a.data} 在 {days[0]}~{days[-1]} 沒有任何日誌項目")
    groups = build(entries)
    note = coverage_note(entries)
    md = render_md(groups, advisor, days, missing, len(entries), note)

    payload = {"range": [days[0], days[-1]],
               "groups": [{k: v for k, v in g.items() if k != "_members"}
                          for g in groups],
               "advisor": advisor}
    if a.out:
        # 過程產物 → `_work/1_materials/`（呼叫者只給日期目錄，子資料夾我們自己開）
        d = paths.work_dir(a.out, "materials", create=True)
        open(os.path.join(d, "merge_groups.md"), "w",
             encoding="utf-8").write(md)
        json.dump(payload, open(os.path.join(d, "merge_groups.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=1)
        n_merged = sum(1 for g in groups if len(g["members"]) > 1)
        print(f"[merge] {len(entries)} 項 → {len(groups)} 組"
              f"（{n_merged} 組是合併提名）→ {d}/merge_groups.md")
        if note:
            print("[merge] " + note.replace("\n> ", " ").replace("**", ""),
                  file=sys.stderr)
    else:
        print(md)


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# 怎麼校準（改門檻或權重時要在這裡記依據）
#
# ── 主判準換成「主線的名字」（⚠️ 探索性結果，尚未獨立驗證）──────
#
# 事前理由（唯一乾淨的辯護）：**一條主線的名字，一定會被反覆提到。**
# 這句話在看資料之前就講得出來 —— 屬於「基於原理」而非「基於量測」的選擇
# （判準：如果量出來的結果相反，我還會這樣選嗎？會 → 站得住）。
#
# 改前／改後（五個區間，實測）：
#   區間A（5 天）    18 →  18  ／  18 →  15
#   區間B（3 天）     5 →   5  ／   5 →   5      （3 天 5 項的冷清區間）
#   區間C（4 天）    27 →  19  ／  27 →   6
#   區間D（2 天）     9 →   9  ／   9 →   4
#   區間C＋D（6 天）    36 →  28  ／  36 →  10
#
# 36 → 10 的三個合併組都對：21 項的日誌工具線、6 項的週報工具線、
# 2 項的資料規則。18 → 15 那組是 4 項的樣本評估線（別名規則讓 `CL771_ALT`
# 併回 `CL771`）。**沒有看到誤合。**
#
# ⚠️ **這是探索性結果，不是已確立的結論。**
#    它是連續換三種信號、在**同一組**資料（區間C＋D，6 天）上調出來的，
#    而且調的人**看得到答案**（知道真主線是哪兩條）。依
#    `.claude/rules/ml-evaluation.md §3.6`「選擇也是一種擬合」，這屬於
#    **基於量測的選擇**。⛔ 不得寫成「合併能力提升到 86%」這種結論。
#
# **下一次實跑要驗什麼**：換另一週的日誌跑一次，看是否也收到個位數的組。
#   · 有 → 這個原理站得住，可以把「探索性」的標籤拿掉
#   · 沒有 → 回頭看是哪一種形狀漏掉（是名字沒被反覆提到？還是名字抽不出來？）
#
# ── 已知的兩個限制（都實測過，不是猜的）─────────────────────────────
#
# ① **v1 舊日誌完全看不見**（區間A＋B，舊 schema 的 8 天）：18 項有 **0 項**抽得到名字。
#    那批的標題是純中文、沒有 kebab/snake 識別字，也沒有 `artifacts` 與
#    `concepts` 欄位（schema v1）。→ 與 `BACKLOG.md` B7 是同一個根因。
#    ⚠️ 「0 組合併」在那種區間**不代表這些事各自獨立**，只代表這支看不見。
#
# ② **沒有數字的專業單字抓不到**：`pipeline`、`throughput` 這種純字母又沒有
#    連字號的詞，兩個正則都不中。放寬成「所有拉丁詞」試過 —— **會誤合**
#    （`claude`／`json`／`skill` 變成主線鍵，把不相關的併成一組 10 項），
#    所以刻意不放寬。⚠️ 代價是那類主線只能靠第二條路（路徑物證）或 LLM 補掛。
#
# ③ ⚠️ **這是同一組資料上的第五次信號設計**。前四次見「三種失敗的抽法」＋
#    「所有拉丁詞」那次。每一次都是看了結果再改 —— **擬合的風險是累積的**。
#    唯一沒有隨著迭代改變的是那句事前理由（「主線的名字會被反覆提到」）與
#    那條方向性（誤合比漏合嚴重）。**下一週的實跑是唯一能證明它的東西。**
#
# ── 其餘門檻（沿用，未校準）──────────────────────────────────────
# · `PATH_JACCARD = 0.15`、`MOD_DEPTH = 3`：第二條路（路徑物證）的門檻。
# · 排序權重（`3*rank + 3*span + 2*files`）：設計時定的起點。
#
# 第一版的失敗仍值得記著：原本用「路徑交集」＋「共用前綴」當兩條**獨立**證據，
# 實跑當場失效 —— 路徑有交集時前綴必然也有，兩條其實是同一條，
# 27 項被串成一組 15 項的巨無霸。獨立性要自己檢查，不能假設。
