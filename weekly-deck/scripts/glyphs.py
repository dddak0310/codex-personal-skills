#!/usr/bin/env python3
"""glyph：盒子裡的**小圖**（PR 4，2026-09-06）—— 由數字畫出來，⛔ 不是由人手排座標。

## 為什麼有這一層

2026-09-06 拿 APG `weekly-deck-builder` 的兩頁手繪 SVG 對照本 skill 的產出：
兩邊**事實一樣多**，APG 看起來「有圖」而我們看起來「表格塞在框裡」。差別只有一件事 ——
APG 每一步都給**那件東西本身的一張小圖**：基因組是一條 bar、k-mer 是一排 tile、
469 個基因組是一片點陣、被 mask 的區段是綠 bar 上挖掉的紅窗、被丟掉的片段是灰色短截。
而我們的盒內文法只有 `lines`／`pairs`／`numbered` 三種 —— **全是字**，沒有一種是圖。

⭐ APG 那些小圖拆開只有十來種基本形，每一種由**兩三個數字**就完全決定。
手寫 SVG 的代價（一頁 3,600～4,100 個輸出 token、比例憑感覺、字級 5～9px、每改一次
整頁重寫）全部來自「由人排座標」，⛔ 不來自「有小圖」。所以小圖進 renderer：
builder 寫 `{"glyph": "dots", "n": 469}`（十幾個 token），比例由程式算、跨頁必然一致、
`<text>` 仍走 `T()` 帶用途 class（zh 版照樣翻得到）、字級一律 deck.css 的 22px。

## 契約

- 一個 glyph 是 `blocks[]` 的**第四種內容**（與 lines／pairs／numbered 擇一）：
  `{"glyph": "<名>", ...參數, "head": 可選, "label": 可選, "value": 可選, "h": 可選}`
- 高度只由**參數**決定（⛔ 不由寬度決定），一律落在 8pt 網格；`h` 可覆寫（48～320）。
  這樣 `_blocks_h()` 不用知道盒寬就算得出總高，既有的高度預算機制照舊。
- 顏色只有三種角色（presentation_rules §5）：分類（`tone`: good／bad／null／ctl）、
  區別（並列的群拿 `mk-c1`~`c12`，種子＝名字，與方框同一套雜湊 → 同名同色）、
  淡（`dim`＝被捨棄／不算）。⛔ 沒有「強調」：形狀不強調，只有字的 `.hl`。
- 文字**只有兩種**：`label`（東西的名字）與 `value inline`（數字）。每個 glyph 最多
  一列說明（左 label、右 value），⛔ 不在圖裡塞旁白 —— 旁白是 annot，一頁 ≤2。
- 基因組座標一律 bp：帶 `total`（或由上層 `genome_tracks` 傳入），glyph 把 bp 線性映到 px。

## 目錄（名 → 參數；詳見 references/glyphs.md）

計數／比例：dots · tiles · segbar · bars · hero · hist · heat · venn
流程／判斷：funnel · tree · checklist · gate · pills
NGS：feat · reads · probes · kmers · lollipop · coverage · align
"""
import math
import sys

# ── 與 render_figure 的連結：**延後綁定**（render_figure 先 import 這支）───────
_R = None


def _r():
    """render_figure 在 import 時把自己綁進 `_R`（見那邊的註解）；這裡的 import 只是保險。"""
    global _R
    if _R is None:
        import render_figure as _rf
        _R = _rf
    return _R


GRID = 8
ROW = 32
CAP = ROW                      # 說明列（左 label、右 value）佔的高
VAL_PX = 12                    # value.inline（22px / 700）每半形字的粗估寬
H_MIN, H_MAX = 48, 320

TONE_CLS = {None: "mk", "": "mk", "good": "mk-good", "bad": "mk-bad",
            "null": "mk-null", "ctl": "mk-ctl", "dim": "mk-dim"}


def _g8(v):
    return int(round(float(v) / GRID) * GRID)


def _n(v):
    return _r()._n(v)


def _T(*a, **k):
    return _r().T(*a, **k)


def _tw(s):
    return _r()._tw(s)


def fmt(v):
    """數字給人看：整數千分位；字串照用。"""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:,.1f}" if v != int(v) else f"{int(v):,}"
    return str(v)


def _mk(tone, name=None):
    """記號的 class：分類色 > 區別色（有 name 才配）> 一般。"""
    if tone in TONE_CLS and tone:
        return TONE_CLS[tone]
    if name is not None:
        r = _r()
        return f"mk-{r._cat_of(str(name), r._CAT_USED)}"
    return "mk"


def _rect(x, y, w, h, cls, rx=2, extra=""):
    return (f'<rect class="{cls}" x="{_n(x)}" y="{_n(y)}" width="{_n(max(w, 1))}" '
            f'height="{_n(h)}" rx="{rx}"{extra}/>')


def _circle(cx, cy, r, cls, extra=""):
    return f'<circle class="{cls}" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"{extra}/>'


def _path(d, cls):
    return f'<path class="{cls}" d="{d}"/>'


def _caption(p, x, y, w):
    """glyph 的說明列：左 label、右 value。回 (parts, 用掉的高)。沒填就 0。"""
    lab, val = p.get("label"), p.get("value")
    if lab is None and val is None:
        return [], 0
    parts = []
    if lab is not None:
        parts.append(_T(x, y + 24, str(lab), "label"))
    if val is not None:
        parts.append(_T(x + w, y + 24, fmt(val), "value inline", anchor="end"))
    return parts, CAP


def _has_cap(p):
    return p.get("label") is not None or p.get("value") is not None


def _sx(total, x, w):
    """bp → px 的線性映射。"""
    total = float(total) if total else 1.0
    return lambda bp: x + (float(bp) / total) * w


def _keycol(names, w, mono=False, frac=None):
    """名字那一欄的寬：先按盒寬配額（同 `_term_w` 的 0.32），名字更長就讓開 ——
    讓開是為了不壓到記號（實測 glyphs_counts 的「signature bp」壓進 bar 裡）。"""
    r = _r()
    quota = max(r.BLK_KEYMIN, _g8(w * (frac or r.TERM_FRAC)))
    px = r.TERM_MONO_PX if mono else r.TERM_PX
    need = _g8(max([_tw(str(k)) * px for k in names] + [0])) + r.GUTTER
    return min(max(quota, need), _g8(w * 0.6))


# ═════════════════════════════════════════════════════════════════════════
# 計數／比例
# ═════════════════════════════════════════════════════════════════════════

def h_dots(p):
    return 64 + (CAP if _has_cap(p) else 0)


def g_dots(p, x, y, w, h):
    """點陣：`n`（或 `groups[{n,tone,label}]`）個東西，一點代表 `unit` 個。
    `of` 給了就把分母補成淡點。點數依可用面積自動選 unit（1、2、5、10…）。"""
    r, pitch = 6, 16
    area_h = h - (CAP if _has_cap(p) else 0)
    cols = max(1, int(w // pitch))
    rows = max(1, int(area_h // pitch))
    groups = p.get("groups")
    if groups:
        seq = [(int(g.get("n", 0)), _mk(g.get("tone"), g.get("label") or i))
               for i, g in enumerate(groups)]
    else:
        seq = [(int(p.get("n", 0)), _mk(p.get("tone")))]
    total = int(p.get("of") or sum(n for n, _ in seq))
    unit = int(p.get("unit") or 0)
    if not unit:
        unit = 1
        for u in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000):
            unit = u
            if math.ceil(total / u) <= cols * rows:
                break
    parts, i = [], 0

    def put(k, cls):
        nonlocal i
        for _ in range(k):
            cr, cc = divmod(i, cols)
            if cr >= rows:
                return
            parts.append(_circle(x + cc * pitch + r + 2, y + cr * pitch + r + 2, r, cls))
            i += 1
    for n, cls in seq:
        put(math.ceil(n / unit), cls)
    rest = math.ceil(total / unit) - i
    if rest > 0:
        put(rest, "mk-dim")
    cap, _ = _caption(p, x, y + area_h, w)
    if unit > 1 and p.get("label") is not None:
        lw = _tw(str(p["label"])) * _r().LABEL_PX + 24
        cap.append(_T(x + lw, y + area_h + 24, f"● = {fmt(unit)}", "label"))
    return parts + cap


def h_tiles(p):
    return 40 + (CAP if _has_cap(p) else 0)


def g_tiles(p, x, y, w, h):
    """一排 tile：`n` 個（≤40），`marks{索引: tone}` 或 `tones[]` 逐格上色，
    `gradient: true` 讓不透明度由左到右漸增（k-mer、逐步遞增那類）。"""
    n = max(1, min(int(p.get("n", 8)), 40))
    gap = 6
    tw = max(8, min(40, int((w - gap * (n - 1)) / n)))
    th = 28
    marks = {str(k): v for k, v in (p.get("marks") or {}).items()}
    tones = p.get("tones") or []
    parts = []
    for i in range(n):
        tone = marks.get(str(i)) or (tones[i] if i < len(tones) else p.get("tone"))
        op = f' fill-opacity="{0.3 + 0.7 * i / max(1, n - 1):.2f}"' if p.get("gradient") else ""
        parts.append(_rect(x + i * (tw + gap), y + 4, tw, th, _mk(tone), rx=3, extra=op))
    cap, _ = _caption(p, x, y + 40, w)
    return parts + cap


def _rows_of(p):
    rows = p.get("rows")
    if not rows:
        rows = [p.get("segs") or []]
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append(r)
        else:
            out.append({"segs": r})
    return out


def h_segbar(p):
    rows = _rows_of(p)
    arrow = p.get("arrow", len(rows) > 1)
    h = 0
    for i, r in enumerate(rows):
        if i and arrow:
            h += 24
        h += 32 if (r.get("label") is not None or r.get("value") is not None) else 0
        h += 32
    return h


def g_segbar(p, x, y, w, h):
    """分段的橫條：`rows[[{len,tone}]]`（一列＝一個狀態），`tone:"gap"` 是空白、
    `"dim"` 是被捨棄。多列之間畫向下的箭頭（before → after）。長度按 `total`
    （沒給就取最長那一列的總和）線性映射。每一列可帶自己的 label／value。"""
    rows = _rows_of(p)
    arrow = p.get("arrow", len(rows) > 1)
    total = float(p.get("total") or max(sum(float(s.get("len", 0)) for s in r["segs"])
                                         for r in rows) or 1)
    parts, cy = [], y
    for i, r in enumerate(rows):
        if i and arrow:
            mx = x + w / 2
            parts.append(_path(f"M{_n(mx)},{_n(cy + 2)} V{_n(cy + 16)}", "arrow"))
            cy += 24
        cap, ch = _caption(r, x, cy, w)
        parts += cap
        cy += ch
        cx = x
        for s in r["segs"]:
            sw = float(s.get("len", 0)) / total * w
            tone = s.get("tone")
            if tone != "gap":
                parts.append(_rect(cx, cy + 4, sw - 2 if sw > 3 else sw, 24,
                                   _mk(tone, s.get("name")), rx=3))
            cx += sw
        cy += 32
    return parts


def h_bars(p):
    return ROW * len(p.get("items") or []) + (ROW if p.get("thr") else 0)


def g_bars(p, x, y, w, h):
    """橫向長條：`items[{k, v, tone}]`，長度 ∝ v（`max` 沒給就取最大值），
    值印在條尾。`thr:{v,label}` 畫一條虛線門檻。這是 `compare` 關係的 glyph 版。"""
    items = p.get("items") or []
    if not items:
        return []
    kw = _keycol([it.get("k", "") for it in items], w)
    vals = [float(it.get("v", 0)) for it in items]
    vmax = float(p.get("max") or max(vals + [float((p.get("thr") or {}).get("v", 0))]) or 1)
    vcol = 8 + max(_tw(fmt(it.get("text", it.get("v", "")))) * VAL_PX for it in items)
    bw = max(48, w - kw - vcol)
    parts, cy = [], y
    for it, v in zip(items, vals):
        parts.append(_T(x, cy + 24, str(it.get("k", "")), "label term"))
        L = max(4, v / vmax * bw)
        parts.append(_rect(x + kw, cy + 6, L, 20, _mk(it.get("tone"), it.get("name")), rx=3))
        parts.append(_T(x + kw + L + 8, cy + 24, fmt(it.get("text", it.get("v", ""))),
                        "value inline"))
        cy += ROW
    thr = p.get("thr")
    if thr:
        tx = x + kw + float(thr.get("v", 0)) / vmax * bw
        parts.append(_path(f"M{_n(tx)},{_n(y)} V{_n(cy + 4)}", "thr"))
        if thr.get("label") is not None:
            parts.append(_T(tx + 8, cy + 24, str(thr["label"]), "label"))
    return parts


def h_hero(p):
    return 64 + (ROW if p.get("sub") else 0)


def g_hero(p, x, y, w, h):
    """一張圖裡**最重要的那個數字**，放大成 `value hero`（44px）。
    `v` 數字、`label` 它是什麼（同一列，接在後面）、`sub` 下一列的補充。
    ⚠️ 一頁一個就夠：兩個 hero 就沒有 hero。"""
    parts = [_T(x, y + 48, fmt(p.get("v", "")), "value hero")]
    vw = _tw(fmt(p.get("v", ""))) * 24 + 16
    if p.get("label") is not None:
        parts.append(_T(x + vw, y + 48, str(p["label"]), "label"))
    if p.get("sub"):
        parts.append(_T(x, y + 64 + 24, str(p["sub"]), "label"))
    return parts


def h_hist(p):
    return 72 + (CAP if _has_cap(p) or p.get("x") else 0)


def g_hist(p, x, y, w, h):
    """直方圖：`bins[]`（高度 ∝ 值），`thr` 是**第幾個 bin 之前**（整數）或 0–1 的比例，
    `x:[左標, 右標]` 是軸兩端的字，`above` 給 tone 讓門檻右邊的 bin 換色。"""
    bins = [float(v) for v in (p.get("bins") or [])]
    if not bins:
        return []
    n = len(bins)
    gap = 3
    bw = max(3, (w - gap * (n - 1)) / n)
    vmax = max(bins) or 1
    ah = 64
    thr = p.get("thr")
    cut = None
    if thr is not None:
        cut = int(thr) if float(thr) >= 1 or float(thr) == 0 else int(round(float(thr) * n))
    parts = []
    for i, v in enumerate(bins):
        bh = max(2, v / vmax * ah)
        tone = p.get("above") if (cut is not None and i >= cut and p.get("above")) else p.get("tone")
        parts.append(_rect(x + i * (bw + gap), y + 4 + ah - bh, bw, bh, _mk(tone), rx=2))
    parts.append(_path(f"M{_n(x)},{_n(y + 4 + ah)} H{_n(x + w)}", "rule"))
    if cut is not None:
        tx = x + cut * (bw + gap) - gap / 2
        parts.append(_path(f"M{_n(tx)},{_n(y)} V{_n(y + 8 + ah)}", "thr"))
    cy = y + 72
    if p.get("x"):
        xs = list(p["x"])[:2]
        parts.append(_T(x, cy + 24, str(xs[0]), "label"))
        if len(xs) > 1:
            parts.append(_T(x + w, cy + 24, str(xs[1]), "label", anchor="end"))
        if p.get("label") is not None:
            parts.append(_T(x + w / 2, cy + 24, str(p["label"]), "label", anchor="middle"))
    else:
        cap, _ = _caption(p, x, cy, w)
        parts += cap
    return parts


def h_heat(p):
    return 40 + (CAP if _has_cap(p) or p.get("x") else 0)


def g_heat(p, x, y, w, h):
    """熱度條：`cells[]`（0～1）逐格以不透明度表示，`x:[左標,右標]` 軸兩端的字。
    給 identity %、每個窗的覆蓋率這種「一串比例」用。"""
    cells = [max(0.0, min(1.0, float(v))) for v in (p.get("cells") or [])]
    if not cells:
        return []
    n = len(cells)
    gap = 2
    cw = max(3, (w - gap * (n - 1)) / n)
    parts = [_rect(x, y + 4, w, 28, "track", rx=3)]
    for i, v in enumerate(cells):
        parts.append(_rect(x + i * (cw + gap), y + 4, cw, 28, _mk(p.get("tone")), rx=1,
                           extra=f' fill-opacity="{0.08 + 0.92 * v:.2f}"'))
    cy = y + 40
    if p.get("x"):
        xs = list(p["x"])[:2]
        parts.append(_T(x, cy + 24, str(xs[0]), "label"))
        if len(xs) > 1:
            parts.append(_T(x + w, cy + 24, str(xs[1]), "label", anchor="end"))
    else:
        cap, _ = _caption(p, x, cy, w)
        parts += cap
    return parts


def h_venn(p):
    return 128 + (ROW if (p.get("la") or p.get("lb")) else 0)


def g_venn(p, x, y, w, h):
    """兩個集合：`a`、`b`、`both`（交集），`la`／`lb` 兩邊的名字。
    數字印在各自的區域裡，⛔ 圓的大小不表示數量（兩圓等大，只講「有沒有重疊」）。"""
    R = 60
    cx = x + w / 2
    cy = y + 64
    d = 44
    ca, cb = _mk(None, p.get("la") or "A"), _mk(None, p.get("lb") or "B")
    parts = [_circle(cx - d, cy, R, ca, ' fill-opacity="0.45"'),
             _circle(cx + d, cy, R, cb, ' fill-opacity="0.45"')]
    parts.append(_T(cx - d - 32, cy + 8, fmt(p.get("a", "")), "value inline", anchor="middle"))
    parts.append(_T(cx, cy + 8, fmt(p.get("both", "")), "value inline", anchor="middle"))
    parts.append(_T(cx + d + 32, cy + 8, fmt(p.get("b", "")), "value inline", anchor="middle"))
    if p.get("la") or p.get("lb"):          # 名字靠盒子兩緣，永遠不會互撞
        if p.get("la"):
            parts.append(_T(x, y + 128 + 24, str(p["la"]), "label"))
        if p.get("lb"):
            parts.append(_T(x + w, y + 128 + 24, str(p["lb"]), "label", anchor="end"))
    return parts


# ═════════════════════════════════════════════════════════════════════════
# 流程／判斷
# ═════════════════════════════════════════════════════════════════════════

def h_funnel(p):
    return ROW * len(p.get("stages") or [])


def g_funnel(p, x, y, w, h):
    """漏斗（小）：`stages[{n, label}]` 由多到少，每段一條**置中**的橫條，寬 ∝ n；
    名字在左、數字在右。要全頁的漏斗用 comp `funnel`，這個是給一個步驟框裡用的。"""
    st = p.get("stages") or []
    if not st:
        return []
    kw = _keycol([s.get("label", "") for s in st], w)
    vcol = 8 + max(_tw(fmt(s.get("n", ""))) * VAL_PX for s in st)
    bw = max(48, w - kw - vcol)
    vmax = max(float(s.get("n", 0)) for s in st) or 1
    parts, cy = [], y
    for s in st:
        L = max(6, float(s.get("n", 0)) / vmax * bw)
        parts.append(_T(x, cy + 24, str(s.get("label", "")), "label term"))
        parts.append(_rect(x + kw + (bw - L) / 2, cy + 6, L, 20, _mk(s.get("tone")), rx=3))
        parts.append(_T(x + kw + bw + 8, cy + 24, fmt(s.get("n", "")), "value inline"))
        cy += ROW
    return parts


def h_tree(p):
    return 112 + (CAP if _has_cap(p) else 0)


def g_tree(p, x, y, w, h):
    """合併樹：`leaves` 個葉（≤12）→ `mid` 個中間節點 → 一個根（`root` 是根的名字）。
    每一層右側印個數。給「由下往上合併」「多對一」用。"""
    L = max(2, min(int(p.get("leaves", 4)), 12))
    M = max(1, min(int(p.get("mid", max(1, L // 2))), L))
    vcol = 64
    aw = w - vcol
    lw = max(8, min(72, (aw - 8 * (L - 1)) / L))
    parts = []
    lx = [x + i * (lw + 8) for i in range(L)]
    for xi in lx:
        parts.append(_rect(xi, y, lw, 16, "mk-dim", rx=3))
    mw = max(16, min(120, (aw - 16 * (M - 1)) / M))
    mx = [x + i * (mw + 16) for i in range(M)]
    for xi in mx:
        parts.append(_rect(xi, y + 44, mw, 18, "mk-ctl", rx=3))
    for i, xi in enumerate(lx):
        j = min(M - 1, int(i * M / L))
        parts.append(_path(f"M{_n(xi + lw / 2)},{_n(y + 16)} V{_n(y + 30)} "
                           f"H{_n(mx[j] + mw / 2)} V{_n(y + 44)}", "link"))
    rw = min(aw, max(120, aw * 0.5))
    rx0 = x + (aw - rw) / 2
    for xi in mx:
        parts.append(_path(f"M{_n(xi + mw / 2)},{_n(y + 62)} V{_n(y + 76)} "
                           f"H{_n(rx0 + rw / 2)} V{_n(y + 88)}", "link"))
    parts.append(_rect(rx0, y + 88, rw, 24, _mk(p.get("tone")), rx=4))
    parts.append(_T(x + w, y + 16, fmt(L), "value inline", anchor="end"))
    parts.append(_T(x + w, y + 62, fmt(M), "value inline", anchor="end"))
    if p.get("root") is not None:
        parts.append(_T(rx0 + rw + 8, y + 106, str(p["root"]), "label"))
    cap, _ = _caption(p, x, y + 112, w)
    return parts + cap


def h_checklist(p):
    return ROW * len(p.get("items") or [])


def g_checklist(p, x, y, w, h):
    """取捨清單：`items[{t, ok}]`，✓ 留、✕ 捨（捨的畫刪除線）。
    給「哪些進來、哪些濾掉」用（tool_use／thinking 濾掉那種）。"""
    parts, cy = [], y
    for it in p.get("items") or []:
        if not isinstance(it, dict):
            it = {"t": str(it), "ok": True}
        ok = bool(it.get("ok", True))
        mx, my = x + 6, cy + 16
        if ok:
            parts.append(_path(f"M{_n(mx)},{_n(my)} l6,6 l12,-13", "ck-ok"))
        else:
            parts.append(_path(f"M{_n(mx)},{_n(my - 8)} l16,16 M{_n(mx + 16)},{_n(my - 8)} l-16,16",
                               "ck-no"))
        parts.append(_T(x + 36, cy + 24, str(it.get("t", "")), "label",
                        style="" if ok else "text-decoration:line-through"))
        cy += ROW
    return parts


def h_gate(p):
    return 64


def g_gate(p, x, y, w, h):
    """人工確認閘：紅色虛線框 ＋ 人形，`label` 寫關卡名。
    ⚠️ 這是結構標記（這裡有人要點頭），⛔ 不是強調 —— 所以是分類色紅，不是金。"""
    parts = [_rect(x, y + 4, w, 56, "gate", rx=8)]
    px, py = x + 24, y + 32
    parts.append(_circle(px, py - 8, 6, "mk-bad"))
    parts.append(_path(f"M{_n(px - 11)},{_n(py + 12)} a11,11 0 0 1 22,0 z", "mk-bad"))
    if p.get("label") is not None:
        parts.append(_T(x + 48, y + 40, str(p["label"]), "label term"))
    if p.get("value") is not None:
        parts.append(_T(x + w - 16, y + 40, fmt(p["value"]), "value inline", anchor="end"))
    return parts


def h_pills(p):
    if p.get("flow") == "col":
        return 40 * len(p.get("items") or []) + 8
    return 48


def g_pills(p, x, y, w, h):
    """小流程：`items[]` 一串藥丸，中間箭頭。給一個步驟框裡的「抓取 → 分類 → 草稿」用。
    `flow:"row"`（預設）橫排 —— 放不下時照樣畫，並登記到圖底的紅色警示帶（N94），
    正解是縮短名字或改 `flow:"col"`（直排、箭頭朝下，高 = 40 × 項數）。"""
    items = [str(t) for t in (p.get("items") or [])]
    if not items:
        return []
    r = _r()
    if p.get("flow") == "col":
        parts, cy = [], y + 4
        pw = _g8(max(_tw(t) * r.LABEL_PX for t in items) + 32)
        for i, t in enumerate(items):
            if i:
                parts.append(_path(f"M{_n(x + pw / 2)},{_n(cy - 8 + 2)} V{_n(cy - 2)}", "arrow"))
            parts.append(_rect(x, cy, pw, 32, "pill", rx=16))
            parts.append(_T(x + pw / 2, cy + 24, t, "label", anchor="middle"))
            cy += 40
        return parts
    gap = 56                                        # 桿 40 + 兩端 8：check_arrow_legible 要桿 ≥ 3× 頭（36）
    widths = [_g8(_tw(t) * r.LABEL_PX + 32) for t in items]
    need = sum(widths) + gap * (len(items) - 1)
    if need > w:
        r._OVERFLOW.append((" → ".join(items), int(need - w), int(w)))
    parts, cx = [], x
    for i, (t, pw) in enumerate(zip(items, widths)):
        if i:
            parts.append(_path(f"M{_n(cx - gap + 8)},{_n(y + 24)} H{_n(cx - 8)}", "arrow"))
        parts.append(_rect(cx, y + 8, pw, 32, "pill", rx=16))
        parts.append(_T(cx + pw / 2, y + 32, t, "label", anchor="middle"))
        cx += pw + gap
    return parts


# ═════════════════════════════════════════════════════════════════════════
# NGS（座標一律 bp；`total` 是這條軸的長度）
# ═════════════════════════════════════════════════════════════════════════

def h_feat(p):
    return 64 + (CAP if _has_cap(p) else 0)


def g_feat(p, x, y, w, h):
    """參考軸上的區段：`features[{s, e, label, tone}]`，座標 bp，軸長 `total`。
    區段畫在一條淡軌上；放得下的區段把名字寫在上面。給 signature 區域、基因、mask 窗用。"""
    total = float(p.get("total") or max([float(f.get("e", 0)) for f in (p.get("features") or [])] + [1]))
    sx = _sx(total, x, w)
    parts = [_rect(x, y + 28, w, 12, "track", rx=3)]
    for f in p.get("features") or []:
        x1, x2 = sx(f.get("s", 0)), sx(f.get("e", 0))
        parts.append(_rect(x1, y + 24, max(3, x2 - x1), 20, _mk(f.get("tone"), f.get("label")), rx=3))
        if f.get("label") is not None and (x2 - x1) >= _tw(str(f["label"])) * _r().LABEL_PX:
            parts.append(_T((x1 + x2) / 2, y + 16, str(f["label"]), "label", anchor="middle"))
    if p.get("axis", True):
        parts.append(_T(x, y + 64, "0", "label"))
        parts.append(_T(x + w, y + 64, fmt(int(total)), "label", anchor="end"))
    cap, _ = _caption(p, x, y + 64, w)
    return parts + cap


def _pack(intervals):
    """區間貪婪排列成不重疊的列。回每個區間的列號。"""
    rows_end, out = [], []
    for s, e in intervals:
        for j, end in enumerate(rows_end):
            if s > end + 0.5:
                rows_end[j] = e
                out.append(j)
                break
        else:
            rows_end.append(e)
            out.append(len(rows_end) - 1)
    return out


def _read_rows(p):
    reads = p.get("reads") or []
    iv = []
    for rd in reads:
        s, e = float(rd.get("s", 0)), float(rd.get("e", 0))
        if rd.get("mate"):
            e = max(e, float(rd["mate"][1]))
        iv.append((s, e))
    return _pack(iv) if iv else []


def h_reads(p):
    rows = _read_rows(p)
    n = (max(rows) + 1) if rows else 1
    return _g8(24 + 16 * n + 8) + (CAP if _has_cap(p) else 0)


def g_reads(p, x, y, w, h):
    """read 堆疊：`reads[{s, e, dir, mm[], mate[s,e]}]`，座標 bp，軸長 `total`。
    每條 read 是一支有方向的箭形；`mm` 是 mismatch 的位置（紅刻）；`mate` 是配對的另一端
    （同一列、細線相連）。列由程式排（貪婪不重疊）。"""
    reads = p.get("reads") or []
    total = float(p.get("total") or max([float(r.get("e", 0)) for r in reads] +
                                         [float(r["mate"][1]) for r in reads if r.get("mate")] + [1]))
    sx = _sx(total, x, w)
    rows = _read_rows(p)
    parts = [_rect(x, y + 4, w, 8, "track", rx=2)]
    for rd, row in zip(reads, rows):
        ry = y + 24 + row * 16
        cls = _mk(rd.get("tone"))
        for (s, e, d) in ([(rd.get("s", 0), rd.get("e", 0), rd.get("dir", "right"))] +
                          ([(rd["mate"][0], rd["mate"][1], "left" if rd.get("dir", "right") == "right" else "right")]
                           if rd.get("mate") else [])):
            x1, x2 = sx(s), sx(e)
            L = max(6, x2 - x1)
            tip = min(8, L / 3)
            if d == "left":
                pts = f"{_n(x1 + tip)},{_n(ry)} {_n(x1 + L)},{_n(ry)} {_n(x1 + L)},{_n(ry + 12)} {_n(x1 + tip)},{_n(ry + 12)} {_n(x1)},{_n(ry + 6)}"
            else:
                pts = f"{_n(x1)},{_n(ry)} {_n(x1 + L - tip)},{_n(ry)} {_n(x1 + L)},{_n(ry + 6)} {_n(x1 + L - tip)},{_n(ry + 12)} {_n(x1)},{_n(ry + 12)}"
            parts.append(f'<polygon class="{cls}" points="{pts}" fill-opacity="0.85"/>')
        if rd.get("mate"):
            parts.append(_path(f"M{_n(sx(rd.get('e', 0)))},{_n(ry + 6)} H{_n(sx(rd['mate'][0]))}", "link"))
        for m in rd.get("mm") or []:
            parts.append(_rect(sx(m) - 1.5, ry - 2, 3, 16, "mk-bad", rx=1))
    n = (max(rows) + 1) if rows else 1
    cap, _ = _caption(p, x, y + _g8(24 + 16 * n + 8), w)
    return parts + cap


def h_probes(p):
    return 96 + (CAP if _has_cap(p) else 0)


def g_probes(p, x, y, w, h):
    """探針鋪瓦：目標區 `total` bp 上每 `stride` bp 放一支長 `probe` bp 的探針
    （兩列交錯，像真的 tiling design）；`hits[]` 是會誤抓 off-target 的探針索引（紅），
    並以虛線落到下方那條「off-target」軌。`n` 可直接給探針數（沒給就由 total／stride 算）。"""
    total = float(p.get("total") or 1)
    probe = float(p.get("probe") or total / 10)
    stride = float(p.get("stride") or probe / 2)
    n = int(p.get("n") or max(1, math.floor((total - probe) / stride) + 1))
    hits = set(int(i) for i in (p.get("hits") or []))
    sx = _sx(total, x, w)
    parts = [_rect(x, y + 4, w, 10, _mk(p.get("tone", "good")), rx=2, extra=' fill-opacity="0.55"')]
    off_y = y + 76
    for i in range(n):
        s = i * stride
        x1, x2 = sx(s), sx(min(total, s + probe))
        ry = y + 24 + (i % 2) * 14
        bad = i in hits
        parts.append(_rect(x1, ry, max(3, x2 - x1 - 2), 10, "mk-bad" if bad else "mk", rx=2))
        if bad:
            mx = (x1 + x2) / 2
            parts.append(f'<path class="link" stroke-dasharray="3 3" d="M{_n(mx)},{_n(ry + 10)} V{_n(off_y)}"/>')
    parts.append(_rect(x, off_y, w, 12, "mk-bad", rx=3, extra=' fill-opacity="0.35"'))
    cap, _ = _caption(p, x, y + 96, w)
    return parts + cap


def h_kmers(p):
    return 40 + 16 * max(1, min(int(p.get("show", 3)), 6)) + 8 + (CAP if _has_cap(p) else 0)


def g_kmers(p, x, y, w, h):
    """k-mer 滑窗：一條長 `n` 格的序列（tile），底下 `show` 個長 `k` 格、各錯一格的窗。
    給「切成 21-mer」這種概念用；⛔ 不畫鹼基字母（那是 read_pileup 的事）。"""
    n = max(4, min(int(p.get("n", 16)), 40))
    k = max(2, min(int(p.get("k", 5)), n))
    show = max(1, min(int(p.get("show", 3)), 6))
    gap = 3
    tw = max(4, (w - gap * (n - 1)) / n)
    parts = []
    for i in range(n):
        parts.append(_rect(x + i * (tw + gap), y + 4, tw, 28, "mk-dim", rx=2))
    for j in range(show):
        wy = y + 40 + j * 16
        x1 = x + j * (tw + gap)
        parts.append(_rect(x1, wy, k * (tw + gap) - gap, 10, _mk(p.get("tone")), rx=2,
                           extra=f' fill-opacity="{0.45 + 0.5 * j / max(1, show - 1):.2f}"'))
    cap, _ = _caption(p, x, y + 40 + 16 * show + 8, w)
    return parts + cap


def h_lollipop(p):
    return 80 + (CAP if _has_cap(p) else 0)


def g_lollipop(p, x, y, w, h):
    """棒棒糖：`marks[{pos, tone, n}]` 在長 `total` 的軸上，一根桿一顆珠；`n` 給了就把
    數字寫在珠上方（value）。給變異位點、斷點、熱點用。"""
    total = float(p.get("total") or 1)
    sx = _sx(total, x, w)
    parts = [_rect(x, y + 64, w, 10, "track", rx=3)]
    for m in p.get("marks") or []:
        mx = sx(m.get("pos", 0))
        parts.append(_path(f"M{_n(mx)},{_n(y + 64)} V{_n(y + 40)}", "link"))
        parts.append(_circle(mx, y + 34, 8, _mk(m.get("tone"))))
        if m.get("n") is not None:
            parts.append(_T(mx, y + 20, fmt(m["n"]), "value inline", anchor="middle"))
    cap, _ = _caption(p, x, y + 80, w)
    return parts + cap


def h_coverage(p):
    return 80 + (CAP if _has_cap(p) else 0)


def g_coverage(p, x, y, w, h):
    """覆蓋深度：`values[]` 沿軸等距取樣（面積圖），`thr` 一條虛線門檻，值印在右端。
    `max` 沒給就取最大值。給 depth、GC、identity 這種沿座標變化的量。"""
    vals = [float(v) for v in (p.get("values") or [])]
    if len(vals) < 2:
        return []
    vmax = float(p.get("max") or max(vals + [float(p.get("thr") or 0)]) or 1)
    ah = 64
    n = len(vals)
    pts = [(x + i * w / (n - 1), y + 4 + ah - (v / vmax) * ah) for i, v in enumerate(vals)]
    poly = " ".join(f"{_n(px)},{_n(py)}" for px, py in pts)
    parts = [f'<polygon class="{_mk(p.get("tone"))}" fill-opacity="0.3" '
             f'points="{_n(x)},{_n(y + 4 + ah)} {poly} {_n(x + w)},{_n(y + 4 + ah)}"/>',
             f'<polyline class="link" points="{poly}"/>',
             _path(f"M{_n(x)},{_n(y + 4 + ah)} H{_n(x + w)}", "rule")]
    if p.get("thr") is not None:
        ty = y + 4 + ah - (float(p["thr"]) / vmax) * ah
        parts.append(_path(f"M{_n(x)},{_n(ty)} H{_n(x + w)}", "thr"))
        tv = fmt(p["thr"])
        pw = _tw(tv) * VAL_PX + 16
        parts.append(_rect(x + w - pw, ty - 26, pw, 26, "pill", rx=6))
        parts.append(_T(x + w - 8, ty - 6, tv, "value inline", anchor="end"))
    cap, _ = _caption(p, x, y + 80, w)
    return parts + cap


def h_align(p):
    return 24 * len(p.get("rows") or []) + 8


def g_align(p, x, y, w, h):
    """多序列對齊（示意）：`rows[{name, cells}]`，cells 是一串字元 —— `M` 相同、`X` 錯配、
    `-` 缺口、`N` 未知。⛔ 不畫鹼基字母（那需要自訂字級；要字母用 read_pileup）。"""
    rows = p.get("rows") or []
    if not rows:
        return []
    kw = _keycol([rw.get("name", "") for rw in rows], w, mono=True, frac=0.24)
    n = max(len(str(rw.get("cells", ""))) for rw in rows) or 1
    gap = 2
    cw = max(3, min(24, (w - kw - gap * (n - 1)) / n))
    parts, cy = [], y
    for rw in rows:
        parts.append(_T(x, cy + 18, str(rw.get("name", "")), "label term", mono=True))
        for i, ch in enumerate(str(rw.get("cells", ""))):
            cx = x + kw + i * (cw + gap)
            if ch == "-":
                parts.append(_path(f"M{_n(cx)},{_n(cy + 10)} H{_n(cx + cw)}", "rule"))
                continue
            cls = {"M": "mk-ctl", "X": "mk-bad", "N": "mk-dim", "I": "mk-good"}.get(ch.upper(), "mk")
            parts.append(_rect(cx, cy + 2, cw, 18, cls, rx=2))
        cy += 24
    return parts


# ═════════════════════════════════════════════════════════════════════════
# 目錄與入口
# ═════════════════════════════════════════════════════════════════════════

GLYPHS = {
    "dots": (h_dots, g_dots), "tiles": (h_tiles, g_tiles), "segbar": (h_segbar, g_segbar),
    "bars": (h_bars, g_bars), "hero": (h_hero, g_hero), "hist": (h_hist, g_hist),
    "heat": (h_heat, g_heat), "venn": (h_venn, g_venn),
    "funnel": (h_funnel, g_funnel), "tree": (h_tree, g_tree),
    "checklist": (h_checklist, g_checklist), "gate": (h_gate, g_gate), "pills": (h_pills, g_pills),
    "feat": (h_feat, g_feat), "reads": (h_reads, g_reads), "probes": (h_probes, g_probes),
    "kmers": (h_kmers, g_kmers), "lollipop": (h_lollipop, g_lollipop),
    "coverage": (h_coverage, g_coverage), "align": (h_align, g_align),
}
GENOMIC = {"feat", "reads", "probes", "lollipop", "coverage", "heat"}   # 吃 `total`（bp）的那幾個


def height(p):
    """一個 glyph 佔的高（不含 head）。⛔ 只看參數，不看寬 —— 見檔頭契約。"""
    name = p.get("glyph")
    if name not in GLYPHS:
        sys.exit(f"[figure] 不認得的 glyph「{name}」。可用：{'、'.join(GLYPHS)}"
                 f"（references/glyphs.md）")
    h = GLYPHS[name][0](p)
    if p.get("h"):
        h = max(H_MIN, min(H_MAX, _g8(p["h"])))
    return _g8(h)


def draw(p, x, y, w):
    """把 glyph 畫在 (x, y) 起、寬 w 的區域裡。回 parts。"""
    name = p.get("glyph")
    h = height(p)
    return GLYPHS[name][1](p, x, y, w, h)


def min_width(p):
    """粗估的最小寬（給 `_blocks_w` 用）。"""
    base = 200
    lab = _tw(str(p.get("label", ""))) * 10.5 if p.get("label") is not None else 0
    val = _tw(fmt(p.get("value", ""))) * VAL_PX if p.get("value") is not None else 0
    return max(base, lab + val + 24)
