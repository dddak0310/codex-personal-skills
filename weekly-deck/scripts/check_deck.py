#!/usr/bin/env python3
"""deck.json 的機械檢查 —— 不要靠自我宣稱，一律跑這支。

檢查項（ERROR 會擋下流程，WARN 只提醒）：
  1. 一頁一重點        每個內容頁要有 point，且不得塞兩個重點
  2. 承接／拋出連貫    第 i 頁的 from 必須等於第 i-1 頁的 to
  3. 數字溯源          投影片上的每個數字必須逐字出現在來源日誌 JSON 裡
                       （來源：aiproductivity.guru 實測，加上這條後編造數字率 1/6 → 0）
  4. 版型容量          表格列數／條列項數／字數上限（真正的把關在 shoot.py 的溢位量測）
  5. 來源可追溯        source 必填、格式 YYYY-MM-DD#N、且該項在 .data 裡真的存在
  6. 週敘事與線結構    要有 arc（PMRC）；outline 頁（全場 1 張 ＋ 每條線 1 張）
  7. I/O 物品鏈        同主線內，第 i 頁的 input 逐字等於第 i-1 頁的 output
  8. 物品登記          input／output 的物品名必須出現在 plan.terms.objects
  9. 頁數預算          主線 ≤15 頁、單一主線 ≤7 頁（backup 不計）
 10. 深度              method 格預設 mechanism；mechanism 頁必須看得到一條具體規則
 11. 結構頁的 body     cover／agenda／thread-intro 的 body 形狀（render_deck.py 的隱性契約，
                       缺欄位會讓 render 崩在 inl(None)）
 12. manifest 對帳     compositions.*.json 點名的物件字串要出現在對應 SVG 的 <text>（WARN）
 13. 語意色一致性      同一個名字在多張圖上不得一頁 good 一頁 bad（§5 一個顏色一種意思）
 14. 帶單位的數字      不在 must_numbers 也不在 point 裡的量測值 → WARN（§2c-2）
 15. 關係證據          宣告 sequence/narrowing/compare… 就必須在圖上看得見（任務 6 L4-1）
 16. 跨頁外觀一致      同一個物件在每頁的長相要一樣（外觀由 SVG 推導，任務 6 L4-2）
 17. 名字的粒度        §1d-0 的兩個方向各一條 WARN（判準：「聽眾可以自己打開這個東西看嗎？」）：
                       太上層＝整頁一個打得開的真名都沒有；太下層＝版面上出現程式識別字

用法：
  check_deck.py <deck.json> [--data <日誌 .data 目錄>]    # 預設由 scripts/paths.py 解析
"""
import argparse, glob, json, os, re, subprocess, sys
import xml.etree.ElementTree as ET

import paths          # 同目錄的 scripts/paths.py（三段式：環境變數 → ~/.config → 慣例）

# 字數上限以英文計（拉丁字母比漢字窄約 1.8 倍）。
# 這些只是早期警告，真正的把關是 shoot.py 的實際溢位量測。
LIMITS = {
    "title": 80, "sub": 96, "point": 90,        # ⛔ 沒有 takeaway：已停用（N67）
                                                #    擋它的是 check_takeaway()，不是字數上限
    "table_rows": 8, "table_cols": 9, "cell": 78,   # 欄數放寬到 9：符號矩陣（O／X／~）的欄很窄
    "agenda": 6, "stats": 4, "points": 6, "point_len": 100,
    "flow": 5, "issues": 4, "col_items": 6,
    # pipeline（單向流程）：上限由 1600×900 的可用寬度推出來，不是隨手訂的。
    #   內容寬 = 1600 − 2×72(padding) = 1456；lane 內距 2×22 → 1412。
    #   箭頭固定 66px，5 個節點 = 5n + 4×66 → n ≈ 230px；6 個節點只剩 n ≈ 191px，
    #   放不下「標題 + 一行內容 + 產出物 chip」而不折成三四行 → 上限 5，超過就拆頁。
    #   lane 高度：可用高 ≈ 900 − 2×72 − 標題區 ≈ 612；一條 lane（標題 + 節點）約 200px，
    #   加 24px gap → 3 條 = 648 已經超出 → 上限 3，建議 2。
    "lanes": 3, "lane_nodes": 5, "node_items": 4, "node_codes": 4,
}
# ── 下限（後補，FINDINGS N110）────────────────────────────────────────────
# ⚠️ 上面 12 個上限、**0 個下限**。實測的失效形狀：`"items": []` 的 stats 頁、
#    1 欄 1 列的表、空標題 —— 全部零報，因為每條檢查都只問「有沒有超過」。
# ⛔ 裁決（2026-09-05，「先寬」）：下限一律 **WARN**，理由是「少」不一定是錯
#    （一張只有兩列的對照表可能正是重點），但「少到版面撐不起一頁」要有人說出來。
#    ⚠️ 反方向（N56）：補下限會把 agent 推去**湊數**（湊到 2 項就好）。擋它的是
#    上面那排上限 ＋ `shoot.py` 的溢位量測 ＋ `check_purpose` 的成句檢查 ——
#    湊出來的項目要嘛成句被擋、要嘛把版面撐爆被擋。兩個方向都有東西在守。
MINS = {
    "table_cols": 2,      # 1 欄的「表」不是表，是一串清單
    "table_rows": 1,      # 只有表頭沒有資料列
    "agenda": 2, "stats": 2, "points": 2, "flow": 2,
    "issues": 1, "col_items": 1, "lanes": 1, "lane_nodes": 2, "node_items": 1,
}
# 主線頁數下限：一條線、一個 user_point 的「2 頁週報」現在會全綠交付（N110 實例）。
# ⚠️ 3 不是校準出來的，是「一份週報至少要說得出開場、做了什麼、結果」的最小數。
MIN_MAIN = 3
STRUCT = {"cover", "agenda", "thread-intro"}
TEXT_ONLY = {"points", "cols", "issues"}   # 以文字為主體的版型：要說得出為什麼不能用圖／表


def is_struct(s):
    """結構頁（封面／議程／週敘事／線開場）與 backup 頁不進承接—拋出的鏈。"""
    return s.get("type") in STRUCT or s.get("backup")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
# #R<N> = 日誌的記錄層（schema v2）。那一層是專門為了讓週報有機制細節可撈而存在的，
# 所以它也可以當 source。
SRC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(#\d+|#R\d+|#issue\d+|#headline)?$")

E, W = [], []
def err(sid, m): E.append(f"  [ERROR] {sid}: {m}")
def warn(sid, m): W.append(f"  [WARN ] {sid}: {m}")


def texts(o):
    """遞迴取出一個 slide 裡所有會被印到投影片上的字串。"""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            # 這些欄位不會印到投影片上：講稿、規劃欄位、以及三層流程的中間量
            # （input／output／depth／slot／composition 是 layer2 的契約，不是頁面內容）
            if k in ("notes", "source", "from", "to", "point", "id", "type",
                     "thread", "tone", "align", "src", "hl", "why_text", "backup",
                     "extra_sources", "input", "output", "depth", "slot",
                     "composition", "example", "example_exception", "pct", "colw", "rowclass",
                     # ⭐ N101（批次 5g）：`must_numbers` 是**關卡② 的規劃契約**
                     #    （「這頁一定要出現哪幾個數字」），⛔ 不是頁面內容。
                     #    漏掉它有兩個後果，實測都撞到了：
                     #      · 數字溯源把它當成「印在頁上的數字」→ 一個**沒畫上去**的
                     #        must_number 照樣被拿去比對來源，畫沒畫看不出來；
                     #      · 反查「指名的數字畫了沒」永遠成立 —— 因為要找的字串
                     #        自己就在 blob 裡，那條檢查**結構上不可能出聲**。
                     #    ⭐ N117 ①：`must_numbers_dropped` 同理，而且更要命 ——
                     #      它逐字寫著「這個數字**沒有**畫上去」，混進 blob 之後
                     #      反查與 layer3 對帳都會判成「畫了」，**宣告本身變成證據**。
                     #      實測：加上這一欄之後 4 個已知砍掉的數字全部翻成
                     #      「宣告砍掉、但它畫在頁上」。⛔ 新增規劃欄位一定要補進這份名單。
                     #    ⭐ N117 ②：`honesty`（圖表誠實性 6 問的答案）同理 ——
                     #      它是**含數字的散文**（「全部 7 個項目」「沒有截斷」），
                     #      混進 blob 會同時汙染數字溯源與 must_numbers 反查。
                     "must_numbers", "must_numbers_dropped", "honesty"):
                continue
            yield from texts(v)
    elif isinstance(o, list):
        for v in o:
            yield from texts(v)


# 專案根：deck 裡引用的相對路徑是相對於它的，用來驗「這個檔還在不在」。
# ⛔ 不要寫死 —— 換一個人用就會靜默失效（找不到檔 → 誤報「檔案不存在」）。
PROJ_ROOT = paths.project_root()


def extra_source_text(s):
    """日誌是壓縮過的，機制與清單要去 docs/ 或 meta.json 撈——那些數字也算有來源。

    用法：在該 slide 加 "extra_sources": ["docs/03_snv_detect/feature_registry.md", ...]
    （專案相對路徑或絕對路徑皆可）。檢查會把那些檔的內容也納入可溯源的數字池。

    ⚠️ 這不是放寬，是把來源講明白：數字仍然必須**逐字出現在某個指名的檔案裡**，
    只是那個檔案可以不是日誌。沒有 extra_sources 就只認日誌。
    """
    out = ""
    for p_ in (s.get("extra_sources") or []):
        fp = p_ if os.path.isabs(p_) else os.path.join(PROJ_ROOT, p_)
        if os.path.isfile(fp):
            try:
                out += open(fp, encoding="utf-8", errors="ignore").read()
            except OSError:
                pass
        elif os.path.isdir(fp):
            # ⚠️ 目錄是合法的（daily-log 的 artifacts.outputs 本來就常是目錄，
            #    例如 results/bench/20250115_lru/），只是它提供不了可比對的文字，
            #    所以不報錯、也不貢獻內容。原本一律當成「不存在」會誤報。
            pass
        else:
            err(s.get("id", "?"),
                f"extra_sources 指到不存在的路徑：{p_}"
                f"（檔案給數字溯源用；目錄合法但提供不了可比對的文字）")
    return out


def svg_numbers(deck_path, s):
    """外部 .svg 圖檔裡的數字也要溯源 —— 圖不是免檢區。"""
    src = (s.get("body") or {}).get("src") or ""
    if not src.lower().endswith(".svg"):
        return ""
    p = os.path.join(os.path.dirname(os.path.abspath(deck_path)), src)
    if not os.path.isfile(p):
        return ""
    # 只取 <text>/<tspan> 的文字內容 —— 座標、寬高、色碼都不是投影片上的「數字」
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError as e:
        err(os.path.basename(src), f"SVG 解析失敗：{e}")
        return ""
    NS = "{http://www.w3.org/2000/svg}"
    txts = ["".join(el.itertext()) for el in root.iter()
            if el.tag in (NS + "text", NS + "tspan", "text", "tspan")]
    for t in txts:
        if is_commentary(t, SVG_LEN):
            warn(os.path.basename(src),
                 f"圖裡有一句像是講者的話：「{t[:56]}」\n"
                 f"           圖上只放標註，推論與結論搬進 notes")
    return " ".join(txts)


# ── N99：`slot` 豁免集的**唯一定義**（批次 5g）────────────────────
#    ⭐ 先答「豁免的語意是什麼」：它只有**一個**意思 ——
#    **「這一頁不必對應到一個 `user_point`」**，因為它是支撐結構、
#    不是使用者指名要講的重點。⛔ 它**不是**「這頁不必交 example」：
#    那是**後果**不是語意（支撐結構頁的 `depth` 預設就不是 `mechanism`，
#    於是不會被要求交 example）—— `check_gate.py` 一直就是這樣實作的。
#
#    成員 ＝ **所有非 `method` 的格**。`SKILL.md` layer2 的節標題逐字寫著
#    「`method` 是唯一預設有頁的格」，`deck_schema.md` 也寫「其餘三格用了要寫理由」。
#    ⚠️ 以前有**三份互不相同**的清單（本檔 {problem,intro,result}／
#    `check_gate.py` {result,intro,buildup}／`deck_schema.md` 少了 `intro`），
#    兩個方向都誤判過：`slot: buildup` 在關卡② 被放行、走到 Step 4 才爆
#    （**圖都畫完了**）；`slot: problem` 反過來在關卡② 被 depth 預設成
#    `mechanism`、被要求交 example，而 Step 4 反而豁免它。
#    ⛔ 現在只有這一份，`check_gate.py` 用 import 拿（比照 MAX_POINT 的先例）。
SLOT_EXEMPT = {"buildup", "problem", "intro", "result"}

PURPOSE = {"label", "value", "annot", "def"}
PURPOSE_CAP = {"annot": 2, "def": 1}        # label／value 不限**硬**則數，見下面的軟上限
# ── N112：「把文章寫在 block 下面」在機械上是滿分 ──────────────────────
# ⚠️ 回饋③ 的機械形狀：`PURPOSE_CAP` 註解明寫「label／value 不限則數」，防線全押在
#    `looks_like_sentence()` 的**單則長度**上，而它的 docstring 自己承認
#    「拆得越短越不像句子」。**沒有任何東西在數則數。**
# ⛔ 裁決（2026-09-05）：則數上限用**實測**訂，不是憑感覺：
#    現有 7 張圖的 label 則數是 15／20／30／40／44／45／45，value 最多 7
#    → 軟上限訂 56（＝實測上緣 45 × 1.25）與 12。⚠️ 這個數字**擋不到**
#    N112 那個實例（12 則硬斷行的散文），它擋的是另一個方向：整張圖被字淹沒。
#    真正擋那個實例的是下面的 DANGLING —— 見那裡的說明。
# ⚠️ ⭐ 與 `shoot.py` 的 65% 密度門檻**同批訂**（HANDOFF 明列這兩條會打架）：
#    密度門檻獎勵「把格子填滿」，最省力的填法就是塞字。所以 shoot.py 那一側
#    同時補了反方向的「文字過密」提示（>60 則 <text>），讓「塞字」不再是唯一
#    過得了密度門檻的手段。⛔ 65% 這個數字**不動** —— 它有實測校準
#    （viewBox 1420×470，仍在高度預算表之內），動它等於推翻那次校準。
PURPOSE_SOFT_CAP = {"label": 56, "value": 12}
# 以虛詞結尾的短句 = 一句話被硬斷行的接縫。真正的標籤（東西的名字、數值）不會這樣結尾。
DANGLING = re.compile(
    r"(?:^|\s)(?:the|a|an|of|to|in|on|for|and|or|is|are|was|were|that|with|by|from"
    r"|it|its|as|at|be|been|but|so|then|than|into|about|which|we|you|this|these"
    r"|those|our)\s*$", re.I)
LEGACY_CLASS = {"t-lg", "t-md", "t-sm", "t-num"}   # 舊的「大小」字彙，已作廢
# ⚠️ **中文與英文要分開量**（後修）。原本只有一個 22 字元的門檻，
#    那是照英文訂的（`every term it is about to use` 是 29 字元）——
#    但一個中文字算一個字元，**22 個中文字已經是一整句話**
#    （實測「每個欄位都會先被查對照表再決定要不要換成白話」剛好 22，判 False 漏掉）。
#    對照：`order-service` 才 13 字元。同一把尺量兩種寬度不同的文字必然失準。
SENTENCE_LEN = 22        # 拉丁文為主時的門檻
SENTENCE_LEN_CJK = 12    # 中文為主時的門檻（12 個中文字已經講得完一句話）
CJK = re.compile(r"[一-鿿]")
# 標籤／數值的形狀：帶符號、數字、檔名，或全大寫的區塊標題。
LABELISH = re.compile(r"""[=:：→←↔／/·•@$"'`]|\d|\.\w{2,4}$|^[A-Z0-9 ._&%-]+$""")
# ⚠️ 後補 `@ $ " ' \``：實跑把一行 shell 指令
#    `codex plugin add daily-log@ccu-lab`（34 字元）判成「句子」。
#    指令、路徑、引號字串都是**東西的名字**，不是散文。


def looks_like_sentence(t):
    """label／value 不得成句。

    ⚠️ 為什麼判「形狀」而不是「長度」：長度上限會被**拆句**繞過。
    首次實跑實測，writing_rules.svg 把一句話拆成
    「every term it is about to use」(29) ＋「is looked up here, and swapped」(30)，
    兩則都在當時的 52 字元上限之下，全部合法通過。
    拆得越短越不像句子；拆到 22 字元以下就真的變成標籤了 —— 那也達到目的。
    """
    t = (t or "").strip()
    if not t or LABELISH.search(t):
        return False
    # 中文字佔一半以上 → 用中文的尺
    limit = SENTENCE_LEN_CJK if len(CJK.findall(t)) * 2 >= len(t) else SENTENCE_LEN
    return len(t) > limit


def _svg_root(deck_path, s):
    """取出這一頁外部 .svg 的 XML root 與檔名；沒有圖／解析失敗回 (None, None)。"""
    src = (s.get("body") or {}).get("src") or ""
    if not src.lower().endswith(".svg"):
        return None, None
    p = os.path.join(os.path.dirname(os.path.abspath(deck_path)), src)
    if not os.path.isfile(p):
        return None, None
    try:
        return ET.parse(p).getroot(), os.path.basename(src)
    except ET.ParseError:
        return None, None                        # 解析錯誤已由 svg_numbers 報過


def collect_svg_purpose(deck_path, s):
    """圖上每則文字的用途分類。回傳 [(用途, 來源, 文字), ...]。

    「沒標用途」「同時標了兩個」這兩種格式錯在這裡就報（掛在 .svg 檔名下，好定位）；
    **則數上限不在這裡比** —— 上限是整頁的額度，見 check_purpose。
    """
    root, name = _svg_root(deck_path, s)
    if root is None:
        return []
    NS = "{http://www.w3.org/2000/svg}"
    out = []
    for el in root.iter():
        if el.tag not in (NS + "text", "text"):
            continue
        t = "".join(el.itertext()).strip()
        if not t:
            continue
        cls = set((el.get("class") or "").split())
        purpose = cls & PURPOSE
        if not purpose:
            legacy = cls & LEGACY_CLASS
            hint = ("（舊的大小字彙 %s 已作廢 —— 它問的是「多大」，"
                    "不是「幹嘛的」）" % "／".join(sorted(legacy))) if legacy else ""
            err(name, f"文字沒有標用途{hint}：「{t[:44]}」\n"
                      f"           每個 <text> 要恰好一個：label（東西的名字）／"
                      f"value（數字或結果）／annot（這張圖怎麼讀）／def（名詞定義）")
            continue
        if len(purpose) > 1:
            err(name, f"文字同時標了 {len(purpose)} 個用途"
                      f"（{'、'.join(sorted(purpose))}）：「{t[:44]}」")
            continue
        # ⭐ `lead` 是 render_figure.py 給**步驟名／群組標題**的標記
        #    （`class="label lead"`）。那一格天生就是「東西的名字」——
        #    builder 只填資料，座標與版位由程式排。
        #    ⚠️ 實跑實測：六步流程圖的步驟名 `Fill narrative skeleton`（23 字元）
        #    被「拉丁文 >22 字元 → 判成句」擋掉。英文詞比中文長，22 字元只夠三個單字。
        #    ⛔ 不要改用調高門檻解決 —— 那會把「把一句話拆成兩則短的」的漏洞放回來。
        #    比照 `agenda`／`issues` 的 `d` 的既有豁免：**結構性欄位不套「不得成句」**。
        out.append((purpose.pop(), name, t, "lead" in cls))
    return out


def _tables_of(b):
    """一頁上所有的表：body.tables[]、表格版型的 body 本身、兩欄版型左右欄內的表。"""
    ts = list(b.get("tables") or [])
    if b.get("columns"):
        ts.append(b)
    for side in ("left", "right"):
        t = (b.get(side) or {}).get("table")
        if t:
            ts.append(t)
    return ts


def collect_json_purpose(s):
    """deck.json 欄位渲染出來的字，也要歸到同一套用途分類（後補）。

    ## 為什麼 SVG 管完還要管欄位

    分類機制原本只管 `<text>`，但**投影片上的淺色字不是只有圖裡那些**：
    `deck.css` 用 `var(--ink-2)`（淺色）渲染的還有副標 `.sub`、圖說 `figcaption`、
    表格 `caption`、流程步驟的 `.step .d`、大數字的 `.stat .k`。
    那些字對觀眾來說跟圖裡的旁白**長得一模一樣**，只是寫在別的欄位裡。
    只擋圖裡的旁白，等於把它們趕到 deck.json 去寫 —— 版面一樣亂。

    舊的把關是 `check_caption()` 的 WARN。**實測 WARN 會被忽略**：
    首次實跑那次它叫了兩次，兩張圖原封不動進了 pptx。
    所以上限一律算**整張投影片**的額度，且是 ERROR。

    ## 每個欄位固定對應哪一種用途

    | 欄位（渲染成） | 用途 | 理由 |
    |---|---|---|
    | `sub`（`.sub`） | annot | SKILL.md 與 presentation_rules §2 早就規定 sub 只能寫「這張圖表怎麼讀」 |
    | `body.caption`（圖說 figcaption） | annot | 同上，caption 的定義就是 annot 的定義 |
    | 表格 `caption` | annot | 同上 |
    | `stats` 的 `k`（`.stat .k`） | label | 它是那個數字的**名字**，不是旁白 → 改用正常色，並套「不得成句」 |
    | `stats` 的 `v`（`.stat .v`） | value | 數字本身 |
    | `flow` 步驟的 `d`（`.step .d`） | label | 它屬於那個步驟框，是框的一部分 → 正常色 ＋「不得成句」；<br>要寫成句子代表它是旁白，該搬進 notes（§2a「把句子裝進方框不算圖」） |

    **豁免（刻意的兩個洞，不是漏掉）**
    · `agenda` 的 `.d`：議程／封面是結構頁（`STRUCT`），本來就不進逐頁檢查，
      它的 `d` 是那一條線的名字，不是旁白。
    · `issues` 的 `.d`：`issues` 頁一律是 backup（`check_body_kind` 已把它擋出主線），
      那段字是**問題本身的內容**，不是圖的旁白。
    所以不變式要寫準：**主線內容頁上，淺色只給 annot 與 def。**
    """
    out = []
    b = s.get("body") or {}
    st = s.get("type")
    if s.get("sub"):
        out.append(("annot", "sub（副標）", s["sub"]))
    if st in ("diagram", "figure") and b.get("caption"):
        out.append(("annot", "圖說 body.caption", b["caption"]))
    for i, t in enumerate(_tables_of(b), 1):
        if t.get("caption"):
            out.append(("annot", f"第 {i} 張表的 caption", t["caption"]))
    if st == "stats":
        for x in (b.get("items") or []):
            if x.get("k"):
                out.append(("label", "stats 的 k（這個數字的名字）", x["k"]))
            if x.get("v"):
                out.append(("value", "stats 的 v", x["v"]))
    if st == "flow":
        for x in (b.get("steps") or []):
            if x.get("d"):
                out.append(("label", f"flow 步驟「{str(x.get('t'))[:14]}」的 d", x["d"]))
    # ⭐ example 的 `aside` 已作廢（使用者原話：「『規則』(黃色背景)那格根本不需要…
    #    放大佔據整個版面就可以了」）。版型改成主圖全寬單欄，右欄不再渲染，
    #    於是 FINDINGS **N29 的豁免也一併拿掉** —— 那個豁免的存在理由是
    #    「aside.rule／aside.boundary 是版型必填、會把 annot 額度 2 吃滿」，
    #    欄位消失，額度就不再被版型自己吃掉，annot ≤2 回到原本的意思。
    #    ⛔ 帶著 body.aside 的頁由 check_example 直接報 ERROR，不會走到這裡。

    # pipeline：整個版型的文字**全部是 label**，只有節點的 v 是 value。
    # 三條理由（比照 diagram-craft §5 判定「分支 pill 上的字算 label」）：
    #   ① 語意：每一則都是「東西的名字」——lane 的名字、節點的名字、
    #      流進節點的物品名、產出物名、節點裡的清單項。沒有一則在講「這張圖怎麼讀」。
    #   ② 額度：annot 是**整頁 ≤2**。一個 2 lane × 4 節點的圖有 20 則以上的文字，
    #      歸成 annot 會讓這個版型結構上不可能通過 —— 那等於版型不能用。
    #      反過來說也成立：如果那些字真的是旁白，這頁本來就不該用這個版型。
    #   ③ 顏色：⛔ 淺色只給 annot 與 def。這些字都寫在 lane 標題列或節點框裡、
    #      是框的一部分，用正常色才讀得到（同 flow 的 .step .d 在 的改法）。
    # 代價是它們一律套「不得成句」——這正是我們要的：節點框裡不准塞散文。
    if st == "pipeline":
        for li, ln in enumerate(b.get("lanes") or [], 1):
            tag = str(ln.get("label") or f"lane{li}")[:14]
            if ln.get("label"):
                out.append(("label", f"lane「{tag}」的名字", ln["label"]))
            if ln.get("note"):
                out.append(("label", f"lane「{tag}」的補語 note", ln["note"]))
            for nd in (ln.get("nodes") or []):
                nt = str(nd.get("t") or "")[:14]
                for key, kind, what in (("t", "label", "節點名"), ("d", "label", "d"),
                                        ("chip", "label", "產出物 chip"),
                                        ("arrow", "label", "箭頭標籤"),
                                        ("v", "value", "大數字 v")):
                    if nd.get(key):
                        out.append((kind, f"pipeline 節點「{nt}」的{what}", nd[key]))
                for x in (nd.get("items") or []):
                    out.append(("label", f"pipeline 節點「{nt}」的清單項", x))
                for c in (nd.get("codes") or []):
                    t = c.get("t") if isinstance(c, dict) else c
                    if t:
                        out.append(("label", f"pipeline 節點「{nt}」的色塊", t))
    # 表格的比例 bar 儲存格：{"v": "53/66", "pct": 80} 的 v 是數值 → value
    for i, t in enumerate(_tables_of(b), 1):
        for r in (t.get("rows") or []):
            for c in r:
                if isinstance(c, dict) and c.get("v"):
                    out.append(("value", f"第 {i} 張表的 bar 儲存格", c["v"]))
    return out


def _renderer_comps():
    """render_figure.py 現在有哪些 renderer —— **從那支腳本讀，不要在這裡抄一份**
    （已知坑 #13：同一事實寫在兩個地方必定分岔）。讀不到就回空集合、不擋。"""
    try:
        import importlib.util
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_figure.py")
        spec = importlib.util.spec_from_file_location("_rf", fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return set(getattr(m, "RENDERERS", {}))
    except Exception:
        return set()


RENDERER_COMPS = _renderer_comps()


def check_renderer_used(s, sid):
    """有 renderer 的構圖**不准手寫 SVG**（後補）。

    ⚠️ `composition-vocabulary.md` 早就寫著這條，但**沒有任何東西在執行** ——
    跟今天打掉的其他幾條同一個形狀（規則寫了、agent 沒照做）。

    ## 為什麼一定要擋

    layer3 的管線是 `① 關係抽取 → ② 構圖選擇 → ③ 填 JSON → ④ 算座標(code)`。
    首次實跑實測：六張圖的 `relation`／`comp`／守門提問**全部填好了**，
    但 `handwritten: true` × 6 —— **第四步從來沒跑過**，前三步的產物沒有下游消費，
    最後仍然自由手繪。後果是第三層的圖**來回改了四輪**，
    以及 `diagram-craft.md` 記載的箭頭壓字、線對不到框（手算座標的必然產物）。

    ⛔ 這條擋的正是「有工具卻不用」。沒有 renderer 的構圖不受影響。
    """
    comp = (s.get("composition") or {}).get("comp")
    if not comp or comp not in RENDERER_COMPS:
        return
    if (s.get("composition") or {}).get("handwritten"):
        err(sid, f"構圖「{comp}」**有 renderer 卻標成 handwritten** —— "
                 f"⛔ 有 renderer 的構圖不准手寫 SVG。\n"
                 f"           手算座標是「箭頭壓字、線對不到框、改一格全部重算」的來源；"
                 f"renderer 保證對齊，改一行 JSON 重跑即可。\n"
                 f"           用法：python3 scripts/render_figure.py spec.json "
                 f"-o figures/<name>.svg")


def check_purpose(deck_path, s, sid):
    """投影片上每則文字都要標**用途**，各類上限由用途推出來（後補）。

    ## 為什麼是分類而不是總量

    舊做法是總量限制（每則 ≤52 字元）。兩個失效：
      · **拆句就能繞過** —— 見 looks_like_sentence 的實例。
      · **誤傷乾淨的圖** —— selection_score.svg 有 31 則文字、531 字元，
        比被擋下的那幾張還多，但全是標籤與數值，是合法的；
        任何「一頁最多幾個字」都會連它一起砍。

    改成分類的理由來自 daily-log 的結論：
    **「要模型判斷『重不重要』會失準，要它分類不會」**（selection-signals.md）。
    「這句話夠不夠精簡」是判斷；「這句話是標籤還是旁白」是分類。

    ## 額度是整張投影片的，不分寫在哪裡

    `annot ≤2`／`def ≤1` 算的是**這一頁**，SVG 裡的 `<text>` 與 deck.json 的欄位
    （sub／圖說／表格 caption）合併計數 —— 觀眾看到的是同一個版面，
    旁白搬個地方寫不會變得比較不吵。

    ⚠️ 分類要在**寫圖／寫欄位的時候**標，不是事後篩 —— 事後標的話
    agent 會先寫出旁白、再替它挑一個標籤。字彙定義在 assets/deck.css。
    """
    items = collect_svg_purpose(deck_path, s) + collect_json_purpose(s)
    if not items:
        return
    counts = {k: [] for k in PURPOSE}
    for it in items:
        # SVG 來源回 4 元組（多一個 lead 旗標），deck.json 欄位來源回 3 元組
        kind, origin, t = it[0], it[1], it[2]
        is_lead = it[3] if len(it) > 3 else False
        counts[kind].append((origin, t))
        if kind in ("label", "value") and not is_lead and looks_like_sentence(t):
            err(sid, f"{origin} 標成 {kind}，但它是一句話（{len(t)} 字元）："
                     f"「{t[:52]}」\n"
                     f"           label／value 是東西的名字與數值，不得成句。"
                     f"要留就改成 annot 的位置（每頁 ≤2），留不下就刪掉、搬進 notes")
    # ── N112：則數的軟上限（WARN）─────────────────────
    for k, softn in PURPOSE_SOFT_CAP.items():
        if len(counts[k]) > softn:
            warn(sid, f"這一頁的 {k} 有 {len(counts[k])} 則，超過軟上限 {softn}"
                      f"（實測上緣 45 則 × 1.25）—— 版面正在被字淹沒。\n"
                      f"           ⚠️ 密度門檻（shoot.py 65%）獎勵把格子填滿，"
                      f"而最省力的填法是塞字。**填的要是事實，不是句子**：\n"
                      f"           真名、數量、限制、檔名各算一則事實；把一句話斷成六則不算。")
    # ── N112：硬斷行的散文 ───────────────────────────
    # ⚠️ 為什麼用**比例**不用則數：實測 7 張合法的圖裡，以虛詞結尾的 label 是
    #    0~4 則（最高 A4 的 2/20 = 10%），而 N112 那個實例是 6 則裡 5 則 = 83%。
    #    單看「有沒有虛詞結尾」會誤殺 `read by`／`counted from` 這種合法的欄位標
    #    → 門檻訂 30%，中間隔著三倍。⛔ 這是 WARN：比例是代理指標，不是判準。
    # ⚠️ 反方向（N56）：這條會把 agent 推去**把散文改寫成一長則**——那一則就會
    #    被 looks_like_sentence() 擋成 ERROR。兩個方向都有東西在守。
    lv = counts["label"] + counts["value"]
    dang = [(o, t) for o, t in lv if DANGLING.search(t)]
    if len(lv) >= 6 and len(dang) >= len(lv) * 0.3:
        lines = "\n".join(f"           · [{o}]「{t[:44]}」" for o, t in dang[:6])
        warn(sid, f"這一頁 {len(lv)} 則 label／value 裡有 {len(dang)} 則"
                  f"（{round(len(dang) / len(lv) * 100)}%）以虛詞結尾"
                  f"（the／of／is／and…）—— 那是**一句話被硬斷行**的接縫，"
                  f"不是東西的名字：\n" + lines + "\n"
                  f"           拆得越短越不像句子，所以逐則的長度檢查看不到它。"
                  f"⛔ label／value 是名字與數值；解釋搬進 notes")
    for k, capn in PURPOSE_CAP.items():
        if len(counts[k]) <= capn:
            continue
        why = "旁白本來就該罕見" if k == "annot" else "一頁講一個新名詞就夠"
        lines = "\n".join(f"           · [{o}]「{t[:44]}」" for o, t in counts[k][:8])
        err(sid, f"這一頁的 {k} 有 {len(counts[k])} 則，上限 {capn} —— {why}。\n"
                 f"           額度算**整張投影片**：圖裡的 <text> 與 deck.json 的欄位"
                 f"（sub／圖說／表格 caption）合併計數。\n"
                 f"           ⛔ 淺色字只給 annot 與 def，多出來的請刪掉或搬進 notes：\n"
                 + lines + ("\n           …" if len(counts[k]) > 8 else ""))


def svg_text_only(deck_path, s):
    """只取 SVG 的 <text>/<tspan> 文字，不重複發 commentary 警告（那由 svg_numbers 發）。"""
    src = (s.get("body") or {}).get("src") or ""
    if not src.lower().endswith(".svg"):
        return ""
    p = os.path.join(os.path.dirname(os.path.abspath(deck_path)), src)
    if not os.path.isfile(p):
        return ""
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError:
        return ""
    NS = "{http://www.w3.org/2000/svg}"
    return "  ".join("".join(el.itertext()).strip() for el in root.iter()
                     if el.tag in (NS + "text", NS + "tspan", "text", "tspan"))


def svg_text_count(deck_path, s):
    """圖上有幾個獨立的文字節點 —— ⓐ 機制描述「有一組具名元件」的機械代理。"""
    t = svg_text_only(deck_path, s)
    return 0 if not t else len([x for x in re.split(r"\s{2,}", t) if x.strip()])


# ── 中文數字 → 阿拉伯數字（後補，見 FINDINGS F10）────────────────────
# ⚠️ **這不是放寬數字溯源**，是讓同一個值的兩種書寫系統算同一個值。
#
# 為什麼需要：日誌是中文寫的（「二十個特徵」「涵蓋十八個檢體」「千分之一」），
# 而三條凌駕一切的原則第 ① 條規定 `deck.json` **一律寫英文** → 投影片上只能是
# 20／18／1e-3。舊實作的 NUM 只認阿拉伯數字，於是
#   `18` vs 日誌「十八」→ 找不到（小整數僥倖只發 WARN）
#   `1e-3` vs「千分之一」→ 找不到且含小數點 → **ERROR，直接擋住整份**
# 而規格同時寫著「數字只能逐字照抄，單位換算也算改寫」——兩條互相打架，
# 規格沒有任何一句處理「來源是中文、交付物要英文」這個情況。
#
# ⛔ **界線（不可放寬）**：位數與單位都沒變的是**書寫系統**（二十↔20），放行；
#    位數變了的是**單位換算**（「3,664 萬列」↔ 36,640,000），⛔ 仍然算改寫、仍然擋。
#    原規則要防的是後者（憑印象把數字換算錯），不是前者。
_CN_D = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
         "六": 6, "七": 7, "八": 8, "九": 9}
_CN_RATIO = {"十分之一": "0.1", "百分之一": "0.01", "千分之一": "0.001",
             "萬分之一": "0.0001", "十萬分之一": "0.00001"}
_CN_RUN = re.compile(r"[零〇一二兩三四五六七八九十百]+")


def _cn2int(w):
    """只處理 0~999 的常見寫法（十八、二十、九十九、一百、兩百三十）。

    ⛔ 刻意不做「萬」「億」—— 那是量級單位，屬於上面說的「換算」那一邊。
    看不懂就回 None，⛔ 不要猜（猜錯會讓一個假數字通過溯源）。
    """
    if not w or any(c not in "零〇一二兩三四五六七八九十百" for c in w):
        return None
    total, cur, seen = 0, None, False
    for c in w:
        if c in _CN_D:
            cur = _CN_D[c]; seen = True
        elif c == "十":
            total += (1 if cur is None else cur) * 10; cur = None; seen = True
        elif c == "百":
            if cur is None:
                return None
            total += cur * 100; cur = None; seen = True
    if cur is not None:
        total += cur
    return total if seen else None


def cn_numbers(s):
    """把字串裡的中文數字寫法，換算成等值的阿拉伯數字字串集合。"""
    out = set()
    for k, v in _CN_RATIO.items():
        if k in s:
            out.add(v)
            out.add(v.rstrip("0").rstrip("."))       # 0.001 也接受 .001 之外的寫法
            out.add(f"1e-{len(v.split('.')[1])}")    # 千分之一 → 1e-3
    for m in _CN_RUN.finditer(s):
        n = _cn2int(m.group(0))
        if n is not None:
            out.add(str(n))
    return out


def norm_nums(s):
    return {m.group(0).replace(",", "") for m in NUM.finditer(s)}


def is_data_number(t):
    """看起來像「資料」的數字：有小數點／百分比／三位數以上。小整數只給 WARN。"""
    return ("." in t) or t.endswith("%") or len(t.rstrip("%")) >= 3


def load_source_text(data_dir, days):
    pool, missing = "", []
    for d in sorted(days):
        p = os.path.join(data_dir, f"{d}.json")
        if not os.path.isfile(p):
            missing.append(d); continue
        pool += json.dumps(json.load(open(p, encoding="utf-8")), ensure_ascii=False)
    return pool, missing


def cap(sid, name, val, limit, unit="字"):
    if val > limit:
        err(sid, f"{name} 超過上限（{val} > {limit} {unit}）")


def capmin(sid, name, val, limit, unit="項"):
    """下限（N110）。⚠️ 一律 WARN —— 少不一定是錯，但要有人說出來。"""
    if val < limit:
        warn(sid, f"{name} 只有 {val} {unit}，低於下限 {limit} {unit} —— "
                  f"這一頁撐不撐得起一整張投影片？撐不起就併頁或補內容")


# 具體標題的錨點：數字、或含內部大寫的專名（樣本名、工具名，例 CL-771 / VarScope）
# ⚠️ 後修：原本是 r"\d|[A-Za-z]+[A-Z0-9]" —— 那是**中文標題**的啟發式
# （中文句子裡冒出一串拉丁字母，幾乎一定是工具名或樣本名）。
# 但 deck.json 規定一律寫英文（SKILL.md 原則①）→ 在全英文標題裡「含拉丁字母」毫無鑑別力，
# `extract_transcript.py` 這種明確的工具名反而被判成沒有錨點。實測 8 頁全數誤報。
# 補上英文語境真正的錨點：snake_case、副檔名、CamelCase、反引號標記的識別字。
ANCHOR = re.compile(
    r"\d"                       # 數字
    r"|[A-Za-z]+[A-Z0-9]"        # VarScope、TF1e-3（中文語境的原判準，保留）
    r"|[a-z]+_[a-z]+"            # extract_transcript、check_deck
    # ⚠️ 後修（FINDINGS N26）：**帶連字號的小寫複合詞**也是這個領域的工具名長相
    # （daily-log、weekly-deck、mattpocock-skills）。實測誤報：
    # 「Name mattpocock-skills, not skill」「daily-log now installs anywhere」
    # 明明點名了工具，卻被判成「沒有錨點」。
    # ⛔ 代價講明白：一般的英文複合修飾語（machine-checked、record-layer）也會被算成錨點，
    #    這條的鑑別力因此降低一格。這是刻意的取捨 —— 假警報會讓整條 WARN 被忽略，
    #    比漏掉一個抽象標題貴。真正抽象的標題（「我們的位置」「順序錯了」）仍然擋得住。
    r"|[a-z]+-[a-z]+"            # daily-log、mattpocock-skills
    r"|\.(?:py|sh|json|md|html|svg|bam|vcf|tsv)\b"   # 副檔名
    r"|`[^`]+`"                  # 反引號標起來的識別字
)


# 推論連接詞 —— 出現在 caption／sub／圖說裡，幾乎一定是「講者的話」而不是「圖表的標註」
INFER = re.compile(
    r"所以|因為|才(?:能|可|會)|代表|表示|反而|應該|否則|才可比|"
    r"\bso\b|\bbecause\b|\bwhich means\b|\botherwise\b")   # 不放 would／should：太常出現在一般標註裡
# 合法的圖例有兩種長相：① 含 =／＝ 的符號定義　② 用全形空格分隔的多組「標記＋短標」
LEGEND = re.compile(r"[=＝]")
# ⚠️ 後修（FINDINGS N27）：**規則本身**與**欄位名清單**被誤判成「講者的話」。
# 實測的兩則假警報：
#   「≥20 messages → 3 · decisive line or 5-19 → 2 · 1-4 → 1」 ← 判準表，
#      正是 depth=mechanism 被要求要有的「一條具體規則」（§2a）—— 這條檢查
#      與 mechanism 的要求互相打架，等於叫 builder 把規則從圖上拿掉。
#   「why · what was done · what came out · so what」 ← 四個欄位的名字，
#      被 INFER 的 `\bso\b` 命中（"so what" 是欄位名，不是「所以」）。
# 兩種形狀的共同點：**它們是對應關係，不是句子**。
#   ① 有映射／比較符號（→ ⟶ ≥ ≤ ⇒）＝ 一條規則的寫法
#   ② 用 `·` 分成三段以上 ＝ 一串並列的欄位名／判準列
# ⛔ 不要改成「調高長度上限」：那會把「把一句話拆成兩則短的」的漏洞放回來，
#    也擋不住 `\bso\b` 那種連接詞誤命中。真正的散文（「Installed …, listed what its
#    18 tools each do」）沒有映射符號、也不是並列清單，仍然報得出來。
RULEISH = re.compile(r"[→⟶⇒≥≤]")


# ── N113：豁免的長度天花板 ─────────────────────────────────────────
# ⚠️ `is_legend()`／`is_question()` 原本是**無條件豁免**：`is_commentary()` 一旦命中
#    兩者之一就 return False，**連長度都不量**。於是含一個 `→` 的 125 字說明句、
#    或任何以 `?` 結尾的 200 字段落，一律放行。
# ⛔ 裁決（2026-09-05）：豁免只在**長度沒有失控**時成立。天花板 = LIMITS["sub"] = 96
#    —— 用既有的字數上限當數字，不另訂一套（同一件事不要有兩個數）。
#    真的圖例確實會長（一整排符號定義），但長到超過一則 sub 的上限時，
#    它已經不是「怎麼讀這張圖」而是「這張圖說明了什麼」。
# ⚠️ 反方向（N56）：加了天花板會把 agent 推去**把長圖例拆成兩則**繞過。
#    擋它的是 check_purpose 的 annot ≤2／def ≤1 額度（拆成兩則就佔兩格額度）。
EXEMPT_LEN = 96


def is_legend(t):
    if len(str(t or "")) > EXEMPT_LEN:
        return False
    return (bool(LEGEND.search(t)) or t.count("　") >= 2
            or bool(RULEISH.search(t)) or t.count("·") >= 2)


def is_question(t):
    """演示類頁面的起始問題是合法的（§1c）——沒有它觀眾不知道在看什麼被解決。

    ⚠️ 代價：以「…？」結尾的說明句也會一併豁免。看到長問句仍要自己判一次：
    它是**這一頁要回答的問題**，還是**你在描述這張圖在幹嘛**？後者要拿掉。
    """
    # ⚠️ N113：以 `?` 結尾**且長度沒有失控**才算起始問題。
    #    200 字的說明句最後加一個問號不會變成起始問題。
    return len(t) <= EXEMPT_LEN and t.rstrip().endswith(("?", "？"))
CAP_LEN, SVG_LEN = 70, 52              # 超過這個長度多半在解釋，不是在標註


def is_commentary(t, limit):
    """兩個判準取聯集：① 出現推論連接詞　② 長度超標且不是符號定義。

    ⚠️ 這是**代理指標，不是判準**：會有誤判（合法的量測條件標註也可能偏長）。
    看到 WARN 要自己用那條判準複驗一次：遮掉它，圖表還讀不讀得懂？

    ⚠️ 單靠連接詞會漏——例如
    「The 3 dropped by criterion 2 use wet-lab chemistry we cannot run」
    一個連接詞都沒有，純粹是一句長的說明。**標註很短，句子很長。**
    """
    t = str(t or "").strip()
    if not t:
        return False
    if is_legend(t) or is_question(t):
        return False
    return bool(INFER.search(t)) or len(t) > limit


# ── N106：缺欄位 = 靜默關掉一到四條檢查 ──────────────────────────────────
# ⚠️ 這是本檔最常見的單向縫：`if not X: return`。刪掉一個鍵就關掉一整組檢查，
#    而**沒有任何地方要求那個鍵存在**。
# ⛔ 裁決（2026-09-05，「先寬」）：**不改成必填**。必填會擋住合法的極簡頁
#    （backup 的清單頁本來就沒有 depth、表格頁本來就沒有 body.src）。
#    改成「缺鍵就說出這一頁有幾條檢查被跳過」——⭐ 比必填溫和，而且把病灶顯形：
#    看得見才有人會問「這頁為什麼可以不填」。
# ⚠️ 反方向（N56）：這條**本身擋不住任何東西**，它是計量不是門檻，所以它的失效
#    是「WARN 太多沒人看」。擋它的做法是只對**真的會關掉檢查**的組合發 ——
#    型態上本來就用不到那個鍵的頁（表格頁沒有 body.src、封面沒有 depth）不發。
SKIPPED_BY = {
    "depth":       ("ⓐⓑⓒ 三選一 / extra_sources 必填 / VAGUE / check_example", 4),
    "composition": ("check_renderer_used / check_manifest / check_depth 的 is_described", 3),
    "body.src":    ("真名 / 程式識別字 / 用途分類 / 圖上數字溯源", 4),
}
FIGURE_TYPES = {"diagram", "example", "figure"}   # 內容主體是圖的版型


def check_skipped(sid, s):
    miss = []
    if is_struct(s) and not s.get("backup"):
        return                                   # 結構頁本來就不進逐頁內容檢查
    if not s.get("depth"):
        miss.append("depth")
    if s.get("type") in FIGURE_TYPES:
        b = s.get("body") or {}
        if not (s.get("composition") or {}).get("comp"):
            miss.append("composition")
        if not (b.get("src") or b.get("svg")):
            miss.append("body.src")
    if not miss:
        return
    n = sum(SKIPPED_BY[k][1] for k in miss)
    lines = "\n".join(f"           · 缺 {k} → 跳過 {SKIPPED_BY[k][1]} 條："
                      f"{SKIPPED_BY[k][0]}" for k in miss)
    warn(sid, f"這一頁有 {n} 條檢查被跳過，因為缺了 {len(miss)} 個鍵：\n" + lines + "\n"
              f"           ⚠️ 這不是「不合格」——極簡頁與 backup 頁本來就可以不填。\n"
              f"           但要知道：**這一頁沒有被那幾條檢查看過**。真的不該填就當它是紀錄；"
              f"是漏填就補上。")


# ── N107：backup: true 一個布林值一次關掉五條檢查 ────────────────────────
# 關掉的是：shoot.py 的密度、真名、程式識別字、承接／IO 鏈、頁數預算。
# ⚠️ 而全份**沒有任何地方限制 backup 頁的數量或比例** —— builder 被密度或真名擋
#    回來時，最省力的解法就是在那幾頁加 `"backup": true`。
# ⛔ 裁決（2026-09-05，「先寬」）：
#    · 數量／比例超標 → **WARN**（backup 多的一週是存在的：講不完的東西留著備問）。
#    · backup 比主線還多 → **ERROR**。那不是「留著備問」，那是把主線改標成備用頁；
#      這就是「明顯作弊的形狀」那一格。
#    · 「backup 頁要不要至少受一條內容檢查管」→ 要：上面的 check_skipped() 對
#      backup 頁照跑（唯一對 backup 出聲的內容檢查）。
# ⚠️ 反方向（N56）：限量會把 agent 推去**刪掉 backup 頁**（少講一件事比被 WARN 便宜）。
#    擋它的是 plan.dropped 的逐項對帳 —— 拿掉的東西仍然要寫「去處 ＋ 理由」，
#    不能默默消失。兩個方向都有東西在守。
MAX_BACKUP, MAX_BACKUP_RATIO = 4, 0.4


def check_backup(slides):
    bk = [s for s in slides if s.get("backup")]
    if not bk:
        return
    main = [s for s in slides if not is_struct(s)]
    ids = "、".join(str(s.get("id") or "?") for s in bk[:8])
    if len(bk) > len(main):
        err("deck", f"backup 有 {len(bk)} 頁，比主線的 {len(main)} 頁還多（{ids}）—— "
                    f"backup 一個布林值就關掉密度、真名、識別字、承接鏈、頁數預算**五條檢查**。\n"
                    f"           ⛔ 這不是「留著備問」，是把主線改標成備用頁。"
                    f"該講的就放進主線並讓它受檢；真的不講就寫進 plan.dropped")
    elif len(bk) > MAX_BACKUP or (main and len(bk) > len(main) * MAX_BACKUP_RATIO):
        warn("deck", f"backup {len(bk)} 頁 vs 主線 {len(main)} 頁（{ids}）—— "
                     f"超過 {MAX_BACKUP} 頁或主線的 {int(MAX_BACKUP_RATIO * 100)}%。\n"
                     f"           backup 頁不受密度、真名、識別字、承接鏈、頁數預算檢查；"
                     f"被擋回來時把頁標成 backup 是最省力的繞法。逐頁問一次："
                     f"這頁是**留著備問**，還是**過不了檢查**？")


def check_caption(sid, s):
    """caption／sub 只能寫「這張圖表怎麼讀」，不能寫「這張圖表說明了什麼」。

    合法：符號定義（O＝可沿用）、欄位說明、量測條件（相同區間、相同算法）
    不合法：推論、對比說明、結論 —— 那是講者要說的話

    典型的違規長相（都該由講者口頭帶，不上投影片）：
      「被第 2 條判準刷掉的那 3 個，用的是我們做不到的方法…」
      「參數設定——與前一組完全相同，兩組才可比」
    版面上的注意力要留給重點本身。
    """
    cands = [("sub", s.get("sub"))]
    b = s.get("body") or {}
    cands.append(("圖說", b.get("caption")))
    for t in (b.get("tables") or []):
        cands.append(("表格 caption", t.get("caption")))
    for name, txt in cands:
        if is_commentary(txt, CAP_LEN):
            warn(sid, f"{name} 像是講者的話，不是圖表的標註：「{str(txt)[:56]}」\n"
                      f"           判準：遮掉它，圖表本身還讀不讀得懂？讀得懂就搬進 notes")


def check_takeaway(sid, s):
    """底部結論條一律不使用 —— 結論由講者口頭講。

    標註與結論句反覆被要求拿掉，所以定成一律不放。
    結論寫進 notes 的「【口頭結論】」，進 pptx 備忘稿，不上投影片。
    """
    if s.get("takeaway"):
        err(sid, "投影片上不放結論句 —— 把它移到 notes 的「【口頭結論】」，由講者口頭講")


def check_notes_substance(sid, s):
    """`notes` 不能只有一句抽象的【口頭結論】—— 那是講者唯一拿得到的口頭稿。

    ⚠️ 這條在防的是實測到的失效（2026-09-09 追查）：builder 規格要求四類東西進
    `notes`（結論句、日誌的 `details`、推論、答不出來的材料），但只有【口頭結論】
    寫成了固定句型，其餘三類是「搬進 notes」這種被動說法，**沒有格式也沒有檢查**。
    乾淨產出實測：七頁的 `notes` 全部恰好一句【口頭結論】，平均 28 字元，
    使用者上台前得自己補 8,677 字才講得動。

    判準不驗字數本身，驗**有沒有具體的東西**：除了【口頭結論】那一句以外，
    還要有錨點（數字／工具名／檔名／樣本名，用與標題同一套 ANCHOR）。
    一律 WARN —— 「這頁真的只有一句話可講」是可能的，但要有人說出來。
    """
    if is_struct(s) or s.get("backup"):
        return
    notes = str(s.get("notes") or "").strip()
    if not notes:
        warn(sid, "這一頁沒有 notes —— 投影片上不放結論句（check_takeaway 會擋），"
                  "所以講者的口頭稿只剩 notes。至少要有「【口頭結論】」那一句")
        return
    # 只有一段【…】時，扣掉那個標籤之後剩下的就是全部內容
    if notes.count("【") <= 1:
        body = re.sub(r"^【[^】]*】", "", notes).strip()
        if len(body) < 60 or not ANCHOR.search(body):
            warn(sid, f"notes 只有一句抽象結論（{len(notes)} 字，無具體錨點）——\n"
                      f"           講者上台只拿得到這一句。把日誌的 `details`"
                      f"（materials.md 的「細節：」）、被版面砍掉的數字、"
                      f"「為什麼這樣做」搬進來，一頁至少要講得滿一分鐘")


def check_title(sid, s):
    """標題要說出這頁在講什麼，不是給它一個文學性的名字。

    反例：「我們的位置」「順序錯了」「一個上游問題」——都看不出這頁在說什麼。
    機械代理：具體標題幾乎一定含一個錨點（數字／樣本名／工具名／檔名）。
    """
    t = (s.get("title") or "").strip()
    if s.get("type") in ("cover", "agenda", "thread-intro"):
        return
    # ⚠️ 後補（N110）：原本 `not t` 也走 return —— **空標題等於把這條檢查關掉**，
    #    而且 check_capacity 的 `if s.get(f)` 對空字串也是 falsy → 一起跳過。
    #    「缺欄位就 return」在這裡的代價是整頁沒有標題卻零報。
    if not t:
        warn(sid, "這一頁沒有標題 —— 空標題會讓標題的錨點檢查與字數上限**兩條一起跳過**；"
                  "真的不需要標題（例如整頁一張圖）就把理由寫進 notes")
        return
    if not ANCHOR.search(t):
        warn(sid, f"標題沒有具體錨點（數字／樣本名／工具名），可能太抽象：「{t}」\n"
                  f"           寫「做了什麼／發現了什麼」，不要給它一個文學性的名字")


def check_body_kind(sid, s):
    """主體優先序：圖解 > 表格 > 文字。用文字版型要說得出為什麼。

    教授明確表示：用圖和數據講解比較好懂，文字描述很難理解。
    所以文字不是預設，是**下下策**，要在 why_text 寫出「為什麼這件事沒有圖或表可放」。
    """
    st = s.get("type")
    if st in TEXT_ONLY and not s.get("why_text"):
        err(sid, f"版型 {st} 以文字為主體，但沒有 why_text —— "
                 f"請先想能不能改成 diagram（.svg）或 table；真的不行才寫理由留下")
    if st == "issues" and not s.get("backup"):
        warn(sid, "主線上出現待決／下一步頁 —— 除非對講解有幫助，"
                   "否則把這週的產出講好就夠了")


# ── 結構頁的 body 形狀（後補，FINDINGS N30）──────────────────────────────────
# ⚠️ 這些形狀**只寫在 render_deck.py 的 builder 裡**（`b_cover`／`b_agenda`／
#    `b_thread_intro`），deck_schema.md 與 slide_types.md 都沒寫，而結構頁又不進
#    逐頁的內容檢查 → 一張沒有 `body` 的 thread-intro **通過 check_deck 全部檢查**，
#    卻讓 render 直接崩：`b_thread_intro()` → `inl(None)` → `html.escape`
#    `AttributeError: 'NoneType' object has no attribute 'replace'`，
#    訊息裡看不出是哪一頁哪一欄。
# 這裡就是把那份隱性契約寫成檢查。哪些欄位「必填」的判準只有一個：
# **builder 沒有用 if 保護它** —— 缺了就會 inl(None) 崩掉。
# （`b_thread_intro` 的 `sub`、`b_agenda` 的 `d`／`n` 有保護 → 選填。）
# ⛔ 這份清單要跟著 render_deck.py 走：那邊改了 builder，這裡要一起改。
STRUCT_BODY_REQ = {
    "cover": ("kicker", "title", "range"),        # b_cover：三個都沒有保護
    "thread-intro": ("label", "title"),           # b_thread_intro：sub 有保護，選填
}


def check_struct_body(sid, s):
    st = s.get("type")
    if st not in ("cover", "agenda", "thread-intro"):
        return
    b = s.get("body")
    if not isinstance(b, dict) or not b:
        err(sid, f"版型 {st} 沒有 body —— 這頁通得過檢查卻會讓 render_deck.py 當場崩"
                 f"（inl(None) → html.escape 的 AttributeError，而且看不出是哪一頁）。\n"
                 f"           形狀：cover 要 {{kicker,title,range}}、"
                 f"thread-intro 要 {{label,title[,sub]}}、agenda 要 items[{{t[,n,d]}}]")
        return
    if st == "agenda":
        items = b.get("items")
        if not items:
            err(sid, "agenda 的 body 沒有 items —— 議程頁至少要列一項"
                     "（items[].t 是那一行的字；n／d 選填）")
            return
        for i, x in enumerate(items, 1):
            if not isinstance(x, dict) or not str(x.get("t") or "").strip():
                err(sid, f"agenda 第 {i} 項缺 t（那一行要顯示的字）—— render 會 inl(None) 崩掉")
        return
    for k in STRUCT_BODY_REQ.get(st, ()):
        if not str(b.get(k) or "").strip():
            err(sid, f"版型 {st} 的 body 缺 {k} —— render_deck.py 對它沒有防護，"
                     f"缺了會直接崩（必填：{'、'.join(STRUCT_BODY_REQ[st])}）")


# ── 名字的粒度：兩個方向（§1d-0 的機械化）────────────────────────────────
# 使用者原話（要真名）：「要提到我們真實實作時，有用到的名詞，而不是用代替表示而已
# (e.g. 不要講:安裝skills，要講:安裝mattpocock-skills)，簡報要真的提到我們有定義的
# 單字，才不會講得太high-level，要講到真的實作的部分」。
# 使用者原話（管粒度，⚠️ 是上一條的**過度修正、不是推翻**）：「我其實不是希望完全到
# 那麼詳細的程式碼用詞(e.g. W_PARTICIPATION 這個太細了)，可以換成文字解釋，只是希望
# 最接近主題的那幾個名詞要出現(extract_transcript.py, daily-log, .html, .json,
# mattpocock-skills)，解釋的部分，可以用比較貼近一般人可以理解的方式來解釋」。
#
# ⭐ **判準只有一句**（§1d-0 唯一定義處，⛔ 本檔不複製那張表）：
#    **「聽眾可以自己打開這個東西看嗎？」**
#      ✅ 打得開（檔案／目錄／副檔名／repo／skill／subagent／腳本名、layer1-3）→ 用真名
#      ⛔ 打不開、要讀原始碼才看得到（W_PARTICIPATION、items[]）→ 換白話
#      ⛔ 打不開、因為它根本不是一個東西（「呈現層」「選材」）→ 往上換成對應真名
#    ⭐ 分工：**東西的名字用真名，動作與判準的解釋用白話。**
# ⚠️ 舊的問法「指得出它被定義的那一行嗎」**已從規格整段刪除** —— 它把人推向最細的
#    識別字（一個程式常數當然指得出定義行，所以它「最合格」），正是回饋④要修的東西。
#    ⛔ 不要把它寫回來（已知坑 #13：同一事實兩處分岔）。
#
# 這一段實作兩條方向相反的 WARN：
#   · check_real_names   —— 太上層（整頁一個打得開的真名都沒有）
#   · check_code_idents  —— 太下層（版面上出現聽眾打不開的程式識別字）
#
# 機械判準（⛔ 不用黑名單，也不用白名單 —— 兩者都要有人維護、必定過期）：
# 一則名字只要**任一個詞**帶下列任一個「識別字特徵」，就算真名
# —— ⚠️ 但**先把程式識別字（CODE_IDENT）挖掉再判**：`W_PARTICIPATION` 帶著
#    `[A-Za-z]_[A-Za-z]` 與 `\b[A-Z]{2,}\b` 兩個特徵，卻是聽眾打不開的東西，
#    拿它當「這頁有真名」的證據會讓整頁塞滿程式常數的版面拿到滿分（見下方 check_code_idents）：
#   snake_case／kebab-case／點分（副檔名、模組路徑）／斜線路徑／駝峰／全大寫縮寫／
#   字母與數字相黏（layer1、B3、v2）／數字—數字（08-28 這種具體日期）／反引號標記／CJK。
# 另外，登記在 `plan.terms.objects` 的具名產物一律算真名（`daily log`、`page plan`
# 這種「我們定義的中文概念名」沒有任何拼寫特徵，只能靠登記表認），⚠️ 但**不硬性要求**
# 圖上的名字都要登記 —— 很多名字不是物品（步驟名、欄位名、門檻名）。
#
# ⚠️ 為什麼是**整頁**判、而且是 WARN：
#   ① 逐則判必然一堆偽陽性（`Title before the rules` 這種階段標籤本來就沒有識別字），
#      逐則報會讓整條檢查被當雜訊忽略 —— 這個 repo 已經被這種形狀打過（annot 的 WARN）。
#   ② 真正要抓的形狀是「**整頁一個真名都沒有**」：B1/B3 的
#      `Pick what to say`／`Plan the pages`／`Build the slides` 就是把 layer1／layer2／layer3、
#      thread_finder／slide_planner／slide_builder 全部換成功能描述。
#   ③ ERROR 會擋死 `Record layer`／`daily log` 這種合法但沒有拼寫特徵的頁 → 一律 WARN，
#      讓 builder 看見並自己判斷。
IDENT_TOKEN = re.compile(
    r"[A-Za-z]_[A-Za-z]"                 # slide_planner、check_deck
    r"|[a-z]-[a-z]"                      # mattpocock-skills、daily-log
    r"|[A-Za-z]\.[A-Za-z0-9]"            # deck.json、paths.py、a.b
    r"|\.[a-z]{2,5}\b"                   # .json、.html、.svg（單獨出現的副檔名）
    r"|[A-Za-z]/[A-Za-z]"                # _work/4_slides
    r"|[a-z][A-Z]"                       # camelCase
    r"|\b[A-Z]{2,}\b"                    # JSON、SVG、KB
    r"|[A-Za-z]\d|\d[A-Za-z]"            # layer1、B3、v2、3x
    r"|\d-\d"                            # 08-28（具體日期／區間也是錨點）
    r"|`[^`]+`"                          # 反引號標起來的識別字
    r"|[一-鿿]"                  # 中文名詞
)


# ── 反方向：聽眾打不開的程式識別字（回饋④的機械化）─────────────────────
# ⚠️ 上面那條真名檢查**對粒度是盲的**：`W_PARTICIPATION` 同時命中
# `[A-Za-z]_[A-Za-z]` 與 `\b[A-Z]{2,}\b`，`items[]`／`NOT_HUMAN`／`MAX_TITLE` 也全部通過
# —— 於是**整頁塞滿程式常數，在真名檢查下是滿分**。它只擋得到太上層，擋不到太下層。
#
# 只認兩種**形狀上無歧義**的程式識別字（⛔ 刻意不碰小寫 snake_case：
# `extract_transcript`／`check_readability` 與 `user_msgs`／`why_demoted` 長得一模一樣，
# 一個打得開、一個打不開，光看拼寫分不出來 —— 那一層留給人判，見 §1d-0）：
#   ① 全大寫底線常數  W_PARTICIPATION、KIND_BONUS、MAX_TITLE、NOT_HUMAN
#   ② 裸欄位名        items[]、record[]
#   ③ 全大寫單詞（≥4 字母，無底線） GENERIC、DECISION —— ⚠️ 扣掉「檔案格式名」，
#      JSON／HTML／PPTX 這種聽眾打得開的東西不算識別字（同一份 KNOWN_EXT，⛔ 不另抄一份）。
#      3 字母以下不判（UTC、CSV、ID 多半是一般英文縮寫，鑑別力不足）。
#
# **例外（不報）**：那個詞出現在**檔名／路徑脈絡**時，它就是一個打得開的東西：
#   `SKILL.md`／`FINDINGS.md`（後面接已知副檔名）、`docs/SNV_DETECT`／`SNV_DETECT/x`
#   （前後相鄰 `/`）、`.data`（前面相鄰 `.`）。
#   ⚠️ `items[].title` **不算例外** —— `.title` 不在 KNOWN_EXT 裡，它是 JSON 欄位不是檔名。
#
# ⚠️ **一定是 WARN 不是 ERROR**：§1d-0 明訂有例外 ——
# **整頁的重點就是那個東西本身**時（一整頁在講「這個門檻是怎麼定出來的」），
# 那個常數就是那頁的主詞，可以放上版面。機器分不出「主詞」與「順便提到」，
# 所以只出聲、不擋；builder 自己用那句話判一次。
KNOWN_EXT = ("py", "sh", "json", "jsonl", "md", "html", "svg", "css", "txt",
             "yml", "yaml", "toml", "csv", "tsv", "pptx", "png", "js")
CODE_IDENT = re.compile(
    r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b"     # ① W_PARTICIPATION、KIND_BONUS、MAX_TITLE
    r"|\b[A-Za-z_][A-Za-z0-9_]*\[\]"     # ② items[]、record[]
    r"|\b[A-Z][A-Z0-9]{3,}\b"            # ③ GENERIC（≥4 字母的全大寫單詞）
)
_EXT_AFTER = re.compile(r"^\.(?:%s)\b" % "|".join(KNOWN_EXT), re.I)


def _in_path_context(t, i, j):
    """這個詞是不是長在檔名／路徑脈絡裡（`SKILL.md`、`docs/SNV_DETECT`、`.data`）。"""
    # ⛔ `before in "/."` 不能少了 `before and` —— 空字串是任何字串的子字串，
    #    於是**每一則開頭的識別字**（`W_PARTICIPATION 3 · user_msgs`、`KIND_BONUS · kind`）
    #    都被當成路徑脈絡放行。實測漏掉一半以上，正是使用者點名的那幾則。
    before = t[i - 1] if i else ""
    return (before in "/." and bool(before)) or t[j:j + 1] == "/" or bool(_EXT_AFTER.match(t[j:]))


def code_idents(t):
    """這一則文字裡，聽眾打不開的程式識別字有哪些（去重、保序）。"""
    out = []
    for m in CODE_IDENT.finditer(str(t or "")):
        w = m.group(0)
        if _in_path_context(t, m.start(), m.end()):
            continue
        if w.rstrip("[]") == "" or w.lower().strip("[]") in KNOWN_EXT:
            continue                      # JSON／HTML：那是檔案格式，聽眾打得開
        if w not in out:
            out.append(w)
    return out


def strip_code_idents(t):
    """把程式識別字挖掉，剩下的才拿去判「這頁有沒有真名」。"""
    return CODE_IDENT.sub(
        lambda m: m.group(0) if _in_path_context(t, m.start(), m.end())
        or m.group(0).lower().strip("[]") in KNOWN_EXT else " ", str(t or ""))


# ── 第三層：長得像檔名、其實是**樣板佔位符** ────────────────────────────────
# ⚠️ 上面兩條都漏了這一類。`daily/<date>.html` 過得了 check_real_names（有 `.html`
# 有 `/`），也過得了 code_idents（不是全大寫常數、不是 `x[]`）—— 而且它通過
# §1d-0 的問法「聽眾可以自己打開這個東西看嗎？」，因為**它看起來就是一個檔名**。
# 但 `<date>` 打不開：那個路徑不存在，它代表「這裡會被換成日期」。
# 使用者原話：「我不知道這是什麼意思? 這是程式碼嗎? 還是沒有渲染好」。
#
# 判準（⛔ 不用黑名單）：**這串字裡有沒有一個「等我被代換」的洞？**
#   ① 角括號佔位符  <date>、<thread>、<out>      —— 中間不含空白才算
#   ② 大括號佔位符  {date}、{}、{0}             —— f-string／format 的寫法
#   ③ 萬用字元      .data/*.json、*.md、T*      —— `*` 貼著路徑字元才算
#
# ⚠️ **SVG 裡是轉義的**（`&lt;date&gt;`），所以一定要先把實體還原再比對；
#    ⛔ 只比對原始 `<` 會整批漏掉（圖上的 label 正是主要犯案處）。
#    _svg_label_texts() 走 ElementTree 已經幫忙還原過，但 deck.json 的
#    title／表頭是生字串，兩種形式都可能出現 —— 兩邊都吃。
#
# ⛔ **不要誤報數學與箭頭**（`≥20 → 3`、`6-7 → border`、`a → b` 在圖上很常見）：
#   · `<`／`>` 只有在「無空白且成對包住一個識別字」時才算洞 —— `≥ 3`、`x > 3`、
#     `a → b` 都不成對也帶空白，不會命中。
#   · `*` 只有在**緊貼著字母／`/`／`.`／`-`／`_`** 時才算萬用字元；`3*4`（兩側都是
#     數字）是乘法，不報。
#
# ⚠️ **一定是 WARN 不是 ERROR**，與同函式其他形狀一致：§1d-0 的例外
# （整頁的主詞就是那個東西）同樣適用 —— 一頁真的在講「檔名的樣板長什麼樣」時，
# 佔位符就是那頁的主詞。機器分不出來，所以只出聲、不擋。
_ENTITIES = (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"))
PLACEHOLDER = re.compile(
    r"<[A-Za-z_][A-Za-z0-9_.\-]{0,30}>"       # ① <date>、<thread>
    r"|\{[A-Za-z0-9_.\-]{0,30}\}"             # ② {date}、{}、{0}
    r"|(?<=[A-Za-z_./\-])\*"                  # ③ .data/*.json、T*（左邊貼著非數字）
    r"|\*(?=[A-Za-z_./\-])"                   #    *.md（右邊貼著非數字）
    # ⛔ 兩側刻意都排除數字：`3*4` 是乘法不是萬用字元（實測會誤報，見上）。
)


def _unescape(t):
    """把 SVG／HTML 實體還原 —— ⛔ 少了這步，圖上的 `&lt;date&gt;` 一則都抓不到。"""
    t = str(t or "")
    for a, b in _ENTITIES:
        t = t.replace(a, b)
    return t


def placeholders(t):
    """這一則文字裡的樣板佔位符／萬用字元有哪些（去重、保序）。"""
    out = []
    for m in PLACEHOLDER.finditer(_unescape(t)):
        w = m.group(0)
        if w not in out:
            out.append(w)
    return out


def _registered_objects(terms):
    return [str(o).strip().lower() for o in (terms.get("objects") or []) if str(o).strip()]


def is_real_name(t, objects):
    """這一則名字裡，有沒有一個**聽眾打得開**的東西的真名。

    ⚠️ 先用 strip_code_idents() 把程式識別字挖掉：它們也帶識別字特徵，
    但聽眾打不開（§1d-0），⛔ 不能拿來當「這頁有真名」的證據。
    """
    t = str(t or "").strip()
    if not t:
        return False
    if IDENT_TOKEN.search(strip_code_idents(t)):
        return True
    low = re.sub(r"\s+", " ", t.lower())
    return any(o in low for o in objects)      # 登記過的具名產物（整串包含才算）


def _svg_label_texts(deck_path, s):
    """這一頁外部 .svg 上、用途是 label 的文字。回 [(文字, 是不是 lead), ...]。

    ⛔ 不重用 collect_svg_purpose()：那支會對格式錯誤發 err，這裡再叫一次會重複報。
    """
    root, _ = _svg_root(deck_path, s)
    if root is None:
        return []
    NS = "{http://www.w3.org/2000/svg}"
    out = []
    for el in root.iter():
        if el.tag not in (NS + "text", "text"):
            continue
        cls = set((el.get("class") or "").split())
        if "label" not in cls:
            continue
        t = "".join(el.itertext()).strip()
        if t:
            out.append((t, "lead" in cls))
    return out


def check_real_names(deck_path, s, sid, terms):
    """圖／表上被命名的格子，至少要有一個是**聽眾打得開**的東西的真名（§1d-0）。

    ⚠️ 這條只管「太上層」那一邊（整頁全是功能描述／類別詞）。
    「太下層」（程式識別字）由 check_code_idents 管 —— 兩條方向相反、同一個判準。
    """
    objects = _registered_objects(terms)
    b = s.get("body") or {}
    cand = []                                   # [(來源, 文字)]
    if s.get("title"):
        cand.append(("標題", s["title"]))
    lead = [t for t, is_lead in _svg_label_texts(deck_path, s) if is_lead]
    cand += [("圖上的 label lead", t) for t in lead]
    for t in _tables_of(b):
        cand += [("表頭", c) for c in (t.get("columns") or []) if c]
    if not cand:
        return
    good = [(w, t) for w, t in cand if is_real_name(t, objects)]
    if good:
        return
    bad = "；".join(f"{w}「{str(t)[:38]}」" for w, t in cand[:6])
    warn(sid, "這一頁被命名的格子裡，**一個聽眾打得開的東西的真名都沒有** —— "
              "全部是功能描述。\n"
              f"           目前的名字：{bad}\n"
              "           判準（§1d-0）：**聽眾可以自己打開這個東西看嗎？** "
              "打得開的長相（layer1／slide_planner／mattpocock-skills／"
              "deck.json／.html／08-28）或登記在 plan.terms.objects 的具名產物"
              f"（目前登記：{'、'.join(objects) or '（空）'}）。\n"
              "           ⚠️ 這是 WARN 不是 ERROR：`Record layer` 這種我們定義的概念名沒有拼寫特徵，"
              "會被誤判 —— 請自己判斷，該換名字就換（使用者原話：「不要講:安裝skills，要講:安裝mattpocock-skills」）。")


def check_code_idents(deck_path, s, sid, terms):
    """版面上出現聽眾打不開的東西 → WARN（§1d-0 的「太下層」那一邊）。

    兩種形狀，各發各的 WARN（正解不一樣，⛔ 不要合成一則）：
      · 程式識別字 `W_PARTICIPATION`／`items[]` → 正解是**換成白話**
      · 樣板佔位符 `daily/<date>.html`／`.data/*.json` → 正解是
        **給一個具體例子**或**只留看得懂的部分**（§1d-0 第三層）

    範圍與 check_real_names 對稱、再加上圖上非 lead 的 label
    （`W_PARTICIPATION 3 · user_msgs` 這種正是寫在一般 label 裡的）：
    `title`／圖上的 `label`（含 `label lead`）／表頭。
    """
    b = s.get("body") or {}
    cand = []
    if s.get("title"):
        cand.append(("標題", s["title"]))
    cand += [("圖上的 label", t) for t, _ in _svg_label_texts(deck_path, s)]
    for t in _tables_of(b):
        cand += [("表頭", c) for c in (t.get("columns") or []) if c]
    # ── 第三層：樣板佔位符（`daily/<date>.html`）──────────────────
    # ⛔ 一定要在下面 `if not hits: return` **之前**算完並發出 ——
    #    這四張圖上一個程式常數都沒有，跟著提早 return 就整批漏掉。
    ph = []
    for w, t in cand:
        for pl in placeholders(t):
            ph.append((w, pl, _unescape(t)))
    if ph:
        pset = []
        for _, pl, _t in ph:
            if pl not in pset:
                pset.append(pl)
        plines = "\n".join(f"           · {w}「{t[:44]}」→ {pl}" for w, pl, t in ph[:8])
        warn(sid, f"版面上有 {len(ph)} 則**樣板佔位符／萬用字元**"
                  f"（{'、'.join(pset[:8])}{'…' if len(pset) > 8 else ''}）—— "
                  f"它長得像檔名，但那個路徑**打不開**（§1d-0 第三層）。\n"
                  f"           判準：**這串字裡有沒有一個「等我被代換」的洞？** "
                  f"有洞就不是名字，是程式寫法，聽眾會問「這是程式碼嗎」：\n"
                  + plines + ("\n           …" if len(ph) > 8 else "") + "\n"
                  f"           兩個正解 —— "
                  f"**① 給一個具體的例子**（`daily/<date>.html` → `daily/2026-08-28.html`）；"
                  f"**② 只留看得懂的部分**（→ `daily`、`.html`、`.md`）。\n"
                  f"           使用者原話：「我不知道這是什麼意思? 這是程式碼嗎? 還是沒有渲染好…"
                  f"真正需要出現的就只有 daily、.html、.md」\n"
                  f"           ⚠️ 這是 WARN 不是 ERROR：整頁的主詞就是「檔名的樣板長什麼樣」時，"
                  f"佔位符可以留；⛔「順便提到」不算。")

    hits = []
    for w, t in cand:
        for ident in code_idents(t):
            hits.append((w, ident, str(t)))
    if not hits:
        return
    idents = []
    for _, ident, _t in hits:
        if ident not in idents:
            idents.append(ident)
    lines = "\n".join(f"           · {w}「{t[:44]}」→ {ident}" for w, ident, t in hits[:8])
    warn(sid, f"版面上有 {len(hits)} 則**聽眾打不開的程式識別字**"
              f"（{'、'.join(idents[:8])}{'…' if len(idents) > 8 else ''}）—— "
              f"要讀原始碼才看得到的東西，換成白話（§1d-0）。\n"
              f"           判準：**聽眾可以自己打開這個東西看嗎？** "
              f"打不開就講它在幹嘛，不講它叫什麼\n"
              f"           （`W_PARTICIPATION 3 · user_msgs` → "
              f"「參與度 3 分：看使用者發了幾則訊息」；⭐ 東西的名字用真名，"
              f"動作與判準的解釋用白話）：\n"
              + lines + ("\n           …" if len(hits) > 8 else "") + "\n"
              f"           ⚠️ 這是 WARN 不是 ERROR：**整頁的重點就是那個東西本身**時"
              f"（例如一整頁在講這個門檻是怎麼定出來的），那個常數就是那頁的主詞，可以留；"
              f"⛔「順便提到」不算。")


def check_example(sid, s, example_first=False):
    """例子優先的機制契約：例子留在**規劃欄位** `example`，呈現走全寬的 type=example。

    ⚠️ `example` 這個規劃欄位（kind/before/operation/after/sources）**保留** ——
    它是 mechanism 頁的可追案例證據，是規劃紀錄不是視覺；被拿掉的只有
    `body.aside`（黃底右欄）。
    """
    # 以 plan.example_first 啟用，讓既有、已交付的歷史週報仍可被檢查。
    # 新版 layer2 範本會一律寫 true，故新產物沒有豁免空間。
    if not example_first or s.get("depth") != "mechanism" or s.get("example_exception"):
        return
    ex = s.get("example") or {}
    missing = [k for k in ("kind", "before", "operation", "after", "sources") if not ex.get(k)]
    if missing:
        err(sid, "depth=mechanism 缺 example." + ",".join(missing) +
            " —— 先用一個案例跑規則，再決定怎麼講；不得直接畫摘要。")
    elif ex.get("kind") not in ("observed", "constructed"):
        err(sid, "example.kind 要是 observed 或 constructed")
    elif ex.get("kind") == "constructed" and not ex.get("disclosure"):
        err(sid, "constructed example 缺 disclosure —— 示意例子必須標明，不得偽裝成實測結果")
    if s.get("type") != "example":
        err(sid, "mechanism 頁必須使用 type=example 的全寬版型；"
            "若確實不適用，填 example_exception 並說明理由。")
    b = s.get("body") or {}
    if s.get("type") == "example":
        if not b.get("src"):
            err(sid, "example 主圖缺 body.src（例子必須可視化，不可只寫文字）")
        if b.get("aside"):
            # ⛔ 不是「忽略多餘欄位」：帶著 aside 的頁，它的規則與邊界**還在右欄裡**，
            #    而右欄已經不會被渲染 —— 靜默放行等於把 mechanism 頁要求的那條規則
            #    從版面上刪掉，且沒有人會發現。
            err(sid, "example 版型已改成主圖全寬單欄，body.aside 不再渲染 —— "
                     "把 aside.rule／aside.boundary 的內容**畫進主圖的 SVG 裡**"
                     "（depth=mechanism 明訂這頁必須看得見一條具體規則），再把 body.aside 刪掉。\n"
                     f"           這一頁還留著的內容：rule=「{str((b.get('aside') or {}).get('rule'))[:40]}」"
                     f"／boundary=「{str((b.get('aside') or {}).get('boundary'))[:40]}」")


# ── 深度（depth）─────────────────────────────────────────────────────────────
# 空洞的頁面共同特徵是**只有動詞沒有規則**。
# 「一條具體規則」的機械代理：出現比較／門檻／算式符號，或本身就是一張判準表。
# ⚠️ token 要**具體**。第一版放了 `\bper\b`／`\bvs\b`／數字範圍，
# 結果標題「Overlap at each of the 3 dilution levels, per feature」就命中，
# 空洞的頁反而過關。寬鬆的 token 等於沒有這條檢查。
RELATIONS = {"sequence","transform","partition","narrowing",
             "compare","containment","correspondence","distribution"}
RULE_TOKEN = re.compile(
    r"[≥≤＝±×÷]|[<>=]\s*\d|\d\s*[%‰]|\d+\s*[:：/]\s*\d+|"
    r"閾值|門檻|判準|規則|公式|條件|threshold|criteri|formula|cutoff|\brule\b")
VAGUE = re.compile(
    r"^(?:我們)?(?:整理|篩選|驗證|優化|改善|完成|建立|處理|分析|確認)了?[^，。；]*$")
DEPTHS = {"overview", "mechanism", "detail"}


def _real_table(s):
    """算得上一張判準表的：**≥2 欄且 ≥2 列**（N111 ①）。

    ⛔ `{"columns":["Step"],"rows":[["Run daily-log"],["Run weekly-deck"]]}`
    是一串清單，不是判準表 —— 它以前足以讓整條 mechanism 檢查通過。
    """
    b = s.get("body") or {}
    ts = (b.get("tables") or []) or ([b] if b.get("columns") else [])
    return any(isinstance(t, dict) and len(t.get("columns") or []) >= 2
               and len(t.get("rows") or []) >= 2 for t in ts)


def check_depth(sid, s, deck_path=None):
    """`mechanism` 頁要看得到規則本身，不是只有動詞。

    驗收（寫給人的那一句，機械擋不了、但 layout_reviewer 要問）：
      **聽眾照這頁講的，能不能自己重做一次？不能的話缺哪一步？**

    這裡只擋機械代理得到的那一半：一張表、或文字／圖裡有比較／門檻／算式符號。
    兩者皆無的 mechanism 頁，幾乎一定是空洞的。
    """
    d = s.get("depth")
    if d is None:
        return
    if d not in DEPTHS:
        err(sid, f"depth「{d}」不合法（overview / mechanism / detail）")
        return
    if d != "mechanism":
        return
    # ⚠️ 後補（N111 ①）：`has_table` 原本是「type==table 或 body.tables 非空」——
    #    **一張 1 欄 2 列的表就足以讓整條 mechanism 檢查通過**，而版面上一條規則都沒有。
    #    「任一命中就過」的門檻，最弱的那一項就是它的實際門檻（N51 同型）。
    #    ⛔ 收緊的只有「什麼算一張表」：≥2 欄且 ≥2 列才算 —— 判準表本來就至少是
    #    「情況 → 怎麼辦」兩欄。⚠️ 反方向：這會讓「真的只有兩列的對照表」被要求
    #    改用另外兩種形狀之一（畫進圖裡、或寫出門檻符號），那正是這條檢查要的東西。
    has_table = _real_table(s)
    # ⚠️ 後修：規則多半畫在 SVG 上，而 texts() 只給 slide dict 裡的字串
    # （`src` 被跳過）→ 圖解型的 mechanism 頁一律誤判成「看不到規則」。
    # 實測：8 頁裡 7 頁誤報。圖不是免檢區，也不該是「檢查看不到區」。
    blob = " ".join(list(texts(s)))
    if deck_path:
        blob += " " + svg_text_only(deck_path, s)
    # ⚠️ 後修：原本只認「算式／門檻」一種形狀，但判準已重定成三種
    # （subagent-slide-planner.md §1）：ⓐ機制描述／ⓑ決定＋依據／ⓒ限制下做得到什麼。
    # ⓐ 型的頁（「這支程式抓哪些欄位」「這四步只有第一步由模型做」）天生沒有門檻符號，
    # 一律被誤判。實測 8 頁裡 5 頁誤報。
    # ⓐ 的機械代理：圖上有一組**具名元件**與它們之間的關係（layer2 的守門提問已答），
    # 而不是只有動詞。真正空洞的頁在這裡仍然擋得住 —— 它們畫不出四個以上的具名元件。
    comp = s.get("composition") or {}
    named = svg_text_count(deck_path, s) if deck_path else 0
    is_described = bool(comp.get("gate")) and comp.get("relation") in RELATIONS and named >= 4
    hits = [("一張判準表", has_table), ("算式／門檻符號", bool(RULE_TOKEN.search(blob))),
            ("圖上的具名元件與關係", is_described)]
    if sum(1 for _, ok in hits if ok) == 1:
        # ⭐ N111：三選一改不成「三選二」（合法的 ⓐ 型頁天生沒有門檻符號，
        #    合法的 ⓑ 型頁可能只有一行算式），但「只靠一項撐住」值得被看一次。
        #    ⚠️ 這是 WARN 不是 ERROR：改成二選才過會誤殺 N26／實測那批 ⓐ 型頁。
        warn(sid, f"depth=mechanism 的三種形狀只命中一項"
                  f"（{[n for n, ok in hits if ok][0]}）—— "
                  f"門檻是「任一命中就過」，所以**最弱的那一項就是實際門檻**。\n"
                  f"           複驗一次那句人的判準：聽眾照這頁講的，能不能自己重做一次？")
    if not has_table and not RULE_TOKEN.search(blob) and not is_described:
        err(sid, "depth=mechanism 但這頁看不到機制——三種合法形狀一個都沒有：\n"
                 "           ⓐ 機制描述（圖上要有一組具名元件與它們的關係，守門提問要答過）\n"
                 "           ⓑ 決定 ＋ 它的依據（算式／門檻／判準表）\n"
                 "           ⓒ 限制下做得到什麼\n"
                 "           只寫「我們整理了／篩選了／驗證了」是空洞。\n"
                 "           真的沒有機制可講，就把 depth 降成 overview 並寫明理由")
    pt = (s.get("point") or "").strip()
    if VAGUE.match(pt):
        warn(sid, f"point 只有動詞沒有對象與規則：「{pt}」")
    # ── D：機制頁必須讀過原始檔（後補）──────────────────────
    # ⚠️ **日報是壓縮過的** —— 保留結論、丟掉機制。所以「這支程式抓哪些欄位」
    #    這種頁只讀 materials.md 的摘要一定寫不出來，寫出來的會是動作詞。
    #    首次實跑實測：planner 寫「查對照表」「跑一支檢查」，
    #    回饋是看不懂、整頁沒有提到任何機制。
    # `SKILL.md` 早就寫著「要講機制就去讀 artifacts 指到的檔」，但**沒有任何東西
    # 在執行**（extra_sources 原本只是給數字溯源開後門）。這條就是那個執行。
    # ⚠️ 只擋 mechanism 頁；overview 頁（盤點、清單）用日誌就夠。
    # ⛔ 讀的是**日誌自己指出來的檔**（materials.md 最後一節列著），不是亂翻 repo。
    if not s.get("extra_sources"):
        err(sid, "depth=mechanism 但沒有 extra_sources —— "
                 "**機制頁只讀日誌摘要寫不出來**。\n"
                 "           日報保留結論、丟掉機制；去讀 artifacts 指到的原始檔"
                 "（materials.md 最後一節列著），把路徑填進 extra_sources。\n"
                 "           真的沒有原始檔可讀，就把 depth 降成 overview 並寫明理由")


# ── I/O 物品鏈 ───────────────────────────────────────────────────────────────
def check_io_chain(slides, terms):
    """同一條主線內，第 i 頁的 input 逐字等於第 i-1 頁的 output。

    這是「上一頁的產出就是下一頁的輸入」的硬版本。
    ⚠️ 只在**同一條主線內**要求 —— 換線本來就串不起來，硬接比誠實斷開更難懂。

    沒有物品的頁（鋪陳頁、結論頁）把 input／output 留空，改用 from／to 承接。
    """
    objects = {str(x).strip() for x in (terms.get("objects") or []) if str(x).strip()}
    used = set()
    if not objects:
        warn("plan", "plan.terms.objects 是空的 —— I/O 物品名沒有登記，"
                     "「同一件事只准用一個名詞」就沒有機制執行")

    last_out = {}          # thread -> (sid, output)
    for i, s in enumerate(slides, 1):
        if is_struct(s):
            continue
        sid = s.get("id") or f"S{i}"
        th = s.get("thread")
        inp, out = (s.get("input") or "").strip(), (s.get("output") or "").strip()

        for name, val in (("input", inp), ("output", out)):
            if val and objects and val not in objects:
                err(sid, f"{name} 物品「{val}」沒有登記在 plan.terms.objects —— "
                         f"先登記再用，否則同一件事會有兩個名字")

        prev = last_out.get(th)
        if inp and prev and prev[1] and inp != prev[1]:
            err(sid, f"input 接不上同主線前一頁的 output：\n"
                     f"           {prev[0]} 的 output「{prev[1]}」\n"
                     f"           {sid} 的 input  「{inp}」")
        # ⚠️ 後修（FINDINGS N23）：**沒有物品的中間頁會把鏈斷開，不是被跳過**。
        # `subagent-slide-planner.md §2a` 認可三種合法斷點，其中兩種就是
        # 「前頁沒有物品 → 這頁的 input 是新引入的原料，不必等於任何東西」與
        # 「後頁沒有物品（結論頁）→ 前頁的 output 不必被消費」。
        # 舊版把 last_out 一路留著，於是**跨過 null 的中間頁**拿下下頁的 input
        # 去比上上頁的 output —— 合法斷點反而製造 ERROR
        # （實測：B2 兩欄皆 null，B3 的 input「thread list」被拿去比 B1 的 output「slide deck」）。
        # ⛔ 記住的一律是**緊鄰的前一頁**的 output：它是空的就斷鏈重新開始。
        last_out[th] = (sid, out)
        used.update(x for x in (inp, out) if x)

    # ── N115：一個空陣列一次關掉物品鏈的兩條檢查 ─────────────
    # ⚠️ 上面所有 ERROR 都需要 val／inp／objects **非空**：
    #    `objects: []` ＋ 每頁 `input: null, output: null` → 第 7、8 兩條檢查
    #    整條關掉，全份只留一則 WARN。而**沒有任何檢查要求**「非結構頁必須有
    #    input 或 output」或「一條線至少要有 N 段鏈」。
    # ⛔ 裁決（2026-09-05，「先寬」）：
    #    · N（一條線至少幾段鏈）＝ **1**，而且只對 **4 頁以上**的線要求。
    #      理由是實測：現有的 B 線 3 頁只有 1 段鏈、A 線 5 頁 2 段，
    #      門檻訂在「4 頁以上的線至少要有一段鏈」剛好落在合法產物之外。
    #    · 「非結構頁必須有 input 或 output」→ **不做逐頁檢查**：合法斷點太常見
    #      （N23 已為此改過一次），逐頁報會製造整頁 WARN 然後被無視。
    #      改成 deck 級：整份**一段鏈都沒有**才報。
    #    · `objects` 空 → **維持 WARN，不升 ERROR**：單線、沒有物品可傳的週是存在的。
    # ⚠️ 反方向（N56）：要求鏈段數會把 planner 推去**編一條鏈**（正是上面 C 段
    #    實測到的那件事：登記 12 個、只用到 6 個）。擋它的就是 C 段的 ERROR
    #    —— 登記了沒被用到的物品一律報。兩個方向都有東西在守。
    per_thread = {}
    for s in slides:
        if is_struct(s):
            continue
        per_thread.setdefault(s.get("thread"), []).append(s)
    for th, ss in sorted(per_thread.items(), key=lambda kv: str(kv[0])):
        links = sum(1 for a_, b_ in zip(ss, ss[1:])
                    if (a_.get("output") or "").strip()
                    and (a_.get("output") or "").strip() == (b_.get("input") or "").strip())
        if len(ss) >= 4 and links == 0:
            warn("plan", f"線「{th}」有 {len(ss)} 頁但**一段物品鏈都沒有**"
                         f"（沒有任何一頁的 input 等於前一頁的 output）—— "
                         f"第 7、8 兩條檢查在這條線上完全沒有東西可驗。\n"
                         f"           「上一頁的產出就是下一頁的輸入」是這條線讀不讀得順的"
                         f"硬版本；真的每頁都沒有物品可傳，就在關卡② 說明一次")
    if not used:
        warn("plan", "整份 deck 的非結構頁 input／output **全部是空的** —— "
                     "I/O 物品鏈（第 7、8 條檢查）整組沒有東西可驗。\n"
                     "           一個空陣列（plan.terms.objects）加上一排 null "
                     "就關掉了兩條檢查，而且不影響 exit code")

    # ── C：登記了卻沒有任何頁用到的物品（後補）─────────────────
    # ⚠️ 那條物品鏈是**編出來的**。首次實跑實測：登記 12 個、實際只用到 6 個 ——
    #    planner 先想一條看起來很順的鏈，再把頁塞進去，於是一半的物品沒上場，
    #    而使用者在關卡② 讀到的是一條半虛構的鏈。
    # ⛔ 鏈只能從**實際的頁**長出來，不能反過來。
    for name in sorted(objects - used):
        err("plan", f"plan.terms.objects 登記了「{name}」但沒有任何頁用到 —— "
                    f"物品鏈是編的。只登記實際被 input／output 用到的物品；"
                    f"鏈要從頁長出來，不是先畫鏈再塞頁")


# ── 頁數預算 ─────────────────────────────────────────────────────────────────
# ⚠️ 12 → 15。原本的 12 是照舊骨架的實測上緣訂的
# （頁數歷史 6、8、11、11、8、11、6，最大 11）。但新骨架讓每條線變成
# `user_points 數 + 1 頁 result`，3 條線各 4 個重點就是 15 —— 而 user_points
# 是使用者親口指定、agent 不得增刪的，撞牆時能砍的東西已經不多。
# ⚠️ 15 同樣沒有校準依據，只是讓「使用者自己指定的量」不會被機械擋死。
# **真正的控制點在關卡①（少給幾條 user_points 或少留幾條線），不在這裡。**
MAX_MAIN, MAX_PER_THREAD = 15, 7
# B17-11：各線 outline 的定義是「把該線的 user_points 逐字列出來」，而一條線最多
# MAX_PER_THREAD 個 user_points（單線 7 頁 = 7 點）。agenda 的容量若小於它，
# 吃滿頁數的線就必然同時違反「項數 = user_points 條數」與「agenda ≤ N 項」，
# 沒有第三條路（2026-09-06 實跑撞到）。⭐ 所以由 MAX_PER_THREAD **推導**，
# ⛔ 不要各寫一個數字 —— 兩個常數對不起來正是這條坑的成因。
LIMITS["agenda"] = max(LIMITS["agenda"], MAX_PER_THREAD)
# `plan.slide_plan[].body` 的合法值 —— ⭐ 唯一定義（deck_schema.md 的 plan 區塊指路到這裡）。
SLIDE_PLAN_BODIES = (None, "diagram", "example", "table", "stats", "flow", "cols",
                     "points", "pipeline")


def check_budget(slides):
    """頁數上限。⚠️ backup 不計；鋪陳頁與 mechanism 頁不得為了湊頁數被砍。

    這條與 editorial_policy §6「頁數是加總出來的結果，不是配額」看似衝突，
    其實不同情境：那條防的是**做完才砍**（貴）；這條擋在關卡②，
    使用者看到頁數時改一列表格的成本是零。
    """
    main = [s for s in slides if not is_struct(s)]
    # ⚠️ 後補（N110）：這條檢查以前**只有上限** —— 一條線、一個 user_point 的
    #    「2 頁週報」全綠交付，關卡① 甚至印綠字。下限是 WARN 不是 ERROR：
    #    真的只有兩件事可講的一週是存在的，但那要被看見、被問一次。
    if len(main) < MIN_MAIN:
        warn("deck", f"主線只有 {len(main)} 頁（下限 {MIN_MAIN}）—— "
                     f"一條線、一個 user_point 的週報以前會全綠交付，關卡① 甚至印綠字。\n"
                     f"           真的只有這麼多可講就留著，但要在關卡① 被看見一次")
    if len(main) > MAX_MAIN:
        err("deck", f"主線 {len(main)} 頁，超過上限 {MAX_MAIN}（backup 不計）——\n"
                    f"           要砍先砍「決策的依據」類的頁與 backup；"
                    f"⛔ 鋪陳頁與 depth=mechanism 的頁不得為了湊頁數被砍")
    per = {}
    for s in main:
        per[s.get("thread")] = per.get(s.get("thread"), 0) + 1
    for th, n in sorted(per.items(), key=lambda kv: -kv[1]):
        if n > MAX_PER_THREAD:
            err("deck", f"主線「{th}」有 {n} 頁，超過單線上限 {MAX_PER_THREAD} —— "
                        f"先問這條線是不是該拆成兩條，而不是硬壓")


def check_bar_cell(sid, c):
    """比例 bar 的 pct 必須真的等於 v 的比例。

    為什麼要驗：`pct` 是**幾何**不是文字，不會出現在投影片上，所以逃得過數字溯源
    （`texts()` 已把它排除）。但讀者是**看長度**在比高低的 —— pct 寫錯的圖比
    數字寫錯更難察覺，因為畫面上完全正常。v 寫成 `a/b` 時就能機械對一次。
    """
    v = str(c.get("v") or "")
    m = re.match(r"^\s*([\d,.]+)\s*/\s*([\d,.]+)\s*$", v)
    if not m:
        return
    try:
        a, b_ = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        pct = float(c["pct"])
    except (ValueError, TypeError):
        return
    if b_ <= 0:
        return
    want = 100.0 * a / b_
    if abs(want - pct) > 1.0:
        err(sid, f"比例 bar 對不上：儲存格寫「{v}」＝ {want:.1f}%，但 pct 給的是 {pct:g}%。\n"
                 f"           bar 的長度是讀者用來比高低的東西，錯了畫面上看不出來")


def check_capacity(sid, s):
    for f in ("title", "sub", "point"):          # takeaway 已停用（N67），不再有上限
        if s.get(f):
            cap(sid, f, len(s[f]), LIMITS[f])
    st, b = s.get("type"), s.get("body", {})
    if st == "table":
        for t in (b.get("tables") or ([b] if b.get("columns") else [])):
            cap(sid, "表格列數", len(t.get("rows", [])), LIMITS["table_rows"], "列")
            cap(sid, "表格欄數", len(t.get("columns", [])), LIMITS["table_cols"], "欄")
            capmin(sid, "表格列數", len(t.get("rows", [])), MINS["table_rows"], "列")
            capmin(sid, "表格欄數", len(t.get("columns", [])), MINS["table_cols"], "欄")
            has_bar = False
            for r in t.get("rows", []):
                for c in r:
                    txt = str(c.get("v", "")) if isinstance(c, dict) else str(c)
                    cap(sid, f"儲存格「{txt[:12]}…」", len(txt), LIMITS["cell"])
                    if isinstance(c, dict) and c.get("pct") is not None:
                        has_bar = True
                        check_bar_cell(sid, c)
            # ⚠️ 這條規則不顯而易見，但少了它 bar 就沒有意義：欄寬隨內容撐開時，
            # 同一個 80% 在窄欄與寬欄畫出來的像素長度不同，肉眼比不出誰的比例高。
            if has_bar and not t.get("colw"):
                err(sid, "表格裡有比例 bar，但沒有 colw（固定欄寬）—— "
                         "欄寬會隨內容撐開，同一個百分比在不同欄畫出來長度不同，"
                         "bar 就失去可比性。請給 colw（每欄寬度，例 [\"28%\",\"18%\",…]）；"
                         "多張表要跨表比較時給同一組寬度")
        if len(b.get("tables") or []) > 2:
            err(sid, "一頁最多兩張表")
    if st == "pipeline":
        lanes = b.get("lanes") or []
        cap(sid, "pipeline lane 數", len(lanes), LIMITS["lanes"], "條")
        capmin(sid, "pipeline lane 數", len(lanes), MINS["lanes"], "條")
        for ln in lanes:
            tag = str(ln.get("label") or "")[:14]
            cap(sid, f"lane「{tag}」的節點數", len(ln.get("nodes") or []),
                LIMITS["lane_nodes"], "個")
            capmin(sid, f"lane「{tag}」的節點數", len(ln.get("nodes") or []),
                   MINS["lane_nodes"], "個")
            for nd in (ln.get("nodes") or []):
                nt = str(nd.get("t") or "")[:14]
                cap(sid, f"節點「{nt}」的清單項", len(nd.get("items") or []),
                    LIMITS["node_items"], "項")
                cap(sid, f"節點「{nt}」的色塊", len(nd.get("codes") or []),
                    LIMITS["node_codes"], "個")
                if not nd.get("t"):
                    err(sid, "pipeline 有節點沒有 t（節點的名字）—— 節點一定要有名字")
            if (ln.get("nodes") or []) and ln["nodes"][0].get("arrow"):
                err(sid, f"lane「{tag}」的第一個節點有 arrow —— "
                         f"arrow 是**流進**這個節點的東西，第一個節點前面沒有箭頭")
    for st_name, key, lim in (("agenda", "items", "agenda"), ("stats", "items", "stats"),
                              ("points", "items", "points"), ("flow", "steps", "flow"),
                              ("issues", "items", "issues")):
        if st == st_name:
            cap(sid, f"{st_name} 項數", len(b.get(key, [])), LIMITS[lim], "項")
            capmin(sid, f"{st_name} 項數", len(b.get(key, [])), MINS[lim], "項")
    if st == "points":
        for x in b.get("items", []):
            cap(sid, f"條列「{x[:12]}…」", len(x), LIMITS["point_len"])
    if st == "cols":
        for side in ("left", "right"):
            cap(sid, f"{side} 欄項數", len(b.get(side, {}).get("items", [])),
                LIMITS["col_items"], "項")
            capmin(sid, f"{side} 欄項數", len(b.get(side, {}).get("items", [])),
                   MINS["col_items"], "項")


# ── manifest 對帳：compositions.*.json 說的東西，圖上要真的有（後補，FINDINGS N36）──
# ⚠️ 之前**沒有任何機械檢查**對照 manifest 與 SVG 的實際內容。實測後果：
#    compositions.A.json 宣稱 A1 有 `daily log` 並叫 B 線 reuse this look，
#    而 `daily log`（兩條線唯一共用的名詞）在 A1／B1 的 <text> 裡根本不存在 ——
#    跨主線的交接在版面上看不見，只有 layout_reviewer 逐字比對才抓得到。
# ⚠️ **一律 WARN，不是 ERROR**：manifest 的 schema 兩條線就寫得不一樣
#    （A 用 figures[]/file/objects{名:描述}，B 用 compositions[]/figure/objects_drawn[{name,look}]），
#    而且物件名常是描述性的（"criteria block"、"title before"），本來就不會逐字上版面。
#    比對只能當提醒；要它變硬，得先把 manifest 的 schema 定死。
def _svg_texts_of_file(p):
    try:
        root = ET.parse(p).getroot()
    except (ET.ParseError, OSError):
        return None
    NS = "{http://www.w3.org/2000/svg}"
    return [" ".join("".join(el.itertext()).split()) for el in root.iter()
            if el.tag in (NS + "text", "text")]


def _manifest_figures(j, name):
    """回 ([(slide, svg 相對路徑, [物件名])], 是不是舊 schema)。認不出來回 (None, False)。

    定案的 schema（`subagent-slide-builder.md` Required outputs 第 3 項）：
        {thread, figures:[{slide, file, comp, handwritten, objects:{<名>: <長相>}}]}
    且 `objects` 的 key **必須逐字等於**該 SVG `<text>` 裡的字串，⛔ 不得寫描述。

    ⚠️ 舊的另一套寫法（`compositions[]` / `figure` / `objects_drawn:[{name,look}]`）
    **認得，但一律發 WARN** —— 兩份產物寫成兩種 schema 正是「同一事實各寫各的」，
    對帳只能靠猜哪個欄位。⛔ 現在**先不要升成 ERROR**：本次交付的兩份 manifest
    都還是舊寫法，升上去會讓既有產物變紅。**下一份週報起可升 ERROR**（schema 已定案）。
    """
    if isinstance(j.get("figures"), list):
        ents, legacy = j["figures"], False
    elif isinstance(j.get("compositions"), list):
        ents, legacy = j["compositions"], True
        warn(name, "manifest 用的是舊 schema（compositions[] / figure / objects_drawn[]）"
                   " —— 定案的形狀是 figures[] ＋ objects{<名>: <長相>}"
                   "（subagent-slide-builder.md Required outputs 第 3 項），請改。\n"
                   "           兩份 manifest 寫成兩種 schema，對帳只能猜欄位")
    else:
        return None, False
    out = []
    for e in ents:
        if not isinstance(e, dict):
            continue
        objs = e.get("objects")
        if isinstance(objs, dict):
            names = [str(k) for k in objs]
        else:
            names = [str(o.get("name")) for o in (e.get("objects_drawn") or [])
                     if isinstance(o, dict) and o.get("name")]
        out.append((e.get("slide"), e.get("file") or e.get("figure"), names))
    return out, legacy


def _manifest_paths(deck_path):
    """manifest 在哪裡？回 [(路徑, 是不是舊位置)]。

    ⚠️ **正確落點是 `_work/4_slides/`**（`paths.work_file()` / `work_dir(out,"slides")`
    是那條事實的唯一來源，見 paths.py 的 WORK_FILE_RULES）。
    ⛔ 這裡不要自己拼 `_work/...` —— N14 就是那樣分岔的。
    舊位置（日期目錄最上層）**也掃**，因為既有交付物在那裡；掃到就發 WARN 叫人搬。
    """
    out_dir = os.path.dirname(os.path.abspath(deck_path))
    found = []
    try:
        new_dir = paths.work_dir(out_dir, "slides", create=False)
    except Exception:
        new_dir = None
    if new_dir:
        found += [(p_, False) for p_ in sorted(glob.glob(
            os.path.join(new_dir, "compositions.*.json")))]
    found += [(p_, True) for p_ in sorted(glob.glob(
        os.path.join(out_dir, "compositions.*.json")))]
    return found, new_dir, out_dir


def check_manifest(deck_path, slides):
    d = os.path.dirname(os.path.abspath(deck_path))
    found, new_dir, out_dir = _manifest_paths(deck_path)
    # ⛔ **找不到 manifest 不准靜默**（後補）：原本的寫法是 glob 掃不到就整個迴圈不跑、
    #    一個字都不印、exit 0 —— 檔案搬個位置就等於這條檢查無聲消失，
    #    正是這個 skill 一直在打的失效形狀。有圖的頁存在就一定要出聲。
    if not found:
        if any((s_.get("composition") or {}).get("comp") for s_ in slides):
            warn("deck", "有頁填了 composition，卻找不到任何 compositions.*.json —— "
                         "manifest 與產物的對帳**整條沒有跑**。\n"
                         f"           找過：{new_dir or '(work_dir 解析失敗)'} "
                         f"與 {out_dir}\n"
                         "           正確落點是 _work/4_slides/（用 paths.work_file()"
                         " 寫檔，⛔ 不要自己拼路徑）")
        return
    for mp, legacy_loc in found:
        name = os.path.basename(mp)
        if legacy_loc:
            warn(name, "manifest 在舊位置（日期目錄最上層）—— 正確落點是 "
                       "_work/4_slides/，請改用 paths.work_file(out, \"" + name + "\")"
                       "。⛔ 不要自己拼 _work/… 的路徑")
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError) as e:
            warn(name, f"讀不到／解析不了這份 manifest：{e}")
            continue
        figs, _legacy_schema = _manifest_figures(j, name)
        if figs is None:
            warn(name, "找不到圖清單欄位（定案的是 figures[]，舊寫法 compositions[] 也認）"
                       " —— 這一份的對帳跳過")
            continue
        seen = ""
        for slide, rel, names in figs:
            if not rel:
                continue
            fp = os.path.join(d, rel)
            txts = _svg_texts_of_file(fp)
            if txts is None:
                warn(name, f"{slide}: manifest 指到的圖讀不到或不是合法 SVG：{rel}")
                continue
            blob = "  ".join(txts).lower()
            exact = {t.strip().lower() for t in txts if t.strip()}
            seen += "  " + blob
            for n in names:
                nm = n.strip().lower()
                if not nm:
                    continue
                if nm in exact:
                    continue                    # 逐字等於某一則 <text>：這才是規格要的
                # ⚠️ 後補（N111 ②）：原本只用 `nm in blob`（子字串），而錯誤訊息
                #    自己寫著「要**逐字等於**圖上的字串」—— 檢查比它自己的訊息鬆。
                #    實例：`{"a": "…"}` 對任何含字母 a 的圖都命中。
                # ⛔ 裁決（「先寬」）：**不改成只認逐字** —— 合法的縮寫標註
                #    （圖上寫 `daily log ×3`、manifest 寫 `daily log`）會被誤殺。
                #    改成分級：逐字命中不出聲、只有子字串命中降級提醒、都沒有才報找不到。
                #    ⚠️ 並且短名不再算子字串命中（`a`／`x` 這種對誰都命中，等於沒檢查）。
                if len(nm) >= 4 and nm in blob:
                    warn(name, f"{slide}: manifest 點名的物件「{n}」只在**子字串**層級"
                               f"命中 {os.path.basename(rel)} —— 圖上沒有任何一則 <text> "
                               f"逐字等於它。\n"
                               f"           規格要的是逐字相等；縮寫或加了尾綴是可以的，"
                               f"但要確認觀眾在圖上看得到這個名字")
                    continue
                warn(name, f"{slide}: manifest 點名的物件「{n}」"
                           f"在 {os.path.basename(rel)} 的 <text> 裡找不到"
                           + ("（名字太短，子字串命中不算數）" if len(nm) < 4 else "")
                           + f" —— manifest 對不上產物。\n"
                           f"           objects 的 key 要**逐字等於**圖上的字串，"
                           f"⛔ 不得寫描述（subagent-slide-builder.md）")
        shared = j.get("shared_terms")
        if isinstance(shared, dict):
            for term in shared:
                if str(term).strip().lower() not in seen:
                    warn(name, f"shared_terms 宣稱共用「{term}」，但這條線的圖裡"
                               f"一個字串都沒有 —— 跨主線的交接在版面上看不見")


# ── 語意色一致性（後補，FINDINGS N38）────────────────────────────────────────
# `presentation_rules.md §5`：一個顏色一種意思。實測失效：`Record layer` 在 A1 是
# 強調框（金＝這頁的主張）、在 A3 是 `box-bad`（紅＝失效）—— **同一個 builder 在
# 同一條線內就分岔了**，而沒有任何機械檢查擋得住。
# 判準（刻意只擋會讓觀眾讀錯的那一種）：
#   · `good`／`bad` 是**這個東西本身的評價**，同一個名字在兩張圖一好一壞 → ERROR。
# ⭐ **6c 之後這條變單純了**：強調形狀（`*-hl`）已從字彙移除，形狀上只剩分類色，
#    所以「金當成第三種評價」那半自然消失 —— ⛔ 但這條**不能因此拿掉**：
#    分類色本身仍會分岔（同一個東西這頁 good 那頁 bad），而那正是它擋的。
#    ⚠️ `hl` 留在 TONE_CLS 裡是**防守用**的：舊圖若還帶著 `*-hl`，
#    `check_emphasis_shape()` 會先報 ERROR，這裡不會漏掉它。
TONE_CLS = ("good", "bad", "hl")


def _tone_of_svg(p):
    """回 {圖上的字串: 語氣}。語氣取自該 <text> 自己的 class，
    沒有就找**幾何上包住它的最小方框**（SVG 是平的，沒有巢狀可用）。"""
    try:
        root = ET.parse(p).getroot()
    except (ET.ParseError, OSError):
        return {}
    NS = "{http://www.w3.org/2000/svg}"
    boxes = []
    for el in root.iter():
        if el.tag not in (NS + "rect", "rect"):
            continue
        cls = el.get("class") or ""
        tone = next((c for c in TONE_CLS if cls.endswith("-" + c)), None)
        try:
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, h = float(el.get("width", 0)), float(el.get("height", 0))
        except ValueError:
            continue
        boxes.append((w * h, x, y, w, h, tone))
    boxes.sort()                       # 面積小的先 → 取「包住它的最小方框」
    out = {}
    for el in root.iter():
        if el.tag not in (NS + "text", "text"):
            continue
        t = " ".join("".join(el.itertext()).split())
        if not t:
            continue
        cls = set((el.get("class") or "").split())
        tone = next((c for c in TONE_CLS if c in cls), None)
        if tone is None:
            try:
                tx, ty = float(el.get("x", 0)), float(el.get("y", 0))
            except ValueError:
                tx = ty = None
            if tx is not None:
                for _, x, y, w, h, bt in boxes:
                    if x <= tx <= x + w and y <= ty <= y + h:
                        tone = bt
                        break
        out[t] = tone or "plain"
    return out


# ── N83：手寫 SVG 的 marker 紀律 ────────────────────────────────
#    ⚠️ 這一組**只有 renderer 那一半免疫**：`render_figure.py` 的 `wrap()` 內建了
#    正確的 `<defs>`，而**手寫 SVG 要自己寫**——而會犯錯的正是後者。
#    在這條檢查之前，沒有任何腳本去**讀** `figures/*.svg`。
MARKER_GEO = ("viewBox", "refX", "refY", "markerWidth", "markerHeight")
SHARED_MARKERS = ("a", "ah")           # deck.css 的 marker-end 只指名這兩個


def _markers_of(p):
    """回 [(id, attrs)]。⚠️ 讀檔失敗回空 —— 壞掉的 SVG 由別的檢查負責出聲。"""
    try:
        root = ET.parse(p).getroot()
    except (ET.ParseError, OSError):
        return []
    NS = "{http://www.w3.org/2000/svg}"
    return [(el.get("id") or "", dict(el.attrib))
            for el in root.iter() if el.tag in (NS + "marker", "marker")]


# ── N121 出貨的 SVG 要**重跑得出來**───────────────────────────────────────────
#: spec 檔裡不該留下的佔位符（`<date>`／`<thread>` 那一族）。
#: ⚠️ 只認**全小寫英數＋底線**且被 `<>` 夾住的，⛔ 不要誤傷 SVG 裡的標籤
#:   （那是 `<text>`／`<rect>`，本檢查只掃 spec 的 JSON 字串值與圖上的 <text> 內容）。
_PLACEHOLDER = re.compile(r"<[a-z][a-z0-9_]*>")


def _spec_of(deck_path, slide_id):
    """這一頁的構圖 spec 檔在哪。⛔ 不自己拼 `_work/...`（N14）——
    唯一的出處是 `paths.work_file()` 的 WORK_FILE_RULES。"""
    out_dir = os.path.dirname(os.path.abspath(deck_path))
    try:
        return paths.work_file(out_dir, f"{slide_id}.json", create=False)
    except Exception:
        return None


def _rerender(spec_path):
    """照 spec 重跑一次 renderer，回 (svg 字串, 錯誤訊息)。

    ⭐ **一條命令、一個輸入檔** —— 這正是 `budget` 要進 spec 檔的理由（N121）：
    重現配方不能有記在別處的隱藏參數，否則「重跑得出來」這件事本身不可驗。
    """
    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_figure.py")
    if not os.path.isfile(exe):
        return None, f"找不到 render_figure.py（找過 {exe}）"
    try:
        r = subprocess.run([sys.executable, exe, spec_path],
                           capture_output=True, timeout=120)
    except Exception as e:                       # noqa: BLE001 —— 什麼都不該讓它靜默
        return None, f"重跑 renderer 失敗：{e}"
    if r.returncode != 0:
        return None, ("重跑 renderer 直接失敗（exit "
                      f"{r.returncode}）：{(r.stderr or b'').decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout.decode("utf-8"), ""


def check_spec_reproduces(deck_path, slides):
    """⭐ **每個 spec 重跑一次，必須逐 byte 重現出貨的 SVG**（FINDINGS N121）。

    ## 為什麼這一條比「掃佔位符」強

    ⚠️ 實測（任務 4 之後、6c 回饋輪撞到的）：`_work/3b_specs/*.json` 還停在
    `<date>`／`<thread>`，而出貨的 SVG 是任務 4 換成真字串之後的版本 ——
    ⛔ **下一個 builder 照規格重跑 renderer，任務 4 的成果就沒了，而且 `verify.py` 全綠**
    （那 10 則字串沒有任何檢查在看）。

    ⭐ **幾何完全沒有差** —— 差的只有那 10 則字串，所以「圖看起來一樣」騙得過眼睛。
    ⛔ **判準必須是逐 byte，不是看圖。**

    這一條同時擋住三件事，⭐ 那是它比佔位符掃描強的地方：

    | 擋住的 | 佔位符掃描擋得到嗎 |
    |---|---|
    | spec 還留著 `<date>`／`<thread>` | ✅ |
    | **手改了 SVG 沒回寫 spec**（改成任何真字串都一樣） | ❌ |
    | **spec 改了但圖沒重跑**（反方向） | ❌ |

    ## ⚠️ `budget` 為什麼一定要在 spec 檔裡

    `render_figure.py` 吃 `--budget`，而出貨時用的是哪個預算**舊版沒有記在任何地方**
    —— 這條檢查要「重跑」，就必須拿得到一份**不靠命令列**的完整輸入。
    ⭐ 所以 `budget` 進 spec 檔（`diagram-craft.md §6` 仍是那個數字的唯一出處，
    spec 只是**記下這一頁查到的是哪一格**）。
    ⚠️ 實測 `--budget` 不影響輸出的任何一個 byte（`_height_guard` 只印警告），
    所以逐 byte 比對本身不靠它 —— 它守的是另一半：這張圖放不放得進那一頁。

    ## ⛔ 反方向（N56）：這條會把人推去哪裡

    | 推去哪 | 是不是我們要的 | 擋法 |
    |---|---|---|
    | 手改了 SVG 就把 spec 也改成一樣 | ⭐ **正是我們要的** —— 兩份從此不分岔 | — |
    | 乾脆不用 renderer、全部手寫（`handwritten: true` 就跳過這條） | ⛔ **不要** | ① `check_renderer_used()`：有 renderer 的構圖標 `handwritten` 直接 ERROR；② `diagram-craft.md §0` 的手繪額度**一份 deck 最多 2–3 張** |
    | 把 spec 檔刪掉讓檢查找不到 | ⛔ 不要 | 找不到 spec 而圖又不是手寫 → **ERROR**，⛔ 不靜默跳過（那正是這個 skill 一直在打的失效形狀） |

    ## 範圍

    只看 manifest 裡 `handwritten` 不為真的 figure 條目 ——
    ⭐ 手寫圖本來就沒有 spec 可以重跑，對它叫是規則否定自己的產物。
    """
    found, _new_dir, _out_dir = _manifest_paths(deck_path)
    if not found:
        return
    d = os.path.dirname(os.path.abspath(deck_path))
    hw_of = {s.get("id"): bool((s.get("composition") or {}).get("handwritten"))
             for s in slides if isinstance(s, dict)}
    for mp, _legacy in found:
        name = os.path.basename(mp)
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError):
            continue                              # check_manifest 已經報過
        for e in (j.get("figures") or j.get("compositions") or []):
            if not isinstance(e, dict):
                continue
            sid, rel_f = e.get("slide"), (e.get("file") or e.get("figure"))
            if not (sid and rel_f):
                continue
            # 手寫以 manifest 與 slides 兩邊**任一邊**說了算：兩邊都說不是手寫才查。
            # ⛔ 只信一邊 = 改另一邊就能繞過去。
            if e.get("handwritten") or hw_of.get(sid):
                continue
            sp = _spec_of(deck_path, sid)
            if not sp or not os.path.isfile(sp):
                err(name, f"{sid}: 這張圖不是手寫（`handwritten` 不為真），"
                          f"但**找不到可以重跑的 spec 檔**：{sp or '(路徑解析失敗)'}\n"
                          f"           ⛔ 沒有 spec 就沒有人能重現這張圖 —— "
                          f"下一個人只能手改 SVG，而手改的東西沒有任何檢查看得到。\n"
                          f"           落點由 paths.work_file() 決定"
                          f"（`_work/3b_specs/<頁 id>.json`），⛔ 不要自己拼路徑")
                continue
            try:
                spec_txt = open(sp, encoding="utf-8").read()
            except OSError as ex:
                err(name, f"{sid}: 讀不到 spec 檔 {sp}：{ex}")
                continue
            ph = sorted(set(_PLACEHOLDER.findall(spec_txt)))
            if ph:
                err(name, f"{sid}: spec 檔裡還留著佔位符 {'、'.join(ph)} —— "
                          f"{os.path.basename(sp)}\n"
                          f"           ⛔ 佔位符會被**逐字**畫到圖上；"
                          f"重跑一次就把定案的真字串洗掉（FINDINGS N121）")
            got, msg = _rerender(sp)
            if got is None:
                err(name, f"{sid}: {msg}\n"
                          f"           spec：{sp}")
                continue
            fp = os.path.join(d, rel_f)
            try:
                want = open(fp, encoding="utf-8").read()
            except OSError as ex:
                err(name, f"{sid}: 讀不到出貨的圖 {rel_f}：{ex}")
                continue
            if got == want:
                continue
            # 逐 byte 不同時，把**最有用的那一半**印出來：差在哪幾則 <text>。
            ga = re.findall(r"<text[^>]*>(.*?)</text>", got, re.S)
            wa = re.findall(r"<text[^>]*>(.*?)</text>", want, re.S)
            diffs = [(x, y) for x, y in zip(ga, wa) if x != y][:6]
            geom_same = (re.sub(r">(.*?)</text>", "></text>", got, flags=re.S)
                         == re.sub(r">(.*?)</text>", "></text>", want, flags=re.S))
            detail = "".join(
                f"           · 重跑「{x}」 vs 出貨「{y}」\n" for x, y in diffs)
            if len(ga) != len(wa):
                detail += (f"           · `<text>` 則數不同：重跑 {len(ga)}、"
                           f"出貨 {len(wa)}\n")
            err(name, f"{sid}: **照 spec 重跑產不出現在出貨的這張圖** —— "
                      f"{os.path.basename(rel_f)}\n"
                      + (f"           ⚠️ **幾何完全相同，只有字串不一樣** —— "
                         f"⛔ 所以「圖看起來一樣」騙得過眼睛，判準是逐 byte\n"
                         if geom_same else "")
                      + detail
                      + f"           ⛔ 兩份必須同源：改了圖就把 spec 改成一樣、"
                        f"改了 spec 就重跑一次（FINDINGS N121）。\n"
                        f"           重現配方：python3 scripts/render_figure.py "
                        f"{os.path.relpath(sp, d)} -o {rel_f}")


def check_terms_zh(deck_path, plan):
    """⭐ 名詞的中譯全場只有一個（N31 的機械版，PR 2）。

    關卡② 凍結 `plan.terms_zh`（物品名 → 中譯），layer3 各 builder 照表翻。
    這裡驗：`strings.zh.json` 裡凡是原句含某個物品名、且已經翻了的，譯文要含那個物品的中譯。
    ⚠️ WARN 不是 ERROR（先寬）：句子裡的物品名可能刻意用原文（`"="`）或改成代稱；
    但至少要有人看得見「這一句沒照表翻」。⛔ 以前這件事只靠 deck_assembler 一個人的自律。
    """
    tz = plan.get("terms_zh") or {}
    if not tz:
        return
    sp = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "strings.zh.json")
    if not os.path.isfile(sp):
        return
    try:
        tr = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        return
    bad = []
    for en, zh in sorted(tr.items()):
        if not zh or zh == "=":
            continue
        for term, term_zh in tz.items():
            if not term or not term_zh:
                continue
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", en, re.I) \
                    and term_zh not in zh and term not in zh:
                bad.append((en, zh, term, term_zh))
    for en, zh, term, term_zh in bad[:12]:
        warn("i18n", f"「{en[:40]}」的譯文「{zh[:40]}」沒有用凍結的譯名："
                     f"{term} → {term_zh}（plan.terms_zh）—— 同一個東西全場一個名字")
    if len(bad) > 12:
        warn("i18n", f"…另有 {len(bad) - 12} 句沒照 terms_zh 翻")


def check_handwritten_quota(deck_path):
    """一份 deck 最多 2–3 張手繪（diagram-craft §0）—— 以前只有 layout_reviewer 數得到（第 5 項），
    現在 manifest 就在這裡，機械先數一次；reviewer 只覆核「拿掉最弱的那張會少講什麼」。"""
    found, _n, _o = _manifest_paths(deck_path)
    hw = []
    for mp, _legacy in found:
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for e in (j.get("figures") or j.get("compositions") or []):
            if isinstance(e, dict) and e.get("handwritten"):
                hw.append(f"{e.get('slide')}:{os.path.basename(e.get('file') or e.get('figure') or '?')}")
    if len(hw) > 3:
        warn("deck", f"手繪 SVG 共 {len(hw)} 張（{'、'.join(hw)}），超過 diagram-craft §0 的 2–3 張 —— "
                     f"逐張問「拿掉最弱的那張，這份 deck 會少講什麼」，答不出來的退回表格或有 renderer 的構圖")


def check_hl_text_roles(deck_path):
    """金字（`<text class="… hl">`）全圖只能有**一種** class 組合（layout_reviewer 3c 第 2 問）——
    兩種組合＝兩個強調理由＝砍到剩一個。這一問純機械，搬進來；reviewer 只留第 3 問（值不值得）。"""
    d = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "figures")
    if not os.path.isdir(d):
        return
    for fp in sorted(glob.glob(os.path.join(d, "*.svg"))):
        try:
            txt = open(fp, encoding="utf-8").read()
        except OSError:
            continue
        combos = set()
        for cls in re.findall(r'<text[^>]*class="([^"]*)"', txt):
            toks = cls.split()
            if "hl" in toks and not any(t.startswith(("box-", "grp-", "arrow-", "bar-")) for t in toks):
                combos.add(" ".join(sorted(toks)))
        if len(combos) > 1:
            warn(os.path.basename(fp), f"金字用了 {len(combos)} 種 class 組合（{'；'.join(sorted(combos))}）—— "
                                       f"兩種＝兩個強調理由，砍到剩一個（presentation_rules §5）")


def check_css_purpose_sync(deck_path):
    """`deck.css` 的 `<text>` 字型選擇器，要蓋得住 `check_purpose()` 認的每一個用途 class。

    ## 這條在補什麼（5a/5b 登記的那條「新的方向題」，批次 5g 定案）

    N84 把 `deck.css` 的 `svg text{}` 換成**綁 class** 的選擇器（規則要求的），
    失效方向因此變成：**某個帶 class 的 `<text>` 不在那串選擇器裡 → 靜靜失去
    字型與顏色，而且看程式碼看不出來**。當時擋它的是 `check_purpose()`
    （每則 `<text>` 必須恰好一個用途 class，逐則 ERROR）——
    ⛔ **但那是兩份手抄的清單**：`deck.css` 的選擇器一份、`PURPOSE` 一份。
    哪天有人放寬 `check_purpose()`，兩層就一起破。

    ⭐ 兩個選項裡選了**加比對**（另一個是「程式產 CSS」）：
    CSS 還要人手寫顏色與字級，產 CSS 等於把樣式決策搬進程式碼，代價大得多；
    而「兩份清單要一致」這件事本身**機械驗得掉**。

    ## 反方向（N56）

    這條只驗**單向包含**（`PURPOSE` ⊆ 選擇器），⛔ 不驗反向 ——
    選擇器裡本來就有 `t-lg`／`grp-h`／`item` 這些**不是用途**的 class
    （舊字彙與元件字彙），要求雙向相等會把它們全部誤報。
    """
    css = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "deck.css")
    if not os.path.isfile(css):
        return
    body = open(css, encoding="utf-8").read()
    # 取所有 `svg .xxx` 形式的 class（夠了：這條只問「有沒有被某條規則選到」）
    sel = set(re.findall(r"svg\s+\.([A-Za-z0-9_-]+)", body))
    missing = sorted(PURPOSE - sel)
    if missing:
        err("deck.css", f"用途 class {'、'.join(missing)} **沒有出現在 deck.css 的任何 "
                        f"`svg .xxx` 選擇器裡** —— 帶這個 class 的 <text> 會靜靜失去"
                        f"字型與顏色，看程式碼看不出來。\n"
                        f"           `check_purpose()` 的 PURPOSE 與 deck.css 的選擇器"
                        f"是**兩份手抄的清單**，這條就是那兩份的比對（N84 的反方向）。\n"
                        f"           改法：在 deck.css 補上對應的 `svg .{missing[0]}` 規則。")


# 任務 6 L0：層級只准有一個來源 —— 字彙（deck.css），不是圖上的 inline style。
INLINE_TYPE = re.compile(r"\b(font-size|font-weight|letter-spacing)\s*:", re.I)
# 具名豁免：內容尺寸座標系的 read／haplotype 一族（render_figure.py 檔頭 N89／N91）。
RAW_SIZE = "raw-size"
# 那三個字串**曾經**是 render_figure.py 的 BLK_*_STYLE，手寫圖照抄了一份。
# 對照到新角色，讓錯誤訊息直接講「改成哪一個」，而不是只說「不准」。
INLINE_HINT = [
    ("letter-spacing", "label section", "盒內的分段標題"),
    ("font-weight:800", "label num", "編號欄的序號"),
    ("font-size:20px", "label section", "盒內的分段標題"),
    ("font-weight:700", "label section", "盒內的分段標題"),
    ("font-weight:600", "label term", "定義列左欄，東西的名字"),
]


def check_inline_type(deck_path):
    """`figures/*.svg` 的 `<text>` 不得帶 inline `font-size`／`font-weight`／`letter-spacing`。

    ## 這條在補什麼

    `deck.css` 給 SVG 文字的用途只有四個，`label` 底下只有 `label` 與 `label.lead`
    兩級 —— 而盒子裡實際有四種層級。缺的那幾級**不存在於字彙裡**，於是 renderer
    與手寫圖各自用 inline `style=` 硬補。實測（任務 6 開工前的 7 張圖）：
    31 處 `font-size` 覆寫、25 處 `font-weight` 覆寫，`A1` 一張就 6 處。
    ⭐ **每張圖發明的值不保證一樣 ＝ 粗糙與跨頁不一致的源頭**，
    而這是「看圖看不出來、要 diff 兩張圖的 style 字串才發現」的那種不一致。

    ⚠️ 而這道門是 `deck.css` 自己開的：它寫著「不要在 SVG 裡寫**字型大小以外**
    的樣式」—— 字級正好是它放行的那一項，所有層級都從那個缺口漏出去。
    L0 補齊 `label.section`／`.term`／`.gloss`／`.num` 四個角色之後，**把門關上**。

    ## 為什麼是 ERROR 不是 WARN

    層級有兩個來源時，兩邊都是「對的」，⛔ 沒有人能判哪一份才算數 ——
    這正是 N117 那類「兩條規則互相否定」的形狀。WARN 擋不住任何東西
    （`plan.layout_reviewed` 那條 WARN **從第一次實跑到 2026-09-05 一場都沒被回填過**，
    就是現成的證據 —— ⭐ 它現在已經升成 ERROR，⛔ 但**先指定了寫的人**才升：
    只把規則變硬而沒有人有義務執行，那是把規則變成路障。見檢查項 0e）。

    ## 反方向（N56）：擋掉合法的自訂字級怎麼辦

    真的有一族需要自訂字級：`render_read_pileup`／`render_haplotype_split`
    產的是**內容尺寸**的 viewBox（N91 尚未裁決），13／14／19px 才是對的比例，
    套 `deck.css` 的 22px 會爆版。**它們豁免，但豁免必須具名**：
    帶 `raw-size` 這個 class 才放行，而且**用掉幾則會被印出來** ——
    ⭐ 具名的好處是 `grep -n raw-size` 就是 N91 那批釘子的完整清單。
    ⛔ 反過來說，`raw-size` 也不能變成新的萬能後門：它只出現在 renderer 的
    那一族裡，手寫圖用它就會在這條的統計行上現形。

    ⚠️ `font-family` **不在**禁令裡 —— 等寬是「這是字面／檔名」的語意記號，
    與字級層級正交（`MONO`／`svg .item`／`svg .file-name` 都在用）。
    ⛔ 一起禁掉會把「這是不是程式碼」這個語意也逼進 inline style，反而更糟。
    """
    d = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "figures")
    if not os.path.isdir(d):
        return
    NS = "{http://www.w3.org/2000/svg}"
    exempt = 0
    for fp in sorted(glob.glob(os.path.join(d, "*.svg"))):
        name = os.path.basename(fp)
        try:
            root = ET.parse(fp).getroot()
        except ET.ParseError:
            continue                         # 解析錯誤已由 svg_numbers 報過
        for el in root.iter():
            if el.tag not in (NS + "text", "text"):
                continue
            st = el.get("style") or ""
            if not INLINE_TYPE.search(st):
                continue
            if RAW_SIZE in (el.get("class") or "").split():
                exempt += 1
                continue
            t = "".join(el.itertext()).strip()
            hit = INLINE_TYPE.findall(st)
            role = next((r for k, r, why in INLINE_HINT if k in st.replace(" ", "")), None)
            why = next((why for k, r, why in INLINE_HINT if k in st.replace(" ", "")), "")
            fix = (f'改成 class="{role}"（{why}）' if role else
                   "去 deck.css 的字彙表**加一個角色 class**，然後標它")
            err(name, f"<text> 帶 inline {'／'.join(sorted(set(x.lower() for x in hit)))}"
                      f"：「{t[:36]}」\n"
                      f"           style={st[:72]!r}\n"
                      f"           ⛔ 層級只准有一個來源 —— 字彙（deck.css），"
                      f"不是圖上的 style。{fix}。\n"
                      f"           ⚠️ 每張圖自己發明的值不保證一樣，"
                      f"那是跨頁不一致裡最難用眼睛看出來的一種。")
    if exempt:
        print(f"[check] {exempt} 則 <text> 帶具名豁免 raw-size —— 內容尺寸座標系的 "
              f"read／haplotype 一族（N91 未裁決前的釘子，`grep -n raw-size` 是完整清單）")


def _path_points(d):
    """走一次 `d`，回傳它經過的點 —— ⛔ 只認直線指令（M/L/H/V，含小寫相對）。

    ⚠️ **不能只把 `d` 裡的數字兩兩配對**（第一版就是那樣寫的，⛔ 錯的）：
    `H`／`V` 只帶**一個**座標，`M424,308 H440` 會被解成 3 個數 → 整支箭頭被跳過。
    實測後果：A3 的 4 支箭頭裡有 1 支這樣寫，那條檢查對它**結構上不可能出聲**。
    ⭐ 曲線（C/Q/A）不解 —— 箭頭是直的，出現曲線代表版型變了，那時再說。
    """
    out, cur = [], [0.0, 0.0]
    for cmd, body in re.findall(r"([MmLlHhVv])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
        n = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", body)]
        rel = cmd.islower()
        c = cmd.upper()
        if c in ("M", "L"):
            for i in range(0, len(n) - 1, 2):
                cur = ([cur[0] + n[i], cur[1] + n[i + 1]] if rel else [n[i], n[i + 1]])
                out.append(tuple(cur))
        elif c == "H":
            for v in n:
                cur = [cur[0] + v if rel else v, cur[1]]
                out.append(tuple(cur))
        elif c == "V":
            for v in n:
                cur = [cur[0], cur[1] + v if rel else v]
                out.append(tuple(cur))
    return out


def check_arrow_legible(deck_path):
    """箭頭讀不讀得出方向：**頭要夠大，桿要比頭長**（6e 的前置裁決 ②）。

    ## 病（實測，2026-09-05）

    全 deck 7 張圖的箭頭頭一律 **8×8 user unit**，而畫布是 **1420 寬** ——
    佔 0.56%，在投影機上讀不出方向。⭐ 病是**全 renderer 同病**
    （`group_blocks`／`funnel`／`chain`／`two_col_link` 都從同一份 `ARROW_DEFS` 拿），
    所以 `render_figure.ARROW_H` 改成 12（＝ 4× 桿寬）一次全治。

    ## ⛔ 為什麼還要這一把量尺（頭放大不等於看得見）

    ⚠️ 只放大頭會製造另一個病：**桿比頭短的箭頭只是一個三角形色塊**，
    方向照樣讀不出來。N125 記過同型的實測 —— `transform_pair` 第一版畫了
    一支 8px 的桿，而 marker 本身 8px，⭐ **整支箭頭剛好被自己的箭頭頭蓋掉**。
    所以判準是**兩件一起**：頭 ≥ 12，且**桿長 ≥ 3× 頭**。

    ⚠️ 一律 **WARN**：桿長是構圖決定的（漏斗的段間距就是窄），
    ⛔ 硬性擋下去會逼 renderer 去改自己刻意訂的間距 —— 那是 N56 的反方向，
    也是 `composition-vocabulary.md` 寫過的「規則否定自己的產物時，錯的是規則」。
    ⭐ 這條要的是「出聲」：桿短的那幾支要嘛加長間距，要嘛那裡本來就不該用箭頭
    （`_chain_band` 逐字寫著「順序靠編號不靠箭頭」，⛔ 那不是缺陷）。
    """
    d = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "figures")
    if not os.path.isdir(d):
        return
    NS = "{http://www.w3.org/2000/svg}"
    num = re.compile(r"-?\d+(?:\.\d+)?")
    for fp in sorted(glob.glob(os.path.join(d, "*.svg"))):
        name = os.path.basename(fp)
        try:
            root = ET.parse(fp).getroot()
        except ET.ParseError:
            continue
        heads = [float(m.get("markerWidth") or 0) for m in root.iter()
                 if m.tag in (NS + "marker", "marker") and m.get("markerWidth")]
        head = min(heads) if heads else 0
        if heads and head < 12:
            warn(name, f"箭頭頭只有 {head:g}×{head:g} user unit，畫布 1420 寬 —— "
                       f"⛔ 在投影機上讀不出方向。\n"
                       f"           ⭐ 治本的地方是 `render_figure.ARROW_H`（現為 12 "
                       f"＝ 4× 桿寬），⛔ 不要在單張圖上改 —— 那會製造跨頁不一致。\n"
                       f"           這張圖是**舊的 defs**：重跑 renderer 產一次就會帶新值。")
        short = []
        for el in root.iter():
            if el.tag not in (NS + "path", "path"):
                continue
            if "arrow" not in (el.get("class") or "").split():
                continue
            pts = _path_points(el.get("d") or "")
            if len(pts) < 2:
                continue
            # 桿長取外接矩形的長邊 —— 直線與折線都適用
            span = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                       max(p[1] for p in pts) - min(p[1] for p in pts))
            if head and span < head * 3:
                short.append(f"{span:g}px")
        if short:
            warn(name, f"{len(short)} 支箭頭的**桿比頭短**（桿長 {'、'.join(short)}，"
                       f"頭 {head:g}px，判準：桿 ≥ 3× 頭）——\n"
                       f"           ⭐ 桿比頭短的箭頭只是一個三角形色塊，方向照樣讀不出來"
                       f"（N125：transform_pair 第一版的 8px 桿被自己的 8px 頭整支蓋掉）。\n"
                       f"           兩條路：① 把那一段的間距加長到容得下"
                       f"（⛔ 間距是 8 的倍數，見 diagram-craft §6）；\n"
                       f"           ② 那裡本來就不該用箭頭 —— 改用編號承擔順序"
                       f"（`_chain_band` 逐字就是這樣做的，⛔ 那不是缺陷）。")


def check_emphasis_shape(deck_path):
    """`figures/*.svg` 不得出現**強調形狀** `box-hl`／`grp-hl`／`arrow-hl`／`bar-hl`。

    ## 判準（使用者裁決，2026-09-05，6c 回饋輪）

    > 「框線還是可以用顏色分類，但不要有特別除出一個的強調框線（剛剛是黃色的）」

    ⭐ **形狀（框、線、長條）的顏色只回答「這是哪一類」，⛔ 不回答
    「這一個特別重要」。** 強調只剩兩個落點：**字**（`svg .hl`，可疊在任一用途
    class 上）與**表格列**（`rowclass:"hl"`）—— 它們標的是一句話／一列資料，
    不是「把一個東西挑出來」。

    ## 為什麼（實測，7 張圖）

    強調框幾乎都落在兩種沒有意義的位置上：

    · **框在本來就最顯眼的東西上** —— `A3` 框中央的 `candidates.py`（它已經是
      最大、最中間的框）、`A4` 框中間的 `check_readability.py`（上紅下綠，
      不用金也知道是它）。⭐ **強調本來就最顯眼的東西 = 沒有強調。**
    · **並列的同類裡標一半** —— `A1` 兩群標一個、`A5` 三列標兩列、
      `B3` 六格標四格。⭐ **並列的東西標一半 = 雜訊，不是重點。**

    金底原本佔版面的 **39.5%**（`A5` 一張 65.2%）；先降成只描邊，回饋後整個拿掉。

    ## 為什麼是 ERROR 不是 WARN

    `deck.css` 已經把這四個 class **刪掉**了 —— 圖上再寫它們就是**沒有樣式的
    裸 class**，渲染成一般色，而**寫的人以為自己標了重點**。⛔ 這正是「靜默失效」
    （N93 花力氣消掉的那個形狀），WARN 攔不住。
    ⚠️ `render_figure.py` 那半已經在源頭擋（`TONE` 拿掉 `"hl"`、`focus` 廢除），
    這條擋的是**手寫 SVG** —— 那是 renderer 管不到的入口。

    ## 反方向（N56）：把強調全拿掉之後，這一頁還有沒有重點？

    ⛔ 有可能沒有 —— 那是這條的真實風險，**但不能靠留著強調框來解**。
    收完之後「三秒內眼睛該落在哪」由**標題 ＋ 一處金字 ＋ 位置**回答；
    「一頁至少一處金」由 `layout_reviewer 3c` 的反向自查擋
    （`presentation_rules §5`）。⭐ 位置本來就是比顏色更強的手段：
    要它最重要，就把它**放大、放中間、放第一個**。
    """
    d = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "figures")
    if not os.path.isdir(d):
        return
    BANNED = {
        "box-hl":   "方框",
        "grp-hl":   "群組外框",
        "arrow-hl": "連線",
        "bar-hl":   "長條",
    }
    for fp in sorted(glob.glob(os.path.join(d, "*.svg"))):
        name = os.path.basename(fp)
        try:
            root = ET.parse(fp).getroot()
        except ET.ParseError:
            continue                         # 解析錯誤已由 svg_numbers 報過
        for el in root.iter():
            for c in (el.get("class") or "").split():
                if c not in BANNED:
                    continue
                err(name, f'<{el.tag.rsplit("}", 1)[-1]} class="{c}"> —— '
                          f'強調{BANNED[c]}已從字彙移除（6c 使用者裁決）。\n'
                          f'           ⛔ 形狀的顏色只做**分類**，不做強調 ——'
                          f'「框線還是可以用顏色分類，但不要有特別除出一個的強調框線」。\n'
                          f'           分類色仍可用：box-bad／good／null／ctl'
                          f'（grp-* 同）。\n'
                          f'           要強調就標在**字**上（class="... hl"），'
                          f'或把它放大／放中間／放第一個。\n'
                          f'           ⚠️ deck.css 已無此 class —— 留著它會渲染成'
                          f'一般色，而寫的人以為標了重點（靜默失效）。'
                          f'→ presentation_rules §5')


# ── L4-1 關係要有視覺證據（任務 6d）───────────────────────────────────────────
# ⚠️ **推導自 SVG，⛔ 不讀任何手寫宣告** —— 理由與方案比較見 FINDINGS N123。

#: `<text>` 的用途 class → 它在版面上扮演的角色。⭐ 唯一出處是 6a／L0 收斂出來的
#: 那四個 class（`label.section`／`.term`／`.gloss`／`.num`）加上原有的 lead／value。
_ROLE_ORDER = ("lead", "section", "num", "value", "term", "gloss", "annot", "def")

#: ⭐ **「標題型」角色**：物件在這裡**被介紹**，它的長相就是這一則的長相。
#: 其餘角色（`gloss`／`value`／`term`／一般 `label`）是**引用**，⛔ 不算長相 ——
#: 見 check_object_consistency 的 docstring。
_HEADLINE = ("lead", "section")

_NUMBERED = re.compile(r"^\s*\d+\s*[—–\-]\s")


def _fig_root(fp):
    try:
        return ET.parse(fp).getroot()
    except (ET.ParseError, OSError):
        return None


def _bare(el):
    return el.tag.rsplit("}", 1)[-1]


def _cls(el):
    return (el.get("class") or "").split()


def _role(el):
    c = _cls(el)
    for r in _ROLE_ORDER:
        if r in c:
            return r
    return "label" if "label" in c else "?"


def _txt(el):
    return " ".join("".join(el.itertext()).split())


def _rects(root):
    """回 [(x, y, w, h, class)]，只取形狀類的 `<rect>`（⛔ 不含 pill 那種裝飾）。"""
    out = []
    for el in root.iter():
        if _bare(el) != "rect":
            continue
        try:
            g = tuple(float(el.get(k, 0)) for k in ("x", "y", "width", "height"))
        except (TypeError, ValueError):
            continue
        out.append(g + ((el.get("class") or ""),))
    return out


def _container(rects, x, y):
    """包住 (x,y) 的**最小**矩形 —— 就是「這個字被畫在什麼裡面」。

    ⭐ 回的是**族＋語意色**（`box`／`grp`／`box-bad`／`grp-good`…），
    ⛔ **區別色（`-c1`~`-c6`）一律歸回它的族**（`box-c3` → `box`）。

    ## ⚠️ 為什麼區別色不能拿來比跨頁一致

    區別色是 renderer **自動配**的（名字雜湊，撞號時往後找沒被用掉的），
    ⭐ 它回答的是「這是這張圖裡並列的哪一個」，⛔ **不是「這個東西長什麼樣」**。
    同一個名字在兩張圖上可能因為**同圖的別人先佔走了那個色**而拿到不同色號 ——
    ⛔ 那不是跨頁不一致，是配色演算法的必然。拿它來比會製造**整批假陽性**，
    而假陽性會逼人去寫豁免，豁免一多這條檢查就退化成裝飾（N123 已經記過這個形狀）。

    ⭐ **真正該比的是「容器族」與「語意色」**：
    A1 把它畫成群（`grp`）、A3 畫成框（`box`）—— 那是設計差異，⭐ 該報；
    A1 是 `grp-c2`、A3 是 `grp-c5` —— 那是配色，⛔ 不該報。
    ⚠️ 語意色**照比**（`box-bad` vs `box-good` 仍然是兩種長相），
    那條由 `check_semantic_color()` 另外再擋一次。
    """
    best = None
    for rx, ry, rw, rh, c in rects:
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            a = rw * rh
            if best is None or a < best[0]:
                head = (c.split() or [""])[0]
                fam = _shape_family(head)
                if fam and re.match(r"^(box|grp)-c\d+$", head):
                    head = fam            # ⭐ 區別色歸回族，⛔ 不進比對
                best = (a, head)
    return best[1] if best else ""


#: ⭐ 形狀 class 的**族**（`box` 還是 `grp`），⛔ 不管它是哪一個色。
#: 2026-09-05 新增區別色 `box-c1`~`c6`／`grp-c1`~`c6`（使用者裁決：「block 都要上色，
#: 這樣才分的開」）之後，⚠️ **凡是硬寫 `("box","grp","box-bad",…)` 白名單的地方
#: 都會靜默漏掉那 12 個 class** —— 漏掉的後果不是報錯，是**檢查安靜地不算數**
#: （漏斗的段不見了 → narrowing 永遠過；群不見了 → partition 永遠過）。
#: ⭐ 所以白名單改成這一支，⛔ 不要再在別處自己列一份。
_SHAPE_RE = re.compile(r"^(box|grp)(-[a-z0-9]+)?$")


def _shape_family(cls):
    """`box-c3` → `box`；`grp-good` → `grp`；`pill`／`file-name` → None。"""
    head = (cls or "").split()
    if not head:
        return None
    m = _SHAPE_RE.match(head[0])
    return m.group(1) if m else None


def _stage_widths(rects):
    """把方框依 x 分欄，回每一欄的**代表寬度**（同欄取最大）——漏斗的每一跳。

    ⚠️ 分欄用 40px 容差：`_g8` 之後同一欄的 x 仍可能差幾個 px（A3 的 380 vs 400）。
    """
    cols = {}
    for x, _y, w, _h, c in rects:
        if not _shape_family(c):          # ⛔ 白名單改用 _shape_family（見它的註解）
            continue
        k = round(x / 40) * 40
        cols[k] = max(cols.get(k, 0), w)
    return [w for _k, w in sorted(cols.items())]


def _evidence(root):
    """一張圖上**看得見的**方向／幾何證據。⛔ 全部推導，不讀宣告。"""
    rects = _rects(root)
    arrows = sum(1 for el in root.iter() if "arrow" in _cls(el))
    numbered = sum(1 for el in root.iter()
                   if _bare(el) == "text" and _NUMBERED.match(_txt(el)))
    numbered += sum(1 for el in root.iter() if "num" in _cls(el))
    tones = {c.split()[0] for _x, _y, _w, _h, c in rects if c}
    # 共用軸：≥2 個方框的 (x, w) 完全相同（同一條垂直軸）或 (y, h) 相同（同一條水平軸）
    xs, ys = {}, {}
    for x, y, w, h, c in rects:
        xs[(x, w)] = xs.get((x, w), 0) + 1
        ys[(y, h)] = ys.get((y, h), 0) + 1
    shared_axis = max(list(xs.values()) + list(ys.values()) + [0])
    return {
        "arrows": arrows, "numbered": numbered, "tones": tones,
        "shared_axis": shared_axis, "stages": _stage_widths(rects),
        "groups": sum(1 for _x, _y, _w, _h, c in rects
                      if _shape_family(c)),
    }


#: 每種關係「看得見」長什麼樣。回 (過了嗎, 沒過的話該說什麼)。
#: ⛔ 判準逐字來自 HANDOFF 任務 6 的 L4-1，⚠️ **包含「編號」那一項** ——
#: `_chain_band` 的設計就是「順序靠編號不靠箭頭」，只認箭頭會否定 renderer 自己的排法。
def _relation_ok(rel, ev):
    if rel == "sequence":
        if ev["arrows"] >= 1 or ev["numbered"] >= 2:
            return True, ""
        return False, ("宣告了 sequence（A 之後是 B），但圖上**沒有任何方向記號**"
                       "—— 箭頭 0 個、編號 0 個。\n"
                       "           觀眾只能靠讀字重建順序，那就是排版沒有代替文字工作。\n"
                       "           出路擇一：畫箭頭（`LINK()`）、或每格加編號"
                       "（`steps[].num`，`_chain_band` 預設就有）")
    if rel == "narrowing":
        st = ev["stages"]
        if len(st) < 2:
            return True, ""                  # 只有一跳，沒有「變窄」可言
        bad = [(i, st[i - 1], st[i]) for i in range(1, len(st)) if st[i] > st[i - 1] + 8]
        if not bad:
            return True, ""
        return False, ("宣告了 narrowing（多 → 少），但**框寬沒有遞減**：\n"
                       f"           逐段寬度 {' → '.join(str(int(w)) for w in st)}\n"
                       + "".join(f"           ⛔ 第 {i} 跳反而變寬（{int(a)} → {int(b)}）\n"
                                 for i, a, b in bad)
                       + "           漏斗的「少」只有靠**寬度**說得出來；"
                         "寬度不遞減就只是幾欄清單，宣告與畫面互相否定")
    if rel == "compare":
        if ev["shared_axis"] >= 2:
            return True, ""
        return False, ("宣告了 compare（幾個對象 × 幾個指標），但**沒有共用軸**"
                       "—— 沒有任何兩個方框對齊在同一條 x 或 y 上。\n"
                       "           不共用軸就比不了：觀眾得自己在心裡對齊兩邊")
    if rel == "correspondence":
        if ev["arrows"] >= 1:
            return True, ""
        return False, ("宣告了 correspondence（左邊每一項對到右邊某一項），"
                       "但圖上**一條連線都沒有**。\n"
                       "           對應關係只有靠線畫得出來；沒有線就是兩張並排的清單")
    if rel == "partition":
        if ev["groups"] >= 2:
            return True, ""
        return False, ("宣告了 partition（整體拆成幾群），但圖上**分不出兩群以上**"
                       "的容器（`grp`／`box`）。\n"
                       "           分群只有靠**容器或留白**看得出來")
    if rel == "transform":
        if len(ev["tones"] & {"box-bad", "box-good", "box-null", "box-ctl"}) >= 1 \
                or ev["arrows"] >= 1:
            return True, ""
        return False, ("宣告了 transform（A 經過某個操作變成 B），但圖上"
                       "**看不出前後**：既沒有分類色（box-bad／good）也沒有箭頭。\n"
                       "           「變成」是有方向的，方向要畫得出來")
    return True, ""                          # containment／distribution：這份 deck 沒用到


def check_relation_evidence(deck_path, slides):
    """⭐ **構圖宣告了什麼關係，就必須看得到那個關係**（任務 6 L4-1）。

    ## 為什麼要有這條

    實測（任務 4 完成後的 7 張圖）：`A3_selection_funnel.svg` 宣告
    `relation: narrowing`／`comp: funnel_named`，實際框寬是
    **360 → 710 → 300×3** —— ⛔ 不但沒變窄，還先變寬再分叉。
    **宣告了漏斗，畫出來是三欄清單。**

    ⭐ 宣告與畫面互相否定時，**吃虧的是觀眾**：他讀到的是圖，不是 JSON。

    ## ⚠️ 「方向記號」包含編號，⛔ 不是只認箭頭

    HANDOFF 的 L4-1 原文寫的是「箭頭／**編號**／明確的左→右節奏」，
    而 HANDOFF 自己給的驗收條件卻寫成「A2 的箭頭數 > 0」——
    ⛔ **那兩句互相否定，而錯的是後者。**

    實測：`A2_scan_chain.svg` 箭頭 0 個，但三條橫幅的標題是
    `1 — extract_transcript.py`／`2 — .data/_cursor.json`／`3 — signals.py → signals.md`
    —— ⭐ **它有方向記號，只是用編號**。而 `_chain_band()` 的 docstring 第一行就寫著
    「全寬橫幅版：每格自己一條，**順序靠編號不靠箭頭**」：全寬橫幅上下相疊，
    中間根本沒有畫箭頭的間隙。

    ⛔ **只認箭頭 = 逼 renderer 在自己刻意不留的位置上硬塞一個記號**，
    那是為了滿足量尺而改畫面，不是為了觀眾。⭐ 這與 6c 那條
    「一頁金色下限是 1」是同一種錯：**規則否定自己的產物時，錯的是規則。**

    ## 反方向（N56）：這條會把 builder 推去哪裡

    | 反方向的失效 | 擋法 |
    |---|---|
    | 為了過關硬加箭頭／編號，卻不是真的有順序 | 那是**語意**問題，由 `composition-vocabulary` Step ② 的守門提問擋（「前一格的產出，是不是後一格的輸入？」）—— ⛔ 這條只管「宣告的東西看不看得見」，不管宣告對不對 |
    | 為了過關把 `relation` 改成比較好過的那一種 | `relation` 決定 `comp`，`comp` 決定 renderer；改了關係圖會整張換掉，⛔ 不是一個便宜的出口 |
    | 漏斗為了遞減把後段硬縮，內容壓字 | 壓字有 `_blocks_fit()` 的 `sys.exit`（N94 修過）在擋 |

    ## 具名豁免

    manifest 的 figure 條目可寫 `relation_exempt: {"reason": ..., "until": ...}`。
    ⛔ **reason 空白不算豁免**（照樣 ERROR）—— 否則它會退化成萬用出口。
    ⚠️ 每一條豁免都會發 WARN，⭐ **債務是吵的，規則對其他人是硬的**。
    """
    found, _new_dir, _out_dir = _manifest_paths(deck_path)
    if not found:
        return
    d = os.path.dirname(os.path.abspath(deck_path))
    rel_of = {s.get("id"): (s.get("composition") or {}).get("relation")
              for s in slides if isinstance(s, dict)}
    for mp, _legacy_loc in found:
        name = os.path.basename(mp)
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError):
            continue                          # check_manifest 已經報過
        for e in (j.get("figures") or j.get("compositions") or []):
            if not isinstance(e, dict):
                continue
            sid, rel_f = e.get("slide"), (e.get("file") or e.get("figure"))
            rel = rel_of.get(sid)
            if not (rel and rel_f):
                continue
            root = _fig_root(os.path.join(d, rel_f))
            if root is None:
                continue                      # check_manifest 已經報過
            ok, msg = _relation_ok(rel, _evidence(root))
            if ok:
                continue
            ex = e.get("relation_exempt") or {}
            reason = str(ex.get("reason") or "").strip() if isinstance(ex, dict) else ""
            if reason:
                warn(name, f"{sid}: ⚠️ 關係證據**具名豁免中**（relation={rel}）"
                           f"—— {reason}\n"
                           f"           解除條件：{ex.get('until') or '（沒寫，⛔ 請補）'}\n"
                           f"           ⛔ 豁免不是修好了，它只是把債務寫在看得見的地方")
                continue
            err(name, f"{sid}: {msg}\n"
                      f"           → composition-vocabulary.md Step ②"
                      f"（構圖宣告了什麼關係，就必須看得到那個關係）")


# ── L4-2 同一個東西每頁長得一樣（任務 6d）─────────────────────────────────────
def check_object_consistency(deck_path):
    """⭐ **同一個物件，在每一頁上要長得一樣**（任務 6 L4-2）。

    ⭐ **跨頁不一致是「精細度」感受的最大殺手 —— 觀眾會以為那是不同的東西。**

    ## ⭐ 外觀是**推導**的，⛔ 不是宣告的（裁決記錄：FINDINGS N123）

    HANDOFF 原本建議「把 `objects` 的散文升成三個結構化欄位（形狀／顏色角色／位置）
    並機械比對」。⛔ **否決**，兩個致命理由：

    1. **比對宣告 ≠ 比對畫面**。兩頁都宣告 `shape:"box"` 就過關，
       而 SVG 裡一個是 `grp` 一個是 `box` 也照樣過 —— ⭐ **檢查可以靠改帳本滿足，
       不必改圖**，那就是裝飾。
    2. **它是同一個事實的第二份手抄本，而手抄本一定會漂**（N14 已經記過同型的）。

    ⭐ 三件外觀事實**全部推得出來**，而且是 **6a／L0 那一批讓它變得可能的**：

    | 事實 | 推導自 |
    |---|---|
    | 顏色角色 | `<text>` 的 `class`（`lead`／`section`／`term`／`gloss`／`num`／`value`）—— L0 把它收斂成單一來源之前，這些值散在 inline style 裡，推不出來 |
    | 形狀 | 包住它的**最小** `<rect>` 的 class（`box`／`grp`／`box-bad`／…） |
    | 位置 | `x`／`y` |

    帳本只需要宣告**唯一推不出來的那一件**：⭐ **身分** ——
    「A3 的 `daily · .html` 跟 A1 的 `daily · .html · .md` 是同一個東西」。
    那是語意，字串比對永遠追不到。→ `shared_terms[].aka`

    ## ⭐ 「長相」只看**標題型**出現，⛔ 不看引用

    ⚠️ 第一版把所有出現都拿來比，量到 3 組不一致，**其中 2 組是誤判**：
    `candidates.py` 在 A1／A3 是框名（`lead`），在 A2 是 key/value 列的
    **value**（`gloss`）—— 那不是「長得不一樣」，那是**同一個東西被引用到**。

    ⭐ 定義：物件的長相 = 它**被介紹**的那一則（`lead`／`section`）。
    其餘（`gloss`／`value`／`term`／一般 `label`）是**指到它的引用**，⛔ 不比。
    收斂後 3 組誤判剩 1 組真發現。

    ## 反方向（N56）

    | 反方向的失效 | 擋法 |
    |---|---|
    | 逼「所有頁一律同一種外觀」→ 合法的角色轉換被誤殺 | ① 只比標題型出現（上面那段）② `role_exempt` 具名豁免＋**必填理由** |
    | 豁免變成萬用出口 | 豁免逐字串、每條發 WARN，⭐ 數字漲了看得見 |
    | 短字串亂命中（`10`／`x` 對誰都命中） | **< 4 字元不比對** —— ⛔ N111② 已經在 `check_manifest` 踩過一模一樣的坑 |
    """
    d = os.path.dirname(os.path.abspath(deck_path))
    figs_dir = os.path.join(d, "figures")
    if not os.path.isdir(figs_dir):
        return
    # ① 掃出每一則標題型 <text> 的推導長相
    occ = {}
    for fp in sorted(glob.glob(os.path.join(figs_dir, "*.svg"))):
        root = _fig_root(fp)
        if root is None:
            continue
        page = os.path.basename(fp).split("_")[0]
        rects = _rects(root)
        for el in root.iter():
            if _bare(el) != "text":
                continue
            r = _role(el)
            if r not in _HEADLINE:
                continue                      # 引用不算長相（見 docstring）
            s = _txt(el)
            if len(s) < 4:
                continue                      # N111②：短字串對誰都命中
            try:
                x, y = float(el.get("x", 0)), float(el.get("y", 0))
            except (TypeError, ValueError):
                x = y = 0.0
            occ.setdefault(s, []).append((page, r, _container(rects, x, y)))
    # ② 讀帳本的**身分**宣告（aka）與具名豁免（role_exempt）
    aka, exempt, srcname = {}, {}, {}
    found, _nd, _od = _manifest_paths(deck_path)
    for mp, _l in found:
        name = os.path.basename(mp)
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for term, v in (j.get("shared_terms") or {}).items():
            if not isinstance(v, dict):
                continue                      # 舊寫法（散文字串）：認得，不報錯
            for _pg, s in (v.get("aka") or {}).items():
                aka[str(s)] = term            # 各頁實際字串 → 登記名
            srcname[term] = name
            for pg, why in (v.get("role_exempt") or {}).items():
                if str(why).strip():
                    exempt.setdefault(term, {})[str(pg)] = str(why).strip()
    # ③-0 ⭐ **同一頁累積 ≥3 條具名豁免 → 那不是三次巧合，是規則之間的張力**（6e 裁決 ①）
    #
    # 實測：`daily · .html`／`.data · .json`／`candidates.py` 三條 role_exempt **全在 A3**，
    # 而且形狀完全一樣 —— L4-1（narrowing 要寬度遞減／判準不畫框）逼出容器差異
    # → L4-2（同名物件跨頁要長得一樣）報不一致 → 具名豁免。
    #
    # ⛔ **裁決是「維持逐條具名，不自動放行」**：讓 L4-2 自動認得 L4-1 的約束
    # 就是 N123 警告的「萬用出口」—— 一旦 L4-2 學會替自己找理由，它就再也擋不住
    # 真正的跨頁不一致（⭐ 那正是 `spec_reviewed` 退化的同一條路）。
    # ⚠️ 但**逐條具名的代價是債會默默長大**：三條各自都有好理由，看不出它們是同一件事。
    # 所以這裡不放行、也不擋，⭐ 只做一件事：**把「同型」本身變成看得見的**。
    by_page = {}
    for term, v in exempt.items():
        for pg in v:
            by_page.setdefault(str(pg), []).append(term)
    for pg, terms in sorted(by_page.items()):
        if len(terms) >= 3:
            warn("compositions",
                 f"{pg} 一頁累積了 **{len(terms)} 條**具名豁免"
                 f"（{'、'.join('「%s」' % t for t in sorted(terms))}）——\n"
                 f"           ⭐ 同一頁上三條同型的豁免**不是三次巧合**，"
                 f"是兩條規則在互相拉扯（L4-1 的寬度遞減 vs L4-2 的跨頁一致）。\n"
                 f"           ⛔ 不要靠再寫一條豁免收掉它，⛔ 也不要讓 L4-2 自動放行"
                 f"（那就是 N123 說的萬用出口，會讓 L4-2 再也擋不住真的不一致）。\n"
                 f"           ⭐ 這條要的是**記帳**：張力升到這個量就該進 FINDINGS "
                 f"當一條規則衝突處理，⛔ 不是繼續一條一條豁免下去。")

    # ③ 依登記名合併同一個物件的各種寫法，再比長相
    groups = {}
    for s, hits in occ.items():
        groups.setdefault(aka.get(s, s), []).extend((p, r, c, s) for p, r, c in hits)
    for term, hits in sorted(groups.items()):
        pages = {p for p, _r, _c, _s in hits}
        if len(pages) < 2:
            continue
        ex = exempt.get(term, {})
        live = [h for h in hits if h[0] not in ex]
        sig = {(r, c) for _p, r, c, _s in live}
        for pg, why in sorted(ex.items()):
            if pg in pages:
                warn(srcname.get(term, "compositions"),
                     f"「{term}」在 {pg} 的外觀**具名豁免中** —— {why}\n"
                     f"           ⛔ 豁免不是一致了，它只是把判斷寫在看得見的地方")
        if len(sig) < 2:
            continue
        detail = "".join(
            f"           · {p}：{s!r} → 角色 {r}／容器 {c or '（無）'}\n"
            for p, r, c, s in sorted(live))
        err(srcname.get(term, "compositions"),
            f"「{term}」在不同頁上**長得不一樣**：\n" + detail
            + "           ⭐ 觀眾會以為那是不同的東西 —— 跨頁不一致是"
              "「精細度」感受的最大殺手。\n"
            + "           出路擇一：① 兩邊改成同一種畫法　"
              "② 若這是**刻意**的角色轉換，寫 shared_terms 的 role_exempt"
              "（⛔ 必須寫理由）\n"
            + "           ⚠️ 外觀是從 SVG **推導**的（class ＋ 包住它的 rect），"
              "⛔ 改帳本改不掉它 → FINDINGS N123")


def check_markers(deck_path):
    """`figures/*.svg` 的 marker：單位一定要寫死，共用 id 的幾何一定要全 deck 一致。

    ## 坑 1：`markerUnits` 預設是 `strokeWidth`（逐檔，ERROR）

    沒寫 `markerUnits` 時，箭頭實際大小 = `markerWidth × stroke-width`。
    **首次實跑那份 deck 的 4 張圖全部中招**：寫 `markerWidth="8"`（想要 8px），
    而 `deck.css` 有 `svg .arrow{stroke-width:3}`／`.arrow-hl{stroke-width:4}`
    → 渲染出來是 **24px 與 32px 的巨大三角形壓字**，「靠微調座標永遠修不好」。
    判準見 `diagram-craft.md §2` 坑 1。

    ## 坑 2：`#a`／`#ah` 是**全域**的（跨檔，ERROR）

    所有圖都內嵌在同一份 `deck.*.html` 裡，同 id 重複定義時瀏覽器只認**第一個**。
    所以任一張手寫圖改了 `#a` 的幾何，**整份 deck 的箭頭跟著變**，
    而那張圖自己看起來是對的 —— ⭐ 這是**逐線 builder 結構上守不住**的形狀
    （它只看得到自己那條線的圖），所以只能機械擋。

    ## 為什麼是 ERROR 不是 WARN（N56 的反方向）

    反方向的失效是「誤報擋住合法的自訂箭頭」。⛔ 不會發生：
    自訂形狀的正解本來就是**換一個獨一無二的 id**（`diagram-craft.md §2` 明文），
    而這條只比對 `a`／`ah` 這兩個**被 `deck.css` 指名**的 id。
    `markerUnits` 那半更沒有第二種寫對的方式 —— renderer 產的圖全部已經帶著它。
    """
    d = os.path.join(os.path.dirname(os.path.abspath(deck_path)), "figures")
    if not os.path.isdir(d):
        return
    geo = {}                            # id -> {幾何簽章: [檔名]}
    for fp in sorted(glob.glob(os.path.join(d, "*.svg"))):
        name = os.path.basename(fp)
        for mid, at in _markers_of(fp):
            if at.get("markerUnits") != "userSpaceOnUse":
                err(name, f"<marker id=\"{mid}\"> 沒寫 "
                          f"markerUnits=\"userSpaceOnUse\"（現在是 "
                          f"{at.get('markerUnits') or '沒寫，預設 strokeWidth'}）——\n"
                          f"           箭頭實際大小會變成 markerWidth × stroke-width，"
                          f"deck.css 的 .arrow 是 3、.arrow-hl 是 4，\n"
                          f"           於是 markerWidth=\"8\" 渲染成 24／32px 的三角形壓字"
                          f"（實測：首次實跑 4 張圖全中招）。\n"
                          f"           ⛔ 靠微調座標修不好，見 diagram-craft.md §2 坑 1。")
            if mid in SHARED_MARKERS:
                sig = tuple((k, at.get(k)) for k in MARKER_GEO)
                geo.setdefault(mid, {}).setdefault(sig, []).append(name)
    for mid, sigs in sorted(geo.items()):
        if len(sigs) < 2:
            continue
        lines = "\n".join(
            "           · " + "、".join(f"{k}={v}" for k, v in sig if v is not None)
            + f"　←　{'、'.join(files)}" for sig, files in sigs.items())
        err("figures", f"<marker id=\"{mid}\"> 的幾何在各圖之間**不一致**"
                       f"（{len(sigs)} 種寫法）——\n" + lines + "\n"
                       f"           ⚠️ 所有圖內嵌在同一份 deck.*.html，同 id 只認"
                       f"**第一個**：那張圖自己看起來對，其餘全被它蓋掉。\n"
                       f"           統一成同一組幾何；真的要自訂形狀就**換一個獨一無二的 "
                       f"id**，⛔ 不要改 a／ah（diagram-craft.md §2）。")


def check_semantic_color(deck_path, slides):
    d = os.path.dirname(os.path.abspath(deck_path))
    seen = {}                          # 字串 -> {語氣: [圖檔名]}
    for s in slides:
        rel = (s.get("body") or {}).get("src") or ""
        if not rel.lower().endswith(".svg"):
            continue
        fp = os.path.join(d, rel)
        if not os.path.isfile(fp):
            continue
        for t, tone in _tone_of_svg(fp).items():
            seen.setdefault(t, {}).setdefault(tone, []).append(os.path.basename(rel))
    for t, tones in sorted(seen.items()):
        meaning = {k: v for k, v in tones.items() if k in ("good", "bad")}
        where = "；".join(f"{k}＝{'、'.join(sorted(set(v)))}" for k, v in sorted(tones.items())
                          if k != "plain")
        if len(meaning) > 1:
            err(t[:28], f"同一個名字在不同圖上帶著互相衝突的語意色：{where}\n"
                        f"           §5「一個顏色一種意思」—— good 與 bad 是對這個東西"
                        f"本身的評價，同一個東西不能一頁好一頁壞。\n"
                        f"           要表達「改之前／改之後」就給它兩個不同的名字")
        elif meaning and "hl" in tones:
            warn(t[:28], f"同一個名字同時帶著評價色與重點色：{where}\n"
                         f"           金色的意思是「這一頁要你看的東西」，"
                         f"跟 good／bad 混在同一個名字上，讀者會把金讀成第三種評價")


# ── 帶單位的數字（後補，FINDINGS G1 ← presentation_rules §2c-2）──────────────
# §2c-2 逐字點名了一批「該被砍掉的標籤」（佐證性的規格數字、旁支的統計），
# 規格寫對了**但沒有任何角色在執行** —— 本次實跑那兩組被點名的標籤
# （`420 / 395-609 words per item`、`2 sessions · 745 turns · 447 KB`）又回到版面上。
# 機械代理：**帶單位的數字**幾乎都是量測值。它如果既不在這頁的 must_numbers
# （planner 指定「一定要出現」的），也不在 point（這頁的重點）裡，
# 多半就是那種「正確但沒有人在乎」的佐證數字 → 進 notes，不進版面。
# ⛔ **一律 WARN，不做成 ERROR**：規則本身就常帶單位（「100-300 words」是判準的一部分），
#    偽陽性一定有。這條要的是「出聲」，不是擋人。
UNIT_NUM = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(%|KB|MB|GB|TB|kB|ms|min\b|hours?\b|days?\b|"
    r"words?\b|chars?\b|characters?\b|files?\b|items?\b|lines?\b|rows?\b|"
    r"pages?\b|messages?\b|turns?\b|sessions?\b|tools?\b|tokens?\b|"
    r"packages?\b|candidates?\b|threads?\b|slides?\b|commits?\b)", re.I)


def number_on_page(blob, want):
    """`want` 這個數字有沒有真的畫在這一頁上（含 SVG 的 <text>）。

    ⭐ **這是唯一的定義**（N117 ①）：`check_gate.py` 的 layer3 對帳
    （`check_must_numbers()`）問的是同一個問題，⛔ 不要在那邊再寫一份 ——
    兩份必定分岔，而分岔的後果是「一支說畫了、另一支說沒畫」。

    ⚠️ 逗號兩邊都normalize：來源可能寫 `1,024`、頁上寫 `1024`（或反過來），
    那是同一個值。⛔ 但**不做**中文數字轉換：那是 `zh_num` 的事，
    而這條的呼叫端（反查／對帳）先寬（WARN）就是為了容忍這類書寫差異。
    """
    w = str(want).strip()
    return w in blob or w.replace(",", "") in blob.replace(",", "")


def dropped_map(s):
    """這一頁**具名宣告砍掉**的 `must_numbers`（N117 ①）：number → 該則紀錄。

    ⚠️ 形狀不對（不是 list／不是 dict／沒有 number）一律**當成沒宣告** ——
    ⛔ 不要在這裡吞掉或報錯：形狀的門在 `check_gate.py` 的 layer3
    （那裡有 layer2 那一邊可以對帳），這裡只負責讀。
    """
    out = {}
    for d in (s.get("must_numbers_dropped") or []):
        if isinstance(d, dict) and str(d.get("number") or "").strip():
            out[str(d["number"]).strip()] = d
    return out


def check_unit_numbers(deck_path, s, sid):
    blob = " ".join(list(texts(s))) + " " + svg_text_only(deck_path, s)
    keep = set(str(x) for x in (s.get("must_numbers") or []))
    pt = (s.get("point") or "") + " " + (s.get("user_point") or "")
    bad = []
    for m in UNIT_NUM.finditer(blob):
        n = m.group(1)
        if n in keep or n.replace(",", "") in {x.replace(",", "") for x in keep}:
            continue
        if n in pt:
            continue
        bad.append(m.group(0).strip())
    # ── N101 (b)（批次 5g）：**反查** —— `must_numbers` 以前只被當豁免清單用，
    #    沒有任何地方問「使用者在關卡② 指名要出現的 96%，到底畫了沒」。
    #    關卡② 指定、builder 沒畫 → **零報**。
    #    ⚠️ 先寬（WARN）：數字可能以不同書寫系統出現，逐字比對會誤報。
    # ── N117 ①：砍掉要留痕 —— 已具名宣告的印**具名 WARN**，⛔ 不是消音。
    #    ⭐ 比照 `wont_fix`／`role_exempt`：宣告了 WARN 數**不會變小**，
    #    所以「宣告一下就沒事了」買不到任何東西（那正是 `spec_reviewed` 退化的原因）。
    #    ⚠️ 這裡一律 WARN。真正會擋的是 `check_gate.py` layer3 的對帳
    #    ——只有那裡看得到 `layer2.<線>.json`，也才分得出「砍了沒記」與「根本沒宣告過」。
    _dropped = dropped_map(s)
    for want in sorted(keep):
        if number_on_page(blob, want):
            if want in _dropped:
                warn(sid, f"must_numbers 的「{want}」**宣告砍掉了、卻畫在這一頁上** ——\n"
                          f"           理由寫的是：{str(_dropped[want].get('why') or '')[:70]}\n"
                          f"           ⛔ 兩者只能有一個為真：真的畫了就把這則 "
                          f"must_numbers_dropped 拿掉（關卡 layer3 會擋）")
            continue
        if want in _dropped:
            warn(sid, f"must_numbers 的「{want}」**沒畫，具名記錄中** —— "
                      f"{str(_dropped[want].get('why') or '')[:70]}\n"
                      f"           搬到：{str(_dropped[want].get('where') or '')[:50]}\n"
                      f"           ⛔ 砍掉不是畫上去了，它只是把判斷寫在看得見的地方")
            continue
        warn(sid, f"must_numbers 指名要出現的「{want}」**這一頁上找不到** —— "
                  f"那是使用者在關卡② 指定的數字。\n"
                  f"           畫上去，或依 §2c-2 寫進 `must_numbers_dropped` 具名留痕"
                  f"（⛔ 不要自己從 must_numbers 刪掉它）。")
    if bad:
        uniq = sorted(set(bad))
        warn(sid, f"{len(uniq)} 個帶單位的數字既不在 must_numbers 也不在 point 裡："
                  f"{'、'.join('「%s」' % x for x in uniq[:8])}"
                  + ("…" if len(uniq) > 8 else "") + "\n"
                  f"           §2c-2：逐個問「聽眾看到這個會拿它做什麼？」"
                  f"答不出來就搬進 notes（佐證性的規格數字與旁支統計是版面複雜度最大的來源）。\n"
                  f"           它真的是重點就寫進 point／must_numbers，這條就不會再叫")


def print_limits():
    """把「規格的權威在程式裡」那些數字**印出來** —— 讓 agent 不必讀原始碼去核對。

    B17-2 的實跑：協調者憑 SKILL.md 推錯了 `SLOT_EXEMPT`，planner 為了核對去讀了
    整支 check_deck.py（214 KB）。這一支印出來的東西就是它要核對的全部。
    ⛔ 這裡只印常數，不解釋規則 —— 規則在 references/，數字在這裡，兩邊不重抄。
    """
    print("# check_deck.py 的門檻與豁免（唯一定義；⛔ 不要抄進文件，要用就指路到這個指令）")
    print("\n## 版型容量上限 LIMITS（ERROR）")
    for k, v in LIMITS.items():
        print(f"  {k:<12} {v}")
    print("\n## 版型容量下限 MINS（WARN）")
    for k, v in MINS.items():
        print(f"  {k:<12} {v}")
    print("\n## 頁數")
    print(f"  MAX_MAIN        {MAX_MAIN}   全場主線內容頁上限（backup／結構頁不計）")
    print(f"  MAX_PER_THREAD  {MAX_PER_THREAD}    單線內容頁上限；LIMITS['agenda'] 由它推導")
    print(f"  MIN_MAIN        {MIN_MAIN}    主線內容頁下限（WARN）")
    print("\n## 豁免與分類")
    print(f"  STRUCT          {sorted(STRUCT)}   結構頁：不進承接鏈、不算內容頁、不對 user_point")
    print(f"  SLOT_EXEMPT     {sorted(SLOT_EXEMPT)}   這些 slot 的頁豁免「一頁對一條 user_point」，但要填 slot_reason")
    print(f"  TEXT_ONLY       {sorted(TEXT_ONLY)}   文字主體版型：必須有 why_text")
    print(f"  SLIDE_PLAN_BODIES {[b for b in SLIDE_PLAN_BODIES if b]}   plan.slide_plan[].body 的合法值")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", nargs="?")
    # default=None 延後解析：使用者明確給了 --data 時，不會因為設定沒設好而先掛掉。
    ap.add_argument("--data", default=None,
                    help="日誌 .data 目錄（預設由 scripts/paths.py 解析）")
    ap.add_argument("--limits", action="store_true",
                    help="印出所有門檻與豁免清單（LIMITS／MINS／頁數上限／SLOT_EXEMPT／"
                         "結構頁／slide_plan 合法 body）後結束。⭐ 要核對某個數字用這個，"
                         "⛔ 不要讀原始碼（214 KB 進 context 就是一整場的錢）")
    a = ap.parse_args()
    if a.limits:
        print_limits()
        return
    if not a.deck:
        ap.error("要給 deck.json（或用 --limits 看門檻）")

    deck = json.load(open(a.deck, encoding="utf-8"))
    slides = deck.get("slides", [])
    if not slides:
        sys.exit("[check] deck.json 沒有 slides")

    # ---- 0. plan：選材與敘事的決策留檔 ----
    # 舊 skill 的第一原則：「全記，不刪」——「不講」的實作是「去處 + 理由」，不是默默消失。
    # 被篩掉的東西加上理由，正是判準未來自我修正的材料。
    plan = deck.get("plan") or {}
    ans = plan.get("answers") or []
    if len(ans) < 3:
        err("plan", "缺 plan.answers —— layer1 關卡① 的複習與提問**不可跳過**"
                    "（SKILL.md「然後停下來問」那一節；N104：舊訊息指的 Step 2 不存在）。"
                    "把問使用者的問題與他的**原話**逐字存進 answers（至少 3 題）。\n"
                    "           那些答案只有他答得出來：教授交代了什麼、哪些不想展開、"
                    "事情之間有沒有因果關係")
    for i, x in enumerate(ans, 1):
        if not str(x.get("a", "")).strip():
            err("plan", f"answers 第 {i} 題沒有答案——沒問到就不要往下做")
        if not str(x.get("q", "")).strip():
            err("plan", f"answers 第 {i} 題沒有問題文字")
    if plan.get("narrative") and not plan.get("narrative_source"):
        err("plan", "缺 plan.narrative_source —— 要寫明那句敘事是怎麼來的"
                    "（使用者自己寫的／由他哪幾題的答案組出並經他確認）")
    # ── N78：兩個「有硬規則背書、卻沒有生產者」的欄位，補上機械的那一半 ──
    #    ⚠️ 兩條都是 **WARN**（B3「先寬」）：它們要的是**留痕**，不是擋交付 ——
    #    真正寫得出內容的只有使用者與協調者，機械只能問「有沒有寫」。
    #    ⛔ 反方向（N56）：升成 ERROR 會逼 agent 去**代填**，而 rebuttals 代填出來的
    #    「教授最可能的反駁」正好是這份 skill 唯一的對抗性自檢裡最沒有價值的東西。
    if not (plan.get("narrative_candidates") or []):
        warn("plan", "缺 plan.narrative_candidates —— `editorial_policy §0` 是硬規則："
                     "**agent 先列候選一句話清單，讓使用者寫敘事**。\n"
                     "           少了它，關卡① 那一步就沒有留痕（下週看不出那句敘事"
                     "是從哪幾條 headline 收斂來的）。\n"
                     "           寫法：把每日 headline 逐條列進來，⛔ 不要自己先挑一句。")
    if not (plan.get("rebuttals") or []):
        warn("plan", "缺 plan.rebuttals —— 這是本 skill **唯一的對抗性自檢**"
                     "（`{claim, rebuttal, answer}`：教授最可能的反駁，用他的口吻）。\n"
                     "           擋不住那個反駁就回頭改主張 —— ⛔ 那件事要在上台前做，"
                     "不是在台上做。")
    for i, f in enumerate(plan.get("feedback") or [], 1):
        if "criterion_wrong" not in f:
            warn("plan", f"feedback 第 {i} 則沒標 criterion_wrong —— "
                         f"**判準錯了**（下次一定再犯，要提議改 references/）"
                         f"還是**本次特例**（記著就好）？\n"
                         f"           ⚠️ 機械只驗這個布林有沒有標；"
                         f"「該不該改判準」由使用者確認，⛔ agent 不得自己改。")
    # 逐項確認表：今天的返工分析顯示，會每週重來的只有「去處／份量／呈現方式」三件，
    # 而三件都是逐項的。抽象問題擋不掉，一張逐項表才擋得掉。
    splan = plan.get("slide_plan") or []
    if not splan:
        err("plan", "缺 plan.slide_plan —— layer2 關卡② 的逐頁表：把主線清單逐項列給使用者確認"
                    "（講什麼｜幾頁｜主體用圖還是表｜一定要出現的數字），改完才寫 deck.json")
    if splan and not plan.get("slide_plan_confirmed"):
        err("plan", "plan.slide_plan 尚未經使用者確認（slide_plan_confirmed 未設為 true）")
    for i, x in enumerate(splan, 1):
        miss = [k for k in ("point", "pages", "body") if not x.get(k)]
        if miss:
            err("plan", f"slide_plan 第 {i} 項缺欄位：{'、'.join(miss)}")
        # B17-7：`example` 是現役且最常用的版型（`example_first` 就是在推它），
        # deck_schema.md 早就列了，這裡的白名單漏掉 → 照文件填必被擋。
        # ⛔ 唯一定義是 SLIDE_PLAN_BODIES，⛔ 不要在訊息裡另抄一份清單。
        if x.get("body") not in SLIDE_PLAN_BODIES:
            err("plan", f"slide_plan 第 {i} 項的 body「{x.get('body')}」不是可用的主體型態"
                        f"（可用：{'、'.join(b for b in SLIDE_PLAN_BODIES if b)}）")

    if not plan.get("narrative"):
        err("plan", "缺 plan.narrative（本週敘事一句話）—— 這句由**使用者**寫，不是 agent 擬。"
                    "先定敘事再選材，判錯後面全錯")
    if plan.get("mode") not in ("single", "multi"):
        err("plan", "plan.mode 要填 single 或 multi（串不成一條線就誠實分兩條，不要硬凹）")
    # ⚠️ N106 ②：`plan.example_first` 沒開時，check_example() 的三組 ERROR
    #    （example.* 必填、mechanism 必用全寬版型、body.aside 已作廢）**整組不跑**，
    #    而那個鍵只在 plan 裡出現一次、沒有任何地方要求它存在。
    #    ⛔ 不升成必填：它本來就是為了讓**既有、已交付的歷史週報**仍可被檢查而設的旗標。
    if not plan.get("example_first"):
        warn("plan", "plan.example_first 沒有開 —— example.* 必填、mechanism 頁必用全寬"
                     "版型、body.aside 已作廢**三組 ERROR 整組不跑**。\n"
                     "           新產物一律要 true（layer2 範本已內建）；"
                     "這是舊週報才有的豁免")
    if not plan.get("terms", {}).get("core_metric"):
        warn("plan", "沒有凍結核心指標名稱 —— 沒先凍結會反覆改，"
                     "每次都要回頭改所有表格")

    # ---- 0b. 每個日誌 item 都要有去處 ----
    used = {x for s_ in slides for x in (s_.get("source") or [])}
    dropped = {d.get("source"): d for d in plan.get("dropped", []) if d.get("source")}
    for d in dropped.values():
        if not d.get("where"):
            err("plan", f"dropped 項缺 where（backup／口頭／不講）：{d.get('source')}")
        if not d.get("why"):
            err("plan", f"dropped 項缺 why —— 沒有理由的篩除無法回頭檢討：{d.get('source')}")

    # ---- 0d. user_points 對帳（後補，第 13 條硬性規定）----
    # 為什麼要機械檢查：規格早就寫著「每頁都要對得上一個 user_point」，
    # 但首次實跑實測——規格寫了、planner 沒照做，七頁裡只有兩頁對得上使用者要講的。
    # SKILL.md 自己有一條「不要靠自我宣稱，一律跑檢查程式」，這裡就是它的實作。
    for t in deck.get("threads", []):
        tid = t.get("id")
        ups = t.get("user_points") or []
        tslides = [x for x in slides if x.get("thread") == tid and not x.get("backup")
                   and not is_struct(x)]
        if not tslides:
            # ⚠️ 後補（FINDINGS N102）：**最嚴重的那個失效，恰好是唯一抓不到的**。
            #    原本是 `continue` —— 一條線一頁都沒有時，這條線的對帳整段跳過：
            #    所有 user_points 一條都不報、一個字都不印、不影響 exit code。
            #    而「某條主線整條沒有頁」（builder 漏交、merge_slides 沒併到、
            #    檔名寫錯）正是最該被說出來的情形。
            # ⛔ 裁決（2026-09-05，「先寬」）：**WARN 不是 ERROR**。
            #    協調者在 builder 交件**之前**跑 check_deck 是正常節奏（N61 的骨架提前
            #    就是為了這件事），升成 ERROR 會讓那個節奏每次都紅。
            # ⚠️ 反方向（N56）：WARN 擋不住「就這樣交出去」。擋它的是關卡三
            #    （`check_gate.py layer3` 要求每條線都有 slides.<線>.json）與
            #    slide_plan 的頁數對帳（說好 N 頁、實際做出 M 頁 → 那條是 ERROR）。
            warn("plan", f"線「{tid}」一頁都沒有 —— 這條線的 user_point 對帳"
                         f"（每頁對得上一個點、每個點都有頁、一點一頁、頁序）"
                         f"**整段跳過**，{len(ups)} 條 user_points 一條都沒有被驗。\n"
                         f"           builder 還沒交件就是正常的；已經交件了就去看"
                         f"是不是漏併（merge_slides.py）或線的 id 寫錯了")
            continue
        if not ups:
            err("plan", f"線「{tid}」沒有 user_points —— 關卡① 漏問了「這條線只講 3~4 個"
                        f"重點是哪幾個」。⛔ 不得由 agent 代擬：那句話是誰寫的，"
                        f"就決定了這條線會講什麼")
            continue
        # ⭐ `method` 以外的格是**支撐結構**，不是使用者指定要講的重點，
        #    所以豁免 (a)(b2) 的 user_point 綁定 —— 但必須填 slot_reason 說出
        #    是哪個觸發成立（result：有量到的數值；介紹：一行解釋不完）。
        #    ⛔ 不填就擋，否則「豁免」會變成繞過 user_points 綁定的後門。
        SUPPORT = SLOT_EXEMPT
        support = [x for x in tslides if x.get("slot") in SUPPORT]
        for x in support:
            if not str(x.get("slot_reason") or "").strip():
                err(x.get("id", "?"),
                    f"slot={x.get('slot')} 的頁缺 slot_reason —— "
                    f"介紹／result 頁豁免「一個 user_point 一頁」，"
                    f"但必須寫出是哪個觸發成立"
                    f"（result：有量到的**數值**，不是成果清點；"
                    f"介紹：那個名詞一行解釋不完）")
        tslides = [x for x in tslides if x.get("slot") not in SUPPORT]
        if not tslides:
            continue
        # (a) 每一頁都要對得上一個 user_point
        for x in tslides:
            up = (x.get("user_point") or "").strip()
            if not up:
                err(x.get("id", "?"), f"缺 user_point —— 對不上使用者指定的重點就不該有這一頁")
            elif up not in ups:
                err(x.get("id", "?"), f"user_point 對不上線「{tid}」的清單（要逐字相同）：{up[:40]}…")
        # (b) 每一個 user_point 都要有頁 —— 少講他要的比多講他不要的嚴重
        covered = {(x.get("user_point") or "").strip() for x in tslides}
        for up in ups:
            if up not in covered:
                err("plan", f"線「{tid}」的 user_point 沒有任何一頁在講：{up[:50]}… "
                            f"（少講一個他要的，比多講一個他不要的嚴重得多）\n"
                            f"           ⚠️ 若你已經寫了那一頁但標成 slot=problem／intro／"
                            f"result：**支撐頁不算「講到那個重點」**（它們是佐證與鋪陳，"
                            f"不進本檢查）。要它算，就把 slot 改成 method")
        # (b2) ⭐ A：**預設一個 user_point 一頁**（後補）
        # ⚠️ (a)(b) 只保證「每頁對得上一個點、每個點都有頁」，**沒有禁止一個點配兩頁**。
        #    所以 4 個點仍然可以生出 8 頁 —— 首次實跑實測 planner 交出 12 頁，
        #    使用者砍到 7 頁；最終剛好 1:1，但那是他砍出來的，不是規則保證的。
        # 這條把「幾頁？」從開放題變成封閉題：**一個點一頁**，要拆得寫理由。
        # ⛔ 這不是在限制 agent，是把它從「決定頁數」解放出來，
        #    省下的注意力放到「這一頁怎麼講」—— 那才是它該做決定的地方。
        from collections import Counter as _C
        for up, n in _C((x.get("user_point") or "").strip() for x in tslides).items():
            if n > 1 and not t.get("split_note"):
                err("plan", f"線「{tid}」有 {n} 頁在講同一個 user_point："
                            f"「{up[:40]}…」\n"
                            f"           **預設一個重點一頁**。真的要拆兩頁，"
                            f"把理由寫進 threads[].split_note 並在關卡② 確認過")
        # (c) 順序 = user_points 的順序，除非寫明理由
        order = [ups.index(u) for x in tslides
                 if (u := (x.get("user_point") or "").strip()) in ups]
        if order != sorted(order) and not t.get("page_order_note"):
            warn("plan", f"線「{tid}」的頁序與 user_points 的順序不同，"
                         f"而 threads[].page_order_note 沒有寫理由")

    # ---- 0e. layer3 的版面審查有沒有跑（後補）----
    # 為什麼要查：首次實跑那次協調者**從頭到尾沒派 layout_reviewer**，
    # 兩條線的圖由兩個 agent 各自畫，跨主線的一致性沒有任何人看過。
    # 這是流程被跳過，不是規則缺失 —— 機械檢查看不出「圖好不好」，
    # 但看得出「該跑的角色有沒有留下紀錄」。
    #
    # ⭐ **2026-09-05：WARN 升成 ERROR。** 舊版是 WARN，而 WARN 擋不住任何東西 ——
    # 實測：這條從第一次實跑到現在**一場都沒有被回填過**。
    # ⚠️ 升級的前提是**先指定寫的人**（⛔ 只把規則變硬 = 把規則變成路障）：
    # `subagent-layout-reviewer.md` 的 Required outputs 第 2 項現在明訂
    # **由 `layout_reviewer` 自己回填**（它是唯一知道結論的人；協調者被
    # `delegation.md` 禁止代填，`deck_assembler` 拿不到它的結論）。
    # ⭐ 舊的 deck 一行就能解：`{"skipped": "理由"}` —— **具名**的逃生口。
    _rev = plan.get("layout_reviewed")
    if len({s_.get("thread") for s_ in slides if s_.get("thread")}) > 1 and not _rev:
        err("plan", "多線 deck 但沒有 layout_reviewer 的紀錄 —— "
                    "跨主線的一致性（同名物件的畫法、語意色）沒有人看過。\n"
                    "           跑完後把結論寫進 plan.layout_reviewed"
                    "（schema 在 deck_schema.md，⭐ 寫的人是 layout_reviewer 自己）；\n"
                    "           刻意不跑就寫成 {\"skipped\": \"理由\"}")

    # ---- 0e-nit. review 的 NIT 有沒有去處（後補）----
    # 為什麼要查：上一份 layout_review.md 的 **4 條 BLOCKING 全部被修了、
    # 7 條 NIT 一條都沒動** —— 因為 BLOCKING 有人管、NIT 沒有人管。
    # ⭐ NIT 沒有去處就等於沒寫。
    #
    # ⚠️ **反方向（N56）**：「全部寫進去處就過關」會讓這一欄退化成**垃圾桶** ——
    # 只加「必須有去處」而不管去處的品質，等於把 NIT 合法地掃掉。
    # 所以下面五道全部是**品質**的門，不是有沒有填的門：
    #   ① 條數必須等於 layout_review.md 的 [NIT] 條數（⛔ 不准只挑好答的寫）
    #   ② status 三選一，⛔ 不接受自由字串（「已知悉」不是狀態）
    #   ③ fixed 要 evidence、wont_fix 要 why、open 要 **owner**（⛔ 沒 owner
    #      正是這整條在治的病：規則寫了、執行的人沒被指定）
    #   ④ 整批共用同一個 why → ERROR（同一個理由是「掃掉」的指紋）
    #   ⑤ 每則 wont_fix 印一條**具名 WARN** —— 比照 role_exempt：
    #      ⛔ 不修不是修好了，它只是把判斷寫在看得見的地方。
    #      ⭐ 於是「掃進去處」會讓 WARN 數**變大**，⛔ 不會讓它消失。
    if isinstance(_rev, dict) and not _rev.get("skipped"):
        _nits = _rev.get("nits")
        # B17-14：正確落點是 `_work/4_slides/layout_review.md`（paths.work_file 是唯一來源）；
        # 舊位置（日期目錄最上層）**也認**，因為既有交付物在那裡 —— 掃到就提醒搬家。
        _out_dir = os.path.dirname(os.path.abspath(a.deck))
        _rvp = paths.work_file(_out_dir, "layout_review.md", create=False)
        _rvp_legacy = os.path.join(_out_dir, "layout_review.md")
        if not os.path.exists(_rvp) and os.path.exists(_rvp_legacy):
            warn("plan", f"layout_review.md 在日期目錄最上層 —— 過程產物一律進 _work/，"
                         f"請搬到 {os.path.relpath(_rvp, _out_dir)}（B17-14）")
            _rvp = _rvp_legacy
        _want = None
        if os.path.exists(_rvp):
            try:
                with open(_rvp, encoding="utf-8") as _fh:
                    _want = sum(1 for _l in _fh
                                if _l.startswith("### [NIT]"))
            except OSError:
                _want = None
        if not isinstance(_nits, list):
            err("plan", "plan.layout_reviewed 沒有 nits[] —— "
                        "review 的 NIT 沒有去處。\n"
                        "           ⭐ BLOCKING 有人管、NIT 沒有，"
                        "上一份 7 條 NIT 一條都沒動就是這樣來的")
        else:
            if _want is not None and len(_nits) != _want:
                err("plan", f"plan.layout_reviewed.nits 有 {len(_nits)} 則，"
                            f"但 layout_review.md 有 {_want} 條 [NIT]。\n"
                            "           ⛔ 不准只挑好答的那幾條寫 —— "
                            "每一條 NIT 都要有去處")
            _reqs = {"fixed": "evidence", "wont_fix": "why", "open": "owner"}
            for _i, _n in enumerate(_nits, 1):
                if not isinstance(_n, dict):
                    err("plan", f"plan.layout_reviewed.nits[{_i}] 不是物件")
                    continue
                _st = str(_n.get("status") or "")
                _fd = str(_n.get("finding") or "").strip()[:40]
                if _st not in _reqs:
                    err("plan", f"NIT{_i}「{_fd}…」的 status 是 {_st!r} —— "
                                "只能是 fixed／wont_fix／open。\n"
                                "           ⛔ 自由字串不是狀態")
                    continue
                if not str(_n.get(_reqs[_st]) or "").strip():
                    err("plan", f"NIT{_i}「{_fd}…」status={_st} "
                                f"但沒寫 {_reqs[_st]}。\n"
                                + ("           ⛔ fixed 要**可驗的東西**"
                                   "（檔名＋字串／class／數字），「已修正」不算"
                                   if _st == "fixed" else
                                   "           ⛔ open 一定要指名**誰接手** —— "
                                   "沒有 owner 的 open 就是沒有人管"
                                   if _st == "open" else
                                   "           ⛔ 不修一定要寫理由"))
                elif _st == "wont_fix":
                    warn("plan", f"NIT{_i} **不修，具名記錄中** —— {_fd}…\n"
                                 f"           理由：{str(_n.get('why')).strip()}\n"
                                 "           ⛔ 不修不是修好了，"
                                 "它只是把判斷寫在看得見的地方")
            _whys = [str(_n.get("why")).strip() for _n in _nits
                     if isinstance(_n, dict) and str(_n.get("why") or "").strip()]
            if len(_whys) > 1 and len(set(_whys)) == 1:
                err("plan", "plan.layout_reviewed.nits 的每一則 why 都是同一句話 —— "
                            "⛔ 整批同一個理由是「把 NIT 掃掉」的指紋，\n"
                            "           ⭐ 逐條寫這一條為什麼不修")

    # ---- 0e2. layout_reviewer 有沒有拿到**實測**輸出（後補）----
    # 為什麼要查：`subagent-layout-reviewer.md` 的 Required inputs 要它讀
    # `shoot.py --check-only` 的**實測**輸出（溢位、字級、留白只有量了才知道），
    # 但以前 `--check-only` 只印在畫面上、不留檔 → 本次實跑的 reviewer 找不到
    # 任何檔案，只能靠協調者**口述**數字，它在回報裡明確抗議了（FINDINGS N37）。
    # 規格現在已改成「缺 → BLOCKED，⛔ 不接受口述的數字」，但**沒有任何東西在驗
    # 那個檔在不在** —— 規格寫了卻沒人查，等於沒寫。這條就是那個查。
    #
    # ⚠️ 只能是 WARN 不能是 ERROR：這份落地是本輪才有的，更早的週報目錄底下
    #    一律沒有這個檔，升成 ERROR 會讓舊的整批變紅（那不是它們的錯）。
    # ⚠️ 路徑一律問 paths.work_file()，⛔ 不在這裡拼 `_work/...`（N14 的成因）。
    _out = os.path.dirname(os.path.abspath(a.deck))
    _langs = sorted({os.path.basename(h).rsplit(".html", 1)[0].split(".")[-1]
                     for h in glob.glob(os.path.join(_out, "deck.*.html"))}) or ["en"]
    for _lang in _langs:
        _cr = paths.work_file(_out, f"shoot_check.{_lang}.txt", create=False)
        if not os.path.isfile(_cr):
            warn("plan", f"找不到 {os.path.relpath(_cr, _out)} —— "
                         f"layout_reviewer 要讀的是 shoot.py --check-only 的**實測**輸出，"
                         f"沒有這個檔它就只能聽口述的數字（⛔ 口述的不是證據，N37）。\n"
                         f"           跑 `shoot.py deck.{_lang}.html --check-only`，"
                         f"它會自己把實測輸出寫到那裡")

    # ---- 6. 週敘事與線結構 ----
    # arc（PMRC）只適用**單線**週。多主角的週沒有單一結論，硬湊一個是造假。
    # 主角多的週不需要單一結論，每個點說明做了什麼、怎麼做就好。
    arc = deck.get("arc") or {}
    if plan.get("mode") == "single":
        miss = [k for k in ("problem", "motivation", "results", "conclusion") if not arc.get(k)]
        if miss:
            err("deck", f"單線週的 arc（PMRC）缺欄位：{'、'.join(miss)}"
                        " —— 單一故事線沒有這一層就是流水帳")
    elif plan.get("mode") == "multi":
        for t in deck.get("threads", []):
            if not t.get("summary"):
                err("deck", f"多線週的每條線都要有 summary（這條線做了什麼、怎麼做）："
                            f"線「{t.get('id')}」缺")
        if arc.get("conclusion"):
            warn("deck", "多線週填了 arc.conclusion —— 主角多的時候不必硬湊一個全週結論，"
                         "每條線各自說清楚做了什麼就好")

    threads = {}
    for i, s in enumerate(slides, 1):
        if not is_struct(s) and s.get("thread"):
            threads.setdefault(s["thread"], []).append(i)
    intro = {s.get("thread") for s in slides if s.get("type") == "thread-intro"}
    real = {t: p for t, p in threads.items() if t != "backup"}

    # ── outline 頁（定義）────────────────────────────────────
    # ⚠️ 這件事以前**沒有規格**：首次實跑實際產了「全場 1 張 ＋ 每條線 1 張」，
    #    但那是臨場做的，換一次執行就可能不一樣。而且當時三處互相矛盾 ——
    #    SKILL.md 原則② 說「線的開場頁已移除」、本檔 docstring 說「線超過 2 頁
    #    要有開場頁」、實際做法是用 `agenda` 版型繞過 `thread-intro` 的禁令。
    #
    # 定案：**`thread-intro` 版型仍然禁用**（它只剩 backup 分隔頁一個用途）；
    #      各線的 outline 用 `agenda` 版型，並掛上 `thread`。
    ag = [s for s in slides if s.get("type") == "agenda"]
    global_ag = [s for s in ag if not s.get("thread")]
    if not global_ag:
        err("deck", "缺全場 outline —— 第一張要是不掛 thread 的 agenda 頁，"
                    "列出本週各主線的名字 ＋ 一句它在做什麼。單一主線的週也要有"
                    "（讓聽眾知道今天只有一件事）。⭐ 由 `merge_slides.py --outline` 產，不用手寫")
    by_thread = {s.get("thread"): s for s in ag if s.get("thread")}
    # ⭐ B17-4：**單線的週只有一張 outline**。全場 outline 直接列該線的 user_points
    #    （否則會連續兩張幾乎一樣的 agenda：一張「這條線在做什麼」、下一張同一條線的 7 點）。
    #    所以 single 時：全場 outline 套「項數＝user_points」那套比對，各線 outline **不要求**，
    #    有的話發 WARN 叫人拿掉。
    single_mode = (plan.get("mode") == "single") or len(real) == 1
    if single_mode and by_thread:
        warn("deck", f"單線的週有 {len(by_thread)} 張掛 thread 的 outline —— B17-4：全場 outline "
                     "已經列了 user_points，第二張是重複的結構頁，拿掉（merge_slides.py --outline 不會產它）")
    for t, pages in sorted(real.items()):
        # 賺得到位置才給：**3 頁以上**的線才需要自己的 outline，
        # 短線由全場 outline 帶到即可，否則結構頁佔比失衡。
        if len(pages) < 3:
            continue
        if single_mode:
            # 單線：拿**全場 outline** 來對 user_points（同一套判準，見下）
            if not global_ag:
                continue
            ag_page = global_ag[0]
            ups = next((x.get("user_points") or [] for x in deck.get("threads", [])
                        if x.get("id") == t), [])
            listed = [str((it or {}).get("t") or "").strip()
                      for it in ((ag_page.get("body") or {}).get("items") or [])]
            if ups and len(listed) != len(ups):
                err(ag_page.get("id", "?"),
                    f"單線的週，全場 outline 有 {len(listed)} 項，但線「{t}」的 user_points 有 "
                    f"{len(ups)} 條 —— B17-4：single 時全場 outline 就是把 user_points 列出來"
                    f"（merge_slides.py --outline）")
            elif ups:
                for i_, (lt, up) in enumerate(zip(listed, ups), 1):
                    a_, b_ = lt.strip(), str(up).strip()
                    if a_ == b_ or (len(a_) >= 6 and b_.startswith(a_)):
                        continue
                    warn(ag_page.get("id", "?"),
                         f"全場 outline 第 {i_} 項對不上同序的 user_point：\n"
                         f"           outline    「{a_[:52]}」\n"
                         f"           user_point 「{b_[:52]}」")
            continue
        # ⚠️ 變數名不要用 `a` —— 這段在 main() 裡，`a` 是 argparse 的 namespace，
        #    蓋掉之後下游的 a.deck 會炸（當場踩過）。
        ag_page = by_thread.get(t)
        if not ag_page:
            err("deck", f"線「{t}」有 {len(pages)} 頁但沒有自己的 outline —— "
                        f"3 頁以上的線要有一張掛 thread=\"{t}\" 的 agenda 頁")
            continue
        # ⭐ 各線 outline 的內容**不是 agent 寫的**：逐字抄 user_points。
        #    這樣使用者在關卡① 講的那幾句話會直接變成那一頁，agent 不必判斷，
        #    而且可以機械比對。
        ups = next((x.get("user_points") or [] for x in deck.get("threads", [])
                    if x.get("id") == t), [])
        listed = [str((it or {}).get("t") or "").strip()
                  for it in ((ag_page.get("body") or {}).get("items") or [])]
        if ups and len(listed) != len(ups):
            err(ag_page.get("id", "?"),
                f"線「{t}」的 outline 有 {len(listed)} 項，但 user_points 有 "
                f"{len(ups)} 條 —— outline 就是把 user_points 列出來，"
                f"⛔ 不要自己增刪")
        elif ups:
            # ── N114：**只比長度**是不夠的 ────────────────
            # ⚠️ 這段的註解自己寫著「各線 outline 的內容**不是 agent 寫的**：
            #    逐字抄 user_points…**而且可以機械比對**」—— 而比對只做了長度。
            #    3 條 user_points 對上 `Part 1／Part 2／Part 3` 就通過。
            # ⛔ 裁決（2026-09-05，「先寬」）：**允許截短，不要求逐字相等**，嚴重度 WARN。
            #    理由是實測：user_points 是使用者的原話，常常一句話 40 字
            #    （「怎麼讓文字敘述變得比較白話，而不是 AI 原來那種…」），
            #    照抄會撐爆 agenda 那一格。合法的截短是**前綴**：抄前半句。
            # ⚠️ 反方向（N56）：允許截短就會被拿去**只抄前兩個字**。擋它的是下面的
            #    最短長度要求（截到剩不到 6 個字元等於改寫），以及 (a)(b) 那組
            #    ERROR —— 頁上的 user_point 仍然必須**逐字**等於清單裡的那一句。
            for i_, (lt, up) in enumerate(zip(listed, ups), 1):
                a_, b_ = lt.strip(), str(up).strip()
                if a_ == b_ or (len(a_) >= 6 and b_.startswith(a_)):
                    continue
                warn(ag_page.get("id", "?"),
                     f"線「{t}」outline 第 {i_} 項對不上同序的 user_point"
                     f"（逐字相等，或**抄前半句**的截短版）：\n"
                     f"           outline    「{a_[:52]}」\n"
                     f"           user_point 「{b_[:52]}」\n"
                     f"           這一頁不是 agent 寫的，是把使用者的原話列出來；"
                     f"⛔ 不要改寫成自己的說法")

    if len(real) > 1:
        # 開場頁要賺得到它的位置：**兩頁以上**的線才需要，單頁線由議程頁帶到即可。
        # 否則 4 條短線會產生 4 張分隔頁，結構頁佔比失衡。
        for t in real:
            if t in intro:
                err("deck", f"線「{t}」有開場頁 —— 線的開場頁一律不使用，"
                            f"標題寫在議程頁上，換線由講者口頭引導"
                            f"（thread-intro 只剩 backup 分隔頁一個用途）")

    # ---- 逐頁 ----
    all_days, prev_to, prev_id, prev_thread = set(), None, None, None
    for i, s in enumerate(slides, 1):
        sid = s.get("id") or f"S{i}"
        st = s.get("type", "")
        struct = is_struct(s)

        # 5. 來源
        srcs = s.get("source") or []
        if st not in STRUCT:
            if not srcs:
                err(sid, "缺 source（無法追溯這頁的內容出自哪一天哪一項）")
            for x in srcs:
                if not SRC_RE.match(x):
                    err(sid, f"source 格式錯誤：{x}（應為 YYYY-MM-DD#N）")
                else:
                    all_days.add(x.split("#")[0])

        # 1. 一頁一重點（backup 頁一樣要有）
        if st not in STRUCT:
            pt = (s.get("point") or "").strip()
            if not pt:
                err(sid, "缺 point（這頁到底要講哪一件事）")
            elif re.search(r"[；;]|另外|同時也|順便", pt):
                err(sid, f"point 疑似塞了兩個重點，請拆頁：「{pt}」")

        # 2. 承接／拋出（backup 頁豁免；**換線時重置**——跨線硬接就是硬串）
        nxt = slides[i] if i < len(slides) else None
        same_thread_next = (nxt is not None and not is_struct(nxt)
                            and nxt.get("thread") == s.get("thread"))
        first_of_thread = (prev_thread != s.get("thread"))
        if not struct:
            # ⚠️ 後修：schema 早就寫著「換線時重置」，但這裡無條件要求 from。
            # 每條線的第一頁沒有前一頁可承接 —— 多線週必然誤報（實測 2 條線各報一次）。
            if not s.get("from") and not first_of_thread:
                err(sid, "缺 from（上一頁的結論是什麼）")
            if not s.get("to") and same_thread_next:
                err(sid, "缺 to（這頁講完，聽眾帶走的那句結論）")
            if (prev_to and s.get("from") and s.get("thread") == prev_thread
                    and s["from"].strip() != prev_to.strip()):
                warn(sid, f"接不上 {prev_id} 的結論：\n"
                          f"           {prev_id} 的結論「{prev_to}」\n"
                          f"           {sid} 承接的是「{s['from']}」")
        if st == "thread-intro":
            prev_to = s.get("to") or prev_to      # 線的開場頁兼轉場
            prev_id = sid
        elif not struct:
            prev_to, prev_id, prev_thread = s.get("to"), sid, s.get("thread")

        # 4. 容量與主體型態
        check_capacity(sid, s)
        check_body_kind(sid, s)
        check_title(sid, s)
        check_takeaway(sid, s)
        check_notes_substance(sid, s)
        check_caption(sid, s)
        check_depth(sid, s, a.deck)
        check_example(sid, s, bool(plan.get("example_first")))
        check_struct_body(sid, s)          # 結構頁的 body 形狀（render 的隱性契約）
        check_skipped(sid, s)              # 這頁有幾條檢查因為缺鍵被跳過（N106）
        if not struct:
            check_unit_numbers(a.deck, s, sid)
            if not s.get("backup"):
                check_real_names(a.deck, s, sid, plan.get("terms") or {})
                check_code_idents(a.deck, s, sid, plan.get("terms") or {})

    # ---- 7~9. I/O 物品鏈、物品登記、頁數預算 ----
    check_io_chain(slides, plan.get("terms") or {})
    check_budget(slides)
    check_backup(slides)               # backup 的數量／比例（N107）
    # ---- 10~11. manifest 對帳、語意色一致性 ----
    # ── N101 (a)：`must_numbers` 沒有生產者時，check_unit_numbers 的豁免清單
    #    恆為空 → 它對**每一頁**都叫，等於報廢。實測：layer2.A/B.json 的 8 頁
    #    **全部都有** must_numbers，而 deck.json 的 13 頁**一頁都沒有** ——
    #    鏈斷在 builder（它的契約以前 grep must_numbers = 0）。
    content = [x for x in slides if x.get("type") not in STRUCT and not x.get("backup")]
    if content and not any(x.get("must_numbers") for x in content):
        warn("deck", f"{len(content)} 個主線內容頁**沒有任何一頁**帶 must_numbers —— "
                     f"那是 `slide_planner` 在 layer2 逐頁產的欄位"
                     f"（它的 Procedure ⑥「從摘錄裡挑必須出現的數字」）。\n"
                     f"           `slide_builder` 交件時要把它**逐字帶進 slides.<線>.json**"
                     f"（⛔ 不得自己改），否則：\n"
                     f"           ① 檢查 14（帶單位的數字）的豁免清單恆空 → 對每一頁都叫；\n"
                     f"           ② 使用者在關卡② 指名要出現的數字，沒畫也沒有人會發現。")
    check_manifest(a.deck, slides)
    check_semantic_color(a.deck, slides)
    check_markers(a.deck)              # 手寫 SVG 的 marker 紀律（N83）
    check_inline_type(a.deck)          # 圖上不得用 inline style 表層級（任務 6 L0）
    check_arrow_legible(a.deck)        # 箭頭頭要夠大、桿要比頭長（任務 6e）
    check_emphasis_shape(a.deck)       # 形狀的顏色只做分類，不做強調（任務 6 L3）
    check_relation_evidence(a.deck, slides)   # 宣告的關係要看得見（任務 6 L4-1）
    check_object_consistency(a.deck)   # 同一個東西每頁長得一樣（任務 6 L4-2）
    check_spec_reproduces(a.deck, slides)     # 出貨的圖要重跑得出來（N121）
    check_css_purpose_sync(a.deck)     # PURPOSE 與 deck.css 選擇器同源
    check_handwritten_quota(a.deck)    # 手繪張數的全域配額（原 layout_reviewer 第 5 項）
    check_hl_text_roles(a.deck)        # 金字只能一種組合（原 layout_reviewer 3c 第 2 問）
    check_terms_zh(a.deck, plan)       # 中譯照 plan.terms_zh 的凍結表（N31 機械版）

    # ---- 3. 數字溯源 ----
    data_dir = a.data or paths.data_dir()
    pool, missing = load_source_text(data_dir, all_days)
    for d in missing:
        err("deck", f"來源日誌不存在：{data_dir}/{d}.json")
    # ⭐ 來源池同時收「阿拉伯數字」與「中文數字換算成的等值阿拉伯數字」（F10）
    pool_nums = norm_nums(pool) | cn_numbers(pool)
    for i, s in enumerate(slides, 1):
        sid = s.get("id") or f"S{i}"
        if s.get("type") in STRUCT:
            continue
        check_purpose(a.deck, s, sid)
        check_renderer_used(s, sid)
        _ex = extra_source_text(s)
        pool_s = pool_nums | norm_nums(_ex) | cn_numbers(_ex)
        blob = list(texts(s)) + [svg_numbers(a.deck, s)]
        for t in sorted({n for txt in blob for n in norm_nums(txt)}):
            if t in pool_s or t.rstrip("%") in pool_s:
                continue
            (err if is_data_number(t) else warn)(
                sid, f"數字「{t}」在來源日誌裡找不到 —— 不得計算、不得改寫，只能逐字照抄")

    # ---- 0c. 對帳：日誌裡的每一項，不是上了投影片就是被明確篩掉 ----
    if all_days:
        every, rec = [], []
        for d in sorted(all_days):
            fp = os.path.join(data_dir, f"{d}.json")
            if not os.path.isfile(fp):
                continue
            j = json.load(open(fp, encoding="utf-8"))
            every += [f"{d}#{i}" for i in range(1, len(j.get("items", [])) + 1)]
            every += [f"{d}#issue{i}" for i in range(1, len(j.get("issues", [])) + 1)]
            # 記錄層另計：它已經是被日誌降級過的一層，逐項要求去處太重，
            # 所以只給 WARN。硬性涵蓋由 layer1（subagent-thread-finder）的
            # completion criteria 負責 —— 那裡的輸入 threads.md 本來就含 R 項。
            rec += [f"{d}#R{i}" for i in range(1, len(j.get("record", [])) + 1)]
        # ── N108 ①：`used` 反查 `every` ────────────────────────────
        # ⚠️ 本檔檔頭第 5 條寫著「source 必填、格式 YYYY-MM-DD#N、**且該項在 .data
        #    裡真的存在**」，但 `used` 從來沒有拿去跟 `every` 反向比對過 ——
        #    `"source": ["2026-09-05#42"]` 而那天只有 7 項 → 零 ERROR 零 WARN，
        #    整頁可以完全沒有出處。對帳一直只做了「日誌項有沒有去處」那個方向。
        # ⛔ 裁決（2026-09-05，「先寬」）：**WARN**，而且**只驗「這一項存在」**，
        #    ⛔ 不要求頁上的數字綁回該項 —— 跨項引用（一張圖講三天的事）是合法且常見的，
        #    綁死粒度會擋掉大量正確的頁。
        # ⚠️ 反方向（N56）：只驗存在性，擋不住「隨便指一項湊數」。擋那個方向的是
        #    數字溯源（數字必須逐字出現在來源池裡）與 §2c-2 的帶單位數字 WARN。
        known = set(every) | set(rec) | {f"{d}#headline" for d in all_days} | set(all_days)
        for x in sorted(used):
            if x not in known:
                d0 = x.split("#")[0]
                warn("plan", f"source「{x}」在 .data 裡找不到對應的項 —— "
                             f"{d0}.json 只有 {sum(1 for y in every if y.startswith(d0 + '#') and '#R' not in y and 'issue' not in y)} 個 items、"
                             f"{sum(1 for y in every if y.startswith(d0 + '#issue'))} 個 issues、"
                             f"{sum(1 for y in rec if y.startswith(d0 + '#R'))} 個 record。\n"
                             f"           格式對不代表指得到東西：編號要真的存在，"
                             f"否則這一頁等於沒有出處")
        orphan = [x for x in every if x not in used and x not in dropped]
        rec_orphan = [x for x in rec if x not in used and x not in dropped]
        if rec_orphan:
            warn("plan", f"{len(rec_orphan)} 個記錄層項目沒有去處 —— 記錄層常有日報壓縮掉的"
                         f"機制細節，週報要講「怎麼做的」時缺的多半是這些：\n"
                         + "\n".join(f"           · {x}" for x in rec_orphan[:8])
                         + ("\n           …" if len(rec_orphan) > 8 else ""))
        if orphan:
            err("plan", f"{len(orphan)} 個日誌項目既沒上投影片、也沒寫進 plan.dropped —— "
                        f"「不講」要有理由，不是默默消失：\n"
                        + "\n".join(f"           · {x}" for x in orphan[:12])
                        + ("\n           …" if len(orphan) > 12 else ""))

    # ---- 3b. 語言對照表：譯文裡的數字一樣要溯源 ----
    for tbl_path in sorted(glob.glob(os.path.join(
            os.path.dirname(os.path.abspath(a.deck)), "strings.*.json"))):
        tbl = json.load(open(tbl_path, encoding="utf-8"))
        lang = os.path.basename(tbl_path).split(".")[1]
        # 值的三種狀態：有內容＝譯文；"="＝刻意不翻（樣本名、工具名、純數字）；
        # ""＝還沒翻（渲染時落回英文原文）。
        # ── N109 ①：`"="` 的用量沒有上限 ────────────────────────
        # ⚠️ 待翻句數只數**空字串**：把每一個值都填成 `"="` → 待翻 0 句、strings 步驟
        #    綠燈，而 render_deck.py 讓 deck.zh.html **逐字全英文**，摘要表印
        #    「N 句、0 句待翻」。「刻意不翻」與「還沒翻」在機械上完全同形。
        # ⛔ 裁決（2026-09-05，「先寬」）：**WARN**，門檻 60%。
        #    全英文的 deck 是合法的（工具名、樣本名、程式碼片段整份都不該翻），
        #    所以不能擋；但**一份中譯有六成句子不翻**要有人看一眼。
        # ⚠️ 反方向（N56）：這條會把 agent 推去**硬翻本來不該翻的東西**
        #    （把 daily-log 翻成「每日日誌」）。擋它的是既有的
        #    check_real_names／check_code_idents（真名被翻掉就少了打得開的名字）
        #    與下面的數字對帳。兩個方向都有東西在守。
        latin = [k for k in tbl if re.search(r"[A-Za-z]{3}", k)]
        keep = [k for k in latin if tbl.get(k) == "="]
        if latin and len(keep) > len(latin) * 0.6:
            warn("i18n", f"{lang}: {len(keep)}/{len(latin)} 句標成 \"=\"（刻意不翻），"
                         f"超過 60% —— 「刻意不翻」與「還沒翻」在機械上同形，"
                         f"整份填 \"=\" 會得到「0 句待翻」的綠燈與一份全英文的譯本。\n"
                         f"           抽幾句確認一次：它們真的是工具名／樣本名／"
                         f"程式碼片段嗎？")
        empty = [k for k, v in tbl.items() if not v and re.search(r"[A-Za-z]{3}", k)]
        if empty:
            warn("i18n", f"{lang}: {len(empty)} 句含英文但沒有譯文，渲染時會落回原文。"
                         f"刻意不翻請把值填成 \"=\""
                         + "".join(f"\n           · {k[:60]}" for k in empty[:8]))
        for k, v in tbl.items():
            if not v or v == "=":
                continue
            # 非對稱規則：譯文**不得憑空生出**來源沒有的數字（那是編造）；
            # 但可以把數字寫成中文字（1,000 → 一千、3rd → 第三），那不是竄改。
            invented = norm_nums(v) - norm_nums(k)
            if invented:
                err("i18n", f"{lang} 譯文出現原句沒有的數字 {sorted(invented)}：\n"
                            f"           原句「{k[:52]}」\n"
                            f"           譯文「{v[:52]}」")
            # ── N109 ②：反向差集從來沒算過 ────────────────
            # 上面那條的註解自承「非對稱規則」，而反方向的失效是真的：
            #   "18 of 24 candidate items were reused" → 「大部分候選項目都沿用了」
            # 零錯誤，而中文版投影片上那兩個關鍵數字**直接消失**。
            # ⛔ 裁決（「先寬」）：**WARN**，而且**只報 is_data_number 那一種**
            #    （含小數點／百分比／三位以上）。理由：中文譯法把小數字寫成中文字
            #    （3 → 三、1,000 → 一千）是正常且被 F10 明文允許的，逐個報會誤報到
            #    整條被忽略；而「28%」「1e-3」這種被整句改寫掉才是真的失去資訊。
            lost = {n for n in norm_nums(k) - norm_nums(v)
                    if is_data_number(n)} - cn_numbers(v)
            if lost:
                warn("i18n", f"{lang} 譯文少了原句有的數字 {sorted(lost)} —— "
                             f"那句話的關鍵數字在譯本上消失了：\n"
                             f"           原句「{k[:52]}」\n"
                             f"           譯文「{v[:52]}」\n"
                             f"           數字寫成中文字（一千／第三）是可以的，"
                             f"整句改寫成「大部分」不行")

    # 確認過的份量要和實際頁數對得上 —— 否則「確認」只是形式
    main_n = sum(1 for x in slides if not is_struct(x) and not x.get("backup"))
    planned = sum(int(x.get("pages") or 0) for x in splan)
    if splan and planned != main_n:
        err("plan", f"slide_plan 說好 {planned} 頁主線，實際做出 {main_n} 頁 —— "
                    f"份量偏離了確認過的規劃。要改就回頭改 slide_plan 並讓使用者再看一次")

    print(f"[check] {len(slides)} 頁、{len(all_days)} 天來源、{len(threads)} 條線")
    if W:
        print(f"\n警告 {len(W)} 項："); print("\n".join(W))
    if E:
        print(f"\n錯誤 {len(E)} 項："); print("\n".join(E))
        sys.exit(1)
    print("\n[check] 全部通過 ✅")


if __name__ == "__main__":
    main()
