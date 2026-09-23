#!/usr/bin/env python3
"""領域圖 renderer：吃 JSON，吐 SVG。**agent 不負責算座標。**

為什麼領域圖優先做（比 8 個概念 renderer 更早）：
  概念圖畫壞了頂多醜；**領域圖畫壞了會畫錯生物學** —— read 疊法不對、
  位點對不上、haplotype 分群分錯邊。用 schema 綁死之後，agent 只能填資料，
  畫不出違反領域慣例的東西。

  而且這兩種在讀序資料的專案裡**每週都用得到**（read 層的分析是主戰場）。
  ⚠️ 非讀序領域的專案用不到這兩個 comp，忽略即可 —— 其餘流程不依賴它們。

規格來源：**本機的參考素材**（一張 read 疊圖、一張 haplotype 分群圖那種畫法）。
⚠️ 那些圖是別人的實驗，不屬於這個 skill，**公版沒有附**，也不寫路徑進來。
本檔要的只是它們的**構圖**（read 怎麼疊、位點怎麼對齊、haplotype 怎麼分群），
那部分已經固化在下面的 schema 與 renderer 裡，不看原圖也能用。

支援的 comp 分兩類：

領域構圖（規格＝本機參考素材的視覺慣例）
  read_pileup      一疊 read，每個 base 一格，特定位置上色
  haplotype_split  同上，但分成兩群（haplotype），中間一條虛線

概念構圖（規格＝從 16 張既有 SVG 逆向抽出來的，見下方那段長註解）
  chain            一排等重的步驟＋箭頭                （sequence）
  chain_gated      同上，每步之後掛一道關卡            （steps[].gate 有值時）
                   ⚠️ 這三個名字**指到同一支 renderer**，差別全在資料
  group_blocks     整體拆成幾群，群裡的成員一個個看見  （partition）
  two_col_link     左欄每一項對到右欄某一項            （correspondence）

用法：
  render_figure.py spec.json -o out.svg
  render_figure.py --demo <outdir>        # DEMO 表裡每一則各產一張，用來眼睛驗收
"""
import argparse, hashlib, json, os, re, sys

import glyphs        # 盒內小圖（PR 4）；它延後綁定本模組拿 T()／_cat_of()／_OVERFLOW
glyphs._R = sys.modules[__name__]   # ⚠️ 一定要綁**這一份**：跑成 __main__ 時 `import render_figure`
                                    #    會載入第二份，_CAT_USED／_OVERFLOW 各一套 → 同名不同色、紅帶不出

# 語意色：沿用 deck.css 的主色盤，語意沿用領域慣例（參考圖）。
# ⚠️ 顏色的語意全場一致（presentation_rules §5）——這裡定了就不要在別的圖改。
PALETTE = {
    "somatic":  ("#C0561B", "#FFFFFF"),   # 體細胞變異：橘（要看這裡）
    "germline": ("#1E2761", "#FFFFFF"),   # 生殖系變異：深藍（deck 主色）
    "error":    ("#F2B705", "#16193B"),   # 定序錯誤：黃（deck accent）
    "plain":    ("#E8EAF2", "#16193B"),   # 一般鹼基
    "ref":      ("#FFFFFF", "#16193B"),   # 參考鹼基（白底外框）
}
READ_TONE = {                              # read 本體（箭頭）的底色
    "h1":   ("#CADCFC", "#8FA8DA"),
    "h2":   ("#D7E9D9", "#95BF9E"),
    "none": ("#EDEEF3", "#C7CBDD"),
}

CELL_W, CELL_H, GAP = 26, 26, 6            # 一個 base 一格
ROW_H = CELL_H + 10
PAD = 16


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def read_arrow(x, y, w, h, direction, tone):
    """一條 read = 一個箭頭形狀。箭頭尖端表示定序方向，這是領域慣例，不要拿掉。"""
    fill, stroke = READ_TONE.get(tone, READ_TONE["none"])
    tip = 12
    if direction == "left":
        pts = (f"{x + w},{y} {x + tip},{y} {x},{y + h / 2} "
               f"{x + tip},{y + h} {x + w},{y + h}")
    else:
        pts = (f"{x},{y} {x + w - tip},{y} {x + w},{y + h / 2} "
               f"{x + w - tip},{y + h} {x},{y + h}")
    return (f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5"/>')


# ⚠️ 以下 read/haplotype 這一族的 `<text>` **不走 `T()`，但一定要帶用途 class**（N89）。
#   · 為什麼要帶：`check_purpose()` 對沒標用途的 `<text>` 是**逐則 ERROR**，
#     而否決 mermaid 的唯一理由就是「它產的 <text> 不帶用途 class」——
#     自己的 renderer 犯同一條，等於那個否決理由不成立。
#   · 為什麼不走 `T()`：`T()` 讓字級與顏色由 `deck.css` 的 class 決定（label 22px、
#     value 30px），那是配 **1420 寬**座標系校準的。這一族目前產的是**內容尺寸**的
#     viewBox（見 N91，尚未裁決），13/14/19px 才是對的比例。
#   · 所以字級／字重／顏色一律寫進 **`style=`**（優先序高於 class 規則），
#     class 只負責「這則字是幹嘛的」。⛔ 不要改寫成 `font-size=` 屬性 ——
#     那是**presentation attribute**，會被 `svg .label{}` 蓋掉，圖會爆版。
#   ⭐ N91 若裁決成「改產 1420 寬」，這些 `style=` 釘子就該一起拆掉、改走 `T()`。
#   ⚠️ 任務 6 L0 把「`<text>` 不得帶 inline 字級／字重」變成 ERROR，這一族是
#     **唯一的豁免**，所以每一則都加了 `raw-size` —— ⭐ 豁免必須是**具名且可 grep** 的：
#     `grep -n raw-size` 就是 N91 那批釘子的完整清單，裁決當天照著拆即可。
#     ⛔ 不要靠「檔案在哪個 renderer 裡」之類猜得出來的條件豁免。
def base_cells(x, y, bases, marks):
    """每個 base 一格。marks 的鍵是 base 在字串裡的**位置索引**（0-based，字串）。"""
    out = []
    for i, ch in enumerate(bases):
        cls = marks.get(str(i), "plain")
        fill, fg = PALETTE.get(cls, PALETTE["plain"])
        cx = x + i * (CELL_W + 2)
        out.append(
            f'<rect x="{cx}" y="{y}" width="{CELL_W}" height="{CELL_H}" rx="3" '
            f'fill="{fill}" stroke="#B8BDD0" stroke-width="1"/>'
            f'<text x="{cx + CELL_W / 2}" y="{y + CELL_H / 2 + 4}" '
            f'class="value raw-size" text-anchor="middle" '
            f'style="font-size:13px;font-weight:600;font-family:inherit;'
            f'fill:{fg}">{esc(ch)}</text>')
    return "".join(out)


def legend_row(x, y, items):
    """圖例：色塊 + 標籤。這是圖唯一合法的文字（presentation_rules §2「圖表標註」）。"""
    out, cx = [], x
    for it in items:
        cls = it.get("color") or it.get("class") or "plain"
        fill, _ = PALETTE.get(cls, PALETTE["plain"])
        label = it.get("label", cls)
        out.append(f'<rect x="{cx}" y="{y}" width="18" height="18" rx="3" '
                   f'fill="{fill}" stroke="#B8BDD0"/>')
        out.append(f'<text x="{cx + 25}" y="{y + 14}" class="label raw-size" '
                   f'style="font-size:14px;font-family:inherit;fill:#16193B"'
                   f'>{esc(label)}</text>')
        cx += 25 + max(52, len(label) * 8.4) + 18
    return "".join(out), cx - x


def _reads_block(reads, x0, y0, default_tone):
    """畫一疊 read，回傳 (svg, 用掉的寬, 用掉的高)。"""
    out, maxx = [], 0
    for r in reads:
        bases = r.get("bases", "")
        off = int(r.get("offset", 0))
        x = x0 + off * (CELL_W + 2)
        w = len(bases) * (CELL_W + 2) + 22
        out.append(read_arrow(x - 8, y0 - 4, w, CELL_H + 8,
                              r.get("dir", "right"), r.get("tone", default_tone)))
        out.append(base_cells(x, y0, bases, r.get("marks") or {}))
        maxx = max(maxx, x + w)
        y0 += ROW_H
    return "".join(out), maxx, y0


def render_read_pileup(spec):
    title = spec.get("title")
    y = PAD
    parts = []
    if title:
        parts.append(f'<text x="{PAD}" y="{y + 20}" class="label lead raw-size" '
                     f'style="font-size:19px;font-weight:700;'
                     f'font-family:inherit;fill:#16193B">{esc(title)}</text>')
        y += 40
    need_w = PAD + len(title or "") * 11
    if spec.get("legend"):
        lg, lw = legend_row(PAD, y, spec["legend"])
        parts.append(lg)
        need_w = max(need_w, PAD + lw)
        y += 34
    body, maxx, y = _reads_block(spec.get("reads", []), PAD + 8, y,
                                 spec.get("tone", "none"))
    parts.append(body)
    return wrap(parts, max(maxx, need_w) + PAD, y + PAD - 10)


def render_haplotype_split(spec):
    """兩群 read，中間一條虛線 —— 分群本身就是這張圖要講的事。"""
    title = spec.get("title")
    y = PAD
    parts = []
    if title:
        parts.append(f'<text x="{PAD}" y="{y + 20}" class="label lead raw-size" '
                     f'style="font-size:19px;font-weight:700;'
                     f'font-family:inherit;fill:#16193B">{esc(title)}</text>')
        y += 40
    need_w = PAD + len(title or "") * 11
    if spec.get("legend"):
        lg, lw = legend_row(PAD, y, spec["legend"])
        parts.append(lg)
        need_w = max(need_w, PAD + lw)
        y += 34

    groups = spec.get("groups", [])
    if len(groups) != 2:
        sys.exit("[figure] haplotype_split 需要剛好 2 群（兩個 haplotype）")

    # 分隔虛線要橫跨**兩群**的寬度，所以先算出總寬再畫（不能只用第一群的）。
    full_w = max((PAD + 64 + int(r.get("offset", 0)) * (CELL_W + 2)
                  + len(r.get("bases", "")) * (CELL_W + 2) + 22)
                 for g in groups for r in g.get("reads", []))
    maxx = max(full_w, need_w)
    for gi, g in enumerate(groups):
        label = g.get("label")
        tone = g.get("tone") or ("h1" if gi == 0 else "h2")
        if label:
            parts.append(f'<text x="{PAD}" y="{y + 18}" class="label lead raw-size" '
                         f'style="font-size:14px;font-weight:600;'
                         f'font-family:inherit;fill:#5A5F82">{esc(label)}</text>')
        body, mx, y = _reads_block(g.get("reads", []), PAD + 64, y, tone)
        parts.append(body)
        maxx = max(maxx, mx)
        if gi == 0:
            y += 8
            parts.append(f'<line x1="{PAD}" y1="{y}" x2="{maxx}" y2="{y}" '
                         f'stroke="#B8BDD0" stroke-width="2" stroke-dasharray="8 6"/>')
            y += 18
    return wrap(parts, maxx + PAD, y + PAD - 10)


# 箭頭 marker 的公版 <defs>。**這是治本的地方** —— 手寫 SVG 會忘記寫 markerUnits，
# renderer 產的圖一律從這裡拿，不會忘。
#
# ⚠️ `markerUnits` 的預設值是 `strokeWidth`，也就是箭頭實際大小 = markerWidth × stroke-width。
#    deck.css 有 `svg .arrow{stroke-width:3}`（`.arrow-hl` 已於 6c 移除），
#    沒寫 markerUnits 的話 markerWidth="8" 會渲染成 24px／32px 的巨大三角形，壓到旁邊的字。
#    寫成 userSpaceOnUse 之後 markerWidth 就是實際 px。→ references/diagram-craft.md §2
#
# ⚠️ id 是**整份 deck.html 全域**的（所有圖都內嵌在同一份文件，同 id 只認第一個定義），
#    所以這裡的幾何必須與手寫 SVG 的 a／ah 完全一致，只差 fill。
#
# ⭐ 尺寸 8 → **12**（6e 的前置裁決 ②，2026-09-05）。為什麼：
#    實測全 deck 的箭頭頭一律 **8×8 user unit**，畫布卻是 **1420 寬** —— 佔 0.56%，
#    在投影機上讀不出方向。⛔ 病是**全 renderer 同病**（group_blocks／funnel／
#    chain／two_col_link 都從這一份 defs 拿），所以治在這裡＝一次全治，
#    ⛔ 不會像「只改一支」那樣製造跨頁不一致。
#    12 的依據：`deck.css` 的 `svg .arrow{stroke-width:3}` → 箭頭頭 = **4× 桿寬**，
#    那是製圖上讀得出方向的最小比例；再大就開始蓋住相鄰的字（8px 間隙的那些構圖）。
# ⚠️ 配套的量尺在 `check_deck.py` 的 `check_arrow_legible()`：**桿長 < 3× 頭**
#    的箭頭會出聲 —— ⭐ 頭放大而桿沒放長，就只是把箭頭變成一個三角形色塊
#    （N125 記過同型：transform_pair 第一版的 8px 桿被自己的 8px 頭整支蓋掉）。
ARROW_H = 12
ARROW_DEFS = (
    '<defs>'
    '<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
    f'markerUnits="userSpaceOnUse" markerWidth="{ARROW_H}" markerHeight="{ARROW_H}" '
    'orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#5A5F82"/></marker>'
    '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
    f'markerUnits="userSpaceOnUse" markerWidth="{ARROW_H}" markerHeight="{ARROW_H}" '
    'orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#F2B705"/></marker>'
    '</defs>'
)


def _height_guard(h):
    """⚠️ viewBox 太高 → `max-height:100%` 會把整張圖等比縮小 → 圖內字級跟著縮，
    shoot.py 的「圖內有效字級過小」就會報。⛔ 調大 fontSize 沒用（viewBox 會一起變大），
    要**縮短比較長的那一邊**：拿掉幾行、或拆頁。→ diagram-craft.md §6"""
    if h > HMAX:
        print(f"[figure] ⚠️ viewBox 高 {int(h)} > 預算 {HMAX} —— 圖會被等比縮小，"
              f"圖內字級跟著縮。請減少內容或拆頁（diagram-craft.md §6）", file=sys.stderr)
        if _BLK_USED[0]:
            print(f"[figure]    這張圖用了 box 內的 blocks，高度是**子區塊撐出來的**"
                  f"（超出 {int(h - HMAX)}px）。⛔ 不會靜默截斷，也不要把子區塊壓回一行"
                  f"（那就退回這一輪要修的病）。三個正解，由優到劣：\n"
                  f"[figure]    ① 全寬的構圖（chain band 的橫幅、group_blocks rows 的列）"
                  f"改 \"flow\": \"row\" —— 子區塊並排，把寬拿來用，不吃高；\n"
                  f"[figure]    ② 減少子項或子區塊數（一格三組以上通常是兩頁的量）；\n"
                  f"[figure]    ③ 拆頁。", file=sys.stderr)
    return h


def wrap(parts, w, h):
    """⚠️ 一定要有 viewBox、不要寫死 width/height —— CSS 負責縮放（log_schema 的約定）。

    ⭐ N94：本次 render 若撞到「子區塊裝不下」，在圖**底部**加一條紅色警示帶 ——
    stderr 會被吞掉，圖上的紅帶不會（照 N95 的先例）。
    """
    parts = list(parts)
    if _OVERFLOW:
        bh = 34 + 26 * len(_OVERFLOW)
        parts.append(f'<rect class="box-bad" x="0" y="{int(h) + 12}" '
                     f'width="{int(w)}" height="{bh}" rx="6"/>')
        parts.append(T(16, int(h) + 12 + 26,
                       f"⚠ RENDER OVERFLOW — {len(_OVERFLOW)} row(s) wider than "
                       f"the column; text collides. Fix the spec, do not ship this.",
                       "annot"))
        for i, (t, over, avail) in enumerate(_OVERFLOW):
            parts.append(T(16, int(h) + 12 + 52 + 26 * i,
                           f"· \u201c{t[:56]}\u201d  +{over}px over {avail}px", "annot"))
        h = int(h) + 12 + bh
    return (f'<svg viewBox="0 0 {int(w)} {int(_height_guard(h))}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" font-family="inherit">'
            + ARROW_DEFS + "".join(parts) + "</svg>\n")



# ═════════════════════════════════════════════════════════════════════════
# 概念構圖 renderer（chain 系列／group_blocks／two_col_link）
#
# 為什麼補這三個：首次實跑那份週報的六張圖，構圖**全部選對了**
# （`composition.relation`／`comp`／守門提問都填了、`off_vocabulary` 全 false），
# 但六張的 `handwritten` 都是 true —— 沒有程式能畫，所以 agent 自己算座標。
# 「箭頭壓字、線對不到框、來回改四輪」是手算座標的必然產物，不是畫圖的人不小心。
# 這三個構圖剛好涵蓋那六張的 6/6（group_blocks ×2、two_col_link ×2、chain_gated ×2）。
#
# schema 不是憑空想的：欄位逐一從 16 張既有 SVG（首次實跑六張、上一版實跑十張）
# 與它們 `composition.spec` 裡的設計意圖反推而來。誰接誰、哪一群包含誰、
# 哪一列要用重點色，這些是**資料**；座標是**結果**，由這裡算。
#
# ⚠️ 三條硬性規則（違反了機械檢查會擋，或畫面會壞）：
#   ① 每個 <text> 帶**恰好一個**用途 class（label／value／annot／def），
#      由 check_deck.py 的 check_purpose() 擋。renderer **預設不產 annot**：
#      annot ≤2、def ≤1 是**整張投影片**的額度（還要跟 deck.json 的 sub／caption
#      合併計數），圖裡隨便一個節點名歸成 annot 就會把額度吃光。
#      節點名、箭頭標籤一律 label，數值一律 value。
#      唯一的例外是 `entry`／`caption` 這種「這張圖怎麼讀」的句子 → annot。
#   ② 箭頭一律用公版 ARROW_DEFS 的 #a／#ah（已寫 markerUnits="userSpaceOnUse"）。
#      ⛔ 不要自己另寫 <marker>：預設的 markerUnits 是 strokeWidth，
#      markerWidth="8" 會渲染成 24px／32px 的巨大三角形，壓到旁邊的字。
#   ③ 一套座標系全用 px、不用 %、不寫 preserveAspectRatio、同一排節點統一 top 與 height。
#      → references/diagram-craft.md
# ═════════════════════════════════════════════════════════════════════════

# ⭐ 數字的**唯一出處是 `references/diagram-craft.md §6`**（N68）。這裡兩個常數
#   都只是「呼叫端沒指定時的預設」，⛔ 不要在這裡另立一套。
CW = 1420          # viewBox 寬。⛔ 全域固定 1420，手繪圖也一樣（diagram-craft §6）。
                   # 1456 是投影片的**可用寬**（1600 − 72×2），不是圖的寬 ——
                   # 既有 16 張圖一律 1420，shoot.py 的密度門檻也照 1420 校準。
HMAX = 537         # viewBox 高的**預設**預算。⚠️ N67 之後改了依據：舊值 540 來自
_HMAX_DEFAULT = HMAX   # `--all`／`--demo` 逐張重設用；⛔ 不要在別處再寫一次 537
                   # 「topic + h2 + takeaway」那一格，而 takeaway 已停用、那一列被刪掉。
                   # 新值取 §6 表格**最小**的那一格（topic+h2+sub 有圖說 = 537）——
                   # 沒傳 `--budget` 時寧可畫小（浪費空間、看得到）也不要溢位（被靜靜裁掉）。
                   # ⭐ 這頁到底幾 px **記在 spec 檔的 `budget` 欄位**（N121 之後的
                   # 唯一記錄處），`--budget` 只是臨時覆寫 —— renderer 看不到這張圖
                   # 要放在哪一種頁上，猜不出來。
                   # ⛔ 不要拿它當「圖就該這麼高」：實跑那 13 頁一頁都沒有 topic，
                   #    正確預算是 **680**，比這個預設多 143px。

# ── 垂直節奏：8pt 基線網格（任務 6 L1）────────────────────────────
# ⭐ 數字的**唯一出處是 `references/diagram-craft.md §6b`**（比照 §6 的高度預算，N68）。
#   ⛔ 不要在各 renderer 裡另挑一個看起來差不多的值 —— 上一版就是這樣挑出
#   「群內 30–32、群間 50」的：**比值 1.56**，而 Gestalt 的鄰近律要 1.75~2 倍才生效，
#   於是分群訊號其實是那條 `.rule` 分隔線在扛，空間沒有在分群。
#
#   GRID     8   所有 `<text>` 的 y 一律落在 8 的倍數上（基線網格）
#   ROW     32   群內行距 —— 同一群裡的相鄰兩列（= 4 × GRID）
#   GROUP   64   群間 = **2 × ROW** ⭐ 這是整個 L1 的關鍵比值
#   SECTION 96   段間 = 3 × ROW（盒內大分段，目前保留給更深的層級）
#   LEAD    48   標題列（`label lead` 26px）自己佔的高
#
# ⚠️ 具名豁免：`read_pileup`／`haplotype_split` 一族走**內容尺寸**座標系
#   （檔頭 N89／N91，`grep -n raw-size` 是那批釘子的清單），CELL_H／ROW_H／PAD
#   不受本網格約束 —— 那套座標系的一格是 26px，硬套 8pt 會把 base 格子畫歪。
GRID = 8
ROW = 32
GROUP = 2 * ROW
SECTION = 3 * ROW
LEAD = 48


def _g8(v):
    """吸附到 8pt 網格（四捨五入）。⛔ 不要用 floor —— 往下吸會讓框比內容短。"""
    return int(round(float(v) / GRID) * GRID)


# ── 盒內留白：**盒寬的函數**，⛔ 不是固定 26px（任務 6 L2）─────────
# 理由：SVG 會等比縮到版面，而每張圖的 viewBox 高不同 → 縮放倍率不同，
# **同一個固定值在不同尺寸的圖上縮出來的光學留白就不一樣** ——
# 這是「有的圖看起來擠、有的鬆」的隱形原因。
# 4% 是校準值：全寬 1420 → 40（上限），grid 一格 ~520 → 24，chain 的 1/3 格 ~440 → 16。
# 上下限都給（N56：單向的規則會被推到另一個極端）——
# 下限 16（2 × GRID）免得窄格連字都放不下，上限 40 免得全寬圖把可用寬吃掉太多。
PAD_FRAC = 0.04
PAD_MIN, PAD_MAX = 2 * GRID, 40


def _pad(w):
    """盒內留白。回傳值一定落在 8pt 網格上。"""
    return min(PAD_MAX, max(PAD_MIN, _g8(w * PAD_FRAC)))


# ── N93 ①：`tone` 的字彙**只有一組**（批次 5g）──────────────────
#    ⚠️ 舊版兩支排法查兩張**不同**的表：`TONE_GRP={hl,null,ctl}` vs
#    `TONE_BOX={hl,bad,good}`。而排法是依 `members`／`rows` 的形狀**自動**選的
#    （`render_group_blocks()`／`render_chain()`），寫 spec 的人選不了 →
#    `tone:"null"`（預期歸零）在 rows 靜默變成一般色，**而「預期歸零」正是
#    那個框存在的全部理由**；反過來 `tone:"bad"` 在 grid 也靜默失效。
#    文件（`composition-vocabulary.md`）又寫「`tone` **一律**吃四個語意值」
#    —— 對兩支都不成立。
#    ⭐ 修法：字彙表只有 TONE 這一份，兩種形狀各自把它映到自己的 class 前綴；
#    ⛔ 缺的 class 已補進 `assets/deck.css`，不靠「查不到就退回一般色」蓋過去。
# ── ⛔ `"hl"` 已從形狀的 tone 字彙**移除**（6c 使用者回饋，2026-09-05）────
#    > 「框線還是可以用顏色分類，但不要有特別除出一個的強調框線（剛剛是黃色的）」
#    ⭐ 形狀的顏色只回答「這是哪一類」，⛔ 不回答「這一個特別重要」。
#    強調只剩**字**（`svg .hl`）與**表格列**（`rowclass:"hl"`）。
#    ⚠️ 留下的四個全是分類：bad／null＝這裡不對勁、good＝通過、ctl＝控制變數。
TONE = ("bad", "good", "null", "ctl")
TONE_BOX = {t: f"box-{t}" for t in TONE}     # 一般方框／橫列
TONE_GRP = {t: f"grp-{t}" for t in TONE}     # 群組外框（grid）
# ── ⭐ 第三種顏色角色：**區別**（使用者裁決，2026-09-05）──────────────────
# 使用者原話（⛔ 判準的來源）：「就是 block 都要上色，這樣才分的開，現在完全沒有色彩」
#
# ⚠️ 在這之前顏色只有兩種角色：**強調**（6c 已從形狀拿掉）與**分類**（bad/good/null/ctl）。
# ⛔ 而分類**要有 good/bad 這條軸才適用** —— 實測 7 張圖有 4 張根本沒有那條軸
#   （A1 兩群是兩種讀者、A2／B1 是同一條流程的三步、B3 是左右對應），
#   於是 21 個框全部同一個灰。⭐ **不是沒填，是字彙裡沒有這一級**（同 6a／N118）。
#
# ⭐ `c1`~`c6` 回答「這是並列的哪一個」，⛔ 不回答好壞、不回答重不重要。
# ⭐ **色數不是「看起來夠用」，是從這個 skill 自己宣告的並列上限推出來的**：
#   一張圖最多的並列框是 `two_col_link` 的左右兩欄，每欄上限是
#   `check_deck.LIMITS["col_items"]` = 6 → **6 + 6 = 12**。
#   ⭐ 所以 12 個色**剛好蓋滿字彙允許的最大情形**，一張合法的圖不必重複用色。
# ⚠️ 上限若改，`assets/deck.css` 的色票與這裡要一起改。
CAT = tuple(f"c{i}" for i in range(1, 13))


def _cat_of(name, used):
    """這個並列項該拿哪一個區別色。`used` 是**這一張圖**的 {種子: 色號}。

    ⭐ **同一個種子一定拿同一個色**（先查表）—— 兩個用途，缺一不可：
    ① `chain` 的關卡框用它前面那一格的名字當種子 → **關卡與它的步驟同色**，
       一眼看得出「這一關屬於這一欄」。⛔ 這與 N34 無關：N34 禁的是關卡繼承
       **語意色**（`gate_tone`），⭐ 那是主張；這裡繼承的是「屬於哪一欄」，那是事實。
    ② 同一個名字在同一張圖出現兩次不會拿到兩個色。

    ⭐ **再來才是名字的雜湊，⛔ 不是位置**：位置編號會讓同一個東西在不同頁拿到
    不同顏色（A1 排第 2、A3 排第 3），⛔ 那正是 L4-2 要擋的跨頁不一致，
    我們不該自己製造。名字雜湊 → **同一個名字全 deck 同一個顏色**，且不必填 spec。

    ⚠️ 雜湊會撞，撞到就往後找第一個沒被用掉的 —— ⭐ **「同一張圖裡分得開」優先於
    「跨頁同色」**（⛔ 使用者的原話是「這樣才分的開」）。
    ⚠️ 代價要講清楚：撞號的那張圖上，那個名字的色會跟別頁不一樣。⛔ 不是 bug，
    是兩個目標無法同時滿足時的取捨 —— 所以 `check_deck` 的 L4-2
    **只比容器族（box／grp），不比色號**，見 `_container()` 的 docstring。

    ⛔ `hash()` 不能用（PYTHONHASHSEED 每次不同 → 圖不可重現，
    N121 那條「重跑要逐 byte 重現」會立刻紅）。用 md5。
    """
    key = str(name)
    if key in used:
        return used[key]
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    taken = set(used.values())
    for k in range(len(CAT)):
        c = CAT[(h + k) % len(CAT)]
        if c not in taken:
            used[key] = c
            return c
    # ── 色用完了：⛔ **不准靜默重複** ─────────────────────────────────
    # ⚠️ 舊版直接 `CAT[h % len(CAT)]` 繞回去用 —— 那正是這個 skill 一直在打的形狀：
    #   **看圖看不出來、看程式碼也看不出來**，讀者只會覺得「這兩個框好像是同一類」。
    # ⭐ 12 個色已經蓋滿字彙允許的最大情形（two_col_link 6+6），所以走到這裡
    #   代表**這張圖的並列項超過字彙自己訂的上限**，那是內容的問題，不是配色的問題。
    used[key] = CAT[h % len(CAT)]
    print(f"[figure] ⚠️ 這張圖的並列項超過 {len(CAT)} 個，區別色**開始重複使用**"
          f"（「{key}」與另一個框同色）—— 讀者會以為它們是同一類。\n"
          f"[figure]    ⭐ {len(CAT)} 是從字彙自己的上限推的（two_col_link 兩欄各 ≤6）"
          f"——超過它代表**這一頁塞了字彙不打算讓你塞的量**。\n"
          f"[figure]    三個正解，由優到劣：① 分群（把同類的收成一個框，"
          f"框內用 blocks 分小標）；② 拆頁；③ 減項。\n"
          f"[figure]    ⛔ 不要靠加色票解決 —— 12 個色已經是人眼分得開的上限附近。",
          file=sys.stderr)
    return used[key]


def _shape_cls(kind, tone, name, used):
    """一個容器的 class。⭐ **明寫的分類色永遠贏過自動的區別色。**

    ⛔ 順序不能反：`bad`／`good`／`null`／`ctl` 是**主張**（這個東西是舊的／通過了），
    區別色只是「這是並列的哪一個」。⭐ 有主張的時候，主張優先。
    """
    if tone:
        return (TONE_GRP if kind == "grp" else TONE_BOX)[tone]
    return f"{kind}-{_cat_of(name, used)}"


MONO = ' style="font-family:ui-monospace,monospace"'


def _n(v):
    """座標一律輸出成乾淨的數字（整數就不要有 .0）。"""
    return int(v) if float(v) == int(v) else round(float(v), 1)


def T(x, y, s, cls="label", anchor=None, mono=False, style=""):
    """一則文字。⚠️ cls 必須含**恰好一個**用途 class（label／value／annot／def）。

    ⛔ **`style` 不再拿來表層級**（任務 6 L0）：小標／詞條／釋義／序號現在是
    `deck.css` 的 `label.section`／`.term`／`.gloss`／`.num` 四個角色 class ——
    ⭐ 層級只剩一個來源，跨頁才會長一樣。inline 字級／字重由
    `check_deck.py` 的 `check_inline_type()` 報 ERROR，這裡傳了也會被擋下來。
    ⛔ 也不要用它改顏色 —— 淺色在字彙表裡只給 annot／def，label 一律正常色。
    ⚠️ 參數留著是給 read／haplotype 那一族（內容尺寸座標系，見檔頭 N89／N91）。
    """
    a = f' text-anchor="{anchor}"' if anchor else ""
    st = (MONO if mono else "") or (f' style="{style}"' if style else "")
    if mono and style:
        st = f' style="font-family:ui-monospace,monospace;{style}"'
    return (f'<text x="{_n(x)}" y="{_n(y)}" class="{cls}"{a}'
            f'{st}>{esc(s)}</text>')


def BOX(x, y, w, h, cls="box"):
    return (f'<rect class="{cls}" x="{_n(x)}" y="{_n(y)}" '
            f'width="{_n(w)}" height="{_n(h)}" rx="6"/>')


def RULE(x1, y, x2):
    return f'<line class="rule" x1="{_n(x1)}" y1="{_n(y)}" x2="{_n(x2)}" y2="{_n(y)}"/>'


def LINK(x1, y1, x2, y2):
    """兩個節點之間的連線。線頭離節點邊 6–10px 由呼叫端負責（這裡只畫）。

    ⛔ 舊版有 `hl=True` → `arrow-hl`（金線）。**已移除**（6c 使用者回饋）：
    強調線跟強調框是同一個裝置 —— 在一堆同類的線裡把一條塗成金色，
    回答的是「這一條特別重要」，而形狀的顏色只該回答「這是哪一類」。
    """
    cls = "arrow"
    d = (f"M{_n(x1)},{_n(y1)} H{_n(x2)}" if y1 == y2
         else f"M{_n(x1)},{_n(y1)} L{_n(x2)},{_n(y2)}")
    return f'<path class="{cls}" d="{d}"/>'


def _lines(v):
    """欄位可以給字串或字串陣列，一律正規化成陣列。"""
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _gate_lines(v):
    """關卡文字：陣列照用；字串含破折號時拆成「名字／確認的東西」兩行。

    來源：three_layers.svg 的 `gate 1 — you confirm the thread list`
    在版面上就是上下兩行（框高 96、兩行分別在 +40 與 +76）。
    """
    if isinstance(v, (list, tuple)):
        return list(v)
    if not v:
        return []
    for sep in (" — ", " – ", " -- "):
        if sep in v:
            a, b = v.split(sep, 1)
            return [a.strip(), b.strip()]
    return [v]


def _tw(s):
    """一段文字的粗估寬度（以「半形字」為單位）。CJK 與全形符號算兩格。

    為什麼要估：欄位若平均分寬，長的那欄會撞到下一欄（實測撞過）。
    這裡只要求「不撞」，不要求精準——真正的排版由瀏覽器做。
    """
    return sum(2 if ord(c) > 0x2E7F else 1 for c in str(s))


def _col_x(rows, x0, x1, pad=3):
    """整張表**共用**一組欄位起點：每欄取所有列裡最寬的內容，再依比例攤到可用寬。

    ⚠️ 逐列各自算寬會讓同一欄在不同列對不齊 —— 那是表格最基本的失效。
    """
    ncol = max(len(r) for r in rows)
    ws = [max([_tw(r[i]) for r in rows if len(r) > i] or [1]) + pad
          for i in range(ncol)]
    tot = float(sum(ws))
    xs, x = [], x0
    for w in ws:
        xs.append(x)
        x += (x1 - x0) * w / tot
    return xs


# ── box 的內部排版（`blocks`）───────────────────────────────────────────
# 為什麼要有這一層（使用者原話）：「block 的內部也是要有明確設計的，不能只是有
# block，然後直接把所有文字都直接填進去，要有明確的分隔和排版」。
#
# 舊資料模型的天花板：一個 box 的內容只有 `lines: [str]` —— **扁平的字串陣列**。
# 於是三組性質完全不同的東西（「每項要寫的四件事」「其他必填欄位」「上限與合併
# 規則」）只能垂直堆成 11 行純文字，作者只好拿 `·` 當分隔符把兩件事塞進同一行。
# 讀者看到的是一段被斷行的文章，不是一張圖。⛔ 密度門檻量不到這件事 —— 塞更多行
# 反而讓密度更高、更像文章。
#
# `blocks` 是 `lines` 的**上位結構，可選**：沒填就完全走舊路徑（既有圖逐位元組不變）。
#
#   "blocks": [
#     {
#       "head": "每項要寫的四件事",       // 子區塊小標（可省）。省略時只靠分隔線分組
#       "tone": "hl",                     // 可省。小標／編號用重點色（accent）
#       "pairs": [["question", "why it was done today"],
#                 ["approach",  "what was done"]]      // ② 對齊的兩欄
#     },
#     {"head": "其他必填欄位", "lines": ["gaps · mandatory on every item"]},  // ① 純文字
#     {"head": "上限與合併", "numbered": ["cap 5 · ties are not split",
#                                        "merge 2 of 4 into 1 item"]}        // ③ 編號子項
#   ],
#   "flow": "row"    // 可省。子區塊**並排**（預設 "col"：由上而下）

#
# 三種內容**擇一**，判別欄位就是內容本身（跟 chain 的 rows／lines 同一個作法，
# 不另外加旗標）：
#   lines[str]          由上往下排（＝舊的 lines，只是包進了子區塊）
#   pairs[[k, v]]       key 一欄、value 一欄。⛔ 不是拿 `·` 串成一行文字。
#                       **key 欄寬由整個 box 的所有 pairs 共同決定** —— 跨子區塊也對齊，
#                       逐區塊各自算寬會讓同一欄在不同子區塊對不齊（表格最基本的失效）。
#   numbered[str]       自動 1 2 3 編號，編號放進一顆 pill，與內容分成兩欄
#                       （A4 手寫圖的 `1 · ACTION_HINT` 就是這種，但那張是用 `·` 串的）
#
# 子區塊之間畫一條 `.rule` 分隔線（間距的正中），這是「block 內還有 block」的可見證據。
#
# `flow`（放在**放 blocks 的那個容器**上：chain 的 step、group_blocks 的 group／member、
# two_col_link 的 left／right 項）：
#   col（預設）  由上而下 —— 窄框（chain row 的 1/n 欄、group_blocks grid 的格子）只能這樣
#   row          並排，中間畫**直的**分隔線 —— **全寬的構圖才放得下**
#                （chain band 的橫幅、group_blocks rows 的整列）。
#                ⚠️ 這不只是好看：band 的高度預算是 (540 − 間距) ÷ 步驟數，
#                   4 個橫幅一格只有 ~126px，子區塊往下堆一定爆；並排是把
#                   1420px 的**寬**拿來用，這才是橫幅該有的幾何。
#
# ⚠️ 高度：blocks 會讓 box 長高，總高仍受 HMAX 約束 —— 超了由 _height_guard 報，
#    ⛔ 不靜默截斷。放不下時的正解是**減少子項或拆頁**，不是把子區塊壓扁回一行。

# ⭐ 任務 6 L1：這一組以前是「看起來差不多」挑出來的（30／32／18／22／26），
#    現在全部由上面的節奏常數推出來，⛔ 不要在這裡另填一個數字。
#    最關鍵的一格是 BLK_SEP：**群間必須 ≥ 2× 行內**，鄰近律才會自己成立。
#    舊值的實際間距是 BLK_ROW + BLK_SEP = 32 + 18 = **50**（比值 1.56，不夠），
#    新值是 32 + 32 = **64**（比值 2.0）。
BLK_HEAD = ROW       # 小標那一列佔的高（32；小標與它自己的內容同一個行距 = 同一群）
BLK_ROW = ROW        # 一個子項的列高（label 22px → 1.45 倍行距）
BLK_SEP = GROUP - ROW  # 兩個子區塊之間**額外**的間距 → 實際群間 = ROW + BLK_SEP = GROUP
BLK_BASE = 24        # 一列裡文字基線離該列頂端的距離（8 的倍數，網格才守得住）
BLK_TOP = BLK_BASE   # 呼叫端給的是「下一條基線」→ 退回 BLK_BASE 就是子區塊的頂端，
                     # 於是**第一條基線正好落在呼叫端給的 y 上**（舊值 26 會偏 4px 出格）
BLK_NUMW = 48        # 編號欄的寬（pill 32px + 16px 間隔，都在網格上）
BLK_PILL = 32        # 編號 pill 的直徑
BLK_KEYMIN = 120     # term 欄的最小寬（太窄的話 gloss 會貼著 term）

# ── L2：定義列是**真的網格**，不是「量完 key 再說」──────────────────
# 舊做法：`kw = max(最寬的 key)*11 + 26`，於是**每個盒子的欄距都不一樣** ——
# 實測 A1 左盒 169px、右盒 180px，差 11px，手挑的痕跡。
# 新做法兩件事：
#   ① term 欄寬 = `TERM_FRAC × 盒寬`（吸附到 8pt），與內容無關 → 同尺寸的盒子必然同寬；
#   ② gloss 從 **固定 gutter** 起算，`GUTTER` **全場同一個值**。
# ⚠️ 安全閥（N94 的立場：不靜默壞掉）：term 真的比配額長時**照樣讓開**，
#    但要出聲 —— 讓開是為了不壓字，不是為了假裝沒事。正解是把 term 寫短
#    （term 是「東西的名字」，不是句子）。
# ⚠️ GUTTER 是 term 與 gloss 之間的**最小**間隔（2 × GRID）。
#   實際看到的空白通常更寬 —— term 欄是**配額**，term 字寫得短就整段留白。
#   ⛔ 不要為了「看起來鬆一點」把它調大：實測 24 會讓 B1 最長的那一列多 3px 壓字
#   （`_blocks_fit` 會畫紅帶），而那 3px 是欄距吃掉的，不是內容變長。
TERM_FRAC = 0.32
GUTTER = 2 * GRID
# 同一個用途（label）裡的層級差只用字重／字級表示 —— 顏色不動（字彙表：淺色只給 annot／def）
# ⭐ 任務 6 L0：層級以前寫在這裡的 **inline `style=`** 上，於是「盒內分段標題」
#    與「定義列的詞條」這兩個角色在字彙裡根本不存在 —— 手寫圖只能抄這三個字串，
#    抄錯或自己發明就是跨頁不一致。現在它們是 `deck.css` 的四個角色 class，
#    ⛔ **層級只剩一個來源**；`check_inline_type()` 把門關上（inline 字級／字重 = ERROR）。
#    ⚠️ 值一個都沒動（見 deck.css 那段註解）—— 這一批只搬家。
BLK_HEAD_CLS = "section"     # 盒內的分段標題
BLK_KEY_CLS = "term"         # 定義列左欄：東西的名字
BLK_VAL_CLS = "gloss"        # 定義列右欄：那個名字的一句話
BLK_NUM_CLS = "num"          # 編號欄的序號

_BLK_USED = [False]  # 這張圖有沒有用到 blocks —— 只給超高時的訊息用，不影響輸出


def _blocks(v):
    """正規化 box 的 `blocks`。字串／字串陣列會被當成一個沒有小標的 lines 子區塊。"""
    out = []
    for b in (v or []):
        if not isinstance(b, dict):
            b = {"lines": _lines(b)}
        kinds = [k for k in ("lines", "pairs", "numbered", "glyph") if b.get(k)]
        if len(kinds) > 1:
            sys.exit(f"[figure] 一個 block 只能有一種內容（lines／pairs／numbered／glyph），"
                     f"收到 {'、'.join(kinds)}。要幾種一起用就拆成幾個 block —— "
                     f"那正是 blocks 存在的理由。")
        if b.get("glyph"):
            glyphs.height(b)            # 不認得的 glyph 名在這裡就擋，不等到畫
        if b.get("pairs") and any(len(p) != 2 for p in b["pairs"]):
            sys.exit("[figure] blocks 的 pairs 每一項要恰好兩格 [key, value]。"
                     "要放三欄請改用 chain band 的 rows[]。")
        out.append(b)
    return out


def _blk_rows(b):
    return b.get("lines") or b.get("pairs") or b.get("numbered") or []


def _blk_h1(b):
    if b.get("glyph"):                  # 小圖：高只由參數決定（glyphs.py 檔頭契約）
        return (BLK_HEAD if b.get("head") else 0) + glyphs.height(b)
    return (BLK_HEAD if b.get("head") else 0) + BLK_ROW * len(_blk_rows(b))


def _blocks_h(blocks, flow="col"):
    """blocks 佔的高。⚠️ 這支與 _blocks_svg 的推進量必須逐項對得上，
    不然框會比內容短，最後一列掉到框外面（既有程式踩過這個坑）。"""
    if not blocks:
        return 0.0
    if flow == "row":                       # 並排：高度由最高的那一個子區塊決定
        return max(_blk_h1(b) for b in blocks)
    h = 0.0
    for i, b in enumerate(blocks):
        if i:
            h += BLK_SEP
        h += _blk_h1(b)
    return h


def _blocks_w(blocks, flow="col"):
    """blocks 需要的粗估寬（半形字 × 11px ＋ 兩側留白）。給欄寬要自己算的構圖用。"""
    if flow == "row":                       # 並排：每個子區塊各要一份寬
        return sum(_blocks_w([b]) for b in blocks)
    w = 0.0
    for b in blocks:
        if b.get("head"):
            w = max(w, _tw(b["head"]) * HEAD_PX + 48)
        for p in (b.get("pairs") or []):
            w = max(w, _tw(p[0]) * TERM_PX + GUTTER + _tw(p[1]) * LABEL_PX + 48)
        for ln in (b.get("lines") or []):
            w = max(w, _tw(ln) * LABEL_PX + 48)
        for ln in (b.get("numbered") or []):
            w = max(w, _tw(ln) * LABEL_PX + BLK_NUMW + 48)
        if b.get("glyph"):
            w = max(w, glyphs.min_width(b))
    return w


# ⚠️ 密度門檻（shoot.py 65%）只量「有沒有填滿」，**量不到「填得有沒有結構」**
#    —— FINDINGS N56。上一輪為了衝密度，builder 就往格子裡塞更多行，反而更像文章
#    （使用者原話：「整個解釋都只是像文章寫在 block 的下面而已，沒有明確的分隔和排版」）。
#    blocks 讓「有結構」變得可能，但**沒有東西在要求它** —— 單向的門檻會把 agent 推到
#    另一個極端，所以這裡補上反向的那一半。
#
# 門檻 5 的理由（不是拍腦袋的數字）：slide_types.md 對「一個節點裡的清單」訂的是
#   `items ≤ 4`；5 是給圖多留一行餘裕之後的**同一條線**。6 行以上還不分組，
#   讀者就只能從上讀到下 —— 那已經是一段被斷行的文章，不是一張圖（A1 那格是 10 行）。
# ⛔ 只警告不擋：這支是產圖工具，擋在這裡會讓 builder 卡死；該擋的位置是
#   shoot.py／check_deck.py。
FLAT_MAX = 5


def _flat_check(where, n, structured):
    """一格塞了太多純文字、又完全沒有分組結構 → 出聲。⛔ 不擋。"""
    if structured or n <= FLAT_MAX:
        return
    print(f"[figure] ⚠️ 「{str(where)[:40]}」這一格有 {n} 行純文字、**沒有任何分隔** "
          f"—— 超過 {FLAT_MAX} 行不分組，讀者只能從上讀到下，那是一段被斷行的文章，"
          f"不是一張圖。\n"
          f"[figure]    改用 box 內的 `blocks`（三種內容擇一，一格可以放好幾個）：\n"
          f"[figure]      pairs[[k, v]]  key 與 value **各自對齊成欄**"
          f"（⛔ 不要再用 `·` 把兩件事串成一行）\n"
          f"[figure]      numbered[str]  自動編號，編號進 pill，與內容分兩欄\n"
          f"[figure]      lines[str]     純文字，但**包在帶小標的子區塊裡**\n"
          f"[figure]    每個子區塊給一個 `head`，子區塊之間會自動畫分隔線；"
          f"全寬的構圖再加 \"flow\": \"row\" 讓子區塊並排（不吃高）。", file=sys.stderr)


# ── 字寬：**量出來的，不是估的**（任務 6 L2）────────────────────
# 方法：playwright 開 deck.en.html，對 247 則 `<text>` 逐則
# `getComputedTextLength() ÷ 半形單位數`（`_tw`），再按 class／字重／字族分組取平均。
# ⛔ 舊版全檔一律 11 —— 對 `label.term` 的**等寬字**低估 21%，
#    於是 B1 的「thread list」直接壓在「layer1.md」上（改版前後同樣壓，
#    ⚠️ 那是舊缺陷不是 6b 造成的），而對一般 label 又高估 7%，
#    白白讓 `_blocks_fit` 報假的溢位。
#   實測：label / label.gloss 22px/400 → 10.2、10.3；label.term 22px/600 比例字 → 11.5；
#         label.term 22px/600 等寬 → 13.31（正好 0.605em）；label.section 20px/700 → 10.35。
#   下面取的是**實測值往上留一格**，量尺寧可保守（寧可提早喊擠，不要漏掉壓字）。
LABEL_PX = 10.5      # label／label.gloss（22px / 400）
HEAD_PX = 10.5       # label.section（20px / 700）
TERM_PX = 12         # label.term（22px / 600）比例字
TERM_MONO_PX = 14    # label.term（22px / 600）等寬 —— ⛔ 用 TERM_PX 會壓字


def _term_w(boxes, w, mono=False, where=""):
    """定義列的 term 欄寬（＝ gloss 相對於盒左緣的 x）。

    ⭐ L2：**先按盒寬配額，內容只當安全閥**。
    ⛔ 舊做法是反過來的（量最寬的 key 再加 26），於是欄距跟著內容浮動 ——
    實測 A1 兩個同寬的盒子欄距 169 vs 180，那正是「手挑」留下的指紋。

    ⚠️ `boxes` 是**一串 blocks 清單**，不是一個：同一排／同一格線上的盒子寬度相同，
    欄距就必須是同一個值 —— 這與既有的「同一排統一 top 與 height」是同一條規矩。
    ⛔ 逐盒各自算，同一欄在不同盒子就對不齊（表格最基本的失效）。
    ⚠️ 例外是 **band 的並排子區塊與 two_col_link 的兩欄**：那些盒子寬度本來就不同，
    共用一個欄距只會讓窄的那一格壓字（實測 A2 共用會多 19px 溢位）→ 各自算。
    """
    keys = [p[0] for blocks in boxes for b in blocks for p in (b.get("pairs") or [])]
    if not keys:
        return 0
    quota = max(_g8(TERM_FRAC * w), BLK_KEYMIN)
    need = _g8(max(_tw(k) for k in keys) * (TERM_MONO_PX if mono else TERM_PX))
    if need > quota:
        # 讓開，但要出聲：讓開是為了不壓字，不是為了假裝沒事。
        print(f"[figure] ⚠️ 定義列的 term 欄被內容撐開{where}：配額 {quota}px "
              f"（盒寬 {int(w)} × {TERM_FRAC}），最長的 term 要 {need}px —— "
              f"這一格的欄距會與其他構圖不一致。\n"
              f"[figure]    正解是把 term 寫短（term 是**東西的名字**，不是句子），"
              f"⛔ 不要靠縮字級或改 TERM_FRAC 把它蓋過去。", file=sys.stderr)
    return min(max(quota, need), _g8(w * 0.62)) + GUTTER


_CAT_USED = {}      # 這一張圖的 {種子: 色號}（⛔ 逐圖獨立，產圖前由呼叫端清空）
_OVERFLOW = []      # N94：這一次 render 撞到的壓字，收集起來畫進圖裡


def _blocks_fit(blocks, w, kw):
    """裝不下就**明講**，而且要**畫在圖上**。回 True＝裝得下。
    ⛔ 不靜默截斷、也不縮字級（縮了 shoot.py 的有效字級會報）。

    ⚠️ 只有這裡量得到「一列放不放得下」：欄寬是 renderer 算的，寫 spec 的人看不到。
    量的尺與全檔一致（label 22px 約 11px／半形字），只求「不撞」不求精準。

    ## 為什麼不是 `sys.exit`（N94，批次 5g）

    `composition-vocabulary.md` 舊版寫「renderer **拒絕產圖**並說明改法」，
    而本函式的唯一出口是一行 stderr，**回傳值也沒有人看** ——
    字壓到隔壁的圖照樣產出、照樣被內嵌，而 `shoot.py` 量的是 `.slide` 的
    `scrollHeight`，**量不到 SVG 內部的橫向壓字** → 沒有任何一關擋得住，
    而 stderr 在 subagent 流程裡最容易被吞掉。

    ⭐ 照 **N95 的先例**（5d：缺 `src` 渲成顯眼的紅色缺頁，不 `sys.exit`）：
    **照樣產圖，但把壓字畫成圖底一條紅色警示帶**。
    `sys.exit` 的反方向失效是「一個過長的 value 讓整份 deck 渲染不出來」——
    半成品階段那是災難；而看得見的紅帶**沒有人會當作沒看到**。
    """
    worst = ("", 0.0)
    for b in blocks:
        rows = [(b["head"], _tw(b["head"]) * HEAD_PX) for _ in [0] if b.get("head")]
        rows += [(f"{k} · {v}", kw + _tw(v) * LABEL_PX) for k, v in (b.get("pairs") or [])]
        rows += [(l, _tw(l) * LABEL_PX) for l in (b.get("lines") or [])]
        rows += [(l, BLK_NUMW + _tw(l) * LABEL_PX) for l in (b.get("numbered") or [])]
        if b.get("glyph"):
            rows.append((f"glyph {b['glyph']}", glyphs.min_width(b)))
        for t, need in rows:
            if need - w > worst[1]:
                worst = (t, need - w)
    if worst[1] > 0:
        print(f"[figure] ⚠️ box 內的子區塊裝不下：「{worst[0][:44]}」超出欄寬 "
              f"{int(worst[1])}px（可用 {int(w)}px）—— 字會壓到隔壁或衝出框。\n"
              f"[figure]    ⛔ 不要縮字級。三個正解：把 value 寫短（子區塊的 value 是"
              f"**事實**不是句子）／把並排的 flow 改回 \"col\"（縱向有整格的寬）／"
              f"減少並排的子區塊數。", file=sys.stderr)
        _OVERFLOW.append((worst[0], int(worst[1]), int(w)))
    return worst[1] <= 0


def _blocks_svg(blocks, x, y, w, mono=False, flow="col", kw=None):
    """把 blocks 畫在 (x, y) 起、寬 w 的區域裡。

    ⚠️ `y` 給的是**下一條基線**（跟各 renderer 內部的 ly／ty 同一個意思），
       不是區塊頂端 —— 這樣呼叫端不必為了接上 blocks 而改自己的行距算法。
    回 (parts, 下一條基線的 y)。
    """
    if not blocks:
        return [], y
    _BLK_USED[0] = True
    if flow == "row":                       # 並排：每個子區塊自己一欄，遞迴畫
        parts, cw = [], w / len(blocks)
        vh = _blocks_h(blocks, "row")       # 直線一律跨**最高**的那一個子區塊，
        for i, b in enumerate(blocks):      # 各自算高的話幾條線長短不一，像沒對齊
            if i:                           # 並排的分隔線是**直的**（畫在間距正中）
                vx = x + i * cw - BLK_SEP / 2
                parts.append(f'<line class="rule" x1="{_n(vx)}" y1="{_n(y - BLK_TOP)}" '
                             f'x2="{_n(vx)}" y2="{_n(y - BLK_TOP + vh)}"/>')
            bp, _ = _blocks_svg([b], x + i * cw, y, cw - BLK_SEP, mono=mono)
            parts += bp
        return parts, y + _blocks_h(blocks, "row")
    parts = []
    top = y - BLK_TOP
    kw = _term_w([blocks], w, mono) if kw is None else kw
    _blocks_fit(blocks, w, kw)
    for i, b in enumerate(blocks):
        if i:
            # ⭐ L1：群間已經是行內的 2 倍（64 vs 32），**空間自己在分群** ——
            #    分隔線於是從「必要」降級成「只有沒有小標時才需要」。
            #    有小標的子區塊：小標本身就是分組訊號，再畫一條線是同一件事講兩次
            #    （病③：分組、強調、語意全壓在同一個訊號上）。
            if not b.get("head"):
                parts.append(RULE(x, top + BLK_SEP / 2, x + w))
            top += BLK_SEP
        hl = " hl" if b.get("tone") == "hl" else ""
        if b.get("head"):
            parts.append(T(x, top + BLK_BASE, b["head"], f"label {BLK_HEAD_CLS}" + hl))
            top += BLK_HEAD
        if b.get("glyph"):
            parts += glyphs.draw(b, x, top, w)
            top += glyphs.height(b)
        elif b.get("pairs"):
            for k, v in b["pairs"]:
                parts.append(T(x, top + BLK_BASE, k, f"label {BLK_KEY_CLS}", mono=mono))
                parts.append(T(x + kw, top + BLK_BASE, v, f"label {BLK_VAL_CLS}"))
                top += BLK_ROW
        elif b.get("numbered"):
            for j, ln in enumerate(b["numbered"], 1):
                py = top + (BLK_ROW - BLK_PILL) / 2
                parts.append(f'<rect class="pill" x="{_n(x)}" y="{_n(py)}" '
                             f'width="{BLK_PILL}" height="{BLK_PILL}" '
                             f'rx="{BLK_PILL // 2}"/>')
                parts.append(T(x + BLK_PILL / 2, top + BLK_BASE, str(j),
                               f"label {BLK_NUM_CLS}" + hl, anchor="middle"))
                parts.append(T(x + BLK_NUMW, top + BLK_BASE, ln, "label"))
                top += BLK_ROW
        else:
            for ln in (b.get("lines") or []):
                parts.append(T(x, top + BLK_BASE, ln, "label", mono=mono))
                top += BLK_ROW
    return parts, top + BLK_TOP


# ── ① chain 系列 ────────────────────────────────────────────────────────
# **一個 renderer 掛三個名字**（chain／chain_focus／chain_gated），不是三個 renderer。
#
# 判斷理由（依 BACKLOG B1 要求，跑過兩份 deck 之後才決定的）：
#   · 兩者的**幾何完全相同** —— 等寬的一排框加箭頭。差別只有 `steps[].gate`
#     有沒有值（下方多一排關卡框），**資料上看得出來**，符合字彙表
#     「由 JSON 的判別欄位決定用哪一個，不由 agent 挑」。
#     拆成兩個 renderer 等於把同一份幾何抄兩遍，改一次要改兩處。
#   · 實測分佈支持這個切法：首次實跑的 chain_gated ×2（three_layers 有 gate、
#     selection_score 有 gate＋表格）。
# ⛔ **`chain_focus` 已於 6c 廢除**（使用者裁決：形狀的顏色只做分類，不做強調）——
#    它與 chain 的唯一差別就是 `focus` 那一格上重點色，而重點色沒有了，
#    這個名字就沒有內容了。`focus` 欄位現在會直接報錯（見 `_step_tone`）。
#
# 兩種排法（`layout`），來源也是實測：
#   row  ── 一排橫向的格子＋箭頭（three_layers、pipeline）
#   band ── 由上而下的全寬橫幅、**不畫箭頭**（selection_score）
#           選它的時機是「某一格裝得下一張表」：格子裡有表就塞不進橫向的 1/n 寬。
#           selection_score 的修訂紀錄寫得很直接：橫幅間距只剩 14~16px，
#           畫箭頭是噪音，順序由 1／2／3／4 的編號承擔。
#   省略 `layout` 時：任一格有 `rows` → band，否則 row。

def render_chain(spec):
    steps = spec.get("steps") or []
    if not steps:
        sys.exit("[figure] chain 需要 steps[]")
    layout = spec.get("layout") or ("band" if any(s.get("rows") for s in steps) else "row")
    if layout not in ("row", "band"):
        sys.exit(f"[figure] chain 的 layout 只能是 row 或 band，收到「{layout}」")
    return (_chain_band if layout == "band" else _chain_row)(spec, steps)


def _bad_tone(where, tone):
    """`tone:"hl"` 已廢除 —— ⛔ 明確報錯，不要靜默退回一般色。
    N93 的教訓：靜默失效是最難查的一種，寧可當場擋下來。"""
    sys.exit(f'[figure] {where} 的 tone:"hl" 已廢除（6c 使用者回饋）——'
             f'形狀的顏色只做分類，不做強調。要強調就標在**字**上'
             f'（`<text class="... hl">`），或把它放大／放中間／放第一個。'
             f'分類色仍可用：{"／".join(TONE)}。→ presentation_rules §5')


def _step_tone(spec, st):
    """⚠️ 回的是**完整 class**，不是 tone —— 沒填 tone 時自動配一個區別色。"""
    tone = st.get("tone")
    if tone == "hl":
        _bad_tone(f'steps[{st.get("id")}]', tone)
    if spec.get("focus"):
        sys.exit('[figure] chain 的 `focus` 已廢除（6c 使用者回饋）—— 它唯一的作用'
                 '就是把那一格塗成強調框，而強調框已從字彙拿掉。'
                 '要指出「看這一格」請靠標題與該格內的一處金字。→ presentation_rules §5')
    return _shape_cls("box", tone, st.get("label") or st.get("id"), _CAT_USED)


def _chain_row(spec, steps):
    # 間隙 = 箭頭桿 ＋ 兩端各 8px 留白。⚠️ B17-9：箭頭頭升到 ARROW_H=12 之後，
    #   `check_arrow_legible` 要求桿 ≥ 3× 頭 = 36px；舊值 48 只剩 32px 的桿，
    #   3 格以上的 chain row **必然** WARN，而那是 renderer 的常數不是 spec 寫壞。
    #   56 是 8 的倍數（diagram-craft §6 的網格），桿 40px ≥ 36。
    # ⭐ 更舊的 65 是手挑的，白白吃掉框寬，而框寬正是定義列擠不擠的來源。
    gap = 56
    n = len(steps)
    w = (CW - gap * (n - 1)) / n
    pad = _pad(w)                              # L2：留白是盒寬的函數，⛔ 不是固定 26
    # 同一排統一 top 與 height —— 高度不齊就得每條線各算一次 y，錯一條歪一條。
    # 高度 = 標題列(LEAD) + 分隔線 + 第一行(112) + 其餘每行 ROW + 底部留白
    # ⚠️ 這裡少算一行就會讓最後一行**掉到框外面**（實測踩過），所以用「最後一行的
    #    基線」倒推，不要用「行數 × 行高」估。
    body = max(len(_lines(s.get("lines"))) for s in steps)
    # 子區塊（可選）：只往既有高度上「加」，沒填時 blk = 0。
    blk = max(_blocks_h(_blocks(s.get("blocks")), s.get("flow", "col")) for s in steps)
    h = _g8(max(128, 112 + ROW * max(0, body - 1) + 24 + blk
                     + (LEAD if any(s.get("value") for s in steps) else 0)))
    # L2：同一排的框同寬 → 定義列的欄距也必須是**同一個值**，逐框各自算會對不齊。
    kw = _term_w([_blocks(s.get("blocks")) for s in steps], w - 2 * pad,
                 any(s.get("mono") for s in steps), "（chain row）")
    top = 16
    parts, gates = [], [s for s in steps if s.get("gate")]
    for i, st in enumerate(steps):
        x = i * (w + gap)
        big = spec.get("focus") and st.get("id") == spec["focus"]
        y, hh = (top - 16, h + 32) if big else (top, h)
        parts.append(BOX(x, y, w, hh, _step_tone(spec, st)))
        ty = y + LEAD
        parts.append(T(x + pad, ty, st.get("label", ""), "label lead", mono=st.get("mono")))
        parts.append(RULE(x + pad, y + GROUP, x + w - pad))
        ly = y + 112
        if st.get("value"):
            parts.append(T(x + pad, ly, st["value"], "value"))
            ly += LEAD
        _flat_check(st.get("label"), len(_lines(st.get("lines"))),
                    bool(st.get("blocks")))
        for ln in _lines(st.get("lines")):
            parts.append(T(x + pad, ly, ln, "label"))
            ly += ROW
        bp, ly = _blocks_svg(_blocks(st.get("blocks")), x + pad, ly, w - 2 * pad,
                             mono=st.get("mono"), flow=st.get("flow", "col"), kw=kw)
        parts += bp
        if i:                                  # 箭頭畫在間隙正中，兩端各離框 8px
            parts.append(LINK(x - gap + 8, top + h / 2, x - 8, top + h / 2))
    y = top + h + 24
    if gates:
        for i, st in enumerate(steps):
            if not st.get("gate"):
                continue
            x = i * (w + gap)
            # 關卡框的顏色由 spec 決定，不寫死（原本寫死 "box-hl"，於是每個關卡
            # 都是金色，語意色被稀釋且**改 deck 改不掉** —— FINDINGS N34）。
            # ⚠️ 預設一般色，而且**刻意不繼承那一格的 tone**：關卡是「這裡有人工
            #    確認點」的結構標記，跟前面那一格是不是本頁重點是兩件事；繼承的話
            #    每個重點格都會多帶一個金框（就是 N34 的症狀）。要金色請明寫
            #    `steps[].gate_tone`。既有 spec 都沒有這個欄位 → 一律一般色。
            parts.append(BOX(x, y, w, 96,
                             _shape_cls("box", st.get("gate_tone"),
                                        st.get("label") or st.get("id"), _CAT_USED)))
            for j, ln in enumerate(_gate_lines(st["gate"])[:2]):
                parts.append(T(x + pad, y + 40 + j * ROW, ln, "label"))
        y += 96 + 24
    y = _axis(parts, spec.get("axis"), y)
    return wrap(parts, CW, y)


# 橫幅左欄（標題欄）的寬。⭐ 以前是散在四處的字面值 470 —— 改一個忘一個就對不齊。
BAND_COL = 472      # 8 的倍數


def _chain_band(spec, steps):
    """全寬橫幅版：每格自己一條，順序靠編號不靠箭頭。

    三種內容各有自己的排法，判別欄位就是內容本身（不是另一個旗標）：
      · `rows`            → 判分表，一列一列排（這一格通常是本頁的主體）
      · 含 `|` 的 `lines` → 一行寫成一個**直欄群**（門檻那種：條件在上、後果在下），
                            並排比上下堆疊省一半的高度 —— 橫幅版的高度預算很緊
      · 其餘 `lines`      → 由上往下排；**只有一行時併到標題那一列**（省 36px）
    """
    parts, y = [], 0
    pad = _pad(CW)                              # 橫幅是全寬的 → 留白吃上限（40）
    for i, st in enumerate(steps):
        rows = st.get("rows") or []
        blks = _blocks(st.get("blocks"))
        # ── N92（批次 5g）：`gate` 以前被**併進普通內文行** —— 沒有框、沒有色、
        #    與一般 lines 無法區分，於是 `gate_tone` 在 band 完全沒有落點
        #    （全檔只命中 1 次，在 _chain_row）。而排法是「任一格有 rows → 自動 band」
        #    選出來的，**寫 spec 的人選不了** → `chain_gated` 這個構圖名在 band 下
        #    等於不存在，N34 修好的 opt-in 金框一併失效。
        #    ⭐ 修法照 `_chain_row`：關卡自己一列、自己一個框、顏色吃 `gate_tone`。
        gate_ln = _gate_lines(st.get("gate"))[:2]
        lines = _lines(st.get("lines"))
        cols = [l for l in lines if "|" in l]
        plain = [l for l in lines if "|" not in l]
        inline = plain[0] if (len(plain) == 1 and not rows and not cols
                              and not blks) else None
        if inline:
            plain = []
        colh = max((len(l.split("|")) for l in cols), default=0)
        only_cols = bool(cols) and not rows and not plain and not blks
        # 一格裡**只有並排的子區塊**時，橫幅標題退到左欄（跟 only_cols 同一個作法），
        # 子區塊與標題**同一列開始** —— 這樣一格省 44px。
        # ⚠️ 這 44px 是 band 能不能用子區塊的關鍵：4 個橫幅時每格只有
        #    (540 − 3×12) ÷ 4 = 126px，標題自己佔一列的話連「小標＋一列」都放不下。
        side_blk = bool(blks) and not rows and not plain and not cols \
            and st.get("flow", "row") == "row"
        # `value` 畫在標題列右側（與 inline 同一列）→ **不佔額外高度**；
        # `gate` 自己一列 → 每一行 +34，另加上下留白 16（沒有 gate 時逐位元組不變）。
        gate_h = (ROW * len(gate_ln) + 16) if gate_ln else 0
        h = _g8(40 + ROW * (colh - 1) + 16 if only_cols else
                _blocks_h(blks, "row") + ROW if side_blk else
                LEAD + (ROW * len(rows) + 24 if rows else 0)
                + ROW * len(plain) + ROW * colh
                + (_blocks_h(blks, st.get("flow", "row")) + 16 if blks else 0) + 16) + gate_h
        # ⚠️ `cols`（`|` 直欄群）**不算已經有結構**：它只是把幾件事並排，
        #    沒有小標、沒有分隔線 —— 使用者原話點名的正是這種格子
        #    （「Page4 的每一個 bar 也都是，解釋都沒有分隔，不夠細緻」）。
        #    只有 `rows`（判分表：欄位對齊＋一條 rule）與 `blocks` 才算。
        _flat_check(st.get("label"),
                    len(plain) + sum(len(l.split("|")) for l in cols),
                    bool(blks or rows))
        parts.append(BOX(0, y, CW, h, _step_tone(spec, st)))
        num = st.get("num", str(i + 1))
        head = f"{num} — {st.get('label','')}" if num else st.get("label", "")
        parts.append(T(pad, y + 40, head, "label lead", mono=st.get("mono")))
        if inline:
            parts.append(T(BAND_COL, y + 40, inline, "label"))
        # N92：`value`（文件：「字會放大並用深藍」）在 band 以前 0 命中。
        # 靠右放，⛔ 不與 inline／only_cols 的左欄搶位置。
        if st.get("value"):
            parts.append(T(CW - pad, y + 40, str(st["value"]), "value", anchor="end"))
        ty = y + 56
        if rows:
            parts.append(RULE(pad, ty, CW - pad))
            ty += 40
            xs = _col_x(rows, pad, CW - pad)
            for r in rows:
                hl = " hl" if st.get("accent_row") and r and r[0] == st["accent_row"] else ""
                for cx, c in zip(xs, r):
                    parts.append(T(cx, ty, c, "label" + hl))
                ty += ROW
            ty -= 8
        for ln in plain:
            parts.append(T(pad, ty, ln, "label"))
            ty += ROW
        if cols:
            # 只有直欄群時排在**標題右側**（標題佔掉左邊那一欄），否則接在下面。
            # 這是版面高度的關鍵：三個門檻並排比上下堆疊省一半的高度。
            cx0, cy = (BAND_COL, y + 40) if only_cols else (pad, ty)
            for gi, ln in enumerate(cols):      # 一行 = 一個直欄群
                gx = cx0 + gi * (CW - pad - cx0) / len(cols)
                for ci, c in enumerate(l.strip() for l in ln.split("|")):
                    parts.append(T(gx, cy + ci * ROW, c, "label"))
            if not only_cols:
                ty += ROW * colh
        # 橫幅是全寬的 —— 子區塊**預設並排**（高度預算見上面 flow 那段）。
        if side_blk:                        # 標題在左欄，子區塊從同一列開始
            # ⭐ BLK_TOP == BLK_BASE 之後，傳進去的 y **就是**第一條基線 ——
            #    給 y+40 子區塊的小標就與橫幅標題同一條基線，真正「同一列開始」。
            bp, _ = _blocks_svg(blks, BAND_COL, y + 40, CW - pad - BAND_COL,
                                mono=st.get("mono"), flow="row")
        else:
            # +16：橫幅標題（label lead 26px、基線 y+40）與子區塊之間要留得開，
            #      不然小標會貼到標題底下（實測會疊在一起）。
            bp, ty = _blocks_svg(blks, pad, ty + 16, CW - 2 * pad, mono=st.get("mono"),
                                 flow=st.get("flow", "row"))
        parts += bp
        # N92：關卡自己一個框，顏色吃 `gate_tone`（⛔ 不繼承那一格的 tone —— 見
        # `_chain_row` 同一段註解：繼承會讓每個重點格都多帶一個金框，那是 N34 的症狀）。
        if gate_ln:
            gy = y + h - gate_h
            parts.append(BOX(pad, gy, CW - 2 * pad, gate_h - 8,
                             _shape_cls("box", st.get("gate_tone"),
                                        st.get("label") or st.get("id"), _CAT_USED)))
            for j, ln in enumerate(gate_ln):
                parts.append(T(2 * pad, gy + 32 + j * ROW, ln, "label"))
        y += h + 16
    y = y - 16                                  # 最後一條橫幅後面不留間距
    y = _axis(parts, spec.get("axis"), y + 10) if spec.get("axis") else y
    return wrap(parts, CW, y)


def _axis(parts, axis, y):
    """底部的成本軸（楔形）。來源：three_layers.svg 的 cost wedge。

    它不是裝飾 —— 「越後面的關卡，改錯的代價越大」這件事只有靠**寬度**才說得出來，
    寫成一句話就只是形容詞（diagram-craft.md §0 第二個觸發訊號）。
    """
    if not axis:
        return y
    left, right = axis.get("left", ""), axis.get("right", "")
    parts.append(T(88, y + 24, left, "label"))
    parts.append(T(CW - 88, y + 24, right, "label", anchor="end"))
    y0 = y + 48
    parts.append(f'<polygon class="bar" opacity="0.22" points="88,{_n(y0+30)} '
                 f'{CW-88},{_n(y0)} {CW-88},{_n(y0+52)} 88,{_n(y0+42)}"/>')
    if axis.get("label"):
        parts.append(T(CW / 2, y0 + 96, axis["label"], "label", anchor="middle"))
        return y0 + 112
    return y0 + 64


# ── ② group_blocks ──────────────────────────────────────────────────────
# partition：整體拆成幾群，**群裡的成員要一個個看見**（字彙表 §3）。
#
# 兩種排法，判別欄位是 members 的形狀（不是 agent 挑的）：
#   grid ── 成員是**字串** → 一格一群、群內直接列出成員
#           （features.svg 4×2 八群、two_layers.svg 兩群）
#   rows ── 成員是**物件**（有 desc／right 這些欄位）→ 一列一個成員、群名縮到左欄
#           （agent_roles.svg：一列一個 agent，layer 標籤在左）
#   一個成員要顯示三個以上的屬性時，格子裡塞不下，只能一列一個 —— 這就是 rows 存在的理由。

def render_group_blocks(spec):
    groups = spec.get("groups") or []
    if not groups:
        sys.exit("[figure] group_blocks 需要 groups[]")
    obj = any(isinstance(m, dict) for g in groups for m in (g.get("members") or []))
    layout = spec.get("layout") or ("rows" if obj else "grid")
    if layout not in ("grid", "rows"):
        sys.exit(f"[figure] group_blocks 的 layout 只能是 grid 或 rows，收到「{layout}」")
    return (_gb_rows if layout == "rows" else _gb_grid)(spec, groups)


def _gb_grid(spec, groups):
    parts = []
    src = spec.get("source")
    x0 = 0
    if src:                                    # 左邊一個來源框，箭頭指向每一群
        x0 = 352
    ncol = int(spec.get("cols") or (len(groups) if len(groups) <= 3 else 4))
    ncol = max(1, min(ncol, len(groups)))
    gap = 32
    w = (CW - x0 - gap * (ncol - 1)) / ncol
    pad = _pad(w)                              # L2：留白是盒寬的函數
    nrow = (len(groups) + ncol - 1) // ncol
    mmax = max(len(g.get("members") or []) for g in groups)
    has_v = any(g.get("value") for g in groups)
    has_s = any(g.get("sub") for g in groups)
    blk = max(_blocks_h(_blocks(g.get("blocks")), g.get("flow", "col")) for g in groups)
    # 抬頭區：value 一列(LEAD) + 群名一列 + sub 一列(LEAD) + 分隔線那一段(LEAD)
    h = _g8(max(192, LEAD + (LEAD if has_v else 0) + (LEAD if has_s else 0)
                + LEAD + ROW * mmax + blk + 24))
    # L2：格線上的每一格同寬 → 欄距共用一個值（實測 A1 逐格各自算差 11px）。
    kw = _term_w([_blocks(g.get("blocks")) for g in groups], w - 2 * pad,
                 any(g.get("mono") for g in groups), "（group_blocks grid）")
    parts_g = []
    for i, g in enumerate(groups):
        r, c = divmod(i, ncol)
        x, y = x0 + c * (w + gap), r * (h + 32)
        _flat_check(g.get("name"), len(g.get("members") or []),
                    bool(g.get("blocks")))
        parts_g.append(BOX(x, y, w, h,
                           _shape_cls("grp", g.get("tone"), g.get("name"), _CAT_USED)))
        ty = y + LEAD
        if g.get("value"):
            for j, v in enumerate(_lines(g["value"])):
                parts_g.append(T(x + pad + j * 136, ty, v,
                                 "value hl" if g.get("accent") else "value", mono=True))
            ty += LEAD
        if g.get("name"):
            parts_g.append(T(x + pad, ty, g["name"], "label lead"))
        if has_s:
            if g.get("sub"):
                parts_g.append(T(x + pad, ty + LEAD, g["sub"], "label"))
            ty += LEAD
        parts_g.append(RULE(x + pad, ty + 16, x + w - pad))
        ty += LEAD
        for m in (g.get("members") or []):
            parts_g.append(T(x + pad, ty, str(m), "label", mono=g.get("mono")))
            ty += ROW
        bp, ty = _blocks_svg(_blocks(g.get("blocks")), x + pad, ty, w - 2 * pad,
                             mono=g.get("mono"), flow=g.get("flow", "col"), kw=kw)
        parts_g += bp
    total_h = nrow * h + (nrow - 1) * 32
    if src:
        sh, sy = 144, _g8((total_h - 144) / 2)
        parts.append(BOX(0, sy, 272, sh,
                         _shape_cls("box", src.get("tone"),
                                    _lines(src.get("label"))[0], _CAT_USED)))
        sl = _lines(src.get("label"))
        # 多行時整組垂直置中：往上退半組（ROW/2 × (n−1)），基線仍落在網格上。
        y0 = sy + _g8(sh / 2) - ROW * (len(sl) - 1) // 2
        for j, ln in enumerate(sl):
            parts.append(T(136, y0 + j * ROW, ln, "label lead",
                           anchor="middle", mono=src.get("mono")))
        for r in range(nrow):                  # 每一列群組拉一條箭頭（線頭離框 8px）
            ay = r * (h + 32) + h / 2
            parts.append(LINK(280, ay, x0 - 8, ay))
    return wrap(parts + parts_g, CW, total_h)


def _gb_rows(spec, groups):
    parts, y = [], 0
    pad = _pad(CW)                              # 整列是全寬的 → 留白吃上限（40）
    hd = spec.get("header")
    if hd:
        parts.append(BOX(0, 0, CW, 80,
                         _shape_cls("box", hd.get("tone"),
                                    hd.get("label"), _CAT_USED)))
        parts.append(T(pad, 48, hd.get("label", ""), "label lead", mono=hd.get("mono")))
        if hd.get("right"):
            parts.append(T(CW - pad, 48, hd["right"], "label", anchor="end"))
        y = 112
    for g in groups:
        # ── N93（批次 5g）：`groups[].value`／`sub`／`accent` 在 _gb_rows 以前
        #    **全部 0 命中**，而排法是依 members 的形狀**自動**選的（成員一寫成
        #    物件就走 rows）—— 寫 spec 的人選不了，三個欄位靜默蒸發。
        #    ⭐ 修法照 _gb_grid：群自己一列抬頭（有 value／sub 才畫，沒有就
        #    逐位元組不變），`accent` 讓 value 用重點色。
        if g.get("value") or g.get("sub"):
            parts.append(BOX(0, y, CW, 64,
                             _shape_cls("grp", g.get("tone"), g.get("name"), _CAT_USED)))
            if g.get("name"):
                parts.append(T(pad, y + 40, g["name"], "label lead", mono=True))
            if g.get("value"):
                for j, v in enumerate(_lines(g["value"])):
                    parts.append(T(BAND_COL + j * 152, y + 40, v,
                                   "value hl" if g.get("accent") else "value",
                                   mono=True))
            if g.get("sub"):
                parts.append(T(CW - pad, y + 40, g["sub"], "label", anchor="end"))
            y += 80
        for m in (g.get("members") or []):
            if not isinstance(m, dict):
                m = {"name": str(m)}
            tone = m.get("tone") or g.get("tone")
            blks = _blocks(m.get("blocks"))
            flow = m.get("flow", "row")     # 整列是全寬的 → 子區塊預設並排
            parts.append(BOX(0, y, CW, 88 + _blocks_h(blks, flow),
                             _shape_cls("box", tone, m.get("name"), _CAT_USED)))
            mid = y + 56
            if g.get("name"):
                parts.append(T(pad, mid, g["name"], "label", mono=True))
            parts.append(T(224, mid, m.get("name", ""), "label lead",
                           mono=m.get("mono", True)))
            if m.get("desc"):
                parts.append(T(624, mid, m["desc"], "label"))
            if m.get("right"):
                parts.append(T(CW - pad, mid - 16, m["right"],
                               "label hl" if tone == "hl" else "label", anchor="end"))
            if m.get("right2"):
                parts.append(T(CW - pad, mid + 16, m["right2"], "label", anchor="end"))
            bp, _ = _blocks_svg(blks, 224, y + 96, CW - 224 - pad, flow=flow)
            parts += bp
            y += 104 + _blocks_h(blks, flow)
    return wrap(parts, CW, y - 16)


# ── ③ two_col_link ──────────────────────────────────────────────────────
# correspondence：左欄每一項對到右欄某一項（字彙表 §7）。
# 守門提問是「有沒有對不到的？」—— 對不到的、或**對到同一個結果**的那幾條常常才是重點，
# ⛔ 舊做法是「links[] 帶 tone:hl → 金線 ＋ 兩端金框」。**已廢除**（6c 使用者回饋）——
#    在一堆同類的線裡塗金一條，回答的是「這一條特別重要」，而形狀的顏色只做分類。
#    ⭐ 現在「對不到的那幾條」要靠**位置**（排在一起／排最上面）或**字**（金字）講。
#    links[] 仍可帶分類色（bad／good／null／ctl）—— 那是「這一類連線」不是「這一條」。

def render_two_col_link(spec):
    left = spec.get("left") or []
    right = spec.get("right") or []
    if not left or not right:
        sys.exit("[figure] two_col_link 需要 left[] 與 right[]")
    parts, y = [], 0
    pad = _pad(CW)
    if spec.get("entry"):                      # 頂部入口條：這張圖怎麼讀 → annot
        parts.append(BOX(0, 0, CW, 56, "box"))
        parts.append(T(pad, 32, spec["entry"], "annot"))
        y = 88
    RH, GAP, MID = 56, 16, 240        # MID：兩欄之間留給箭頭的走道，固定不壓縮
    # 欄寬**依內容算**，不寫死 —— 寫死 440/634 的話，長一點的標籤會衝出框、
    # 而箭頭正好從那段字上穿過去（實測踩過）。
    # 每半形字的寬度：label lead 26px 約 15px、label 22px 約 11px。
    #
    # ⚠️ FINDINGS N54：右欄原本**連 note 欄位都沒有**、列高又寫死 56，
    #    於是「每格多放一點事實」在右欄結構性做不到，右欄只能塞一句越寫越長的話。
    #    現在兩欄同一套算式：`note`（名字右邊的註解）與 `blocks`（框內的子區塊）
    #    左右都吃，列高改成**逐列算**。沒填時 = 舊行為，逐位元組不變。
    def _note_x(name, cw):            # 註解排在名字右邊，名字短的時候仍對齊在 140px
        return 24 + max(140, _tw(name) * cw) + 20

    def _cw(it, cw):                  # ⚠️ 這裡的算式要**和實際放字的位置同一條**，
        name = it.get("label", "")    #    不然框會剛好比字短一點點，字就貼到框線上
        base = (_note_x(name, cw) + _tw(it["note"]) * 11 + 24 if it.get("note")
                else 24 + _tw(name) * cw + 24)
        return max(base, 24 + _blocks_w(_blocks(it.get("blocks")), it.get("flow", "col")))

    def _rows(items, y0):             # 逐列算高：有 blocks 的那一列自己長高
        ys, yy = [], y0
        for it in items:
            blk = _blocks_h(_blocks(it.get("blocks")), it.get("flow", "col"))
            hh = RH + (blk + GRID if blk else 0)     # 每一段都留在 8pt 網格上
            ys.append((yy, hh))
            yy += hh + GAP
        return ys, yy - GAP

    lw = max(_cw(it, 15) for it in left)
    rw = max(_cw(it, 11) for it in right)
    avail = CW - MID
    LW = max(300, min(lw, avail * lw / float(lw + rw)))
    RW = avail - LW
    if lw > LW + 1 or rw > RW + 1:
        sys.exit(
            f"[figure] two_col_link 放不下：左欄需要 {int(lw)}px（有 {int(LW)}px）、"
            f"右欄需要 {int(rw)}px（有 {int(RW)}px）。\n"
            f"         ⛔ 不要縮字級。**兩欄都是長句代表這不是對應關係** —— "
            f"對應關係的兩端是東西的名字，不是句子。\n"
            f"         改用 before_after（上下疊，兩欄各自佔滿整個寬度）或退回表格。")
    RX = CW - RW
    links = spec.get("links")
    if not links:                              # 沒給就 1:1 對位（兩欄等長時的預設）
        links = [[l.get("id", i), right[i].get("id", i), None]
                 for i, l in enumerate(left) if i < len(right)]
    # 一個節點被多條連線提到時的 tone 合併語意（FINDINGS N35）：
    #   **「任一條連線有 tone 就套用」（or）；兩條給了不同的 tone 才報錯。**
    # 為什麼選 or 而不是「後寫覆蓋」或「第一條為準」：tone 是節點自己的語意
    # （這個東西是不是這頁的重點），不是那條線的屬性 —— 而「沒填」是**沒有意見**，
    # 不是「主張它是一般色」，所以沒填的連線不該把別條的主張洗掉（原本後寫覆蓋，
    # B3 的 ["l3","r4"] 就把 l3 洗成一般色，同一個節點兩端不同色）。
    # 順序無關也是必要的：links 的排列順序是資料的書寫順序，不該影響顏色。
    # 真正的矛盾（同一個節點被要求 hl 又被要求 bad）沒有正確答案，寧可報錯。
    tone_of = {}
    for lk in links:
        t = lk[2] if len(lk) > 2 else None
        if t is None:
            continue
        if t == "hl":
            _bad_tone(f"two_col_link 的 links {lk[:2]}", t)
        for iid in lk[:2]:
            if tone_of.get(iid, t) != t:
                sys.exit(f"[figure] two_col_link 的 links 給了節點「{iid}」互相矛盾的 "
                         f"tone：{tone_of[iid]} 與 {t}。一個節點只能有一個語意色，"
                         f"請改其中一條連線。")
            tone_of[iid] = t
    ypos = {}

    def _side(items, x0, cw, colw, lead):
        """畫一欄。lead=True 是左欄（名字用 label lead），False 是右欄。"""
        ys, bottom = _rows(items, y)
        for i, it in enumerate(items):
            yy, hh = ys[i]
            iid = it.get("id", i)
            ypos[iid] = yy + hh / 2
            parts.append(BOX(x0, yy, colw, hh,
                             _shape_cls("box", it.get("tone") or tone_of.get(iid),
                                        it.get("label") or iid, _CAT_USED)))
            name = it.get("label", "")
            parts.append(T(x0 + 24, yy + 40, name, "label lead" if lead else "label",
                           mono=it.get("mono", True) if lead else it.get("mono")))
            if it.get("note"):
                # 註解排在名字右邊：名字欄約 cw px/半形字，再留 20px 的間隔（不要貼死）
                parts.append(T(x0 + _note_x(name, cw), yy + 40, it["note"], "label"))
            bp, _ = _blocks_svg(_blocks(it.get("blocks")), x0 + 24, yy + RH + 16,
                                colw - 48, mono=it.get("mono") is True,
                                flow=it.get("flow", "col"))
            parts.extend(bp)        # ⚠️ 不能寫 parts += bp —— 那會讓 parts 變成區域變數
        return bottom

    bl = _side(left, 0, 15, LW, True)
    br = _side(right, RX, 11, RW, False)
    for lk in links:                           # 線頭離節點邊 8px
        a, b = ypos.get(lk[0]), ypos.get(lk[1])
        if a is None or b is None:
            sys.exit(f"[figure] two_col_link 的 links 指到不存在的 id：{lk[:2]}")
        parts.append(LINK(LW + 8, a, RX - 8, b))   # ⛔ 強調線已廢除（6c）：LINK 不再吃 hl
    h = max(bl, br)
    if spec.get("footer"):
        parts.append(T(CW, h + 48, spec["footer"], "value inline", anchor="end"))
        h += 56
    return wrap(parts, CW, h)


# ── ④ funnel／funnel_named ──────────────────────────────────────────────
# narrowing：多 → 少，每一跳有判準（字彙表 §4）。
# **一個 renderer 掛兩個名字**：`stages[].survivors[]` 有沒有值是資料上看得出來的
# 判別欄位，兩個名字指到同一支排法（composition-vocabulary.md「funnel」節）。
#
# ⚠️ 這支是照著一個記錄有案的失效反過來寫的：`A3_selection_funnel.svg`（手寫版）
# 宣告 `relation: narrowing`，實際框寬 360 → 710 → 300×3 —— 判準（710 那格）被畫成
# 跟族群同樣分量的框，於是 `check_deck._stage_widths()` 把它也算成一段，
# L4-1「寬度逐段不得變寬」立刻被自己的判準框否定。
# ⭐ 這支的核心規則：**`criterion` 不畫 `<rect>`**，只用 `label lead` ＋ 兩側各一條
# 垂直 `.rule` ＋ 子區塊 —— 量尺（`_stage_widths`）只數方框，判準不畫框就不會被
# 誤算成一段；讀者看到的是「兩個大小不同的族群，中間夾著一把篩子」。
#
# 座標唯一出處：composition-vocabulary.md「funnel」節與 diagram-craft.md §6b。
#   · 欄序 S1 · [C1] · S2 · [C2] · S3 …，欄間距 GAP = 4×GRID = 32。
#   · criterion 欄寬 = clamp(_g8(_blocks_w(...)), 280, 720)。
#   · 段欄寬：R = 1420 − Σ判準欄寬 − GAP×(欄數−1)，依權重 0.7^i 攤到各段、
#     `_g8` 之後強制嚴格遞減；段寬下限 240，攤不出來 sys.exit。
#   · 每個段欄的框垂直置中於圖的中線；survivors 是同 x 同寬的一疊小框，
#     間距 GROUP/2 = 32，整疊置中。
#   · 箭頭：欄與欄之間各一支水平 LINK()；分岔到 survivors 時每一個框各一支。

def _funnel_criterion_w(c):
    """criterion 欄寬：clamp(_g8(_blocks_w(...)), 280, 720)。⛔ 唯一出處見上方註解。

    ⚠️ 不能直接呼叫共用的 `_blocks_w()`：那支是「逐行各自估」（每個 pair 只看
    自己的 term），而 `pairs` 的 term 欄實際是**整組共用一個寬**（`_term_w()` 的
    規矩，跨子區塊也對齊）——term 長短差很多時，共用寬會比任何一行自己估的都寬，
    逐行估就會低估（實測：本頁「changed ×2」那行的 term 比「seen before ×1」短，
    共用寬被後者撐大，逐行估短列 44px，字會壓出框）。
    這裡改成跟 `_term_w()` 同一條公式，對 (欄寬 → padding → 可用寬 → 欄寬) 這個
    互相依賴的迴圈做**不動點疊代**（含 padding 的公式本身就依賴最終欄寬）。
    """
    blocks = _blocks(c.get("blocks"))
    pairs = [p for b in blocks for p in (b.get("pairs") or [])]
    if not blocks:
        need = max([_tw(l) * LABEL_PX for l in _lines(c.get("lines"))] or [0]) + 48
        return min(720, max(280, _g8(need)))
    w = 320.0
    for _ in range(12):
        pad = _pad(w)
        avail = max(1.0, w - 2 * pad)
        content = 0.0
        if pairs:
            quota = max(_g8(TERM_FRAC * avail), BLK_KEYMIN)
            need_term = _g8(max(_tw(k) for k, _v in pairs) * TERM_PX)
            kw = min(max(quota, need_term), _g8(avail * 0.62)) + GUTTER
            content = max(kw + _tw(v) * LABEL_PX for _k, v in pairs)
        for b in blocks:
            if b.get("head"):
                content = max(content, _tw(b["head"]) * HEAD_PX)
            for ln in (b.get("lines") or []):
                content = max(content, _tw(ln) * LABEL_PX)
            for ln in (b.get("numbered") or []):
                content = max(content, BLK_NUMW + _tw(ln) * LABEL_PX)
        new_w = content + 2 * pad
        if abs(new_w - w) < 0.5:
            w = new_w
            break
        w = new_w
    return min(720, max(280, _g8(w)))


def _funnel_box_h(lines, blocks, flow="col"):
    """一個段欄／判準／survivor 框要的高：名字列(LEAD) ＋ rule 後的內容起點(LEAD) ＋
    純文字或 blocks ＋ 底部留白(24)。三者都用同一支，逐位元組同一套幾何。"""
    return _g8(LEAD + LEAD + ROW * len(lines) + _blocks_h(blocks, flow) + 24)


def _funnel_stage_h(st):
    if st.get("survivors"):
        items = st["survivors"]
        if not items:
            sys.exit("[figure] funnel 的 stages[].survivors 不能是空陣列——"
                     "沒有東西可以點名就不要填這個欄位。")
        step = GROUP // 2
        hs = [_funnel_box_h(_lines(it.get("lines")), _blocks(it.get("blocks")),
                            it.get("flow", "col")) for it in items]
        return sum(hs) + step * (len(items) - 1)
    return _funnel_box_h(_lines(st.get("lines")), _blocks(st.get("blocks")),
                         st.get("flow", "col"))


def _funnel_box(parts, name, mono, tone, value, lines, blocks, flow, x, y, w, h, where):
    """畫一個**有框**的段（stage 或 survivor 項）：同一支幾何，呼叫端只給內容。"""
    pad = _pad(w)
    parts.append(BOX(x, y, w, h, _shape_cls("box", tone, name or where, _CAT_USED)))
    parts.append(T(x + pad, y + LEAD, name or "", "label lead", mono=mono))
    if value:
        parts.append(T(x + w - pad, y + LEAD, str(value), "value", anchor="end"))
    parts.append(RULE(x + pad, y + LEAD + 16, x + w - pad))
    ty = y + 2 * LEAD
    _flat_check(name, len(lines), bool(blocks))
    for ln in lines:
        parts.append(T(x + pad, ty, ln, "label", mono=mono))
        ty += ROW
    kw = _term_w([blocks], w - 2 * pad, bool(mono), where)
    bp, ty = _blocks_svg(blocks, x + pad, ty, w - 2 * pad, mono=mono, flow=flow, kw=kw)
    parts.extend(bp)


def _funnel_survivors(parts, items, x, y, w, h):
    """⭐ `funnel_named` 的判別欄位：同 x 同寬的一疊小框，間距 GROUP/2 = 32，整疊置中。"""
    step = GROUP // 2
    hs = [_funnel_box_h(_lines(it.get("lines")), _blocks(it.get("blocks")),
                        it.get("flow", "col")) for it in items]
    total = sum(hs) + step * (len(items) - 1)
    yy = _g8(y + (h - total) / 2)          # 通常 total == h（見 _funnel_stage_h），
    centers = []                            # 這裡防的是呼叫端傳了不同的 h
    for it, ih in zip(items, hs):
        tone = it.get("tone")
        if tone == "hl":
            _bad_tone(f'funnel survivor「{it.get("name","")}」', tone)
        _funnel_box(parts, it.get("name", ""), it.get("mono"), tone, None,
                    _lines(it.get("lines")), _blocks(it.get("blocks")),
                    it.get("flow", "col"), x, yy, w, ih,
                    f'（funnel survivor「{it.get("name","")}」）')
        centers.append(yy + ih / 2)
        yy += ih + step
    return centers


def _funnel_criterion(parts, c, x, y, w, h):
    """⭐ 這支 renderer 最重要的一條：criterion **不畫框**——只有 label lead ＋
    兩側各一條垂直 .rule ＋ 子區塊。量尺（`_stage_widths`）只數方框，
    判準不畫框就不會被誤算成一段（見本節開頭的 A3 反例）。"""
    pad = _pad(w)
    parts.append(f'<line class="rule" x1="{_n(x)}" y1="{_n(y)}" '
                 f'x2="{_n(x)}" y2="{_n(y + h)}"/>')
    parts.append(f'<line class="rule" x1="{_n(x + w)}" y1="{_n(y)}" '
                 f'x2="{_n(x + w)}" y2="{_n(y + h)}"/>')
    name = c.get("name", "")
    mono = c.get("mono")
    parts.append(T(x + pad, y + LEAD, name, "label lead", mono=mono))
    ty = y + 2 * LEAD
    lines, blocks = _lines(c.get("lines")), _blocks(c.get("blocks"))
    _flat_check(name, len(lines), bool(blocks))
    for ln in lines:
        parts.append(T(x + pad, ty, ln, "label", mono=mono))
        ty += ROW
    kw = _term_w([blocks], w - 2 * pad, bool(mono), f'（funnel criterion「{name}」）')
    bp, ty = _blocks_svg(blocks, x + pad, ty, w - 2 * pad, mono=mono,
                         flow=c.get("flow", "col"), kw=kw)
    parts.extend(bp)


def render_funnel(spec):
    stages = spec.get("stages") or []
    n = len(stages)
    if not (2 <= n <= 4):
        sys.exit(f"[figure] funnel 的 stages[] 要 2–4 段（左→右），收到 {n} 段。")
    if stages[-1].get("criterion"):
        sys.exit("[figure] funnel 最後一段不該有 criterion——判準是「進入下一段」的門檻，"
                 "最後一段沒有下一段可進。")
    for i, st in enumerate(stages):
        if st.get("tone") == "hl":
            _bad_tone(f"funnel stages[{i}]", "hl")
        if not st.get("name") and not st.get("survivors"):
            sys.exit(f"[figure] funnel stages[{i}] 缺 name——只有 survivors 那一段可以省。")

    GAP = 4 * GRID                          # 32：欄間距，箭頭畫在間距正中
    crit = [st.get("criterion") for st in stages]
    crit_w = [_funnel_criterion_w(c) if c else 0 for c in crit]
    total_cols = n + sum(1 for w in crit_w if w)
    R = CW - sum(crit_w) - GAP * (total_cols - 1)
    weights = [0.7 ** i for i in range(n)]
    raw = [R * wt / sum(weights) for wt in weights]
    stage_w = [_g8(v) for v in raw]
    for i in range(1, n):                   # 強制嚴格遞減：每段至少比前一段窄 8px
        if stage_w[i] >= stage_w[i - 1]:
            stage_w[i] = stage_w[i - 1] - GRID
    if min(stage_w) < 240:
        sys.exit(f"[figure] funnel 段欄寬攤不出來（逐段 {stage_w}px，最窄 < 240px 下限）。\n"
                 f"         正解擇一：① 減一段 stages[]　② 把 criterion 的內容寫短"
                 f"（縮小判準欄寬，讓段欄多分到一些寬）　③ 拆成兩頁。")

    parts, y0 = [], 0
    if spec.get("entry"):                  # 頂部入口條：這張圖怎麼讀 → annot
        pad0 = _pad(CW)
        parts.append(BOX(0, 0, CW, 56, "box"))
        parts.append(T(pad0, 32, spec["entry"], "annot"))
        y0 = 88

    stage_h = [_funnel_stage_h(st) for st in stages]
    crit_h = [_funnel_box_h(_lines(c.get("lines")), _blocks(c.get("blocks")),
                            c.get("flow", "col")) if c else 0 for c in crit]
    content_h = max(stage_h + crit_h)
    mid = y0 + content_h / 2

    x = 0
    prev_centers, prev_x_end = None, None
    for i, st in enumerate(stages):
        w, h = stage_w[i], stage_h[i]
        y = _g8(mid - h / 2)
        if st.get("survivors"):
            centers = _funnel_survivors(parts, st["survivors"], x, y, w, h)
        else:
            _funnel_box(parts, st.get("name", ""), st.get("mono"), st.get("tone"),
                        st.get("value"), _lines(st.get("lines")), _blocks(st.get("blocks")),
                        st.get("flow", "col"), x, y, w, h,
                        f'（funnel stage「{st.get("name","")}」）')
            centers = [mid]
        if prev_centers is not None:         # 欄與欄之間各一支水平 LINK；
            for a in prev_centers:            # 分岔到 survivors 時每一個框各一支。
                for b in centers:
                    parts.append(LINK(prev_x_end + 8, a, x - 8, b))
        prev_centers, prev_x_end = centers, x + w
        x += w
        c = crit[i]
        if c:
            cw, ch = crit_w[i], crit_h[i]
            cy = _g8(mid - ch / 2)
            cx = x + GAP
            _funnel_criterion(parts, c, cx, cy, cw, ch)
            parts.append(LINK(prev_x_end + 8, mid, cx - 8, mid))
            prev_centers, prev_x_end = [mid], cx + cw
            x = cx + cw + GAP
        else:
            x += GAP
    return wrap(parts, CW, y0 + content_h)


# ── ⑤ transform_pair ────────────────────────────────────────────────────
# transform：A 經過某個操作變成 B（字彙表 §2 第 2 類）。
#
# 座標唯一出處：composition-vocabulary.md「transform_pair」節與 diagram-craft.md §6b。
#   · `from`／`op` 由上而下各一條全寬橫幅（x=0, w=1420），之間一支向下的
#     LINK(710, y1, y2)——「變成」是有方向的，方向要畫得出來（L4-1）。
#   · `to`：沒有 `boundary` 時也是全寬；有 `boundary` 時
#     `w_bd = clamp(_g8(需要的寬), 320, 560)`、`w_to = 1420 − w_bd − GAP`，
#     兩者同 y 同高（共用水平軸）。
#   · 每條橫幅：`label lead` ＋ `.rule` ＋ 內容；`value` 有值時 `label value`
#     畫在標題列右端（`anchor="end"`）——這一段跟 `funnel` 的 box 是**同一支幾何**
#     （`_funnel_box`／`_funnel_box_h`），⛔ 不重寫一份、⛔ 不改那兩支。
#   · 分類色靠 `from.tone`／`to.tone` 明寫，renderer 不預設塗紅塗綠
#     （照 `gate_tone` 的 opt-in 先例）。
#
# ⚠️ 契約只明寫 `from`／`op` 之間那一支箭頭（見上面第一條），`op`→`to` 沒有第二支
# 的明文——三條橫幅由上而下疊本身已經是方向（跟 `_chain_band` 順序靠疊放、
# 不畫箭頭同一個道理），這裡照契約字面**只畫那一支**。
#
# ⚠️ 高度預算的坑（交件報告會覆述）：三條橫幅是「96 固定 overhead ＋ 內容」的
# 疊加（`_funnel_box_h` 的公式，跟 funnel 共用），A4 這頁 `op` 這格本身就要
# 128px（3 條編號 ＋ 2 行 class words 並排取最高者），三格疊起來是 616px，
# 634 的預算只夠再擠出 `GRID`（8px）當 band 間距——不是排法選錯，是內容量本來
# 就吃掉了預算的 97%。有箭頭的那個間距因此只有 8px 長，肉眼看是一個貼著兩條
# 橫幅的小三角形，不是一條有長度的線；這是內容撐出來的結果，不是座標算錯。
GAP_H = 4 * GRID          # 32：to／boundary 兩欄之間的走道，跟 funnel／two_col_link 同一個值
GAP_V = GRID              # 8：band 與 band 之間的間距——見上面那段，634 的預算只擠得出這個


def _transform_box_w(node):
    """`boundary` 欄需要的寬：`clamp(_g8(需要的寬), 320, 560)`。

    跟 `_funnel_criterion_w` 同一支不動點疊代（pad 依賴最終寬，寬又依賴 pad），
    只是多算 `lines`——`transform_pair` 的 box 兩者可以同時有，`funnel` 的
    `criterion` 實務上只填其中一種。
    ⛔ 不量 `label`（`label lead` 26px/700 沒有量過的字寬常數，見 diagram-craft §6b
    的字寬表）——跟 `_funnel_criterion_w` 對 `criterion.name` 的做法一致：
    標題列是固定高度的一列，這支量尺量的是「內容裝不裝得下」，不是標題多長。
    """
    lines = _lines(node.get("lines"))
    blocks = _blocks(node.get("blocks"))
    mono = bool(node.get("mono"))
    pairs = [p for b in blocks for p in (b.get("pairs") or [])]
    if not lines and not blocks:
        return 320
    w = 320.0
    for _ in range(12):
        pad = _pad(w)
        avail = max(1.0, w - 2 * pad)
        content = max([_tw(l) * LABEL_PX for l in lines] or [0])
        if pairs:
            quota = max(_g8(TERM_FRAC * avail), BLK_KEYMIN)
            need_term = _g8(max(_tw(k) for k, _v in pairs)
                            * (TERM_MONO_PX if mono else TERM_PX))
            kw = min(max(quota, need_term), _g8(avail * 0.62)) + GUTTER
            content = max(content, max(kw + _tw(v) * LABEL_PX for _k, v in pairs))
        for b in blocks:
            if b.get("head"):
                content = max(content, _tw(b["head"]) * HEAD_PX)
            for ln in (b.get("lines") or []):
                content = max(content, _tw(ln) * LABEL_PX)
            for ln in (b.get("numbered") or []):
                content = max(content, BLK_NUMW + _tw(ln) * LABEL_PX)
        new_w = content + 2 * pad
        if abs(new_w - w) < 0.5:
            w = new_w
            break
        w = new_w
    return min(560, max(320, _g8(w)))


def render_transform_pair(spec):
    frm, op, to = spec.get("from"), spec.get("op"), spec.get("to")
    bd = spec.get("boundary")
    if not (frm and op and to):
        sys.exit("[figure] transform_pair 需要 from／op／to 三個都填"
                 "（同一組欄位：label／mono／tone／value／lines[]／blocks[]／flow，"
                 "見 composition-vocabulary.md「transform_pair」節）")
    for where, node in (("from", frm), ("op", op), ("to", to), ("boundary", bd)):
        if node and node.get("tone") == "hl":
            _bad_tone(f"transform_pair {where}", "hl")

    parts, y = [], 0
    if spec.get("entry"):                   # 頂部入口條：這張圖怎麼讀 → annot（唯一的 annot）
        pad0 = _pad(CW)
        parts.append(BOX(0, 0, CW, 56, "box"))
        parts.append(T(pad0, 32, spec["entry"], "annot"))
        y = 88

    def _band_h(node):
        return _funnel_box_h(_lines(node.get("lines")), _blocks(node.get("blocks")),
                             node.get("flow", "row"))

    def _band(node, x, yy, w, h, where):
        _funnel_box(parts, node.get("label", ""), node.get("mono"), node.get("tone"),
                    node.get("value"), _lines(node.get("lines")), _blocks(node.get("blocks")),
                    node.get("flow", "row"), x, yy, w, h, where)

    h_from = _band_h(frm)
    _band(frm, 0, y, CW, h_from, "（transform_pair from）")
    y1 = y + h_from
    y = y1 + GAP_V
    # ⛔ **這裡刻意不畫箭頭**（協調者裁決，2026-09-05）。
    #
    # 第一版照契約字面畫了一支 `LINK(CW/2, y1, CW/2, y)` —— 實測它只有 **8px**，
    # 而 marker 本身就是 8px，⭐ **整支箭頭剛好被自己的箭頭頭蓋掉**，
    # 畫面上是一個貼在兩條橫幅之間的小點，不是一條有方向的線。
    #
    # 為什麼不是「把間距拉大就好」：三條全寬橫幅的內容高是 184 + 248 + 184 = **616**，
    # 而這一頁的預算是 **634**（`diagram-craft §6`，topic + h2）——
    # ⭐ **只剩 18px 可以分給兩道間距**，畫得下箭頭的間距（≥32）湊不出來。
    #
    # ⭐ 有先例，而且就在這一支檔案裡：`_chain_band()` 的 docstring 第一行寫著
    # 「全寬橫幅上下相疊，**中間沒有畫箭頭的間隙**，順序靠編號不靠箭頭」。
    # A4 正是同一種形狀。⛔ **在自己刻意不留的位置上硬塞一個記號，
    # 是為了滿足量尺而改畫面，不是為了觀眾** —— 那正是 `check_relation_evidence`
    # 的 docstring 逐字寫著要避免的事（L4-1「只認箭頭」那一段）。
    #
    # ⭐ 方向由**分類色**承擔：`from.tone: "bad"` → `to.tone: "good"`，
    # 那正是 `_relation_ok("transform")` 認的兩種證據之一（分類色 **或** 箭頭）。
    # ⚠️ 所以這支 renderer 產的圖 `.arrow` 數是 **0** —— ⛔ 那不是漏掉，是決定。

    h_op = _band_h(op)
    _band(op, 0, y, CW, h_op, "（transform_pair op）")
    y2 = y + h_op
    y = y2 + GAP_V                                # op → to：契約沒提第二支箭頭
                                                    # （見本節開頭那段註解），只留間距

    if bd:
        w_bd = _transform_box_w(bd)
        w_to = CW - w_bd - GAP_H
        if w_to < 240:
            sys.exit(f"[figure] transform_pair 的 to／boundary 兩欄攤不出來："
                     f"boundary 要 {w_bd}px，剩給 to 只有 {int(w_to)}px（< 240 下限）。\n"
                     f"         正解擇一：① 把 boundary 的內容寫短（縮小它的欄寬，"
                     f"boundary 是「不轉換的那一類」，不必逐句解釋）"
                     f"② 去掉 boundary，把那句話併進 op 的子區塊 ③ 拆頁。")
    else:
        w_bd, w_to = 0, CW

    flow_to = to.get("flow", "row")
    flow_bd = bd.get("flow", "row") if bd else "row"
    h_to = _funnel_box_h(_lines(to.get("lines")), _blocks(to.get("blocks")), flow_to)
    h_bd = (_funnel_box_h(_lines(bd.get("lines")), _blocks(bd.get("blocks")), flow_bd)
            if bd else 0)
    h_last = max(h_to, h_bd)          # ⭐ to／boundary 同 y 同高，共用水平軸

    _band(to, 0, y, w_to, h_last, "（transform_pair to）")
    if bd:
        _band(bd, w_to + GAP_H, y, w_bd, h_last, "（transform_pair boundary）")

    return wrap(parts, CW, y + h_last)


# ── ⑥ before_after ───────────────────────────────────────────────────────
# compare：幾個對象 × 幾個指標（字彙表 §2 第 5 類）。
#
# 座標唯一出處：composition-vocabulary.md「before_after」節與 diagram-craft.md §6b。
# ⭐ 共用軸是**真的**共用：三條全寬橫幅（同 x、w）自動就過 L4-1 的 compare 量尺，
#   但那條量尺對這支 renderer**沒有實質作用**——真正讓觀眾「比得起來」的是
#   before／after／delta 三欄的 x **全圖只算一次**（X_BEFORE／X_AFTER／X_DELTA），
#   ⛔ 不逐列各自算（那是表格最基本的失效，跟 `_col_x()`／`_term_w()` 擋的是同一件事）。
#
# ⚠️ 高度預算的坑（交件報告會覆述）：這一頁的預算是 **581**（topic+h2+sub，
# 比 A3／A4 的 634 更緊），而 3 列每列的右半都要放「小標＋2 行」的 blocks
# （每列 96px，跟列數無關，是內容本身要的），三列疊起來光是 blocks 內容就要
# 288px。**直接套用 `_funnel_box_h()` 的字面公式**（`2*LEAD + blocks_h + 24`）
# 每列要 216px，三列＋列間距（GROUP/4=16 ×2）＝680px，光是列本體就已經
# 超過 581 預算 99px（還沒算欄頭列）——那支公式是為「一排橫向、不疊放」的
# funnel 段欄調的，疊放三次會把它内建的保守留白（實測：最後一行基線到框底
# 有 56px，遠比它自己的 `+24` 字面值寬裕）放大三倍。
# 這裡改用**同一組網格常數、但省掉那份多餘保守量**的版式（下面 BA_* 那組），
# 每列改成 160px（省下的 56px 全部來自「重新量過的框頂／框底留白」，⛔ 不是
# 縮小 LEAD／ROW／GRID 本身，也没有把任何一行文字的字級或行距改小）。
# ⚠️ 即使這樣，欄頭列還要另外兩行（baseline 一整句＋before/after 兩個欄名，
# 見下面 BA_HEAD_Y1／Y2 那段的理由），實測整張圖最後是 **568px**——低於
# 581 的預算，見交件報告。
BA_RULE_GAP = 2 * GRID      # 16：name 基線到 .rule，跟 `_funnel_box` 完全同一個值
BA_TOP_GAP = 0              # 0：.rule 到內容頂端——`_funnel_box_h` 用 `2*LEAD` 當
                            #    內容基線時，內容頂端其實落在 `2*LEAD − BLK_TOP`，
                            #    换算出來多留了一個 GRID(8) 的緩衝；三列疊放、
                            #    每列都要吃滿 96px 的 blocks 時這裡讓不起，改成
                            #    內容頂端直接貼 .rule——`BLK_BASE`(24) 本身就是
                            #    「基線離區塊頂端」的安全距離，不需要再疊一層。
BA_BOTTOM_GAP = 0           # 0：內容底部到框底的**額外**留白。⚠️ 這是本支比
                            #    `_funnel_box_h` 緊最多的一格：那支字面的 `+24`
                            #    疊上前面 "2*LEAD 當基線" 的换算誤差，實測框底
                            #    留白有 56px；`_blocks_h()` 的算法本身已經在
                            #    最後一行基線後留了 `BLK_ROW − BLK_BASE = 8px`
                            #    （見 `_blk_h1`），所以「0」不等於文字貼框底，
                            #    只是不再疊加第二層留白。三列疊放、每列都要吃滿
                            #    96px 的 blocks 時，這兩格（連同上面的 BA_TOP_GAP）
                            #    是唯一有本錢讓的地方——⛔ 沒有動 LEAD／ROW／GRID
                            #    本身，也沒有把任何一行文字的字級或行距改小。
BA_HEAD_Y1 = 2 * GRID       # 16：欄頭列第一行（baseline／annot）的 baseline——
                            #    8pt 網格上能安全落腳的最小值，再往上會讓字頂在
                            #    viewBox 內變負值，被裁掉
BA_HEAD_Y2 = BA_HEAD_Y1 + ROW   # 48：欄頭列第二行（before_label／after_label）
                            #    ⚠️ 兩行不能疊在同一條 y 上：baseline 是一整句
                            #    （這一頁的 baseline 41 個半形字，用 LABEL_PX 估
                            #    有 ~430px 寬），跟對齊窄值欄（X_BEFORE 這一頁只有
                            #    40）的 before_label 幾乎一定會撞在一起。分兩行、
                            #    間距一個 ROW，兩者才不會互相蓋字。
BA_HEAD_GAP = GRID          # 8：欄頭列最後一行到第一列框頂，量尺允許的最小單位
BA_GAP = 4 * GRID           # 32：before／after／delta 欄之間的走道，跟 funnel／
                            #    transform_pair 的欄間距（GAP／GAP_H）同一個值
BA_ROW_GAP = GROUP // 4     # 16：列間距——契約直接給的數字，唯一出處在
                            #    composition-vocabulary.md「before_after」節


def _ba_row_h(lines, blocks, flow):
    """一列的高：name(LEAD) + rule 間距 + 內容頂端間距 + max(一行數值, 右半內容) + 框底留白。

    ⚠️ 不是呼叫 `_funnel_box_h()`——那支假設内容是「單欄由上而下」，
    before_after 的內容是「左半數值列＋右半 lines/blocks」並排，兩欄取高的那個。
    右半跟 `_funnel_box` 一樣是 lines 疊在 blocks 上面（先畫 lines 再畫 blocks），
    所以右半總高是兩者相加，不是取大。
    """
    content = max(ROW, ROW * len(lines) + _blocks_h(blocks, flow))
    return _g8(LEAD + BA_RULE_GAP + BA_TOP_GAP + content + BA_BOTTOM_GAP)


# ⭐ before／after／delta 用 svg `.value`（30px / 800，`deck.css`）——
# diagram-craft.md §6b 的字寬表**沒有量過這個 class**（那張表只量了 `label`
# 系列）。這裡照同一套方法（playwright `getComputedTextLength()` ÷ `_tw()`）
# 另外量了 `wd-test`／`wd-test2` 兩份已出貨 deck 裡全部既有的 `.value`／
# `.value hl` 文字（25 則，涵蓋純數字、百分比、帶小數點的長字串）：
#   純數字／百分比最重——"−28%" 19.39px/半形字、"≤2" 18.05、"3" 18.06；
#   帶小數點的長字串最輕——"0.583413" 15.6、"19.4402" 15.49。
# 取樣本裡的**最大值**（19.39）往上留一格 → VALUE_PX = 20
# （同 §6b「量出來的，不是估的……取值往上留一格」的規矩，⛔ 不是憑空的魔術數字）。
VALUE_PX = 20


def render_before_after(spec):
    rows = spec.get("rows") or []
    n = len(rows)
    if not (2 <= n <= 4):
        sys.exit(f"[figure] before_after 的 rows[] 要 2–4 列，收到 {n} 列。")
    baseline = spec.get("baseline")
    if not baseline:
        sys.exit("[figure] before_after 需要 baseline（判別欄位：對照組是什麼）")
    for i, r in enumerate(rows):
        if r.get("tone") == "hl":
            _bad_tone(f"before_after rows[{i}]", "hl")
        if not (r.get("name") and r.get("before") and r.get("after")):
            sys.exit(f"[figure] before_after rows[{i}] 缺 name／before／after（三者都必填）")
        hl = r.get("hl")
        if hl is not None and hl not in ("before", "after", "delta"):
            sys.exit(f'[figure] before_after rows[{i}].hl 只能是 before／after／delta，'
                     f'收到「{hl}」')
        if hl == "delta" and not r.get("delta"):
            sys.exit(f"[figure] before_after rows[{i}].hl 指到 delta，但這一列沒有 delta")

    before_label = spec.get("before_label") or "before"
    after_label = spec.get("after_label") or "after"

    # ── ⭐ 欄的分類色（`before_tone`／`after_tone`）──────────────────────────
    # **這是「欄」的屬性，⛔ 不是「列」的屬性** —— 那一刀很重要：
    # before_after 的分類軸是**舊 vs 新**，那是**兩欄**的差別；
    # 三列講的是同一件改動的三個面向，⭐ **是同一類**。
    # ⛔ 逐列上色 = 「並列的同類裡標一半」，正是 6c 使用者點名的雜訊
    #   （`presentation_rules §5`：「並列的東西標一半 = 雜訊」）。
    # ⭐ 欄級上色則是不折不扣的**分類**：整欄同色，回答「這一欄是舊的還是新的」。
    #
    # 語意直接引用 §5 的字：`box-bad` = **舊的**、`box-good` = **新的** ——
    # ⭐ 前後對照正好是這兩個詞，⛔ 不是我另外發明的用法。
    # 這也讓第 6 頁（`transform_pair` 的 from=bad／to=good）與第 7 頁**用同一個裝置**。
    #
    # ⛔ **opt-in，renderer 不預設塗紅塗綠**（照 `steps[].gate_tone` 的先例，N34）：
    # 「前面那一欄一定是壞的」不成立 —— 有些 before_after 的 before 只是基準，不是缺陷。
    before_tone = spec.get("before_tone")
    after_tone = spec.get("after_tone")
    for where, t in (("before_tone", before_tone), ("after_tone", after_tone)):
        if t == "hl":
            _bad_tone(f"before_after {where}", t)
        if t and t not in TONE:
            sys.exit(f"[figure] before_after 的 {where} 只吃分類色 "
                     f"{'／'.join(TONE)}（⛔ 沒有 hl，6c 已廢除），收到「{t}」。")
    pad = _pad(CW)                              # 40：全寬 box 的內距

    def vw(s):                                  # 一個 .value 字串需要的寬
        return _tw(s) * VALUE_PX

    before_w = _g8(max(vw(r["before"]) for r in rows))
    after_w = _g8(max(vw(r["after"]) for r in rows))
    delta_rows = [r for r in rows if r.get("delta")]
    delta_w = _g8(max(vw(r["delta"]) for r in delta_rows)) if delta_rows else 0

    # ── 共用軸：X_BEFORE／X_AFTER／X_DELTA 全圖各一個，⛔ 不逐列各自算 ──────
    X_BEFORE = pad
    X_AFTER = _g8(X_BEFORE + before_w + BA_GAP)
    X_DELTA = _g8(X_AFTER + after_w + BA_GAP) if delta_rows else None
    arrow_x = _g8((X_BEFORE + before_w + X_AFTER) / 2)     # → 畫在 before／after 走道正中

    X_BLOCK = _g8(CW * 0.535)                    # 760：右半起點，全圖一個值（契約唯一出處）
    last_col_end = (X_DELTA + delta_w) if X_DELTA is not None else (X_AFTER + after_w)
    if last_col_end + BA_GAP > X_BLOCK:
        sys.exit(f"[figure] before_after 三欄 x 攤不出來：before/after/delta 需要撐到 "
                 f"{last_col_end}px，右半 blocks 從 {X_BLOCK}px 開始，中間留不出一條 "
                 f"{BA_GAP}px 的走道。\n"
                 f"         正解擇一：① 把 before／after／delta 的值寫短"
                 f"（它們是數字，不是句子）② 減少列數 ③ 拆頁。")

    right_w = CW - X_BLOCK - pad
    norm_blocks = [_blocks(r.get("blocks")) for r in rows]
    norm_lines = [_lines(r.get("lines")) for r in rows]
    monos = [bool(r.get("mono")) for r in rows]
    # term 欄寬跨列共用（右半 blocks 全部同寬，符合「同一排的盒子共用同一個欄距」）
    kw = _term_w(norm_blocks, right_w, monos[0] if monos else False,
                 "（before_after 右半 blocks）")

    row_hs = [_ba_row_h(ln, b, r.get("flow", "row"))
              for r, ln, b in zip(rows, norm_lines, norm_blocks)]
    row_h = max(row_hs)                          # 契約要求「同 w、同 h」

    parts = []
    # ── 欄頭列：不畫框 ───────────────────────────────────────────────
    parts.append(T(pad, BA_HEAD_Y1, baseline, "annot"))
    parts.append(T(X_BEFORE, BA_HEAD_Y2, before_label, "label section"))
    parts.append(T(X_AFTER, BA_HEAD_Y2, after_label, "label section"))

    y = BA_HEAD_Y2 + BA_HEAD_GAP
    for r, lines, blocks, mono in zip(rows, norm_lines, norm_blocks, monos):
        tone = r.get("tone")
        parts.append(BOX(0, y, CW, row_h,
                         _shape_cls("box", tone, r["name"], _CAT_USED)))
        parts.append(T(pad, y + LEAD, r["name"], "label lead", mono=mono))
        rule_y = y + LEAD + BA_RULE_GAP
        parts.append(RULE(pad, rule_y, CW - pad))

        content_top = rule_y + BA_TOP_GAP
        value_y = content_top + BLK_BASE          # 與右半第一行同一條基線
        hl = r.get("hl")

        # 欄的底色：整欄同色（⛔ 不逐列判斷），⭐ 只有設了 tone 的欄才畫。
        # ⚠️ **縱向範圍是「分隔線以下到列底」，⛔ 不是「貼著數值那一行」** ——
        #   第一版把它畫成 48px 高、以數值基線為中心，實測直接切過列名與 `.rule`：
        #   列名基線 → `.rule` → 數值基線的間距只有 **16／24px**，
        #   ⭐ **框不進去，那是算得出來的，不是調一調就好**。
        #   改成整欄的直帶之後兩個問題一起消失：不碰列名、不碰線，
        #   而且讀起來就是「這一整欄是舊的／新的」—— ⭐ 那正是它要講的話。
        # 縱向：**貼著數值那一行**（`LEAD` 48 高，數值 30px 的字剛好包得住），
        # ⛔ 不是整列高 —— 整列高會變成一個大半是空的色塊，數值反而縮在最上緣。
        # ⚠️ 上緣 `value_y − 32`：列名（`label lead` 26px）的下伸部到 y+6 為止，
        #   這裡留 2px，⭐ **不碰列名**；`.rule` 會被色塊蓋掉一段，那是對的 ——
        #   有色塊的地方不需要再畫一條線分隔（同 §6b「有小標就不畫線」的道理）。
        cell_top = value_y - 32
        cell_h = LEAD
        for cx, cw_, ct in ((X_BEFORE, before_w, before_tone),
                            (X_AFTER, after_w, after_tone)):
            if not ct:
                continue
            parts.append(BOX(cx - GRID, cell_top, cw_ + 2 * GRID, cell_h,
                             TONE_BOX[ct]))

        def _val(x, s, col):
            cls = "value" + (" hl" if hl == col else "")
            parts.append(T(x, value_y, s, cls))

        _val(X_BEFORE, r["before"], "before")
        parts.append(T(arrow_x, value_y, "→", "label", anchor="middle"))
        _val(X_AFTER, r["after"], "after")
        if r.get("delta"):
            _val(X_DELTA, r["delta"], "delta")

        # 右半：lines 疊在 blocks 上面（跟 `_funnel_box` 同一支寫法）——
        # ⚠️ blocks 從 lines 畫完之後的 ty 接著畫，不是各自從 content_top 起算，
        #   不然兩者會疊在同一個 y 上互相蓋掉。
        _flat_check(r["name"], len(lines), bool(blocks))
        ty = content_top + BLK_BASE
        for ln in lines:
            parts.append(T(X_BLOCK, ty, ln, "label", mono=mono))
            ty += ROW
        bp, _ty = _blocks_svg(blocks, X_BLOCK, ty, right_w,
                              mono=mono, flow=r.get("flow", "row"), kw=kw)
        parts.extend(bp)

        y += row_h + BA_ROW_GAP

    return wrap(parts, CW, y - BA_ROW_GAP)


# ⚠️ chain／chain_focus／chain_gated 三個名字**指到同一支 renderer**（理由見上面那段）。
# ⚠️ funnel／funnel_named 也是**同一支**：`stages[].survivors[]` 有沒有值是判別欄位。
# ── ⑦ bars ──────────────────────────────────────────────────────────────
# compare（一個指標 × 多個對象；字彙表 §5）。2026-09-06 之前這一格寫著「還沒有 renderer」，
# 於是 deck 裡每一個「120,830 → 18,500」「被 4／5／3 項提到」都退回成框裡的一列字。
# ⭐ 長度 ∝ 值，值印在條尾；`thr` 畫一條虛線門檻。並列的對象自動拿區別色（同名同色）。

def render_bars(spec):
    items = spec.get("items") or []
    if not (2 <= len(items) <= 8):
        sys.exit(f"[figure] bars 的 items[] 要 2–8 個對象，收到 {len(items)} 個。"
                 f"超過 8 個是表格（slide type `table`），不是比較。")
    for it in items:
        if it.get("tone") == "hl":
            _bad_tone(f"bars items[{it.get('k')}]", "hl")
    pad = _pad(CW)
    kw = _g8(CW * 0.26)
    vals = [float(it.get("v", 0)) for it in items]
    thr = spec.get("thr") or {}
    vmax = float(spec.get("max") or max(vals + [float(thr.get("v", 0))]) or 1)
    texts = [glyphs.fmt(it.get("text", it.get("v", ""))) for it in items]
    vcol = 24 + max(_tw(t) * 17 for t in texts)          # value 30px/800 ≈ 17px／半形字
    bw = CW - 2 * pad - kw - vcol
    y, parts = 16, []
    if spec.get("title"):
        parts.append(T(pad, y + 26, spec["title"], "label lead"))
        y += LEAD
    y0 = y
    for it, v, t in zip(items, vals, texts):
        parts.append(T(pad, y + 32, str(it.get("k", "")), "label term", mono=it.get("mono")))
        L = max(6, v / vmax * bw)
        parts.append(f'<rect class="{glyphs._mk(it.get("tone"), it.get("k"))}" x="{_n(pad + kw)}" '
                     f'y="{_n(y + 8)}" width="{_n(L)}" height="32" rx="4"/>')
        parts.append(T(pad + kw + L + 16, y + 32, t, "value"))
        y += 48
    if thr:
        tx = pad + kw + float(thr.get("v", 0)) / vmax * bw
        parts.append(f'<path class="thr" d="M{_n(tx)},{_n(y0)} V{_n(y + 4)}"/>')
        if thr.get("label") is not None:
            parts.append(T(tx + 8, y + 28, str(thr["label"]), "label"))
            y += ROW
    if spec.get("unit"):
        parts.append(T(CW - pad, y + 28, str(spec["unit"]), "label", anchor="end"))
        y += ROW
    return wrap(parts, CW, y + 8)


# ── ⑧ genome_tracks ────────────────────────────────────────────────────
# 領域構圖（NGS）：一條參考軸（bp），底下幾條**共用同一個座標**的軌 —— 區段、探針、
# 深度、read、變異位點、mask。⭐ 這正是 IGV／genome browser 的排法，實驗室的人一看就懂，
# 而每一條軌只是一個 glyph（glyphs.py）套上同一個 `total`。
# ⛔ 不要拿它畫沒有座標的東西（那是 chain／group_blocks 的事）。

LANE_COL = 224      # 軌名那一欄的寬（與 group_blocks rows 的 224 同一個值）
TRACK_GLYPHS = glyphs.GENOMIC | {"segbar"}


def render_genome_tracks(spec):
    lanes = spec.get("lanes") or []
    length = float(spec.get("length") or 0)
    if not lanes or length <= 0:
        sys.exit("[figure] genome_tracks 需要 length（bp）與 lanes[]")
    pad = _pad(CW)
    x0, w = LANE_COL, CW - LANE_COL - pad
    parts, y = [], 8
    if spec.get("title"):
        parts.append(T(pad, y + 26, spec["title"], "label lead"))
        y += LEAD
    # 座標軸：一條底條、兩端的座標、單位
    parts.append(f'<rect class="track" x="{_n(x0)}" y="{_n(y + 8)}" width="{_n(w)}" height="8" rx="2"/>')
    ticks = int(spec.get("ticks") or 4)
    for i in range(ticks + 1):
        tx = x0 + w * i / ticks
        parts.append(f'<path class="tick" d="M{_n(tx)},{_n(y + 16)} V{_n(y + 24)}"/>')
        bp = length * i / ticks
        lab = glyphs.fmt(int(round(bp)))
        parts.append(T(tx, y + 44, lab, "label", anchor=("start" if i == 0 else "end" if i == ticks else "middle")))
    parts.append(T(pad, y + 44, str(spec.get("unit", "bp")), "label"))
    y += 64
    for i, ln in enumerate(lanes):
        g = dict(ln)
        g["glyph"] = g.pop("type", g.get("glyph"))
        if g["glyph"] not in TRACK_GLYPHS:
            sys.exit(f"[figure] genome_tracks 的軌只能是 {'、'.join(sorted(TRACK_GLYPHS))}，"
                     f"收到「{g['glyph']}」（沒有座標的東西不該放在座標軸上）")
        g["total"] = length
        g.setdefault("axis", False)
        name = g.pop("label", None)
        gh = glyphs.height(g)
        if i:
            parts.append(RULE(pad, y - 8, CW - pad))
        if name is not None:
            parts.append(T(pad, y + 24, str(name), "label term", mono=g.get("mono", False)))
        parts += glyphs.draw(g, x0, y, w)
        y += gh + 16
    return wrap(parts, CW, y)


RENDERERS = {"read_pileup": render_read_pileup,
             "bars": render_bars, "genome_tracks": render_genome_tracks,
             "haplotype_split": render_haplotype_split,
             "chain": render_chain,
             "chain_focus": render_chain,
             "chain_gated": render_chain,
             "group_blocks": render_group_blocks,
             "two_col_link": render_two_col_link,
             "funnel": render_funnel,
             "funnel_named": render_funnel,
             "transform_pair": render_transform_pair,
             "before_after": render_before_after}


DEMO = {
    "read_pileup": {
        "comp": "read_pileup", "title": "Long-read Sequencing",
        "legend": [{"label": "Somatic", "color": "somatic"},
                   {"label": "Germline", "color": "germline"},
                   {"label": "Error", "color": "error"}],
        "reads": [
            {"offset": 1, "bases": "ATTCTG", "marks": {"3": "error", "4": "germline"}},
            {"offset": 0, "bases": "ATGAGT", "marks": {"2": "germline", "5": "somatic"}},
            {"offset": 1, "bases": "TGAGTC", "marks": {"4": "somatic"}},
            {"offset": 0, "bases": "TTATGC", "marks": {"4": "germline"}},
            {"offset": 2, "bases": "GCGGCT", "marks": {"0": "germline", "1": "error"}},
            {"offset": 1, "bases": "GCTGCT", "marks": {"1": "error", "2": "germline"}},
        ]},
    "haplotype_split": {
        "comp": "haplotype_split", "title": "Phasing",
        "legend": [{"label": "Somatic", "color": "somatic"},
                   {"label": "Germline", "color": "germline"},
                   {"label": "Error", "color": "error"}],
        "groups": [
            {"label": "HP1", "tone": "h1", "reads": [
                {"offset": 0, "bases": "GAGT", "marks": {"0": "germline", "3": "somatic"}},
                {"offset": 0, "bases": "GAGT", "marks": {"0": "germline", "3": "somatic"}},
                {"offset": 0, "bases": "GCGG", "marks": {"0": "germline", "1": "error"}}]},
            {"label": "HP2", "tone": "h2", "reads": [
                {"offset": 1, "bases": "TCTG", "marks": {"1": "error", "2": "germline"}},
                {"offset": 1, "bases": "TATG", "marks": {"2": "germline"}},
                {"offset": 1, "bases": "TCTG", "marks": {"1": "error", "2": "germline"}}]},
        ]},
    # ── 概念構圖 ──────────────────────────────────────────────────────
    # ⚠️ 範例文字刻意寫成**短標籤**：label／value 不得成句，
    #    check_deck.py 的 looks_like_sentence() 會擋（>22 字元又不帶數字／符號）。
    # ⚠️ 範例不得帶已廢除的欄位（chain `focus`／tone "hl"）—— 6c 廢除之後這裡沒跟上，
    #    於是 `--demo` 在第 3 張就 sys.exit，builder 照 brief 跑它會以為 renderer 壞了。
    "chain_gated": {
        "comp": "chain_gated",
        "steps": [
            {"id": "s1", "label": "collect", "mono": True,
             "lines": ["1. list the candidates", "2. drop the duplicates"],
             "gate": "gate 1 — you confirm it"},
            {"id": "s2", "label": "score", "mono": True,
             "lines": ["1. count 4 signals", "2. add them up"],
             "gate": "gate 2 — you sign it off"},
            {"id": "s3", "label": "cut", "mono": True,
             "lines": ["1. apply the threshold"],
             "gate": "gate 3 — you see the page"},
        ],
        "axis": {"label": "cost of a wrong call",
                 "left": "1 line of text", "right": "1 redrawn page"}},
    "group_blocks": {
        "comp": "group_blocks",
        "source": {"label": ["one input,", "one file"]},
        "groups": [
            {"value": [".html", ".md"], "accent": True, "name": "read by a person",
             "members": ["at most 5 items", "one screen each"]},
            {"value": [".json"], "accent": True, "name": "read by a program",
             "members": ["no cap on items", "every field kept"]},
        ]},
    # ── box 內部有排版的範例（blocks）──────────────────────────────
    # 兩張：一張示範**縱向**的子區塊（窄格子），一張示範**並排**（全寬橫幅）。
    # ⚠️ 範例值一律寫短 —— blocks 的 value 是**事實**不是句子（同樣被
    #    check_deck.py 的 looks_like_sentence() 擋）。
    "group_blocks_nested": {
        "comp": "group_blocks", "cols": 2,
        "groups": [
            {"name": "items[] → .html · .md", "blocks": [
                {"head": "each item", "pairs": [["question", "why today"],
                                                ["approach", "what was done"],
                                                ["result", "numbers, tables"]]},
                {"head": "always required", "pairs": [["gaps", "on every item"],
                                                      ["concepts", "term + wording"]]},
                {"head": "cap and merge", "numbered": ["cap 5 · no split ties",
                                                       "merge 2 of 4 into 1"]}]},
            {"name": "record[] → .data/<date>.json", "blocks": [
                {"head": "each record",
                 "pairs": [["what · why · did", "result · state"],
                           ["what", "100-300 words"],
                           ["under 60", "validate_log.py warns"]]},
                {"head": "evidence", "pairs": [["evidence.ref", "session_id:line"],
                                               ["quotes", "_private/, not git"]]},
                {"head": "no cap", "numbered": ["collapsed in .html",
                                                "ordered by score"]}]}]},
    "chain_band_nested": {
        "comp": "chain", "layout": "band",
        "steps": [
            {"id": "s1", "label": "extract_transcript.py", "mono": True, "blocks": [
                {"head": "reads", "pairs": [["~/.claude/projects", "every project"],
                                            [".jsonl", "1 per session"]]},
                {"head": "keeps", "pairs": [["text", "in full"],
                                            ["tool_use", "300 chars"]]}]},
            {"id": "s2", "label": "signals.py → signals.md", "mono": True, "blocks": [
                {"head": "counts", "pairs": [["user_msgs", "80 · 39 decisive"],
                                             ["files", "117 tool_use"]]},
                {"head": "zero", "numbered": ["titles in past 7 days 0",
                                              "commits 0 · not in git"]}]}]},
    "two_col_link": {
        "comp": "two_col_link",
        "entry": "one row per block type; red = dropped",
        "left": [{"id": "a", "label": "text", "note": "what we said"},
                 {"id": "b", "label": "tool_use", "note": "commands run"},
                 {"id": "c", "label": "image", "note": "screenshots"}],
        "right": [{"id": "keep", "label": "kept in full"},
                  {"id": "cut", "label": "cut at 300 characters"},
                  {"id": "drop", "label": "thrown away"}],
        "links": [["a", "keep"], ["b", "cut"], ["c", "drop", "bad"]]},
    # ── PR 4（2026-09-06）：glyph 小圖與兩個新構圖 ─────────────────────────
    # ⚠️ 範例數字是虛構的 NGS 情境（TB 專一性區域探勘），只為了看形狀；
    #    label 一律短、value 一律數字（check_deck 的 looks_like_sentence 會擋句子）。
    "bars": {
        "comp": "bars", "title": "probes that also hit off-target genomes",
        "unit": "probes", "max": 9587,
        "items": [{"k": "designed", "v": 9587, "tone": "ctl"},
                  {"k": "clean", "v": 8021, "tone": "good"},
                  {"k": "off-target hit", "v": 1566, "tone": "bad", "text": "1,566 · 16.3%"}],
        "thr": {"v": 959, "label": "10% cap"}},
    "genome_tracks": {
        "comp": "genome_tracks", "budget": 680, "title": "signature sig-2 · 120 kb window", "length": 120000,
        "lanes": [
            {"type": "feat", "label": "signatures",
             "features": [{"s": 4000, "e": 26000, "label": "sig-1"},
                          {"s": 41000, "e": 74000, "label": "sig-2"},
                          {"s": 88000, "e": 117000, "label": "sig-3"}]},
            {"type": "probes", "label": "probes 120 bp", "probe": 6000, "stride": 3000,
             "hits": [3, 4, 17, 29], "value": "4 / 39 hit"},
            {"type": "coverage", "label": "depth", "thr": 30,
             "values": [12, 28, 41, 55, 62, 58, 47, 31, 18, 9, 22, 44, 66, 71, 60, 38, 21, 15, 33, 52]},
            {"type": "reads", "label": "reads",
             "reads": [{"s": 5000, "e": 19000, "mm": [11000]}, {"s": 9000, "e": 22000, "dir": "left"},
                       {"s": 30000, "e": 43000, "mate": [52000, 64000]}, {"s": 47000, "e": 60000, "mm": [50000, 57000]},
                       {"s": 70000, "e": 84000, "dir": "left", "tone": "ctl"}, {"s": 86000, "e": 99000, "mate": [104000, 116000]},
                       {"s": 2000, "e": 15000, "tone": "good"}]},
            {"type": "lollipop", "label": "variants",
             "marks": [{"pos": 11000, "tone": "bad", "n": 3}, {"pos": 50000, "tone": "bad"},
                       {"pos": 57000, "n": 12}, {"pos": 101000, "tone": "good"}]},
            {"type": "segbar", "label": "masked",
             "rows": [{"segs": [{"len": 40000, "tone": "good"}, {"len": 12000, "tone": "bad"},
                                {"len": 48000, "tone": "good"}, {"len": 8000, "tone": "bad"}, {"len": 12000, "tone": "good"}]}]}]},
    "glyphs_counts": {
        "comp": "chain", "budget": 680,
        "steps": [
            {"id": "g1", "label": "two groups", "blocks": [
                {"head": "genomes", "glyph": "dots", "label": "on-target", "value": 469,
                 "groups": [{"n": 469, "label": "on-target", "tone": "good"}, {"n": 817, "label": "off-target", "tone": "bad"}]},
                {"glyph": "hero", "v": 1286, "label": "genomes in"}]},
            {"id": "g2", "label": "21-mer filter", "blocks": [
                {"head": "k-mers", "glyph": "tiles", "n": 14, "gradient": True, "marks": {"4": "bad", "9": "bad"},
                 "label": "shared by all 469", "value": "2 / 14 fail"},
                {"head": "kept · dropped", "glyph": "bars", "max": 627199,
                 "items": [{"k": "signature bp", "v": 627199, "tone": "good"},
                           {"k": "masked bp", "v": 166526, "tone": "bad"}]},
                {"head": "identity per window", "glyph": "heat", "x": ["5'", "3'"],
                 "cells": [0.98, 0.99, 0.97, 0.62, 0.41, 0.88, 0.95, 0.99, 0.99, 0.93, 0.7, 0.96]}]},
            {"id": "g3", "label": "mask windows", "blocks": [
                {"head": "before → after", "glyph": "segbar", "total": 100,
                 "rows": [{"label": "signature", "value": "627,199 bp",
                           "segs": [{"len": 100, "tone": "good"}]},
                          {"label": "hit windows", "value": "26.6%",
                           "segs": [{"len": 18, "tone": "good"}, {"len": 12, "tone": "bad"}, {"len": 34, "tone": "good"},
                                    {"len": 9, "tone": "bad"}, {"len": 27, "tone": "good"}]},
                          {"label": "kept", "value": "460,673 bp",
                           "segs": [{"len": 18, "tone": "good"}, {"len": 12, "tone": "gap"}, {"len": 34, "tone": "good"},
                                    {"len": 9, "tone": "gap"}, {"len": 27, "tone": "good"}]}]}]}]},
    "glyphs_flow": {
        "comp": "chain", "budget": 680,
        "steps": [
            {"id": "f1", "label": "extract", "blocks": [
                {"head": "turns kept", "glyph": "checklist",
                 "items": [{"t": "user text", "ok": True}, {"t": "assistant text", "ok": True},
                           {"t": "tool_use · tool_result", "ok": False}, {"t": "thinking · system", "ok": False}]},
                {"head": "sessions → topics", "glyph": "funnel",
                 "stages": [{"n": 22, "label": "sessions"}, {"n": 19, "label": "tasks"},
                            {"n": 5, "label": "topics"}, {"n": 11, "label": "pages"}]}]},
            {"id": "f2", "label": "merge", "blocks": [
                {"head": "bottom-up", "glyph": "tree", "leaves": 8, "mid": 3, "root": "daily report"},
                {"head": "shared k-mers", "glyph": "venn", "a": 1204, "b": 388, "both": 1657,
                 "la": "on-target", "lb": "lit. markers"}]},
            {"id": "f3", "label": "reply", "blocks": [
                {"head": "read-only stages", "glyph": "pills", "flow": "col", "items": ["fetch", "classify", "draft"]},
                {"glyph": "gate", "label": "human confirms", "value": "before API call"},
                {"head": "insert size", "glyph": "hist", "thr": 0.7, "above": "bad", "x": ["150 bp", "600 bp"],
                 "bins": [1, 3, 8, 15, 24, 31, 28, 19, 11, 6, 3, 2, 1, 1]}]}]},
    "glyphs_ngs": {
        "comp": "chain", "budget": 680,
        "steps": [
            {"id": "n1", "label": "k-mer windows", "blocks": [
                {"head": "21-mer", "glyph": "kmers", "n": 18, "k": 7, "show": 4, "label": "sliding by 1"},
                {"head": "alignment", "glyph": "align",
                 "rows": [{"name": "H37Rv", "cells": "MMMMMMMMMMMMMMMM"},
                          {"name": "isolate-7", "cells": "MMMXMMMM--MMMMXM"},
                          {"name": "M. bovis", "cells": "MMMMMXMMMMNNMMMM"}]}]},
            {"id": "n2", "label": "capture check", "blocks": [
                {"head": "probes over sig-2", "glyph": "probes", "total": 33000, "probe": 3000, "stride": 1500,
                 "hits": [2, 3, 11], "value": "3 / 21 hit"},
                {"head": "off-target reads", "glyph": "reads", "total": 33000,
                 "reads": [{"s": 1000, "e": 6000, "mm": [3200]}, {"s": 4000, "e": 9500, "dir": "left"},
                           {"s": 12000, "e": 17000, "mate": [19000, 24000]}, {"s": 21000, "e": 27000, "mm": [22500, 26000], "tone": "bad"},
                           {"s": 27500, "e": 32500}], "value": "5 reads · 4 mm"}]},
            {"id": "n3", "label": "depth & variants", "blocks": [
                {"head": "depth ≥ 30×", "glyph": "coverage", "thr": 30,
                 "values": [8, 19, 34, 52, 61, 58, 49, 37, 26, 14, 20, 45, 63, 70, 55, 33]},
                {"head": "SNVs", "glyph": "lollipop", "total": 33000,
                 "marks": [{"pos": 3200, "tone": "bad", "n": 2}, {"pos": 14000}, {"pos": 22500, "tone": "bad", "n": 5},
                           {"pos": 29000, "tone": "good"}], "value": "4 sites"},
                {"head": "gene models", "glyph": "feat", "total": 33000,
                 "features": [{"s": 500, "e": 9000, "label": "Rv0001"}, {"s": 12000, "e": 18500, "label": "Rv0002", "tone": "ctl"},
                              {"s": 20000, "e": 31000, "label": "Rv0003"}]}]}]},
}


def _render_one(spec):
    """渲染一份 spec（含 budget 與逐張重置的全域狀態），回 SVG 字串。"""
    global HMAX
    HMAX = int(spec["budget"]) if spec.get("budget") else _HMAX_DEFAULT
    comp = spec.get("comp")
    if comp not in RENDERERS:
        raise ValueError(f"不認得的 comp「{comp}」。可用：{'、'.join(RENDERERS)}")
    _OVERFLOW.clear()               # N94：逐張獨立，⛔ 不要累積到下一張
    _CAT_USED.clear()
    _BLK_USED[0] = False
    return RENDERERS[comp](spec)


def render_all(out_dir, thread=None):
    """渲染 `<out>/_work/3b_specs/*.json` —— 一個回合，不是一頁一個。

    輸出檔名的來源依序：manifest（compositions.*.json 的 figures[].slide → file）、
    spec 自己的 `out` 欄位、最後退回 `figures/<頁 id>.svg`。
    ⚠️ 手寫圖（manifest 標 handwritten）沒有 spec 可跑，這裡自然掃不到。

    `thread` 給了就**只渲染這條線的**：多線時每個 builder 各跑一次，⛔ 不准碰別線的圖
    （兩個 builder 平行時，A 正在重寫 B 的 SVG、B 的 verify 同時在讀它 → 假的
    parse／reproduce 失敗）。一張 spec 屬於這條線的三種證據，任一成立即可：
    ① `compositions.<線>.json` 的 figures[].slide 列了它；② 檔名（＝頁 id）以線 id 開頭、
    後面接數字（`B1`、`B12`）；③ spec 自帶 `thread` 欄位。
    寫檔一律先寫 `.tmp` 再 os.replace，讀的人看到的不是半張圖。
    """
    import glob as _glob
    import paths as _paths
    out_dir = os.path.abspath(out_dir)
    spec_dir = _paths.work_dir(out_dir, "specs", create=False)
    specs = sorted(_glob.glob(os.path.join(spec_dir, "*.json")))
    if not specs:
        sys.exit(f"[figure] {spec_dir} 底下沒有任何 spec（*.json）")
    slides_dir = _paths.work_dir(out_dir, "slides", create=False)
    manifests = (_glob.glob(os.path.join(slides_dir, f"compositions.{thread}.json")) if thread
                 else _glob.glob(os.path.join(slides_dir, "compositions.*.json")))
    file_of = {}
    for mp in manifests:
        try:
            j = json.load(open(mp, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for e in (j.get("figures") or []):
            if isinstance(e, dict) and e.get("slide") and e.get("file"):
                file_of[e["slide"]] = e["file"]
    sid_re = re.compile(r"^" + re.escape(thread) + r"\d") if thread else None
    ok, bad, skipped = 0, 0, []
    for sp in specs:
        sid = os.path.splitext(os.path.basename(sp))[0]
        try:
            spec = json.load(open(sp, encoding="utf-8"))
        except (OSError, ValueError) as ex:
            if thread and not (sid in file_of or sid_re.match(sid)):
                skipped.append(sid); continue          # 別線的壞 spec 也不是我的事
            print(f"[figure] ✗ {sid}: spec 讀不了：{ex}"); bad += 1; continue
        if thread and not (sid in file_of or sid_re.match(sid) or spec.get("thread") == thread):
            skipped.append(sid); continue
        rel = file_of.get(sid) or spec.get("out") or f"figures/{sid}.svg"
        dest = os.path.join(out_dir, rel)
        try:
            svg = _render_one(spec)
        except SystemExit as ex:              # renderer 用 sys.exit 報 spec 錯誤
            print(f"[figure] ✗ {sid}: {ex}"); bad += 1; continue
        except ValueError as ex:
            print(f"[figure] ✗ {sid}: {ex}"); bad += 1; continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(svg)
        os.replace(tmp, dest)                 # 原子換入：讀的人看到整張或舊的，不是半張
        src = ("manifest" if sid in file_of else "spec.out" if spec.get("out") else "預設")
        print(f"[figure] ✓ {sid} → {rel}　（輸出名來自 {src}）")
        ok += 1
    if thread and not ok and not bad:
        sys.exit(f"[figure] {spec_dir} 底下沒有一張 spec 屬於線「{thread}」"
                 f"（看了 {len(specs)} 張：{', '.join(skipped[:12])}{'…' if len(skipped) > 12 else ''}）。"
                 f"頁 id 要以線 id 開頭，或先把它登進 compositions.{thread}.json")
    if skipped:
        print(f"[figure] （跳過別線的 {len(skipped)} 張：{', '.join(skipped[:12])}"
              f"{'…' if len(skipped) > 12 else ''}）")
    print(f"[figure] {ok} 張渲染完成" + (f"、{bad} 張失敗" if bad else "") +
          "。⛔ 接著跑 verify.py（check_spec_reproduces 會逐 byte 對這批圖）")
    return 1 if bad else 0


def main():
    global HMAX
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?", help="JSON 規格檔（或 - 讀 stdin）")
    ap.add_argument("-o", "--out")
    ap.add_argument("--demo", metavar="OUTDIR",
                    help="DEMO 表裡每一則各產一張範例圖"
                         "（⛔ 不在這裡寫死張數：同一個 comp 可以有多則）")
    ap.add_argument("--all", metavar="OUTDIR",
                    help="⭐ 一個回合渲染整份 deck 的圖：讀 <OUTDIR>/_work/3b_specs/*.json，"
                         "輸出位置依序取 compositions.*.json 的 figures[].file → spec 的 "
                         "`out` 欄位 → figures/<頁 id>.svg。builder 寫完所有 spec 跑這一次，"
                         "⛔ 不要一頁一次（每次呼叫都是一個 API 回合）")
    ap.add_argument("--thread", metavar="線ID",
                    help="配 --all：只渲染這條線的 spec（頁 id 以線 id 開頭、或登在 "
                         "compositions.<線>.json 裡、或 spec 有 thread 欄位）。"
                         "⭐ 多線平行時每個 builder **一定要給**，⛔ 不准重寫別線的圖")
    ap.add_argument("--budget", type=int, metavar="PX",
                    help="這一頁給圖的高度預算（px）。⭐ 去 references/diagram-craft.md §6 "
                         f"的表查：看這頁有沒有 topic／sub，查到幾就傳幾。"
                         f"⛔ 出貨版要寫進 spec 檔的 `budget` 欄位（那是唯一的記錄處，"
                         f"N121）—— 這個旗標只是臨時覆寫。都沒有＝{HMAX}")
    a = ap.parse_args()

    if a.demo:
        os.makedirs(a.demo, exist_ok=True)
        for name, spec in DEMO.items():
            # ⚠️ 用 spec["comp"] 查 renderer，不是用 key —— 同一個 comp 可以有
            #    多張範例（例如 blocks 的縱向版與並排版），key 只是檔名。
            p = os.path.join(a.demo, f"{name}.svg")
            try:
                svg = _render_one(spec)     # 逐張重置全域狀態（N94）
            except SystemExit as ex:        # 一張壞掉不要讓其餘的範例跟著消失
                print(f"[figure] ✗ {name}: {ex}")
                continue
            open(p, "w", encoding="utf-8").write(svg)
            print(f"[figure] {p}")
        return

    if a.all:
        return render_all(a.all, thread=a.thread)
    if a.thread:
        sys.exit("[figure] --thread 只配 --all 用")

    if not a.spec:
        sys.exit("[figure] 要給 spec.json，或用 --demo / --all <日期目錄>")
    spec = json.load(sys.stdin if a.spec == "-" else open(a.spec, encoding="utf-8"))

    # ── 高度預算：⭐ **唯一的記錄處是 spec 檔的 `budget` 欄位**（N121）─────────
    # ⛔ 高度預算是**每一頁不同**的（有沒有 topic／sub 差好幾十 px，數字查
    #    `diagram-craft.md §6` 的表），renderer 自己看不到這張圖要放在哪一種頁上（N68）。
    #
    # ⚠️ 舊版**只**能由 `--budget` 傳進來，於是「出貨時用的是哪個預算」
    #    **沒有記在任何地方** —— 重跑的人只能猜（預設 537），而 N121 那把量尺
    #    （「每個 spec 重跑一次要逐 byte 重現出貨的 SVG」）需要一個
    #    **不必靠命令列就重現得出來**的輸入。⭐ 所以它進 spec 檔：
    #    `render_figure.py <spec> -o <svg>` 這一條命令自己就是完整的重現配方。
    #
    # ⛔ **不放 `compositions.*.json` 的 figure 條目**：那份是**帳本**（畫出來的東西的
    #    紀錄），把 render 的輸入拆到兩個檔＝製造第二份手抄本，正是 N123 否決方案 B
    #    的那個理由。⭐ 一條命令的輸入只該有一個檔。
    #
    # ⚠️ 實測：`--budget` **不影響輸出的任何一個 byte**（`_height_guard` 只印警告，
    #    不改幾何）—— 所以逐 byte 重現本身不靠它。它要守的是另一半：
    #    **這張圖到底放不放得進那一頁**。不記下來，重跑的人拿預設 537 去量，
    #    對 634 的頁面會喊假警報、對 581 的頁面會漏掉真的超高。
    # 優先序：命令列 `--budget` > spec 的 `budget` > 預設（HMAX 537）。
    #   ⭐ 命令列贏，是為了「臨時換一頁試試看」不必改檔；⛔ 但出貨版一定要寫進 spec。
    if a.budget:
        HMAX = a.budget
    elif spec.get("budget"):
        HMAX = int(spec["budget"])

    comp = spec.get("comp")
    if comp not in RENDERERS:
        sys.exit(f"[figure] 不認得的 comp「{comp}」。可用：{'、'.join(RENDERERS)}\n"
                 f"         沒有對應 renderer 時才准手寫 SVG，"
                 f"並在 plan 寫明為什麼現有構圖都不適用。")
    _OVERFLOW.clear()
    _CAT_USED.clear()
    svg = RENDERERS[comp](spec)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(svg)
        print(f"[figure] {a.out}")
    else:
        sys.stdout.write(svg)


if __name__ == "__main__":
    sys.exit(main())     # --all 有任何一張失敗回 1，呼叫端才能拿它當關卡
