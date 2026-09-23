#!/usr/bin/env python3
"""deck.json -> deck.<lang>.html（1600x900 投影片 ＋ 內嵌播放器）。

產出的 deck.en.html / deck.zh.html **就是交付物**：一次一頁、自動縮放貼合視窗、鍵盤翻頁，
可以直接用 file:// 打開上台講（pptx 是選用的）。播放器是 assets/deck.js，
與 CSS 同樣**內嵌**進 HTML —— 單檔可攜、零外部依賴。
快捷鍵與 raw 模式（shoot.py 量測時停用播放器）見 references/delivery.md「怎麼播」。

deck.json 是事實來源，HTML 是產物：想改內容改 JSON 再重跑，
想改樣式改 assets/deck.css（一次改全部頁）。**不要手改 HTML**，會被覆蓋。

用法：
  render_deck.py <deck.json>              # 產出同目錄的 deck.en.html（英文）
  render_deck.py <deck.json> --lang zh    # 產出同目錄的 deck.zh.html（中文）
  render_deck.py <deck.json> -o out.html

欄位定義見 references/deck_schema.md，版型與容量上限見 references/slide_types.md
"""
import argparse, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(HERE, "..", "assets", "deck.css")
JS  = os.path.join(HERE, "..", "assets", "deck.js")   # 播放器（raw 模式下完全不啟動）
BASE = [os.getcwd()]      # deck.json 所在目錄，圖檔路徑以此為基準
THREAD_INDEX = {}         # {thread_id: (編號, 主題標題)}，用來在每頁標主題編號
TR = {}                   # 語言對照表：{英文原句: 譯文}。空的代表輸出英文原文
MISSING = set()           # 沒有譯文的句子，收集起來一次回報


# ---------- 語言對照 ----------
def tr(s):
    """把英文原句換成譯文。查不到就原樣輸出並記下來（不中斷，缺譯不該擋住預覽）。

    ⚠️ 只換字串，**不複製結構**：表格、SVG 幾何、頁面順序全部共用一份 deck.json。
       產兩份 deck.json 會讓兩版的數字慢慢分岔，而數字是最不能錯的東西。
    """
    if not TR:
        return s
    k = str(s or "").strip()
    if not k:
        return s
    if k in TR:
        v = TR[k]
        # "=" 代表刻意不翻（樣本名、工具名、純數字）；"" 代表還沒翻，一律落回原文
        return s if v in ("", "=") else v
    MISSING.add(k)
    return s


# ---------- 複合字串與它的片段（N32）----------
# 圖裡常常同一個東西出現兩次：漏斗左欄寫 `18 external tools · 8`（帶分數），
# 結果框只寫 `18 external tools`，門檻框只寫 `8`。三個都是獨立的 SVG 文字節點，
# 所以 --dump-strings 收到的是**三筆各自獨立的條目**，翻譯時要人**手動**維持一致
# （`18 個外部工具 · 8` 必須包含 `18 個外部工具`）——漏了不會有人發現。
#
# ⛔ 不合併成一筆：strings.<lang>.json 的格式是 {英文原句: 譯文}，
#    查表的鍵就是頁面上那一個文字節點的原文；把三筆併成一筆就查不到了，
#    而且下游有人在讀這個格式。
# ✅ 改成**把關係說出來 ＋ 自動查一致性**：dump 時列出這些「家族」讓翻譯的人看見，
#    渲染時（--lang）逐家族檢查「整句的譯文有沒有包含片段的譯文」，不一致就出聲。
_SEG = re.compile(r"\s*[·|;]\s*")


def families(keys):
    """回傳 [(複合字串, [出現在 keys 裡的片段, ...]), ...]。

    片段的認定**只認分隔符切出來的完整段**（`·`、`|`、`;`），
    ⛔ 不做任意子字串比對 —— 那樣 `1` 會是幾十句話的「片段」，全是雜訊。
    """
    ks = {k for k in keys if k}
    out = []
    for whole in sorted(ks):
        segs = [x.strip() for x in _SEG.split(whole)]
        if len(segs) < 2:
            continue
        # ⚠️ 第一段若是單字元（`1 · 標題有動作提示`）那是**清單編號**，
        #    不是「同一個東西在圖上出現兩次」——濾掉，否則家族清單全是它。
        mem = [x for i, x in enumerate(segs)
               if x and x != whole and x in ks and not (i == 0 and len(x) < 2)]
        if mem:
            out.append((whole, mem))
    return out


def _out_text(k):
    """這個原句最後會印在頁面上的樣子（沒譯文／標 `=` 就是原文）。"""
    v = TR.get(k)
    return k if v in (None, "", "=") else v


def check_families(keys, lang):
    """片段的譯文必須出現在複合字串的譯文裡，否則同一個東西在同一張圖上會有兩種講法。"""
    bad = []
    for whole, mem in families(keys):
        for part in mem:
            if _out_text(part) not in _out_text(whole):
                bad.append((whole, part))
    if bad:
        print(f"[render] ⚠️ {len(bad)} 組複合字串與它的片段在 {lang} 版不一致"
              f"（同一個東西在同一張圖上會出現兩種講法）：", file=sys.stderr)
        for whole, part in bad:
            print(f"    片段 {part!r} → {_out_text(part)!r}\n"
                  f"    卻不在 {whole!r} → {_out_text(whole)!r} 裡面", file=sys.stderr)
    return bad


# ---------- 目前渲染到哪一頁（只為了讓錯誤訊息說得出是哪一頁）----------
CUR = {"idx": "?", "id": "?", "type": "?"}


def die(msg):
    """帶頁面座標的致命錯誤。

    ⚠️ **這支腳本的錯誤訊息必須指得出頁與欄位。** 沒有這一層的時候，
    一張 `thread-intro` 少了 `body` 只會噴
    `AttributeError: 'NoneType' object has no attribute 'replace'`，
    要人自己照著 traceback 的行號回頭讀原始碼才知道是哪一頁少了什麼 ——
    那不是錯誤訊息，那是叫人自己去查。
    """
    c = CUR
    sys.exit(f"[render] 第 {c['idx']} 頁（id={c['id']}、type={c['type']}）：{msg}")


def need(b, *fields, opt=()):
    """結構頁的必填欄位；缺了就當場指名頁與欄位。

    ⛔ 不要「缺了就當空字串渲染下去」—— 版型少了 title 產出的是一張空白頁，
    而空白頁在 30 頁的 deck 裡沒有人會發現。
    """
    shape = "{" + ", ".join(list(fields) + [f"{o}?" for o in opt]) + "}"
    if not isinstance(b, dict):
        die(f"body 必須是物件 {shape}，實際拿到 {type(b).__name__}。"
            f"請補上 deck.json 這一頁的 body。")
    missing = [f for f in fields if b.get(f) in (None, "")]
    if missing:
        die(f"body 缺少必填欄位 {'、'.join(repr(f) for f in missing)}；"
            f"type={CUR['type']} 的 body 形狀是 {shape}（`?` 是選填）。"
            f"（欄位定義見 references/slide_types.md）")
    return b


def missing_block(field, hint):
    """缺了必要的圖來源時，**在版面上渲出一塊顯眼的紅色缺頁**（後補，FINDINGS N95）。

    ⚠️ `diagram` 是文件反覆宣告的第一選擇版型，卻是唯一 `src`／`svg` 兩缺時不報錯的：
    `b_diagram()` 走 `else: inner = ""` 產出空的 `<figure>`、`b_figure()` 輸出
    `src="None"`。連 `shoot.py` 的密度都救不了它 —— 墨水為 0 → `rs.length` 為 0
    → **連檢查都不跑** → 完全靜默。

    ⛔ 裁決（2026-09-05，「先寬」）：**不 `sys.exit`**。半成品 deck 是正常的中間狀態
    （builder 還在畫 B 線時協調者要看 A 線），整份渲染不出來會讓人退回去用眼睛找。
    改成渲一塊紅色缺頁 ＋ stderr 一行 —— **看得見、翻頁就會發現**，這正是 need()
    的 docstring 說「空白頁在 30 頁的 deck 裡沒有人會發現」要防的那件事。
    ⚠️ 反方向（N56）：紅色缺頁不擋，所以它可能被**帶著交付**。擋它的是
    `check_deck.py` 的 check_skipped()（缺 body.src 會出聲）與 `shoot.py` 的密度門檻
    —— 缺頁塊本身墨水很少，密度過不了 65%，`shoot.py` 會擋下截圖。
    """
    c = CUR
    sys.stderr.write(f"[render] ⚠️ 第 {c['idx']} 頁（id={c['id']}、type={c['type']}）"
                     f"缺 {field} —— 已渲成缺頁塊，不是空白頁\n")
    return ('<div class="missing"><div class="missing-h">⛔ 缺圖</div>'
            f'<div class="missing-b">第 {esc(c["idx"])} 頁 <code>{esc(c["id"])}</code>'
            f'（type={esc(c["type"])}）缺 <code>{esc(field)}</code></div>'
            f'<div class="missing-b">{esc(hint)}</div></div>')


# ---------- 行內格式（與 daily-log/render.py 同一套語法）----------
def inl(s):
    # None 不當場炸 —— 選填欄位缺席是正常的；**必填**欄位由 need() 擋，
    # 那裡才說得出是哪一頁哪一欄。這裡炸只會炸出一個看不懂的 traceback。
    s = html.escape(tr("" if s is None else s), quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def esc(s):
    return html.escape(str(s or ""), quote=True)


# ---------- 各版型的主體 ----------
def b_cover(b):
    need(b, "title", opt=("kicker", "range"))
    return (f'<div class="kicker">{inl(b.get("kicker"))}</div>'
            f'<h1>{inl(b.get("title"))}</h1>'
            f'<div class="range">{inl(b.get("range"))}</div>')


def b_agenda(b):
    li = "".join(
        f'<li><span class="n">{inl(x.get("n", ""))}</span>'
        f'<span class="t">{inl(x.get("t"))}'
        + (f'<span class="d">{inl(x["d"])}</span>' if x.get("d") else "")
        + "</span></li>"
        for x in b.get("items", []))
    return f'<ul class="agenda">{li}</ul>'


def b_thread_intro(b):
    # 形狀 {label, title, sub}：label 與 title 必填，sub 選填。
    # ⚠️ 這個形狀以前**只寫在這一行程式碼裡**（schema 與 slide_types.md 都沒寫），
    # 於是一張沒有 body 的 thread-intro 過得了 check_deck，卻在這裡崩。
    need(b, "label", "title", opt=("sub",))
    return (f'<div class="big">{inl(b.get("label"))}</div>'
            f'<h1>{inl(b.get("title"))}</h1>'
            + (f'<div class="sub">{inl(b["sub"])}</div>' if b.get("sub") else ""))


def _cell(c):
    """儲存格：字串照舊；dict 則是「數值 + 比例 bar」。

    {"v": "53/66", "pct": 80, "tone": "bad"} → 上面一行 53/66，下面一條寬度 80% 的紅條。

    ⚠️ **一定要搭配 colw（固定欄寬）**，否則欄寬會隨內容撐開，
    同一個 80% 在窄欄與寬欄畫出來的像素長度不同，肉眼比不出高低。
    check_deck.py 會擋「有 bar 卻沒有 colw」。
    """
    if not isinstance(c, dict):
        return inl(c)
    out = f'<div class="cellv">{inl(c.get("v", ""))}</div>'
    if c.get("pct") is not None:
        tone = f' {c["tone"]}' if c.get("tone") in ("good", "bad") else ""
        pct = max(0.0, min(100.0, float(c["pct"])))
        out += (f'<div class="bar-track"><div class="bar-fill{tone}" '
                f'style="width:{pct:g}%"></div></div>')
    return out


def _one_table(t):
    align = t.get("align") or []
    colw = t.get("colw") or []
    def cls(i):
        return ' class="num"' if i < len(align) and align[i] == "num" else ""
    head = "".join(f"<th{cls(i)}>{inl(c)}</th>" for i, c in enumerate(t.get("columns", [])))
    rowcls = t.get("rowclass") or []
    def rc(i):
        return f' class="{rowcls[i]}"' if i < len(rowcls) and rowcls[i] in ("drop", "hl") else ""
    body = "".join(
        f"<tr{rc(ri)}>" + "".join(f"<td{cls(i)}>{_cell(c)}</td>" for i, c in enumerate(r)) + "</tr>"
        for ri, r in enumerate(t.get("rows", [])))
    cap = f"<caption>{inl(t['caption'])}</caption>" if t.get("caption") else ""
    cg = ("<colgroup>" + "".join(f'<col style="width:{esc(w)}">' for w in colw) + "</colgroup>"
          if colw else "")
    tcls = ' class="fixed"' if colw else ""
    return (f"<table{tcls}>{cap}{cg}<thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table>")


def b_table(b):
    ts = b.get("tables") or ([b] if b.get("columns") else [])
    return "".join(_one_table(t) for t in ts)


def b_stats(b):
    return '<div class="stats">' + "".join(
        f'<div class="stat{" hl" if x.get("hl") else ""}">'
        f'<div class="v">{inl(x.get("v"))}</div><div class="k">{inl(x.get("k"))}</div></div>'
        for x in b.get("items", [])) + "</div>"


def _col(c):
    tone = f' {c["tone"]}' if c.get("tone") in ("good", "bad") else ""
    inner = f'<h3>{inl(c.get("h"))}</h3>' if c.get("h") else ""
    if c.get("items"):
        inner += "<ul>" + "".join(f"<li>{inl(x)}</li>" for x in c["items"]) + "</ul>"
    if c.get("text"):
        inner += f"<p>{inl(c['text'])}</p>"
    if c.get("table"):
        inner += _one_table(c["table"])
    return f'<div class="col{tone}">{inner}</div>'


def b_cols(b):
    return '<div class="cols">' + _col(b.get("left", {})) + _col(b.get("right", {})) + "</div>"


def b_flow(b):
    return '<div class="flow">' + "".join(
        f'<div class="step"><div class="n">{inl(s.get("n", ""))}</div>'
        f'<div class="t">{inl(s.get("t"))}</div>'
        + (f'<div class="d">{inl(s["d"])}</div>' if s.get("d") else "")
        + "</div>" for s in b.get("steps", [])) + "</div>"


def _pipe_node(nd):
    tone = f' {nd["tone"]}' if nd.get("tone") in ("good", "bad", "hl") else ""
    h = f'<span class="n">{inl(nd["n"])}</span>' if nd.get("n") else ""
    h += f"<span>{inl(nd.get('t'))}</span>"
    out = f'<div class="h">{h}</div>'
    if nd.get("d"):
        out += f'<div class="d">{inl(nd["d"])}</div>'
    if nd.get("v"):
        out += f'<div class="v">{inl(nd["v"])}</div>'
    if nd.get("items"):
        out += "<ul>" + "".join(f"<li>{inl(x)}</li>" for x in nd["items"]) + "</ul>"
    if nd.get("codes"):
        out += '<div class="codes">' + "".join(
            '<span class="code%s">%s</span>' % (
                (" " + c["tone"]) if isinstance(c, dict) and c.get("tone") in ("good", "bad") else "",
                inl(c.get("t") if isinstance(c, dict) else c))
            for c in nd["codes"]) + "</div>"
    if nd.get("chip"):
        out += f'<div class="chip">{inl(nd["chip"])}</div>'
    return f'<div class="node{tone}">{out}</div>'


def b_pipeline(b):
    """單向流程：lane（可多條）→ node → arrow，純 CSS flex，不用管座標。

    路由表第一格的實作（見 references/composition-vocabulary.md）。
    ⛔ **只走單一方向**：要分支、要回圈、要精準控位就不要用這個版型，改手刻 SVG。
    箭頭畫在每個「非第一個」節點之前；`node.arrow` 是**流進這個節點的東西**的名字。
    """
    lanes = []
    for ln in b.get("lanes", []):
        tone = f' {ln["tone"]}' if ln.get("tone") in ("good", "bad", "hl") else ""
        head = ""
        if ln.get("label"):
            note = f'<span class="note">{inl(ln["note"])}</span>' if ln.get("note") else ""
            head = f'<div class="lane-h">{inl(ln["label"])}{note}</div>'
        cells = []
        for i, nd in enumerate(ln.get("nodes", [])):
            if i:
                lbl = f'<div class="lbl">{inl(nd["arrow"])}</div>' if nd.get("arrow") else ""
                cells.append(f'<div class="arr"><div class="bar"></div>{lbl}</div>')
            cells.append(_pipe_node(nd))
        lanes.append(f'<div class="lane{tone}">{head}'
                     f'<div class="lane-nodes">{"".join(cells)}</div></div>')
    return '<div class="pipeline">' + "".join(lanes) + "</div>"


def b_points(b):
    return '<ul class="points">' + "".join(f"<li>{inl(x)}</li>" for x in b.get("items", [])) + "</ul>"


def b_issues(b):
    return '<div class="issues">' + "".join(
        f'<div class="issue"><div class="t">{inl(x.get("t"))}</div>'
        + (f'<div class="d">{inl(x["d"])}</div>' if x.get("d") else "")
        + (f'<div class="r">→ {inl(x["r"])}</div>' if x.get("r") else "")
        + "</div>" for x in b.get("items", [])) + "</div>"


def b_diagram(b):
    """第一選擇的版型。svg = 內嵌字串；src = 外部 .svg／圖檔路徑（相對 deck.json）。

    .svg 一律**內嵌**進 HTML，不用 <img src>：用 <img> 載入的 SVG 是獨立文件，
    deck.css 的 .box/.bar/.t-* 完全不會套用，圖形會全部退成預設黑色
    （上一版實跑踩過一次）。內嵌才吃得到主題。
    """
    src = b.get("src") or ""
    if b.get("svg"):
        inner = b["svg"]
    elif src.lower().endswith(".svg"):
        fp = os.path.join(BASE[0], src)
        if not os.path.isfile(fp):
            sys.exit(f"[render] \u627e\u4e0d\u5230\u5716\u6a94\uff1a{fp}")
        inner = re.sub(r"<\?xml[^>]*\?>", "", open(fp, encoding="utf-8").read()).strip()
        if TR:   # 只換文字內容，不動座標與屬性；CSS（含 { }）一律跳過
            inner = re.sub(
                r">([^<>]+)<",
                lambda m: ">" + (m.group(1) if re.search(r"[{}]", m.group(1))
                                 else html.escape(tr(m.group(1)), quote=False)) + "<",
                inner)
    elif src:
        inner = f'<img src="{esc(src)}" alt="">'
    else:
        # ⛔ 不要「缺了就當空字串渲染下去」（need() 的 docstring 逐字寫著）——
        #    這裡以前正是那樣：`inner = ""` → 一個空的 <figure>，沒有人會發現。
        inner = missing_block(
            "body.src / body.svg",
            "diagram 版型的主體是圖：填 body.src（相對 deck.json 的 .svg 路徑）"
            "或 body.svg（內嵌字串）。圖還沒畫好就先讓這一頁留著紅色缺頁塊。")
    cap = f'<figcaption>{inl(b["caption"])}</figcaption>' if b.get("caption") else ""
    return f'<figure class="diagram">{inner}{cap}</figure>'


def b_example(b):
    """例子優先的機制頁：主圖**全寬單欄**跑一次真實／明示為示意的案例。

    ⚠️ 改（使用者原話）：「『規則』(黃色背景)那格根本不需要，呈現上只需要左邊
    ('藍色背景')的那一塊內容，放大佔據整個版面就可以了。」
    → 右欄（`body.aside`）取消，主圖佔滿整個 body。
    ⛔ 規則與邊界**沒有消失**，它們改成必須畫進主圖的 SVG 裡
    （`depth: mechanism` 明訂「這頁必須看得到一條具體規則」）。
    例子的來源與 before/operation/after 仍留在 slide.example（規劃契約，不印在頁上）。
    """
    if b.get("aside"):
        die("body.aside 已作廢 —— example 版型改成主圖全寬單欄，右欄不再渲染。\n"
            "        ⛔ 不要只把 aside 刪掉：`aside.rule` 與 `aside.boundary` 的內容"
            "必須**畫進主圖的 SVG 裡**（depth=mechanism 要求這頁看得見一條具體規則），"
            "然後才把 body.aside 從 deck.json 的這一頁移除。\n"
            f"        目前這一頁的 aside 內容："
            f"{ {k: v for k, v in (b['aside'] or {}).items()} }")
    if not (b.get("svg") or b.get("src")):
        need(b, "src", opt=("svg", "caption"))     # 由 need() 指名頁與欄位
    src = b.get("src") or ""
    if b.get("svg"):
        inner = b["svg"]
    elif src.lower().endswith(".svg"):
        fp = os.path.join(BASE[0], src)
        if not os.path.isfile(fp):
            sys.exit(f"[render] 找不到圖檔：{fp}")
        inner = re.sub(r"<\?xml[^>]*\?>", "", open(fp, encoding="utf-8").read()).strip()
        if TR:
            inner = re.sub(r">([^<>]+)<",
                           lambda m: ">" + (m.group(1) if re.search(r"[{}]", m.group(1))
                                              else html.escape(tr(m.group(1)), quote=False)) + "<",
                           inner)
    else:
        inner = f'<img src="{esc(src)}" alt="">'
    cap = f'<figcaption>{inl(b["caption"])}</figcaption>' if b.get("caption") else ""
    return (f'<div class="case-layout">'
            f'<figure class="case-main">{inner}{cap}</figure></div>')


def b_figure(b):
    cap = f'<figcaption>{inl(b["caption"])}</figcaption>' if b.get("caption") else ""
    # ⚠️ 後補（N95）：`src` 缺席時這裡以前輸出 `<img src="None">` —— 瀏覽器畫一個
    #    破圖圖示，看起來像「圖檔壞了」，而真正的原因是 deck.json 根本沒填。
    if not b.get("src"):
        return (f'<figure class="figure">'
                + missing_block("body.src", "figure 版型要有 body.src（圖檔路徑）；"
                                            "是圖解就改用 type=diagram")
                + f'{cap}</figure>')
    return f'<figure class="figure"><img src="{esc(b.get("src"))}" alt="">{cap}</figure>'


BUILDERS = {
    "cover": b_cover, "agenda": b_agenda, "thread-intro": b_thread_intro,
    "diagram": b_diagram, "table": b_table, "stats": b_stats, "cols": b_cols,
    "flow": b_flow, "points": b_points, "issues": b_issues, "figure": b_figure,
    "pipeline": b_pipeline, "example": b_example,
}
DARK_BY_DEFAULT = {"cover", "thread-intro"}


def render_slide(s, idx, total):
    st = s.get("type", "points")
    CUR.update(idx=idx, id=s.get("id", f"S{idx}"), type=st)
    if st not in BUILDERS:
        die(f"未知版型 {st!r}（可用：{', '.join(sorted(BUILDERS))}）")

    cls = ["slide", f"t-{st}"]   # 前綴隔離：內層元件也叫 .cols/.stats，不加前綴會覆蓋 .slide 的 display
    tone = s.get("tone")                       # dark / soft，未指定時依版型預設
    if tone in ("dark", "soft"):
        cls.append(tone)
    elif st in DARK_BY_DEFAULT:
        cls.append("dark")

    parts = []
    # 主題編號：多線時聽眾需要知道現在講到第幾個主題，否則會以為還在上一個
    # 沒有編號時，聽眾會以為還在講第 1 條，其實已經換到第 2 條了
    ti = THREAD_INDEX.get(s.get("thread"))
    if ti and st not in ("cover", "agenda", "thread-intro"):
        parts.append(f'<div class="topic"><b>{ti[0]}</b>{inl(ti[1])}</div>')
    if s.get("title") and st not in ("cover", "thread-intro"):
        parts.append(f"<h2>{inl(s['title'])}</h2>")
    if s.get("sub") and st not in ("thread-intro",):
        parts.append(f'<div class="sub">{inl(s["sub"])}</div>')

    body = s.get("body")
    if body is None:
        body = {}
    try:
        inner = BUILDERS[st](body)
    except SystemExit:
        raise
    except Exception as ex:
        # 兜底：任何沒被 need() 攔下的例外都要帶上頁座標再丟出去。
        # ⛔ 不要讓原始 traceback 直接見人 —— 它指的是版型函式的行號，不是那一頁。
        die(f"渲染失敗：{type(ex).__name__}: {ex}\n"
            f"        多半是 body 的欄位缺了或型別不對（body 的鍵："
            f"{sorted(body) if isinstance(body, dict) else type(body).__name__}）。")
    parts.append(f'<div class="body">{inner}</div>')

    # N67：`takeaway`（底部結論條）**已真的停用** —— 這裡不再渲染它。
    # 六處文件宣告停用、`check_takeaway()` 也擋，但渲染／CSS／高度預算原本都還在，
    # 於是「停用」只是散文。⛔ 不要加回來：結論不上投影片，寫進 `notes` 的「【口頭結論】」。

    # 講者備忘：以 attribute 帶進來，⛔ **不進 DOM**。
    # 兩個理由：① 它是講者看的，不是投影片內容，預設絕不能顯示、也不能被 shoot.py 截進圖裡；
    #          ② shoot.py 的版面自檢會掃 div/td/li/p 的高度與字級，多一個隱藏節點就會多一組
    #             假的量測值（「容器過空」之類）。attribute 對版面與量測都是零影響。
    # notes 不進 tr()：它本來就允許寫中文，不是投影片上的字串。
    nt = f' data-notes="{esc(s.get("notes"))}"' if s.get("notes") else ""
    # backup 旗標要進 DOM：shoot.py 的「容器過空」是**會擋的**檢查，而 backup 頁
    # 本來就該疏（它是備問頁，不是主線）。沒有這個 attribute，shoot.py 在 HTML 上
    # 分不出主線頁與 backup 頁，只能整條放寬 —— 那就等於這條檢查又變成不擋的建議。
    bk = ' data-backup="1"' if s.get("backup") else ""
    return (f'<section class="{" ".join(cls)}" id="{esc(s.get("id", f"S{idx}"))}" '
            f'data-slide="{idx}"{nt}{bk}>' + "".join(parts) + "</section>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("-o", "--out")
    ap.add_argument("--dump-strings", metavar="LANG",
                    help="產生 strings.<LANG>.json 骨架（收集所有待翻字串，值留空），"
                         "填完再用 --lang <LANG> 渲染")
    ap.add_argument("--lang", default="en",
                    help="en（預設，直接用 deck.json 的原文）或其他語言碼，"
                         "會讀同目錄的 strings.<lang>.json 做字串替換")
    ap.add_argument("--thread", metavar="ID",
                    help="--dump-strings 時只收**這條線**的頁的字串（給 builder 交逐線譯文片段用）")
    ap.add_argument("--strings-out", metavar="PATH",
                    help="--dump-strings 的輸出檔（預設 deck.json 旁的 strings.<LANG>.json）。"
                         "⭐ builder 用它寫 _work/4_slides/strings.<線>.zh.json，⛔ 不動交付物")
    a = ap.parse_args()

    BASE[0] = os.path.dirname(os.path.abspath(a.deck))
    if a.lang != "en":
        sp = os.path.join(BASE[0], f"strings.{a.lang}.json")
        if not os.path.isfile(sp):
            sys.exit(f"[render] 找不到語言對照表：{sp}")
        TR.update(json.load(open(sp, encoding="utf-8")))
    if TR:
        check_families(TR, a.lang)
    deck = json.load(open(a.deck, encoding="utf-8"))
    slides = deck.get("slides", [])
    if not slides:
        sys.exit("[render] deck.json 沒有任何 slides")
    for i, t in enumerate(deck.get("threads", []), 1):
        THREAD_INDEX[t["id"]] = (str(i), t.get("title", ""))

    if a.dump_strings:
        TR["__collect__"] = ""          # 讓 tr() 進入收集模式
        for i, sl in enumerate(slides, 1):
            if a.thread and sl.get("thread") != a.thread:
                continue                # 逐線片段：別條線的字串不是這個 builder 的
            render_slide(sl, i, len(slides))
        if not a.thread:
            tr(deck.get("meta", {}).get("title", ""))
        MISSING.discard("__collect__")
        sp = a.strings_out or os.path.join(BASE[0], f"strings.{a.dump_strings}.json")
        old = json.load(open(sp, encoding="utf-8")) if os.path.isfile(sp) else {}
        if a.thread and not a.strings_out:
            sys.exit("[render] --thread 要搭配 --strings-out（逐線片段不能蓋掉全場的 strings.zh.json）")
        out = {k: old.get(k, "") for k in sorted(MISSING)}
        json.dump(out, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        n = sum(1 for v in out.values() if not v)
        print(f"[render] {len(out)} 句 → {sp}（其中 {n} 句待翻）")
        fams = families(out)
        if fams:
            print(f"[render] ⚠️ 其中 {len(fams)} 句是**複合字串**，它的片段也各自獨立成一筆 ——"
                  f"翻譯時三者要一致（渲染時會檢查）：")
            for whole, mem in fams:
                print(f"    {whole!r}\n        ⊃ " + "、".join(repr(x) for x in mem))
        return

    # ⭐ 檔名一律帶語言碼（後改）：英文版是 `deck.en.html`，不是 `deck.html`。
    # 兩版是平等的交付物、會同時流通，**檔名就要看得出手上這份是哪一版** ——
    # 舊的 `deck.html` 只有打開來才知道是英文的。
    out = a.out or os.path.join(BASE[0], f"deck.{a.lang}.html")
    css = open(CSS, encoding="utf-8").read()
    js = open(JS, encoding="utf-8").read()   # 內嵌，不用 <script src>：deck.html 要能單檔 file:// 開
    title = tr(deck.get("meta", {}).get("title", "週報"))
    total = len(slides)
    body = "\n".join(render_slide(s, i + 1, total) for i, s in enumerate(slides))

    # 語言標記：兩版是平等的交付物，⛔ 沒有哪一版是「正式版」。
    # 但**看的人要一眼看得出手上這份是哪一版** —— 實驗室有外籍生，
    # 兩版會同時在流通，全螢幕播放時檔名看不到，所以標在頁面上。
    lang_tag = {"en": ("en", "EN"), "zh": ("zh-Hant", "中文")}.get(
        a.lang, (a.lang, a.lang.upper()))
    doc = (f'<!DOCTYPE html>\n<html lang="{lang_tag[0]}" data-lang-label="{lang_tag[1]}">'
           f'<head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">'
           f"<title>{esc(title)}</title><style>\n{css}\n</style></head>"
           f"<body>\n{body}\n<script>\n{js}\n</script>\n</body></html>\n")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[render] {total} 頁 → {out}" + (f"（lang={a.lang}）" if TR else ""))
    if MISSING:
        print(f"[render] ⚠️ {len(MISSING)} 句沒有 {a.lang} 譯文，已用英文原文輸出：",
              file=sys.stderr)
        for k in sorted(MISSING):
            print(f"    {k[:78]}", file=sys.stderr)


if __name__ == "__main__":
    main()
