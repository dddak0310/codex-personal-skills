#!/usr/bin/env python3
"""從日誌 .data/*.json 抽出這週的素材，產出 materials.md 與 deck.draft.json。

分工（重要）：
  這支腳本**只做機械抽取**，不做選材判斷。它把一週的日誌壓成一份精簡素材清單，
  並把每個 item 展成候選頁；**選哪幾件事講、什麼順序、怎麼銜接，是模型的編輯工作**，
  由模型把 deck.draft.json 改寫成 deck.json。

  骨架來自哪裡：每天的 headline 是使用者當天自己判定的重點，
  所以線（thread）的種子直接取自 headline，不由模型憑空編。

用法：
  build_deck.py --out <週報目錄> [--days 2024-03-04 2024-03-08] [--data <.data 路徑>]
  build_deck.py --out ... --last 7          # 最近 7 天
"""
import argparse, datetime as dt, glob, json, os, re, sys

import _range
import merge_items
import paths

# N69：草稿的字數上限**不在這裡另立一份**。唯一的定義是 check_deck.py 的 `LIMITS`
# （`deck_schema.md:133`：「字數上限一律指路 LIMITS，⛔ 不在文件裡再寫一次數字」）。
# 原本這裡寫死 44／32／60，是 N42 清理 `.md` 時漏掉的同一家族副本 ——
# 草稿被裁得比檢查允許的還短，而**沒有任何一處寫出為什麼要更短**。
from check_deck import LIMITS as DECK_LIMITS

# 路徑一律由 paths.py 解析（環境變數 → ~/.config/weekly-deck/ → 慣例），
# 日誌 repo 的部分再轉發給 daily-log 自己的 paths.py。
# ⛔ 不要寫死 —— 這兩個 skill 是配套的，路徑規則只該有一份，而且要能在別人的機器上跑。
# ⛔ 也不要 try/except 退回預設值：找不到 daily-log 就該直接報錯，
#    靜默用一個猜出來的路徑只會產出一份空週報。
DEF_DATA = paths.data_dir()
# 實際使用的 .data 目錄（main() 依 --data 設定；_groups() 要用它去重讀日誌）。
DATA_DIR = [DEF_DATA]


def load_days(data_dir, days):
    out = []
    for d in days:
        p = os.path.join(data_dir, f"{d}.json")
        if os.path.isfile(p):
            out.append(json.load(open(p, encoding="utf-8")))
        else:
            print(f"[build] ⚠️ 沒有 {d} 的日誌（{p}）", file=sys.stderr)
    return out


def daterange(a, b):
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(a + dt.timedelta(n)).isoformat() for n in range((b - a).days + 1)]


def clip(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "…"


def table_digest(t, i):
    cols = "｜".join(t.get("columns", []))
    return (f"      表{i}「{t.get('caption','')}」 {len(t.get('rows',[]))}列×"
            f"{len(t.get('columns',[]))}欄：{cols}")


PATH_RE = re.compile(r"\b((?:docs|results|pipeline|data|config)/[\w./\-]+|\.claude/[\w./\-]+)")
# 專案根：日誌裡的路徑是相對於它的，用來標「這個檔到底還在不在」。
PROJ = paths.project_root()


def _artifact_paths(entry):
    """日誌 schema v2 的 artifacts 欄位：日誌自己列的檔案／指令／產出。

    v1 沒有這欄，只能用正則從自由文字裡撈路徑——撈得到是巧合
    （路徑要剛好被寫進 details 或 result 才撈得到）。
    v2 起改讀這裡，正則降為 v1 舊檔的後備。
    """
    art = entry.get("artifacts") or {}
    out = []
    for key in ("files", "outputs"):
        out += [str(v) for v in (art.get(key) or [])]
    return out


def _search_bases():
    """artifacts 的相對路徑要接在哪個根上 —— **不只一個**。

    ⚠️ 這裡曾經只有 `PROJ` 一個根，後果是靜默的：
    凡是那一週的工作發生在**別的 repo**（做工具、改 skill、整備公版），
    它的 artifacts 全部會被判成「⚠️不存在」，於是那條主線一個可深入的原檔都沒有 ——
    而 SKILL.md 同時要求「講機制的頁一定要讀原檔」。不報錯，只是那幾頁沒有原料。

    ⛔ 不要把這串寫死成專案名。每一個都由 `paths.py` 解析，
    順序 = 由專有到通用，第一個找得到的就是答案（會印出來，看得出來自哪個 repo）。
    """
    seen, out = set(), []
    for label, fn in (("專案", paths.project_root),
                      ("日誌 repo", paths.log_repo),
                      ("本 skill", lambda: os.path.dirname(
                          os.path.dirname(os.path.abspath(__file__))))):
        try:
            p = fn()
        except Exception:
            continue
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            out.append((label, p))
    return out


BASES = _search_bases()

# 「這根本不是一個路徑」的形狀。日誌的 artifacts 欄是人寫的，裡面混著
# URL、commit 清單、帶中文註記的字串 —— 拿它們去 os.path.exists 必然「不存在」，
# 那是**假警報**，會把真正找不到的檔淹掉。
_URLISH = ("http://", "https://", "git@", "ssh://")
# 沒有 scheme 的 URL：`github.com/someone/some-skill（private）`。
# 它長得跟相對路徑一模一樣（第一段有點、後面是斜線），拿去 os.path.exists 必然
# 「不存在」→ 被報成「定位不到」→ 又一則假警報。**第一段是網域**就不是路徑。
_HOSTISH = re.compile(r"^(?:www\.)?[\w-]+(?:\.[\w-]+)*\."
                      r"(?:com|org|net|io|dev|gov|edu|co|tw|cn|ai|sh)(?:/|$)", re.I)
# shell 展開／萬用字元寫法：`~/.config/daily-log/{repo,audience,watch-paths}`。
# 那是**一句話講四個檔**，不是一個路徑；逐字拿去檢查存在性一定失敗。
_GLOBBISH = re.compile(r"[{}*?\[\]]")


def _is_pathlike(s):
    if s.startswith(_URLISH) or _HOSTISH.match(s):
        return False
    if _GLOBBISH.search(s):
        return False
    if re.search(r"[一-鿿]", s):        # 帶中文註記（例：`.../（36 檔，688 KB）`）
        return False
    if re.search(r"\s", s):                     # 帶空白（例：`repo commit 6585744、cd115a3`）
        return False
    return True


def _is_prior_deck(s, resolved):
    """這是**上一份週報自己的產物**，不是這週的原料。

    ⚠️ 為什麼要獨立分類：凡是「這週的工作就是做週報工具」的一週，
    artifacts 必然指回 `weekly_reports/`／`<reports-root>/`，
    於是素材清單會把**上一份的成品**推薦成這一份的原料 —— 等同鼓勵抄上一份。
    它們不是不存在，是**去處不同**：可以拿來對照格式，⛔ 不可以拿來當內容來源。
    """
    if s.startswith("_work/") or "/_work/" in s:
        return True
    if re.search(r"(^|/)weekly_reports(/|$)", s):
        return True
    try:
        root = os.path.realpath(paths.reports_root())
    except Exception:
        return False
    return bool(resolved) and os.path.realpath(resolved).startswith(root + os.sep)


def _is_selflocating(p_):
    """這個路徑**自己就說了它在哪** —— 絕對路徑或 `~/` 家目錄路徑。

    ⚠️ 它們找不到時**不是「定位不到」**：位置寫得清清楚楚，只是這台機器上沒有
    （別的 repo、別台機器、或已經搬走）。混進「定位不到」節等於製造假警報 ——
    那一節的用途是「這一項只記了相對路徑，不知道是哪個 repo，去問使用者」，
    自帶絕對位置的東西根本不需要問。
    """
    return os.path.isabs(p_) or p_.startswith("~/")


def _resolve(p_):
    """回傳 (絕對路徑, 來自哪個根)；找不到回 (None, None)。"""
    if p_.startswith("~/"):
        # `~/.claude/hooks/...` 是真的讀得到的檔，只是根不是任何一個 repo。
        # 不展開的話它會被當成「定位不到」，而它其實是**可深入的原料**。
        ex = os.path.expanduser(p_)
        return (ex, "家目錄") if os.path.exists(ex) else (None, None)
    if os.path.isabs(p_):
        return (p_, "絕對路徑") if os.path.exists(p_) else (None, None)
    for label, base in BASES:
        cand = os.path.join(base, p_)
        if os.path.exists(cand):
            return cand, label
    return None, None


def source_index(days):
    """日誌自己就指向了原料 —— 把 details/result 裡提到的檔案路徑抽出來當索引。

    為什麼要這個：日報是**壓縮過的**（每天寫給教授看，保留結論、丟掉機制）。
    要講「怎麼做的」「有哪些」就一定不夠，得回頭讀 docs/ 的原檔。
    只讀日誌會做出空洞的頁：日誌多半只有統計（「11 現成／2 便宜／8 部分缺」），
    能畫成圖表的結構在 docs/ 的原檔裡（feature_registry.md、COMPETITIVE_MAP.md 之類）。

    分四堆，⛔ 不要混在一起（混在一起就是這一節以前的樣子）：
      ✅ 可深入的原料　⛔ 前期週報產物　📦 不在這台機器上　⚠️ 定位不到　🔗 非檔案的引用

    ⚠️ 「⚠️ 定位不到」要**短**才有用（它是一張「去問使用者」的待辦清單）。
    凡是能自己判定去處的 —— URL、`~/`、絕對路徑、`{a,b}` 這種一句講多個檔的寫法 ——
    一律先分出去；它們留在那一節只會是假警報，把真正該問的那幾條淹掉。
    """
    hits = {}
    for d in days:
        entries = ([("", i, it) for i, it in enumerate(d.get("items", []), 1)]
                   + [("R", i, r) for i, r in enumerate(d.get("record", []), 1)])
        for layer, i, it in entries:
            tag = f"{d['date']}#{layer}{i}"
            found = set(_artifact_paths(it))
            if not found:
                # v1 舊檔沒有 artifacts，退回正則
                blob = " ".join(str(it.get(k, "")) for k in
                                ("details", "result", "approach", "interpretation",
                                 "what", "why_demoted"))
                found = set(PATH_RE.findall(blob))
            for m in found:
                hits.setdefault(m, []).append(tag)
    ok_, prior, miss, refs, elsewhere = [], [], [], [], []
    for p_, src in sorted(hits.items()):
        who = "、".join(sorted(set(src)))
        if not _is_pathlike(p_):
            refs.append(f"- 🔗 `{p_}` ← {who}")
            continue
        abs_, base = _resolve(p_)
        if _is_prior_deck(p_, abs_):
            prior.append(f"- ⛔ `{p_}` ← {who}")
        elif abs_:
            ok_.append(f"- ✅ `{abs_}`　〔{base}〕 ← {who}")
        elif _is_selflocating(p_):
            # 位置寫死了、這台機器上沒有 → 不是「定位不到」，是「不在這裡」。
            elsewhere.append(f"- 📦 `{p_}` ← {who}")
        else:
            miss.append(f"- ⚠️ `{p_}` ← {who}")

    L = ["## 四、可深入的原料（日誌的 artifacts 欄位）", "",
         "來源優先讀 `artifacts`（日誌自己列的）；v1 舊檔沒有那欄，退回從自由文字撈路徑。",
         "編號帶 `R` 的來自**記錄層**（`record[]`）——那層是專門為了讓這裡有東西可撈而存在的。", "",
         "⚠️ **日報是壓縮過的。** 凡是要講「機制」「怎麼做的」「有哪些」的頁面，",
         "**先讀這裡對應的檔**，不要只用日誌的摘要——摘要沒有清單也沒有機制。", "",
         "相對路徑會依序接上這幾個根（第一個找得到的就是答案）："
         + "、".join(f"{lb}=`{bp}`" for lb, bp in BASES), ""]
    L += ok_ or ["（無）"]

    if prior:
        L += ["", "### ⛔ 前期產物，**不是原料**", "",
              "這些是**上一份週報自己的產出**（`weekly_reports/`、`<reports-root>/`、`_work/`）。",
              "可以拿來對照格式與既有說法，⛔ **不可以拿來當這一份的內容來源** ——",
              "凡是「這週的工作就是做週報工具」的一週，artifacts 必然指回這裡，",
              "照單全收等於拿上一份的成品當這一份的素材。", ""] + prior

    if miss:
        L += ["", "### ⚠️ 定位不到（多 repo 的已知限制）", "",
              "上面那幾個根都找不到。**多半不是檔案不見了**，是那一項的工作發生在",
              "另一個 repo（做工具、改 skill、整備公版），而日誌只記了相對路徑。",
              "⛔ 不要據此判定「沒有原料可讀」—— 先問使用者那條線的原始檔在哪個 repo，",
              "或直接去那個 repo 讀（本節的 `←` 標了它出自哪一個日誌項）。", ""] + miss

    if elsewhere:
        L += ["", "### 📦 不在這台機器上（絕對路徑／家目錄）", "",
              "這些路徑**自己就寫明了位置**（`/...` 或 `~/...`），只是這台機器上沒有 ——",
              "別的 repo、別台機器，或已經搬走。⛔ 不要拿它們去問「這是哪個 repo」，",
              "位置就在字面上；要讀就直接去那個位置找。", "",
              "（跟下一節的差別：那一節是**只記了相對路徑**、不知道根在哪，那才需要問。）",
              ""] + elsewhere

    if refs:
        L += ["", "### 🔗 非檔案的引用", "",
              "URL、commit、帶說明文字的字串。**不是路徑**，所以不做存在性檢查",
              "（以前它們會被判成「不存在」，假警報把真正找不到的檔淹掉）。", ""] + refs

    return "\n".join(L) + "\n"


def materials(days):
    """給模型讀的精簡素材（比原始 JSON 小約 4 倍）。

    ⚠️ **這份是截斷過的**，而且以前沒有任何地方說出這件事 ——
    於是每個角色都把它當成完整的素材，缺了也不知道要去哪裡補
    （實測：`details` 整欄沒被渲染，全流程沒有一個角色看過那 2,480 字）。
    現在開頭一律印出原始 `.data/*.json` 的絕對路徑，讓「還有更完整的東西」
    這件事變成寫在紙上的、而不是要靠人記得的。
    """
    L = ["# 本週素材（機械抽取，未做選材）", ""]
    raw = [os.path.join(DATA_DIR[0], f"{d['date']}.json") for d in days]
    L += ["> ⚠️ **本檔的每個欄位有字數上限**（摘要 300、問題 300、做法 500、"
          "結果 900、解讀 600、細節 1200、還缺 400 字元）。上限留了 1.4 倍以上餘裕，"
          "正常情況不會截到；**行尾有 `…` 才代表被截**。",
          "> 覺得某一項「講不出具體的東西」時，**先去讀它的原始 JSON**，不要下結論說日誌沒寫：",
          ""] + [f"> - `{p_}`" for p_ in raw] + [
          "",
          "> 一項的完整內容 ＝ 那天 JSON 裡的 `items[i-1]`（sid `日期#i`）",
          "> 或 `record[i-1]`（sid `日期#Ri`）。逐項的原檔與指令列在該項底下的",
          "> 「原檔：」「指令：」兩行，全域索引在 §四。", ""]

    # ⚑ advisor 是 daily-log schema v2 專為週報而設的欄位，而且是**排序的第一順位**
    #    （editorial_policy §3：教授交代的排最前）。
    #    ⚠️ 它是日誌裡唯一「沒有自動來源就會壞掉」的輸入 —— 掃不到就是真的沒記到，
    #    這時要在關卡① 直接問使用者，不要當成「本週教授沒交代」。
    adv = [(d["date"], a) for d in days for a in (d.get("advisor") or [])]
    L += ["## ⚑ 零、教授交代（排序第一順位）", ""]
    if adv:
        for date, a in adv:
            kind = a.get("kind", "")
            mark = "未答" if kind == "question" and not a.get("answered") else kind
            L.append(f"- [{date}][{mark}] {a.get('text','')}")
    else:
        L += ["本週日誌的 `advisor` 欄位是空的。**這不代表教授沒有交代** ——",
              "那一欄只有使用者補得了。關卡① 要直接問他：",
              "上次問了什麼還沒回答、哪些是他指定的方向。"]
    L += [""]

    L += ["## 一、每日 headline —— 這是使用者當天自己判定的重點，線的種子", ""]
    for d in days:
        L.append(f"- **{d['date']}**　{d['headline']}")
    # ⚠️ 改：這一節原本**按日期分節**，於是同一件事做三天就變成
    #    三個看起來平行的候選。首次實跑那份實測：4 天 16 個 item，
    #    「daily-log 改版」一件事就佔了 7 項 —— 關卡① 要在十幾個平行候選裡挑重點，
    #    於是**重點很雜**。根因不是選材判準不好，是**選材之前沒有先合併**
    #    （daily-log 的合併判準只在單日內生效，跨日沒有人管）。
    #    現在改成按 merge_items.py 的合併組分節，組內仍按日期排。
    groups, gerr = _groups(days)
    L += ["", "## 二、逐項清單（按合併組，不按日期）", "",
          "> ⚠️ **組是機械提名的，不是判斷。** 依據只有兩種物證"
          "（主要模組相同 ＋ 改的是同一批檔）；",
          "> daily-log 的合併判準是語意的（推進同一目標／同一依賴鏈／同一交付物"
          "／會被寫進週報的同一頁）。",
          "> **逐組確認：寫得出一個說得出共同目標的標題嗎？寫不出來就拆回去。**",
          "> 沒有 artifacts 的項目一定落單，那不是雜訊，是機械看不見的那一半。", "",
          "> ⚠️ `score` 只用來**排序**，不決定上不上台 —— 那是關卡① 使用者的事。",
          "> 完整的提名依據與信號在 `merge_groups.md`。", ""]
    if gerr:
        L += [f"⚠️ 合併提名失敗（{gerr}），退回按日期列。", ""]
    by_sid = {}
    for d in days:
        for i, it in enumerate(d.get("items", []), 1):
            by_sid[f"{d['date']}#{i}"] = ("item", d, it)
        for i, r in enumerate(d.get("record", []), 1):
            by_sid[f"{d['date']}#R{i}"] = ("record", d, r)

    for g in groups:
        sg = g["signals"]
        head = f"### {g['gid']}　{len(g['members'])} 項　score {sg['score']}"
        if len(g["members"]) == 1:
            head += "　（未提名合併）"
        L += [head, f"　　信號：{merge_items.signal_line(sg)}"]
        if len(g["members"]) > merge_items.BIG_GROUP:
            L.append(f"　　⚠️ **{len(g['members'])} 項可能是整條主線而不是一件事** —— "
                     "寫不出一個共同標題就拆。")
        for sid in g["members"]:
            kind, d, it = by_sid.get(sid, (None, None, None))
            if kind == "item":
                _item_lines(L, sid, it)
            elif kind == "record":
                L.append(f"  - `{sid}` 〔記錄層〕**{it.get('title')}**")
                L.append(f"      {clip(it.get('what'), 1200)}")
                if it.get("why_demoted"):
                    L.append(f"      未進呈現層的理由：{clip(it.get('why_demoted'), 160)}")
                _origin_lines(L, it)
        L.append("")

    # issues／未收錄／給教授的問題不是「工作項」，沒有合併的對象，仍按日期列。
    L += ["## 二之二、其他（按日期）", ""]
    for d in days:
        rows = []
        for i, x in enumerate(d.get("issues", []), 1):
            rows.append(f"  - `{d['date']}#issue{i}` (問題) {x.get('title')}"
                        f" → {clip(x.get('resolution'), 160)}")
            if x.get("detail"):
                rows.append(f"      細節：{clip(x.get('detail'), 200)}")
        if d.get("not_recorded"):
            rows.append(f"  - `{d['date']}#未收錄` 當天被擠掉 "
                        f"{len(d['not_recorded'])} 個候選：")
            for x in d["not_recorded"]:
                rows.append(f"      · {x.get('title')} —— {clip(x.get('reason'), 100)}")
        if d.get("questions_for_advisor"):
            rows.append(f"  - ⚑ 給教授的問題 {len(d['questions_for_advisor'])} 則"
                        "（必講且排最前）")
        if rows:
            L.append(f"### {d['date']}　{d.get('phase','')}")
            L += rows + [""]

    return _stats(L, days)


def _groups(days):
    """跨日合併提名。失敗一律退回「每項自成一組」，不要讓素材產不出來。

    ⚠️ **後修：這裡原本自己重建一份 entries**，於是 `merge_items.py`
    換了主判準（改用「主線的名字」）之後，這邊沒跟上 —— 同一個區間
    `merge_items` 報 7 組、`materials.md` 卻分成 19 節，**兩邊分岔**。
    那正是本 repo 已知坑 #13（同一事實寫在兩個地方必定分岔）。
    現在一律**呼叫 `merge_items.load_entries()`**，只有一份定義。
    """
    try:
        d0, d1 = days[0]["date"], days[-1]["date"]
        wanted = daterange(d0, d1)
        entries, _missing, _adv = merge_items.load_entries(DATA_DIR[0], wanted)
        return merge_items.build(entries), None
    except Exception as ex:                                   # pragma: no cover
        out = []
        for d in days:
            for i, it in enumerate(d.get("items", []), 1):
                out.append({"gid": f"G{len(out)+1}", "members": [f"{d['date']}#{i}"],
                            "signals": {"score": 0, "best_rank": i, "span_days": 1,
                                        "files": 0, "n_item": 1, "n_record": 0,
                                        "kinds": []}})
            for i, r in enumerate(d.get("record", []), 1):
                out.append({"gid": f"G{len(out)+1}", "members": [f"{d['date']}#R{i}"],
                            "signals": {"score": 0, "best_rank": None, "span_days": 1,
                                        "files": 0, "n_item": 0, "n_record": 1,
                                        "kinds": []}})
        return out, repr(ex)


def _item_lines(L, sid, it):
    """一個呈現層 item 在素材裡的長相。

    ⚠️ 現在保留 result 與 approach 並放寬截斷：素材是給模型讀的，
    省那幾百字換來的是彙整時得回頭翻原始 JSON。
    """
    pri = it.get("priority")
    tag = f"[{it.get('status')}]" + (f"[{pri}]" if pri else "") \
          + ("[工具]" if it.get("kind") == "tooling" else "")
    L.append(f"  - `{sid}` {tag} **{it.get('title')}**")
    L.append(f"      摘要：{clip(it.get('summary'), 300)}")
    # ⚠️ 上限的用途是**防爆，不是省字**：`materials.md` 整份會進每一個 brief，
    #    成本 ＝ 檔案大小 × 角色數 × 對話回合數。所以留天花板，但要留在
    #    「不會誤傷正常資料」的高度 —— 掃過全部日誌的各欄最長值是
    #    details 870／result 638／what 593／interpretation 356／approach 353／
    #    question 177／gaps 136／summary 120，**原本 question 160、approach 220、
    #    result 500 三條比實際資料還低，等於保證每次都切掉一點**（實測四天漏 59 字）。
    #    現在一律留 1.4 倍以上的餘裕。
    for label, key, n in (("問題", "question", 300), ("做法", "approach", 500),
                          ("結果", "result", 900), ("解讀", "interpretation", 600),
                          ("細節", "details", 1200), ("還缺", "gaps", 400)):
        if it.get(key):
            L.append(f"      {label}：{clip(it.get(key), n)}")
    # ⭐ `concepts` 是日誌自己寫的「術語 → 白話」對照。planner 的名詞凍結表
    #    （`terms_proposed_zh`）與 builder 的 `def` 文字本來就該用它，
    #    不該讓下游自己重新發明一套講法。
    for c in (it.get("concepts") or [])[:6]:
        L.append(f"      名詞：{c.get('term')} ＝ {clip(c.get('plain'), 120)}")
    for j, t in enumerate(it.get("tables", []), 1):
        L.append(table_digest(t, j))
    if it.get("figures"):
        L.append(f"      （附圖 {len(it['figures'])} 張，原始 JSON 內）")
    _origin_lines(L, it)


def _origin_lines(L, it, cap_files=6, cap_cmds=3):
    """⭐ 把「這一項可以爬回哪裡」貼在項目旁邊，不要只留在 §四。

    §四 是一張**按路徑排序**的全域索引（路徑 → 哪些 sid 用到），
    給的是「這個檔被誰碰過」；讀某一項的時候，它在幾十行以外。
    實測的後果：builder 讀完一項就直接動筆，`extra_sources` 常常是空的或猜的。
    這裡補的是相反方向：**項目 → 它自己的原檔**，看到內容的同一眼就看到能去哪裡讀。

    `commands` 從來沒有被用過（本週區間有 51 條）—— 它是最具體的一種材料
    （實際下過的指令），mechanism 頁畫「這一步實際做了什麼」時直接可用。
    """
    art = it.get("artifacts") or {}
    files = [str(v) for v in (art.get("files") or [])] + \
            [str(v) for v in (art.get("outputs") or [])]
    shown = []
    for f_ in files[:cap_files]:
        abs_, base = _resolve(f_)
        shown.append(f"`{abs_}`〔{base}〕" if abs_ else f"`{f_}`⚠️定位不到")
    if shown:
        more = f"（另 {len(files) - cap_files} 個見 §四）" if len(files) > cap_files else ""
        L.append(f"      原檔：{'　'.join(shown)}{more}")
    cmds = [str(v) for v in (art.get("commands") or [])]
    if cmds:
        more = f"（另 {len(cmds) - cap_cmds} 條）" if len(cmds) > cap_cmds else ""
        L.append(f"      指令：{'　'.join(f'`{clip(c, 90)}`' for c in cmds[:cap_cmds])}{more}")


def _stats(L, days):
    L += ["## 三、統計", "",
          f"- 天數 {len(days)}　item {sum(len(d.get('items',[])) for d in days)} 個"
          f"　record {sum(len(d.get('record',[])) for d in days)} 個"
          f"　issue {sum(len(d.get('issues',[])) for d in days)} 個"
          f"　表格 {sum(len(t) for d in days for it in d.get('items',[]) for t in [it.get('tables',[])])} 張",
          "",
          "> 一週的日誌天生只有時間順序。**時間順序不是敘事順序** ——",
          "> 週的層級要重走一次 PMRC（問題→為何非解不可→做出什麼→所以呢），",
          "> 不要把 item 按日期排上去。"]
    return "\n".join(L) + "\n"


# ⚠️ 這張表要與 SKILL.md「layer1 — 找主線」那節的七題表**逐題對得起來**。
# 順序即七題表的第 1~7 題。第 2 題是**逐條主線各問一次**，而本腳本跑在 layer1 **之前**、
# 還不知道有幾條線 —— 所以它在這裡留成一個「每條主線各一題」的模板（見 plan_todo()），
# ⛔ 不要把它壓成全場一題。
QUESTIONS = [
    {"q": "這幾項是同一件事嗎？（列出被提名合併、以及被拆開的組——寫得出一個共同目標的標題嗎？）",
     "why": "合併的定案。⚠️ 合併要在分群之前做完，順序顛倒的話主線裡仍然是一堆平行的零件",
     "a": ""},
    {"q": "【每一條主線各問一次】這條線如果只講 3~4 個重點，是哪幾個？",
     "why": "⭐ 七題裡最重要的一題：它直接決定有哪幾頁。答案逐字存成 threads[].user_points。"
            "⛔ 不得由 agent 代擬——沒有它，選材的濾網會變成 agent 自己編的那句敘事",
     "a": "",
     "_per_thread": True,
     "_note": "layer1 判出幾條線，就把這一題複製成幾則（q 補上線名），一線一則 a。"
              "⛔ 不要只留一則當成全場一題回答。"},
    {"q": "這週的主角是哪一件事？（可以有多個；若有多個，它們之間有因果關係嗎，還是各自獨立？）",
     "why": "決定敘事重心、plan.mode（single／multi）、以及排序",
     "a": ""},
    {"q": "這週讓什麼從「做不到」變成「做得到」？（主角多的話，可以回答「不需要單一結論」）",
     "why": "決定結論；多主角的週不強求全週結論",
     "a": ""},
    {"q": "教授上次問了什麼還沒回答？還有哪些是他指定的方向？",
     "why": "教授交代的排最前；agent 分不出哪件事是他交代的，一定要問",
     "a": ""},
    {"q": "有沒有哪件事**沒被列進上面的候選**、但這週一定要講？"
          "（agent 的候選來自每日 headline，實測只涵蓋約八成）",
     "why": "⭐ 這一題在補候選集本身的缺口。`editorial_policy §0` 明訂要多問這一句"
            "（例：「測試集比訓練集乾淨 22~29%」是全週最該講的發現之一，卻沒進任何一天的 "
            "headline）。⚠️ 這一刀之後就上鎖了：user_points 定案後，layer2／layer3 "
            "只能在這些點裡排版，沒有任何一步能補內容進來。"
            "答有東西 → 補進對應那條線的 user_points（或另開一條線）",
     "a": ""},
    {"q": "有哪些你這次不想展開？有沒有哪個概念他還不熟、需要先鋪陳一頁？",
     "why": "決定哪些降級 backup／口頭，以及要不要加鋪陳頁",
     "a": ""},
]


def plan_todo(days):
    """把「記得要問使用者」變成「有一個檔案空著」。

    ⚠️ 這是本流程唯一**結構上**跳不掉的關卡。
    ⚠️ 七題與 SKILL.md 的七題表一一對應（2026-09-06 補上原本漏掉的第 1、2 題，B14-⑤）。
    帶 `_per_thread` 的第 2 題必須在 layer1 定案後展開成「每條主線一則」——
    ⛔ 本腳本跑在 layer1 之前，這裡只放得下模板。
    ⚠️ check_deck.py 只要求 plan.answers 至少 3 題且每則 a 非空，
    補題**不會**讓那條檢查變嚴；防呆效果來自「檔案上看得到一個空格」。
    check_deck.py 會要求 plan.answers 的每一則 a 非空——
    而那些答案只有使用者答得出來（教授交代了什麼、哪些不想展開、事情之間有沒有因果）。
    跳過複習與提問、丟四條 headline 就要人寫敘事，對方會答不出來——手上沒有素材。
    而 check 只驗 narrative 非空，agent 自己編一句就能過，那不是關卡。
    """
    return {
        "_how": "先把 materials.md 複習給使用者聽，再用 AskUserQuestion 問下面七題，"
                "把他的原話逐字填進 a，最後由這些答案組出 plan.narrative。"
                "⚠️ 帶 _per_thread 的那一題要在 layer1 判出主線之後，"
                "**每條線各複製一則**再問；⛔ 不要壓成一題。",
        "questions": QUESTIONS,
        "headlines": [{"date": d["date"], "headline": d["headline"]} for d in days],
        "reminder": "headline 只給約八成的骨架。一定要多問一句："
                    "有沒有哪件事沒進 headline 但這週該講？",
    }


def draft(days, week):
    """deck.draft.json：每個 item 一張候選頁，等模型篩選、合併、排序、補承接／拋出。"""
    # 不產封面、不產「本週的問題與結論」頁 —— 簡報從 outline 直接開始。
    # arc（PMRC）留在 deck 頂層當規劃欄位，不佔投影片。
    slides = [
        {"id": "S1", "type": "agenda", "title": "This week", "source": [],
         "body": {"items": [{"n": "1", "t": "", "d": ""}]}},
    ]
    n = len(slides)
    for d in days:
        for i, it in enumerate(d.get("items", []), 1):
            n += 1
            tabs = it.get("tables", [])
            # 候選頁一律先給 table（有表）或 points（沒表）。
            # points 是**下下策**：改寫時先想能不能畫成 diagram(.svg)，
            # 真的不行才留 points 並補 why_text，否則 check_deck.py 會擋。
            body = ({"tables": [tabs[0]]} if tabs
                    else {"items": [clip(it.get("summary"),
                                         DECK_LIMITS["point_len"])]})
            slides.append({
                "id": f"S{n}", "_candidate": True,
                "type": "table" if tabs else "points",
                "why_text": "" if tabs else "★ 填理由，或改成 diagram",
                "thread": "", "point": clip(it.get("title"),
                                            DECK_LIMITS["point"]),
                "from": "", "to": "",
                "source": [f"{d['date']}#{i}"],
                "title": clip(it.get("title"), DECK_LIMITS["title"]),
                "body": body,
                "notes": it.get("details", ""),
            })
    return {
        "meta": {"week": week, "range": [days[0]["date"], days[-1]["date"]],
                 "title": f"研究進度週報 {week}"},
        # 新版 layer2 的明確選擇：機制頁先以案例跑過規則，再安排敘事。
        # check_deck 依此對 mechanism 頁啟用 type=example 的 70/30 契約。
        "plan": {"example_first": True},
        "arc": {"problem": "", "motivation": "", "results": "", "conclusion": ""},
        "threads": [],
        "slides": slides,
    }


def _load(p):
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def headlines(out):
    """印每日 headline（`plan.narrative_candidates` 的來源）—— 協調者不必讀 materials.md。"""
    todo = _load(os.path.join(paths.work_dir(out, "materials"), "plan.todo.json")) or {}
    hl = todo.get("headlines") or []
    if not hl:
        sys.exit("[build] plan.todo.json 裡沒有 headlines —— 先跑 Step 1（build_deck.py --days …）")
    for h in hl:
        print(f"{h.get('date')}：{h.get('headline')}")
    return [f"{h.get('date')}：{h.get('headline')}" for h in hl]


def skeleton(out, review):
    """⭐ 關卡② 過了就由**腳本**寫 `deck.json` 骨架（N61 的落點；PR 2 起不再由協調者手寫）。

    來源（SKILL.md 那張「欄位從哪來」的表，現在就是這段程式）：
      meta            ← _work/1_materials/deck.draft.json
      arc／answers／narrative／mode／rebuttals ← _work/2_layer1/gate1_answers.json（使用者原話）
      narrative_candidates ← plan.todo.json 的每日 headline
      threads／dropped ← _work/2_layer1/layer1_confirmed.json（含每線的 members_without_point）
      slide_plan／terms.objects／terms_zh ← _work/3_layer2/layer2.<線>.json ＋ gate2_answers.json
      slides          ← []（留給 merge_slides.py）
      layout_reviewed ← --no-review 時寫 {"skipped": …}（具名逃生口）；--review 時不寫，等 reviewer 回填
    ⛔ 已有 deck.json 且 slides 非空 → 拒絕覆寫（那是做到一半的週）。
    """
    dm, d1, d2 = (paths.work_dir(out, "materials"), paths.work_dir(out, "layer1"),
                  paths.work_dir(out, "layer2"))
    dest = os.path.join(out, "deck.json")
    old = _load(dest)
    if old and old.get("slides"):
        sys.exit(f"[build] {dest} 已經有 {len(old['slides'])} 頁 —— 骨架只在關卡② 之後、"
                 "builder 交件之前寫一次。要重來就自己把 slides 清成 []")
    draft = _load(os.path.join(dm, "deck.draft.json")) or {}
    todo = _load(os.path.join(dm, "plan.todo.json")) or {}
    l1 = _load(os.path.join(d1, "layer1_confirmed.json"))
    g1 = _load(os.path.join(d1, "gate1_answers.json")) or {}
    g2 = _load(os.path.join(d2, "gate2_answers.json")) or {}
    if not l1:
        sys.exit(f"[build] 找不到 {d1}/layer1_confirmed.json —— 關卡① 還沒定案"
                 "（check_gate.py layer1 --confirm <答案檔>）")
    l2 = {}
    for f in sorted(glob.glob(os.path.join(d2, "layer2.*.json"))):
        j = _load(f) or {}
        l2[j.get("thread") or os.path.basename(f)[7:-5]] = j
    if not l2:
        sys.exit(f"[build] {d2} 底下沒有 layer2.*.json —— 關卡② 還沒定案")

    threads = []
    dropped = list(l1.get("dropped") or [])
    for t in l1.get("threads") or []:
        threads.append({k: t.get(k) for k in ("id", "title", "summary", "user_points")
                        if t.get(k) is not None})
        for e in t.get("members_without_point") or []:
            if e.get("sid"):
                dropped.append({"source": e["sid"], "where": e.get("where", ""),
                                "why": e.get("why", "") or "關卡①：上了主線但使用者沒選成重點"})
    # 同一個 sid 只留一筆（後面的蓋前面的）
    dropped = list({x.get("source"): x for x in dropped if x.get("source")}.values())

    slide_plan, objects, terms_zh = [], [], {}
    for tid in [t["id"] for t in threads]:
        j = l2.get(tid) or {}
        pages = [p for p in (j.get("pages") or j.get("slide_plan") or [])
                 if (p.get("body") or "") not in ("agenda", "cover", "thread-intro")]
        bodies = [p.get("body") for p in pages if p.get("body")]
        body = max(set(bodies), key=bodies.count) if bodies else "example"
        tt = next((t for t in threads if t["id"] == tid), {})
        slide_plan.append({"thread": tid, "point": tt.get("summary") or tt.get("title") or tid,
                           "pages": len(pages), "body": body})
        for o in j.get("terms_proposed") or []:
            if o not in objects:
                objects.append(o)
        for k, v in (j.get("terms_proposed_zh") or {}).items():
            terms_zh.setdefault(k, v)
    gt = g2.get("terms") or {}
    for o in gt.get("objects") or []:
        if o not in objects:
            objects.append(o)
    terms_zh.update({k: v for k, v in (gt.get("zh") or {}).items() if v})

    deck = {
        "meta": draft.get("meta") or {"week": dt.date.today().isoformat(), "range": [], "title": ""},
        "arc": g1.get("arc") or {"problem": "", "motivation": "", "results": "", "conclusion": ""},
        "plan": {
            "answers": [{"q": a.get("q", ""), "a": a.get("a", ""), "date": a.get("date", "")}
                        for a in (g1.get("answers") or []) if str(a.get("a") or "").strip()],
            "slide_plan": slide_plan,
            "slide_plan_confirmed": True,
            "narrative": l1.get("narrative", ""),
            "narrative_source": l1.get("narrative_source") or g1.get("narrative_source", ""),
            "narrative_candidates": [f"{h.get('date')}：{h.get('headline')}" for h in todo.get("headlines") or []],
            "mode": l1.get("mode", ""),
            "example_first": True,
            "terms": {"core_metric": gt.get("core_metric") or "尚未凍結（關卡② 沒有指定核心指標）",
                      "objects": objects},
            "terms_zh": terms_zh,
            "rebuttals": g1.get("rebuttals") or [],
            "dropped": dropped,
            "quotes": [],
            "feedback": [],
        },
        "threads": threads,
        "slides": [],
    }
    if not review:
        deck["plan"]["layout_reviewed"] = {
            "skipped": "lite：本週未派 layout_reviewer（build_deck.py --skeleton 預設 --no-review；"
                       "要派就加 --review，並由 reviewer 自己回填這一欄）"}
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(deck, fh, ensure_ascii=False, indent=2)
    print(f"[build] deck.json 骨架 → {dest}")
    print(f"[build]   threads {[t['id'] for t in threads]}　slide_plan {[(x['thread'], x['pages']) for x in slide_plan]}"
          f"　objects {len(objects)} 個（{sum(1 for o in objects if terms_zh.get(o))} 個有中譯）"
          f"　dropped {len(dropped)} 項　layout_reviewed={'等 reviewer 回填' if review else 'skipped（lite）'}")
    missing_zh = [o for o in objects if not terms_zh.get(o)]
    if missing_zh:
        print(f"[build] ⚠️ {len(missing_zh)} 個物品名沒有中譯（{'、'.join(missing_zh[:6])}"
              f"{'…' if len(missing_zh) > 6 else ''}）—— 補進 gate2_answers.json 的 terms.zh 再跑一次，"
              "否則 builder 各自翻，譯名會分岔（N31）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=None)
    ap.add_argument("--skeleton", action="store_true",
                    help="⭐ 關卡② 過了之後：從 deck.draft／layer1_confirmed／gate1_answers／"
                         "layer2.*／gate2_answers 組 deck.json 骨架（slides: []）。不吃區間參數")
    ap.add_argument("--review", dest="review", action="store_true",
                    help="--skeleton 時：本週會派 layout_reviewer，plan.layout_reviewed 留給它回填")
    ap.add_argument("--no-review", dest="review", action="store_false",
                    help="--skeleton 時（預設）：不派 reviewer，寫 plan.layout_reviewed = {skipped: …}")
    ap.set_defaults(review=False)
    ap.add_argument("--headlines", action="store_true",
                    help="印每日 headline（narrative_candidates 的來源），協調者不必讀 materials.md")
    _range.add_args(ap)          # --days / --since-last-deck / --last
    a = ap.parse_args()
    if a.headlines:
        headlines(os.path.abspath(a.out))
        return
    if a.skeleton:
        skeleton(os.path.abspath(a.out), a.review)
        return
    DATA_DIR[0] = a.data = a.data or DEF_DATA

    # 區間一律走 _range：它會從上一份 deck 推導起日，並在有缺口／重疊時警告。
    # ⛔ 不要自己算日期 —— 那正是「每次都由呼叫的人手填」的來源。
    start, end = _range.from_args(a)
    wanted = daterange(start, end)

    days = load_days(a.data, wanted)
    if not days:
        sys.exit("[build] 這段期間沒有任何日誌")

    os.makedirs(a.out, exist_ok=True)
    # 三份都是**過程產物**（給人看的素材、候選骨架、待問的七題），不是交付物 →
    # `_work/1_materials/`。⭐ 交付物（deck.json 與兩份 HTML）才留在日期目錄本身。
    d = paths.work_dir(a.out, "materials", create=True)
    week = dt.date.today().isoformat()
    mp = os.path.join(d, "materials.md")
    dp = os.path.join(d, "deck.draft.json")
    tp = os.path.join(d, "plan.todo.json")
    open(mp, "w", encoding="utf-8").write(materials(days) + "\n" + source_index(days))
    json.dump(draft(days, week), open(dp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    if not os.path.exists(tp):
        json.dump(plan_todo(days), open(tp, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"[build] {len(days)} 天 → {mp}")
    print(f"[build] 候選頁骨架 → {dp}")
    print(f"[build] ★ 待問使用者的七題 → {tp}")
    # ⚠️ N104：舊版這裡指「Step 2」，而 `SKILL.md` 只有 Step 0／1／4／5 ——
    #    協調者照著去找會找不到。真正的落點是 layer1 那一節的關卡①。
    print("[build] ⛔ 下一步是 SKILL.md 的 layer1「然後停下來問」那一節（關卡①）："
          "把 materials.md 複習給使用者聽，再把上面那七題問完"
          "（帶 _per_thread 的那一題要每條主線各問一次）。"
          "不要跳過去寫 deck.json —— check_deck.py 會擋 plan.answers。")


if __name__ == "__main__":
    main()
