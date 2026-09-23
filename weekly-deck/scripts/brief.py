#!/usr/bin/env python3
"""把某個角色、某條主線該讀的東西打包成**一個檔**。

## 為什麼有這支

帳單不是「檔案有多大」，是「檔案大小 × 回合數」—— 每次 API 請求都會重送整段對話。
實測：`thread_finder` 讀進去的檔案約 30,000 tokens，帳單卻是 **120,830 tokens**，
差別在它跑了 **22 次工具呼叫**，每一次都把前面全部重送一遍。

所以省錢的施力點是**回合數**，不是內容。這支把 8~10 次 Read 壓成 **1 次**：
subagent 讀一個檔 → 想 → 寫兩個檔，大約 5 個回合。

### 順帶解掉的第二個問題

派遣訊息裡那一長串絕對路徑以前是**協調者手打的**，於是
`subagent-thread-finder.md` 裡寫死的舊路徑 `weekly_reports/_explanations.md`
一路被抄進派遣訊息，找不到時又因為規格寫「若存在」而**靜默略過**。
路徑改由 `paths.py` 解析一次寫進 brief，手打的機會就沒有了。

### 它**不做**什麼

⛔ 不做摘要、不做改寫。全部逐字複製，只挑「這個角色該讀的節」（`@for` 標籤）。
   摘要會把判準的理由弄丟，而這個 skill 的每一條規則都是靠理由才不會被改回去。
   （PR 3 起 builder 包多一層切法：`composition-vocabulary`／`slide_types`／`deck_schema`／`diagram-craft`
   裡**標題只指向這條線沒用到的 comp／關係／type** 的小節整段拿掉、切掉的列一行清單；
   標題含任何不認識的識別字就整段保留，⛔ 寧可多給不可切錯。仍是逐字，不改寫。）
⛔ 不夾帶別條線的 `user_points` —— `check_gate.py` 會擋（逐線隔離）。

用法：
  brief.py finder            --out <日期目錄>
  brief.py planner --thread T1 --out <日期目錄>
  brief.py builder --thread T1 --out <日期目錄>
  brief.py reviewer          --out <日期目錄>      # 跨主線，不吃 --thread
  brief.py fixer   --thread T1 --out <日期目錄> --findings <合成後的 findings 檔>
                                                   # 退回 builder 的修復包：⛔ 不是完整派遣包
（`deck_assembler` 已於 2026-09-06 拿掉：全場 outline 改由 merge_slides.py --outline 產，
  中文譯文由寫英文的 builder 一起交 strings.<線>.zh.json —— 見 subagent-slide-builder.md §6。）
"""
import argparse, json, os, re, sys

import paths

ROLE_SPEC = {
    "finder":   "subagent-thread-finder.md",
    "planner":  "subagent-slide-planner.md",
    "builder":  "subagent-slide-builder.md",
    "reviewer": "subagent-layout-reviewer.md",   # 跨主線，不吃 --thread
    # ⭐ fixer（PR 2）：三方 findings 合成一輪退回 builder 時，**派新的、給修復包**，
    #    ⛔ 不是再送一次 116 KB 的完整派遣包（delegation.md：損益點 3 個回合）。
    #    角色規格同 builder；共用判準只帶 presentation_rules 裡最常被退的兩節；
    #    其餘需要時去讀完整的 brief.builder.<線>.md（路徑寫在包裡）。
    "fixer": "subagent-slide-builder.md",
    # ⛔ `deck_assembler` 已拿掉（2026-09-06）：outline 是腳本產的（merge_slides.py --outline），
    #    譯文由 builder 交逐線片段（strings.<線>.zh.json）。角色清單只有這一份。
}
# ⭐ 判準（實測得來，⛔ 不要憑感覺改）：
#   **會被完整讀完的 → INLINE**（省一次工具呼叫，內容成本一模一樣）
#   **只會被抽樣查的 → 只給路徑**（inline 是純浪費，而且之後每一個回合都要重送它）
#
# 為什麼要分：第一版把兩種混在一起全部 inline（50,000 tokens），結果
#   thread_finder 逐檔讀 = 120,830 tokens / 22 呼叫（基準）
#   planner T1 有 brief  = 232,110 / 25　　T2 = 161,778 / 25　　T3 = 220,841 / 30
# **打包之後更貴**：回合數沒降（規格本來就要求 subagent 去讀第一手核對），
# 而 50k 在第 2 個回合就進 context，之後每一回合重送一次。
# ⛔ 前置載入大 blob ＋ 多回合 = 最糟的組合。
INLINE_REFS = {          # 依 @for 切片後 inline —— ⛔ 不要整份，也不要只給路徑
    "finder":   ["editorial_policy.md"],
    "planner":  ["editorial_policy.md", "presentation_rules.md",
                 "composition-vocabulary.md", "slide_types.md"],
    "builder":  ["composition-vocabulary.md", "glyphs.md", "presentation_rules.md",
                 "slide_types.md", "diagram-craft.md", "deck_schema.md"],
    "reviewer": ["presentation_rules.md", "slide_types.md"],
    "fixer":    [],      # 修復包只帶 findings ＋ 該線的頁；判準去完整 brief 查（路徑在包裡）
}
# ⛔ 這裡刻意**空著**。三個版本都實測過，只有「切片後 inline」是對的：
#
#   v1 整份 inline（50,000t）→ planner 232k/162k/221k tokens，比不打包更貴
#   v2 只給路徑＋節名        → **agent 照樣把整份讀回來**，白給
#   v3 切片後 inline（現在）  → 該讀的在包裡，不必再開一次工具呼叫
#
# v2 失敗的實測證據（builder 的工具呼叫紀錄）：
#   buildT1 Read presentation_rules.md 全份 8,252t、diagram-craft 4,785t、
#           slide_types 4,391t、deck_schema 3,728t —— 四份都在「只給路徑」的清單上
#   buildT3 Read presentation_rules.md 全份 14,447t
# **「告訴它去哪讀」不會讓它少讀，只會讓它多花一次呼叫。**
POINTER_REFS = {k: [] for k in ROLE_SPEC}
# ⛔ 這幾支**不要讀**：它們是拿來跑的，而且很大。契約寫在 references 裡。
DO_NOT_READ = {
    "render_figure.py": "10,064 tokens。構圖的欄位契約在 composition-vocabulary.md，"
                        "⛔ 不要去讀實作。要看範例圖跑 `render_figure.py --demo <outdir>`",
    "check_deck.py":    "18,108 tokens。它會擋你什麼，references 裡都寫了；"
                        "⛔ 不要讀原始碼，直接跑它看輸出",
    "shoot.py":         "⛔ 不要讀。跑 `shoot.py <deck>.html --check-only` 看輸出就好",
    "check_gate.py":    "⛔ 不要讀。跑它看輸出",
}
# ⚠️ 另一種實測到的浪費：**一次 bash 產出太多**。輸出過大時會被存成檔案，
#    agent 再把那個檔讀回來 —— 而且大檔要分頁，等於一份內容付兩三次。
#    實測 buildT3 讀回自己的 bash 輸出兩次，合計 20,935 tokens。
BIG_OUTPUT_WARNING = """
## ⛔ 不要一次產生大量輸出

`cat` 一個大檔、`sed -n '1,250p'`、把整個資料表印出來 —— 輸出過大會被存成檔案，
你得再讀回來（大檔還要分頁），**同一份內容付兩三次錢**。
實測：一個 builder 把自己的 bash 輸出讀回來兩次，合計 20,935 tokens。

⭐ 要什麼就抽什麼：`grep -n <關鍵字>`、`head -30`、`awk` 取欄位、`wc -l` 先看多大。
⛔ **資料檔（.tsv/.csv/.bam 之類）一律不要整份讀** —— 幾 MB 的檔會塞爆 context。
   要引用其中的數字，用 `grep`／`awk` 抽出**那一行**，並把檔案路徑掛進 `extra_sources`。
"""
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(SKILL, "references")
TAG = re.compile(r"^<!--\s*@for:\s*([\w,\s]+?)\s*-->\s*$")


def slice_for(path, role):
    """依 `@for` 標籤挑節。未標的節（前言、總則）全員都讀。

    ⚠️ 標籤不存在時**整份回傳**，⛔ 不要靜默回傳空的 ——
    沒標籤代表那份還沒分類過，不是「這個角色不用讀」。

    ⭐ **兩種「沒標籤」，以前只擋住第一種**（N66，批次 5g）：
      ① 這份檔**整份**沒有 `@for:` → 早就整份回傳（下面第一個 if）。
      ② 這份檔有標籤，但**這個角色一次都沒被標到** → 舊版照樣逐節比對，
         於是 `reviewer` 只拿到 `presentation_rules.md` 的 **291 / 26,532 字元**，
         **24 節被靜默略過** —— 而其中 §2b 面積、§2c-2 標籤用途、§5 顏色語意
         **正是 `subagent-layout-reviewer.md` 要它逐項比對的四項**。
         `slide_types.md` 另被略掉 4 節。派遣包看起來完全正常，短得沒有人會發現。
    ⛔ 兩種都回整份。⚠️ 這是**保護**不是常態：把節標成該角色仍然比較省，
    整份回傳只是保證「漏標的代價是多讀，不是靜默少讀」。

    ⚠️ 被略過的節要**列出節名**，⛔ 不要無聲消失：
    subagent 才知道「這裡還有東西、但不歸我」，需要時去原檔查得到。
    """
    src = open(path, encoding="utf-8").read()
    if "@for:" not in src:
        return src, []
    # ② 這份檔有標籤，但這個角色一次都沒被標到（N66）
    if not any(role in {w.strip() for w in m.group(1).split(",")}
               for m in (TAG.match(ln) for ln in src.split("\n")) if m):
        return src, []
    lines = src.split("\n")
    blocks, cur = [[None, []]], 0          # [標題, 內容行]；第 0 塊是前言
    for ln in lines:
        if ln.startswith("## "):
            blocks.append([ln, []])
            cur += 1
        else:
            blocks[cur][1].append(ln)
    keep, omitted = [], []
    for title, body in blocks:
        who = None
        for ln in body:
            m = TAG.match(ln)
            if m:
                who = {w.strip() for w in m.group(1).split(",")}
                break
        body = [ln for ln in body if not TAG.match(ln)]
        if title is None or who is None or role in who:
            if title:
                keep.append(title)
            keep += body
        else:
            omitted.append(title[3:].strip())
    return "\n".join(keep), omitted


# ⭐ PR 3：builder 的派遣包只帶**這條線用到的**構圖／版型的節。
#   實測 builder 的包 116 KB 裡，composition-vocabulary（26 KB）整份、slide_types（11 KB）整份、
#   deck_schema（15 KB）整份 —— 而一條線通常只用 2~3 個構圖、1~2 種版型。
#   帳單是「檔案大小 × 回合數」：這裡切掉的每一 KB 都乘上 builder 的幾十個回合。
#   ⛔ 被切掉的 `###` 一律列名（同 slice_for 的規矩），需要時去原檔查。
ALIAS = {"chain_gated": "chain", "chain_focus": "chain", "funnel_named": "funnel"}
ALWAYS_KEEP = {"blocks"}                     # 三個構圖共用的子區塊排版，小、常用，不切
# ⛔ 只有標題裡的識別字**全部**是已知的構圖／關係／版型名，那個子節才可能被切 ——
#    否則像 diagram-craft 的「pill 上的字算哪一種用途 class？→ `label`」會因為 `label` 不在
#    這條線的 comp 集合裡被誤切（實測踩到）。名單：renderer 的 comp、八種關係、slide 的 type。
RELATIONS = {"sequence", "transform", "partition", "narrowing", "compare",
             "containment", "correspondence", "distribution"}
SLIDE_TYPES = {"agenda", "thread-intro", "table", "stats", "cols", "flow", "points",
               "issues", "figure", "cover", "pipeline", "example", "diagram"}
HAND_SECTIONS = ("1.", "2.", "3.", "4.", "5.", "7.")   # diagram-craft 手繪座標學：沒有手繪就不帶
IDENT = re.compile(r"`([^`]+)`")


def used_vocab(out, tid):
    """(這條線用到的識別字集合, 需不需要手繪) —— 來源是 layer2.<線>.json（關卡② 定案），
    deck.json 已經有這條線的頁時也一併收。⚠️ 讀不到就回 (None, True)：整份照舊，⛔ 不靜默切空。"""
    ids, hand = set(), False
    l2 = os.path.join(paths.work_dir(out, "layer2"), f"layer2.{tid}.json")
    try:
        j = json.load(open(l2, encoding="utf-8"))
        pages = j.get("pages") or j.get("slide_plan") or []
    except (OSError, ValueError):
        return None, True
    renderers = _renderers()
    dk = os.path.join(out, "deck.json")
    extra = []
    if os.path.isfile(dk):
        try:
            extra = [s_ for s_ in (json.load(open(dk, encoding="utf-8")).get("slides") or [])
                     if s_.get("thread") == tid]
        except (OSError, ValueError):
            extra = []
    for p in list(pages) + extra:
        c = p.get("composition") or {}
        comp = c.get("comp")
        if comp:
            ids.add(comp); ids.add(ALIAS.get(comp, comp))
            if comp not in renderers or c.get("handwritten"):
                hand = True
        if c.get("off_vocabulary"):
            hand = True
        if c.get("relation"):
            ids.add(str(c["relation"]))
        b = p.get("body")
        if isinstance(b, str) and b:
            ids.add(b)
        elif isinstance(p.get("type"), str):
            ids.add(p["type"])
    return ids, hand


def _renderers():
    try:
        import render_figure as _rf
        return set(_rf.RENDERERS)
    except Exception:                            # noqa: BLE001 —— 匯入失敗就當全部要手繪、不切
        return set()


def _known():
    return _renderers() | set(ALIAS) | set(ALIAS.values()) | RELATIONS | SLIDE_TYPES


def _idents(heading):
    """`### \`chain\` ／ \`chain_gated\``、`### \`type: "example"\``、`### 1. \`sequence\`` → 識別字。
    回 (識別字集合, 是否全部都是已知的構圖／關係／版型名)。"""
    out = set()
    for tok in IDENT.findall(heading):
        m = re.search(r'type:\s*"([\w-]+)"', tok)
        tok = m.group(1) if m else tok.strip()
        if re.fullmatch(r"[a-z][a-z_-]*", tok):
            out.add(tok)
    known = _known()
    return out, bool(out) and out <= known


def slice_subsections(text, keep, hand, fn):
    """把 `###` 子節裡「標題帶識別字、而識別字都不在 keep 裡」的整段拿掉；
    diagram-craft 的手繪座標學（`## 1.`～`## 5.`、`## 7.`）在不需要手繪時整節拿掉。
    回 (新文字, 被略過的標題清單)。"""
    lines, out, omitted = text.split("\n"), [], []
    skip = False
    for ln in lines:
        if ln.startswith("## ") or ln.startswith("### "):
            title = ln[4:].strip() if ln.startswith("### ") else ln[3:].strip()
            skip = False
            if fn == "diagram-craft.md" and ln.startswith("## ") and not hand \
                    and title.startswith(HAND_SECTIONS):
                skip = True
            elif ln.startswith("### "):
                ids, all_known = _idents(ln)
                if all_known and not (ids & keep) and not (ids & ALWAYS_KEEP):
                    skip = True
            if skip:
                omitted.append(title)
                continue
        if not skip:
            out.append(ln)
    return "\n".join(out), omitted


def sections(md):
    """把 markdown 依 `## ` 切塊，回傳 [(標題行 or None, 內容字串)]。"""
    out, cur, body = [], None, []
    for ln in md.split("\n"):
        if ln.startswith("## "):
            out.append((cur, "\n".join(body))); cur, body = ln, []
        else:
            body.append(ln)
    out.append((cur, "\n".join(body)))
    return out


ITEM = re.compile(r"^\s{0,4}-\s+`([^`]+)`")     # §二 的逐項：`- \`2026-08-28#1\` [done] **…**`
ARROW = re.compile(r"←\s*(.+?)\s*$")             # §四 的來源標記：`… ← 2026-08-28#1、2026-08-29#2`


def _omit_note(kind, names, src, extra=""):
    """⚠️ 被略過的東西一律**列出名字＋原檔絕對路徑**，⛔ 不要靜默刪掉。

    這是 `delegation.md` 已經明訂的作法（依 `@for` 略過的節就是這樣做的），
    新切的地方一律照辦 —— 靜默失效是這個 repo 反覆在打的失效形狀（FINDINGS N41）。
    """
    if not names:
        return ""
    return ("\n\n> ⚠️ 下列 %d %s**不屬於你這條線**，本包沒有收進來（逐線隔離）。\n"
            "> ⛔ **不要憑印象猜它們寫了什麼** —— 需要時去原檔查：`%s`%s\n> - %s\n"
            % (len(names), kind, src, extra, "\n> - ".join(names)))


def _slice_items(body, sids):
    """把一段「前言 ＋ 一串 `- \`sid\`` 逐項」切成（前言, 命中的項, 略過的項名）。"""
    head, items, cur = [], [], None
    for ln in body.split("\n"):
        m = ITEM.match(ln)
        if m:
            if cur is not None:
                items.append(cur)
            cur = [m.group(1), [ln]]
        elif cur is None:
            head.append(ln)
        else:
            cur[1].append(ln)
    if cur is not None:
        items.append(cur)
    hit = [it for it in items if it[0] in sids]
    miss = [it for it in items if it[0] not in sids]
    return head, hit, miss, items


def _item_name(it):
    """給被略過的項一個看得出是什麼的名字：`sid` ＋ 粗體標題（沒有就取首行）。"""
    first = it[1][0]
    m = re.search(r"\*\*(.+?)\*\*", first)
    return "`%s`%s" % (it[0], "　" + m.group(1) if m else "")


def _plain(t):
    """節名拿來列表用：去掉粗體記號，⛔ 不要產生 `**a**b**` 這種巢狀。"""
    return t.replace("**", "").strip()


def materials_for(md, sids, src):
    """只留這條線用得到的部分。

    ⚠️ 為什麼要過濾：`materials.md` 整份會進**每一個** brief，而
    §二「逐項清單」與 §四「可深入的原料」加起來就佔掉 builder brief 的 **~19%**
    （實測本場：§二 10,480 字元、§四 9,713 字元）。
    `--thread A` 明明知道是 A 線，卻連 B 線的逐項敘述與 B 線的原料都一起送。

    ⭐ 切的規則：
      §零（教授交代）、§一（每日 headline）、§二之二、§三（統計）→ **整段保留**。
        那是全局脈絡，而且都只有幾百字元，切它省不到什麼、卻會弄丟脈絡。
      §二 → 先依 `### ` 的合併組，再**逐項**（`- \`sid\``）過濾。
        ⚠️ 只切到組是不夠的：本場 G1 一組 16 項橫跨兩條線，整組留下等於沒切。
      §四 → 依每一列尾巴的 `← sid` 過濾；**前言與小節說明整段保留**
        （那幾行講的是「怎麼用這個索引」，不是原料本身）。

    ⛔ 被切掉的一律列名 ＋ 附原檔絕對路徑，不做靜默刪除。
    """
    keep = []
    for title, body in sections(md):
        if title is None:
            keep.append(body); continue
        t = title[3:]
        if t.startswith("二、"):
            # 逐項清單：先切組，組內再逐項切 —— ⛔ 只切到組會漏（一組會橫跨兩條線）
            pre, groups, cur = [], [], None
            for ln in body.split("\n"):
                if ln.startswith("### "):
                    if cur is not None: groups.append(cur)
                    cur = [ln, []]
                elif cur is None: pre.append(ln)
                else: cur[1].append(ln)
            if cur is not None: groups.append(cur)
            out, dropped = [], []
            for gtitle, gbody in groups:
                head, hit, miss, items = _slice_items("\n".join(gbody), sids)
                if not hit:
                    dropped.append("**%s**（整組 %d 項）" % (_plain(gtitle[4:]), len(items)))
                    continue
                note = ("" if not miss else
                        "　← ⚠️ 本包只收其中 %d 項，另 %d 項屬別條線"
                        % (len(hit), len(miss)))
                dropped += [_item_name(it) for it in miss]
                out.append(gtitle + note + "\n" + "\n".join(head).rstrip()
                           + "\n" + "\n".join("\n".join(it[1]) for it in hit))
            keep.append(title + "\n" + "\n".join(pre).rstrip() + "\n\n"
                        + "\n\n".join(out)
                        + _omit_note("個逐項／合併組", dropped, src))
        elif t.startswith("四、"):
            # 可深入的原料：是索引，但**每一列都標了它出自哪個 sid** —— 照 sid 切。
            # ⛔ 前言、各 `### ` 小節的說明文字整段保留（那是「怎麼用」，不是原料）。
            out, dropped = [], 0
            sec_lines, sec_kept, sec_drop = [], 0, 0
            def flush():
                # ⛔ 小節的**說明文字一律保留**：那幾段是護欄（「前期產物不可當素材」、
                #    「定位不到不代表沒有原料」），不是原料本身，切掉等於拿掉防線。
                note = ("\n\n> ⚠️ 本小節有 **%d 列**原料的 `←` 指向別條線的日誌項，"
                        "本包沒有收進來（逐線隔離）%s"
                        % (sec_drop, "，你這條線在本小節一列都沒有。" if not sec_kept
                           else "，你這條線的 %d 列都在上面。" % sec_kept)
                        ) if sec_drop else ""
                out.append("\n".join(sec_lines) + note)
            for ln in body.split("\n"):
                if ln.startswith("### "):
                    flush(); sec_lines, sec_kept, sec_drop = [ln], 0, 0
                    continue
                m = ARROW.search(ln)
                if m and ln.lstrip().startswith("- "):
                    if any(sid in m.group(1) for sid in sids):
                        sec_lines.append(ln); sec_kept += 1
                    else:
                        sec_drop += 1; dropped += 1
                else:
                    sec_lines.append(ln)
            flush()
            tail = ""
            if dropped:
                tail = ("\n\n> ⚠️ 本節合計 **%d 列原料**屬於別條線，本包沒有收進來（逐線隔離）。"
                        "\n> ⛔ **不要據此判定「沒有原料可讀」**，也 ⛔ 不要憑印象猜它們是什麼 —— "
                        "需要全貌時讀原檔：`%s`\n" % (dropped, src))
            keep.append(title + "\n" + "\n\n".join(out) + tail)
        else:
            keep.append(title + "\n" + body)
    return "\n".join(keep)


def explanations_for(md, keys, src):
    """`_explanations.md` §2「解釋資產」依相關性切。

    ⚠️ 為什麼：§2 記的是**研究概念**的既有說法（候選 tumor read、compendium、
    Z-score、SVM 去噪…）。本場兩條線都是方法／流程，20 條**一條都用不到**，
    卻整份進了每一個 brief（實測 3,5xx 字元）。

    ⛔ **§1（教授的提問與功課）一個字都不准切** —— 「未答的提問排最前」是硬規則，
    而且那正是先前靜默失效過的那條（delegation.md ②）。§3、§4 也整段留（很短）。

    比對用的關鍵詞來自這條線的 `user_points` 與 plan 的名詞表（`terms`）。
    ⚠️ CJK 取 **3 字以上**的 n-gram：2 字會亂命中（「候選清單」會把
    「候選 tumor read」拉進來），3 字才切得準。切錯的代價由「列出節名」兜底。
    """
    if not keys:
        return md, []
    keys = re.compile("|".join(sorted(keys)))
    out, omitted = [], []
    for title, body in sections(md):
        if title is None or not title[3:].strip().startswith("2."):
            out.append((title + "\n" + body) if title else body)
            continue
        pre, subs, cur = [], [], None
        for ln in body.split("\n"):
            if ln.startswith("### "):
                if cur is not None: subs.append(cur)
                cur = [ln, [ln]]
            elif cur is None: pre.append(ln)
            else: cur[1].append(ln)
        if cur is not None: subs.append(cur)
        hit = []
        for stitle, slines in subs:
            blob = "\n".join(slines).lower()
            if keys.search(blob):
                hit.append("\n".join(slines))
            else:
                omitted.append("**%s**" % _plain(stitle[4:]))
        out.append(title + "\n" + "\n".join(pre).rstrip()
                   + ("\n\n" + "\n".join(hit) if hit else "\n")
                   + _omit_note("節解釋資產", omitted, src,
                                extra="（比對的是你這條線的 `user_points` 與名詞表；"
                                      "⚠️ 關鍵詞比對會漏，覺得該有就去原檔看）"))
    return "\n".join(out), omitted


def keywords_for(out, tid):
    """這條線的關鍵詞：`user_points` ＋ 標題／summary ＋ plan 的名詞表。

    ⚠️ `plan.terms` 要到 layer2 之後才長出來（`delegation.md` 已經寫明它不能打包），
    所以這裡是**盡力而為**：撈得到就用，撈不到就只用 `user_points`。
    ⛔ 撈不到不報錯也不整份丟掉 —— 匹配不到的節會被列名，查得回去。
    """
    src = []
    p = os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json")
    try:
        j = json.load(open(p, encoding="utf-8"))
        t = next(x for x in j["threads"] if x.get("id") == tid)
        src += list(t.get("user_points") or [])
        src += [t.get("title", ""), t.get("summary", "")]
    except Exception:
        pass
    l2 = os.path.join(paths.work_dir(out, "layer2"), f"layer2.{tid}.json")
    if os.path.isfile(l2):
        try:
            j2 = json.load(open(l2, encoding="utf-8"))
            NAMEY = {"name", "zh", "title", "term", "terms", "objects", "core_metric"}
            def walk(v):
                # ⛔ 只收名詞本身，不收 `note`／`what` 那種長段散文 ——
                #    散文會生出一堆泛用 n-gram，把不相關的節全部誤留。
                if isinstance(v, str): src.append(v)
                elif isinstance(v, list): [walk(x) for x in v]
                elif isinstance(v, dict):
                    [walk(x) for k2, x in v.items() if k2.lower() in NAMEY]
            for k, v in j2.items():
                if "term" in k.lower():
                    walk(v)
            walk((j2.get("plan") or {}).get("terms"))
        except Exception:
            pass
    keys = set()
    for s in src:
        if not isinstance(s, str):
            continue
        s = s.lower()
        # ⚠️ 5 個字母起跳：4 個字母的英文字太泛（`deck` 會命中路徑裡的 `weekly-deck`）。
        for w in re.findall(r"[a-z][a-z0-9_]{4,}", s):
            for part in w.split("_"):
                if len(part) >= 5:
                    keys.add(r"\b%s\b" % re.escape(part))     # ⛔ 整字，不吃子字串
        for run in re.findall(r"[\u4e00-\u9fff]+", s):
            for i in range(len(run) - 3):
                keys.add(re.escape(run[i:i + 4]))
    return keys


def read(p):
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else None


def thread_block(out, tid):
    """只給這一條線的資料。⛔ 別條線的 user_points 一個字都不能出現。"""
    p = os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json")
    j = json.load(open(p, encoding="utf-8"))
    t = next((x for x in j.get("threads", []) if x.get("id") == tid), None)
    if not t:
        sys.exit(f"[brief] ⛔ layer1_confirmed.json 裡沒有主線「{tid}」"
                 f"（有的是 {[x.get('id') for x in j.get('threads', [])]}）")
    L = [f"你負責的主線：{tid} — {t.get('title','')}", "",
         f"- summary：{t.get('summary','')}",
         f"- members（日誌 sid）：{'、'.join(t.get('members') or [])}", "",
         "### ⭐ user_points —— 使用者在關卡① 親口指定，**逐字，不得增刪改寫**", ""]
    for i, u in enumerate(t.get("user_points") or [], 1):
        L.append(f'{i}. "{u}"')
    mwp = t.get("members_without_point") or []
    if mwp:
        L += ["", "### ⚠️ 這條線的落單成員（上了主線但**不成頁**）", "",
              "使用者沒有把它們選成重點，所以 ⛔ **不要為它們開頁**，",
              "也 ⛔ **不要把內容塞進 `notes` 復活**（規格明文禁止）。去處已經定了：", ""]
        for e in mwp:
            L.append(f"- `{e.get('sid')}` → **{e.get('where')}**（{e.get('why','')}）")
    # ⚠️ `narrative` 與 `user_points` 都是**關卡① 才長出來**的欄位，`thread_finder`
    #    交件時它們一律留白（規格明訂 agent 不得代擬）。⛔ 所以這裡不能假設它們有值：
    #    舊版直接把 `None` 丟進 `"\n".join()`，得到的是
    #    `TypeError: sequence item 12: expected str instance, NoneType found`
    #    —— 那句話**完全看不出缺的是哪一欄**，而唯一會踩到它的情境正是
    #    「跳過關卡① 就往下跑」，也就是最需要一句清楚訊息的時候。
    #    ⭐ 改成比照本檔其他缺輸入的作法：`sys.exit` 並指名缺哪一欄、該回去做什麼。
    #    （`check_gate.py layer1` 會先擋一次，這裡是第二道防線，⛔ 不是取代它。）
    missing = [k for k in ("narrative", "mode") if not j.get(k)]
    if missing:
        sys.exit(f"[brief] ⛔ layer1_confirmed.json 缺 {'、'.join(missing)} —— "
                 f"關卡① 還沒定案（那幾欄由**使用者**填，⛔ 不得由 agent 代擬）。"
                 f"先跑 `check_gate.py layer1 <日期目錄>` 把紅燈清掉再派 planner。")
    L += ["", "### 本週敘事（使用者定稿，⛔ 不得改寫）", "",
          j.get("narrative"), "",
          f"mode = {j.get('mode')}"]
    # ⭐ PR 2：deck.json 骨架在派 builder 之前就寫好了（build_deck.py --skeleton），
    #    所以 `plan.terms` 與 `plan.terms_zh` **可以**打包 —— 舊版 delegation.md 說它們
    #    「不能打包、要協調者補進派遣訊息」，那是骨架還在 Step 4 才寫的年代。
    dk = os.path.join(out, "deck.json")
    if os.path.isfile(dk):
        try:
            d = json.load(open(dk, encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        terms = (d.get("plan") or {}).get("terms") or {}
        tz = (d.get("plan") or {}).get("terms_zh") or {}
        if terms.get("objects") or tz:
            L += ["", "### 名詞（關卡② 凍結，⛔ 不得改名、不得另譯）", "",
                  f"- core_metric：{terms.get('core_metric', '')}",
                  "- objects（en → zh）："]
            for o in terms.get("objects") or []:
                L.append(f"  - `{o}` → {tz.get(o) or '（沒有中譯：用原文，並在回報裡點名）'}")
    return "\n".join(L)


def show_refs():
    """印出「誰讀哪一份」的完整對照 —— 這是唯一的一份，⛔ 不要在文件裡抄第二份。"""
    print("角色 ↔ 檔案對照（唯一定義：brief.py 的 ROLE_SPEC ＋ INLINE_REFS）")
    print("⚠️ inline 的每一份都先依 `@for:` 切片，只送標到這個角色的節。\n")
    w = max(len(r) for r in ROLE_SPEC)
    for role in sorted(ROLE_SPEC):
        print(f"{role:<{w}}  角色規格   references/{ROLE_SPEC[role]}")
        for fn in INLINE_REFS[role]:
            print(f"{'':<{w}}  切片 inline  references/{fn}")
        print()
    rev = {}
    for role in sorted(ROLE_SPEC):
        for fn in INLINE_REFS[role]:
            rev.setdefault(fn, []).append(role)
    print("反查（每一份 reference 會被誰讀到）")
    w2 = max(len(f) for f in rev)
    for fn in sorted(rev):
        print(f"  references/{fn:<{w2}}  {', '.join(rev[fn])}")
    print("\n⛔ 不在這張表上的 references 一份都不進派遣包"
          "（它們的成本掛在協調者身上）。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("role", nargs="?", choices=sorted(ROLE_SPEC))
    ap.add_argument("--thread")
    ap.add_argument("--out")
    ap.add_argument("-o", "--outfile")
    ap.add_argument("--show-refs", action="store_true",
                    help="印出 ROLE_SPEC ＋ INLINE_REFS 的角色↔檔案對照表後結束")
    ap.add_argument("--findings", metavar="PATH",
                    help="fixer 專用：三方 findings（check_deck ERROR ＋ shoot ＋ reviewer BLOCKING）"
                         "合成後的檔，逐字進包")
    a = ap.parse_args()
    if a.show_refs:
        show_refs()
        return
    if not a.role:
        ap.error("要給 role（或用 --show-refs 看誰讀哪一份）")
    if not a.out:
        ap.error("--out 是必要的")
    if a.role in ("planner", "builder", "fixer") and not a.thread:
        sys.exit("[brief] ⛔ planner/builder/fixer 要 --thread（一條主線一個 subagent）")
    if a.role == "fixer" and not (a.findings and os.path.isfile(a.findings)):
        sys.exit("[brief] ⛔ fixer 要 --findings <檔>（合成後的 findings；沒有 findings 就沒有修復包）")
    if a.role == "reviewer" and a.thread:
        sys.exit("[brief] ⛔ layout_reviewer 是**跨主線**的，只派 1 個，不要給 --thread")

    out = a.out
    mat = paths.work_dir(out, "materials")
    parts, skipped = [], []

    parts.append(f"""# 派遣包 —— {a.role}{' / ' + a.thread if a.thread else ''}

> 這一份是**打包好的必要輸入**，逐字複製自原檔、沒有摘要。
> 讀完它就可以開始工作，⛔ 不必再逐檔 Read（那會讓帳單乘上回合數）。
> 需要更深的原料時再去讀 `materials.md` §四列的原檔。

工作目錄（日期目錄本身）：`{os.path.abspath(out)}`
""")

    spec = os.path.join(REFS, ROLE_SPEC[a.role])
    parts.append(f"\n---\n\n# 一、角色規格（{ROLE_SPEC[a.role]}）—— 這是唯一的一份\n\n"
                 + read(spec))

    if a.thread:
        parts.append("\n---\n\n# 二、" + thread_block(out, a.thread))

    vocab, hand = (used_vocab(out, a.thread) if a.role == "builder" else (None, True))
    if a.role == "builder" and vocab is not None:
        parts.append("\n> ⭐ 下面的共用判準已依這條線用到的構圖／版型切過"
                     f"（{'、'.join(sorted(vocab)) or '（layer2 沒填 comp／body）'}"
                     f"；{'需要' if hand else '不需要'}手繪）。被切掉的子節都列了名。\n")
    if INLINE_REFS[a.role]:
        parts.append("\n---\n\n# 三、共用判準\n")
    for fn in INLINE_REFS[a.role]:
        p = os.path.join(REFS, fn)
        if not os.path.isfile(p):
            skipped.append(fn); continue
        body, omitted = slice_for(p, a.role)
        sub_omit = []
        if a.role == "builder" and vocab is not None and fn in (
                "composition-vocabulary.md", "slide_types.md", "deck_schema.md", "diagram-craft.md"):
            body, sub_omit = slice_subsections(body, vocab, hand, fn)
        note = f"（{len(omitted)} 節不屬於 {a.role}，已略過）" if omitted else "（整份）"
        if sub_omit:
            note += f"（另 {len(sub_omit)} 個子節是這條線沒用到的構圖／版型，已略過）"
        blk = f"\n## 【全文】`references/{fn}` {note}\n\n{body}"
        if omitted:
            blk += ("\n\n> ⚠️ 這份還有下列幾節不屬於 `" + a.role + "`，本包沒收進來。"
                    "需要時去原檔查（⛔ 不要憑印象猜）：\n> - " + "\n> - ".join(omitted))
        if sub_omit:
            blk += ("\n\n> ⚠️ 下列子節講的構圖／版型**這條線沒用到**（依 layer2.<線>.json 的 "
                    "`composition.comp`／`body`），本包沒收進來。⛔ 要換構圖先回報 BLOCKED，"
                    "不要憑印象填它們的欄位；要查就開原檔 `" + p + "`：\n> - " + "\n> - ".join(sub_omit))
        parts.append(blk)

    if POINTER_REFS[a.role]:
        L = ["\n## 【只給指標】下面這幾份**沒有**收進本包 —— 需要時自己去讀",
             "",
             "⚠️ 刻意不 inline：這幾份你多半是**查**特定一條規則，不是從頭讀到尾。",
             "整份塞進來的話，之後每一個回合都要重送它一次（實測就是這樣讓成本變成 1.4 倍）。",
             "⛔ 但**不要憑印象猜它們寫了什麼** —— 要用就去讀那一節。", ""]
        for fn in POINTER_REFS[a.role]:
            p = os.path.join(REFS, fn)
            if not os.path.isfile(p):
                skipped.append(fn); continue
            src = open(p, encoding="utf-8").read()
            mine = []
            for title, body in sections(src):
                if title is None:
                    continue
                m = TAG.search(body) if False else None
                who = None
                for ln in body.split("\n"):
                    mm = TAG.match(ln)
                    if mm:
                        who = {w.strip() for w in mm.group(1).split(",")}
                        break
                if who is None or a.role in who:
                    mine.append(title[3:].strip())
            L.append(f"### `{p}`")
            L.append(f"　該你讀的節（{len(mine)}）＋**檔頭前言**（前言沒有標籤 ＝ 全員都讀）：\n　"
                     + "、".join(f"`## {x}`" for x in mine))
            L.append("")
        parts.append("\n".join(L))

    if a.role == "fixer":
        full = paths.work_file(out, f"brief.builder.{a.thread}.md", create=False)
        parts.append("\n---\n\n# 三、這一輪要修的 findings（合成過的，⛔ 一次修完，不要分幾輪）\n\n"
                     + read(a.findings))
        sl = paths.work_file(out, f"slides.{a.thread}.json", create=False)
        if os.path.isfile(sl):
            parts.append(f"\n---\n\n# 四、你這條線目前的頁（`{sl}`）\n\n```json\n" + read(sl) + "\n```")
        specs = []
        try:
            j = json.load(open(sl, encoding="utf-8")) if os.path.isfile(sl) else {}
            ids = [x.get("id") for x in (j.get("slides") if isinstance(j, dict) else j) or [] if x.get("id")]
        except (OSError, ValueError):
            ids = []
        for sid in ids:
            sp = paths.work_file(out, f"{sid}.json", create=False)
            if os.path.isfile(sp) and sid in read(a.findings):
                specs.append(f"### `{sp}`\n\n```json\n" + read(sp) + "\n```")
        if specs:
            parts.append("\n---\n\n# 五、findings 點名的頁的構圖 spec（改了 spec 就重跑 `render_figure.py --all <日期目錄> --thread <線>`）\n\n"
                         + "\n\n".join(specs))
        parts.append(
            "\n---\n\n# 六、判準去哪查\n\n"
            f"完整的派遣包（角色規格 ＋ 五份共用判準 ＋ 素材）在 `{full}`。\n"
            "⛔ 不要整份讀 —— findings 每一條都寫了它出自哪一節（`presentation_rules §2c-2`、"
            "`diagram-craft §6`…），需要就 `grep -n '^## <節號>' -A 40` 那一節。\n\n"
            "## 交件條件\n\n```bash\n"
            f"S={os.path.join(SKILL, 'scripts')}\n"
            f"python3 $S/render_figure.py --all {out} --thread {a.thread}\n"
            f"python3 $S/verify.py --out {out} --thread {a.thread} --quiet   # exit 0\n"
            "```\n\n⛔ 不要 Read 自己產出的 .svg；⛔ 不要改別條線的頁；改了 must_numbers 以外的"
            "關卡② 欄位（point／depth／body）→ BLOCKED 回報，不要自己動。\n")
    if a.role == "builder":
        parts.append(
            "\n## 交件前自己跑一次（⛔ 不要靠自我宣稱）\n\n"
            "```bash\n"
            f"S={os.path.join(SKILL, 'scripts')}\n"
            f"python3 $S/render_figure.py --demo /tmp/_demo   # 每個構圖一張範例，看欄位怎麼填\n"
            f"python3 $S/render_figure.py --all {out} --thread {a.thread}   # ⭐ 寫完**所有** spec 後一次渲染，不要一頁跑一次；⛔ 只渲染自己這條線\n"
            f"python3 $S/verify.py --out {out} --thread {a.thread} --quiet   # ⛔ 交件條件：exit 0\n"
            "```\n\n"
            "⭐ **`--quiet` 一律加**：七支腳本的全文會落地到 `_work/4_slides/verify.<線>.log`，"
            "終端只剩摘要表與你這條線的 ERROR 抬頭。要細看某一步就 `grep -n '▶ \\[check\\]' -A 40` "
            "那份 log，⛔ 不要 `cat` 整份 —— 那正是把 context 撐到幾十萬 token 的來源。\n"
            "⭐ **不要 Read 自己產出的 .svg**：看得懂不懂是 `shoot.py` 與 layout_reviewer 的事；"
            "讀回一張 SVG 就是幾千 token 留到收尾的每一個回合。要確認字串就 `grep -c '<text' <svg>`。\n\n"
            "⭐ **`verify.py --thread` 就是你的交件條件** —— 它自己會先把 "
            "`_work/4_slides/slides.*.json` 併進 `deck.json` 再跑 `check_deck.py`，"
            "所以數字溯源與文字用途額度**你自己驗得到**。\n"
            "⚠️ 它跑的是合併後的整份 deck：別條線的錯照樣印出來，但標成「非本線」、"
            "**不算你的紅燈**。被別條線擋住 → 回報協調者，⛔ 不要自己去修別條線。\n"
            "⚠️ 中文版（`strings`／`render_zh`／`shoot_zh`）在 `--thread` 模式下是 SKIP —— "
            "全場的中文版由協調者的完整 verify 跑。⭐ **但你要交這條線的譯文片段**：\n\n"
            "```bash\n"
            f"python3 $S/render_deck.py {out}/deck.json --dump-strings zh --thread {a.thread} "
            f"--strings-out {paths.work_file(out, 'strings.' + a.thread + '.zh.json', create=False)}\n"
            "```\n\n"
            "然後把值填滿（**一次 Write 整份**，⛔ 不要逐條 Edit）：譯文／`\"=\"`（刻意不翻）／`\"\"`（未翻）。"
            "物品名一律照上面「名詞」那張表翻（⛔ 不得另譯），命中 `plan.quotes[].en` 的填 `quotes[].zh` 逐字。"
            "merge_slides 會把片段併進全場的 strings.zh.json。\n\n"
            "⛔ 自驗**之外**還要你逐條人工複核的兩件事（機械檢查抓不到）：\n"
            "①**量級換算**：`check_deck.py` 比的是「這個數字有沒有逐字出現在來源」"
            "（中文數字↔阿拉伯數字可），⛔ 但你把 3 小時寫成 180 分鐘它一樣放行 —— "
            "換算過的數字要自己回去對來源；\n"
            "②**用途標對了沒**：額度（`annot` ≤2、`def` ≤1、整張投影片合併計算）它會算，"
            "⛔ 但一句旁白標成 `label` 就繞過了額度 —— 每則文字要自己判"
            "「這是東西的名字，還是我在講話」。")
    parts.append(BIG_OUTPUT_WARNING)
    parts.append("\n## ⛔ 這幾支**不要讀**\n\n"
                 "它們是拿來**跑**的，不是拿來讀的，而且很大：\n\n"
                 + "\n".join(f"- `scripts/{k}` —— {v}" for k, v in DO_NOT_READ.items()))

    exp = os.path.join(paths.reports_root(), "_explanations.md")
    if a.role == "fixer":
        exp, m_skip = None, True          # 修復包不帶素材與解釋資產：findings 點名的東西才進包
    else:
        m_skip = False
    if exp and os.path.isfile(exp):
        emd, eom = read(exp), []
        if a.thread:
            # ⛔ §1（教授的提問與功課）不切；只有 §2「解釋資產」依相關性收。
            emd, eom = explanations_for(emd, keywords_for(out, a.thread), exp)
        parts.append("\n---\n\n# 四、`_explanations.md` —— 未答的教授提問、"
                     "既有的說法與比喻、名詞慣例"
                     + (f"（§1 教授提問**全份保留**；§2 解釋資產已依你這條線收，"
                        f"{len(eom)} 節不相關、已列名）" if eom else "")
                     + "\n\n" + emd)
    elif not m_skip:
        parts.append(f"\n---\n\n# 四、`_explanations.md`：**不存在**（找的是 {exp}）\n\n"
                     "⚠️ 這代表「未答的教授提問」與「既有說法」這兩件事**沒有來源**，"
                     "不是「沒有提問」。請在回報裡說明。")

    m = os.path.join(mat, "materials.md")
    if os.path.isfile(m) and not m_skip:
        md = read(m)
        if a.thread:
            j = json.load(open(os.path.join(paths.work_dir(out, "layer1"),
                                            "layer1_confirmed.json"), encoding="utf-8"))
            t = next(x for x in j["threads"] if x.get("id") == a.thread)
            sids = list(t.get("members") or []) + \
                   [e.get("sid") for e in (t.get("members_without_point") or [])]
            md = materials_for(md, sids, os.path.abspath(m))
        parts.append("\n---\n\n# 五、本週素材（`materials.md`"
                     + ("，已依你這條線過濾：§二逐項清單與 §四可深入的原料只收你這條線的 sid；"
                        "§零／§一／§二之二／§三 是全局脈絡，整段保留。"
                        "⛔ 被略過的都列了名，需要時查原檔）" if a.thread else
                       "，**整份未過濾** —— 你的工作就是找主線，"
                       "⛔ 這一份不切，切了你就看不到跨線的合併關係）")
                     + "\n\n" + md)

    txt = "\n".join(parts)
    # ⛔ 不要自己拼 `_work/...`：檔案該落在哪一格由 paths.py 一份定義說了算
    # （N14：路徑只寫在散文裡，於是每個寫檔的人各拼各的）。
    name = f"brief.{a.role}{'.' + a.thread if a.thread else ''}.md"
    dest = a.outfile or paths.work_file(out, name, create=True)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(txt)
    cjk = sum(1 for c in txt if "一" <= c <= "鿿")
    print(f"[brief] {a.role}{'/' + a.thread if a.thread else ''} → {dest}")
    print(f"[brief] {len(txt):,} 字元　估 {cjk + (len(txt)-cjk)//4:,} tokens"
          + (f"　⚠️ 缺檔：{skipped}" if skipped else ""))
    print("[brief] ⛔ 派遣訊息只要給這一個檔的路徑，不要再列一長串必讀清單。")


if __name__ == "__main__":
    main()
