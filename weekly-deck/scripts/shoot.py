#!/usr/bin/env python3
"""deck.<lang>.html -> _export/slides[_<lang>]/*.png（先量測溢位，超出就擋下來）。

為什麼要量測：`.slide` 的 CSS 是 overflow:hidden，內容超出時會被**靜靜裁掉**，
截圖看起來「正常」但字沒了。所以截圖前先把 overflow 改成 auto 量 scrollHeight，
任何一頁超出就 exit 1 並列出是哪幾頁、超出幾 px —— 溢位永遠不會偷偷進到 pptx。

用法：
  shoot.py deck.en.html                 # 量測 + 截圖到 _export/slides/
  shoot.py deck.zh.html                 # 中文版另存 _export/slides_zh/（⛔ 不互相覆蓋）
  shoot.py deck.en.html --check-only    # 只量測不截圖（⚠️ 不建 _export/）
                                        #   實測輸出 → _work/4_slides/shoot_check.<lang>.txt
  shoot.py deck.en.html --only 3,7      # 只重截這幾頁（改一頁時用）
  shoot.py deck.en.html --allow-overflow  # 明知會裁掉仍要截（不建議）
  shoot.py deck.en.html --allow-sparse    # 明知主線頁太空仍要截（不建議）

⚠️ 本腳本一律以 raw 模式開頁（`window.__DECK_RAW__ = true`），播放器不啟動。
   量測與截圖看到的永遠是未縮放的 1600×900 版面。詳見 main() 裡的註解。
"""
import argparse, json, os, shutil, sys

import paths


def export_dir(base):
    """截圖去處的上層：`<日期目錄>/_export`。⚠️ 這裡只算路徑、**不建目錄** ——
    `--check-only` 不該留下截圖產物（見 SKILL.md「不跑就不該存在」）。
    ⚠️ 它唯一會留下的是 `_work/4_slides/shoot_check.<lang>.txt`（實測輸出，
    layout_reviewer 的必要輸入 —— 見 check_report_path）。"""
    return paths.export_dir(base)


def lang_of(src):
    """`deck.en.html` → `en`；`deck.zh.html` → `zh`；沒標語言的當 `en`。"""
    stem = os.path.basename(src).rsplit(".html", 1)[0]      # deck.zh / deck.en / deck
    return stem.split(".")[-1] if "." in stem else "en"


def slides_dirname(src):
    """`deck.en.html` → `slides`；`deck.zh.html` → `slides_zh`。

    為什麼不是兩版共用一個 `slides/`：中英行高不同、頁面長相不同，
    共用會讓後跑的那版**無聲覆蓋**前一版，而 pptx 拿到的是哪一版看不出來。
    """
    lang = lang_of(src)
    return "slides" if lang == "en" else f"slides_{lang}"


def check_report_path(src):
    """`--check-only` 的實測輸出落地位置：`_work/4_slides/shoot_check.<lang>.txt`。

    **為什麼要落地**：`layout_reviewer` 的 Required inputs 要讀 `--check-only` 的
    **實測**輸出（溢位、字級、留白只有量了才知道），但這支腳本以前只印在畫面上、
    `--check-only` 不留任何檔 → reviewer 只能聽協調者口述數字，而口述的不是證據
    （FINDINGS N37）。現在由本腳本自己寫，不必靠 `| tee`（漏打就又沒有了）。

    ⚠️ 路徑一律問 `paths.work_dir()`，⛔ 不在這裡拼 `_work/...`（N14 就是那樣來的）。
    """
    return os.path.join(paths.work_dir(os.path.dirname(src), "slides", create=True),
                        f"shoot_check.{lang_of(src)}.txt")


def write_check_report(src, lines):
    """把這一輪 `--check-only` 印出來的每一行原樣寫成檔（含失敗那次）。

    ⛔ 溢位擋下來的那一次**也要寫** —— 那正是 reviewer 最需要看到的一份。
    """
    path = check_report_path(src)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[shoot] 實測輸出 → {path}")
    return path


W, H = 1600, 900
MEASURE_JS = """() => {
  const out = [];
  document.querySelectorAll('.slide').forEach((el, i) => {
    const prev = el.style.overflow;
    el.style.overflow = 'auto';
    const oh = el.scrollHeight - el.clientHeight;
    const ow = el.scrollWidth  - el.clientWidth;
    el.style.overflow = prev;
    out.push({n: i + 1, id: el.id, dy: oh, dx: ow});
  });
  return out;
}"""

# 後補：溢位以外的排版問題。
# 溢位只抓「塞不下」，抓不到「塞得下但版面很空、字很小」——後者在投影時一樣讀不到。
# 再補三項容器檢查（子內容溢出／容器過空／表格溢出容器）：
#   `.slide` 是 overflow:hidden，但**它裡面的 div 不是** —— 子內容超出某個內層容器時
#   不會被 MEASURE_JS 的 scrollHeight 抓到（整頁還是塞得下），畫面上卻是內容蓋住下方區塊。
AUDIT_JS = """() => {
  const out = [];
  const add = (n, type, msg) => out.push({n, type, msg});
  document.querySelectorAll('.slide').forEach((slide, i) => {
    const n = i + 1;
    // ⚠️ 後修：這裡原本寫死 `const H = 720`（抄自 1280×720 的來源），
    //    但我們的投影片是 **1600×900**（deck.css 的 --W/--H）。
    //    後果：真實留白 = 900 − bottom − padding-bottom，它卻拿 720 − bottom 去比 150，
    //    幾乎永遠是負數 → **這個檢查從來沒有觸發過**，四項自檢實際只有三項在跑。
    //    改成量 slide 自己的高度，並扣掉 padding-bottom（那段留白是版型設計的一部分，不是空洞）。
    const cs = getComputedStyle(slide);
    const H = slide.offsetHeight || 900;
    const padBottom = parseFloat(cs.paddingBottom) || 0;
    // position:absolute 的元素不參與 flow（例如頁碼、章節標），不能拿來當「內容底邊」
    const kids = [...slide.children].filter(
      e => e.offsetHeight > 0 && getComputedStyle(e).position !== 'absolute'
           && e.tagName !== 'STYLE');
    if (kids.length) {
      const bottom = Math.max(...kids.map(e => e.offsetTop + e.offsetHeight));
      const gap = H - bottom - padBottom;
      if (gap > 150) add(n, '底部留白', '內容只到 ' + Math.round(bottom) + 'px，下方空 ' + Math.round(gap) + 'px');
    }
    slide.querySelectorAll('table').forEach(t => {
      const rows = t.querySelectorAll('tr');
      if (rows.length < 2) return;
      const rh = t.offsetHeight / rows.length;
      const fs = parseFloat(getComputedStyle(t).fontSize) || 14;
      if (rh > fs * 3.2) add(n, '列高過鬆', '列高 ' + Math.round(rh) + 'px vs 字級 ' + fs + 'px，容器撐大但字沒放大');
      // ⚠️ 後補（FINDINGS N110）：這條以前**只有過鬆沒有過緊**。
      //    `line-height:1; padding:0` 把比值壓到 1.0，兩條檢查都不響，而字上下相黏。
      //    1.35 的依據：deck.css 的 table 預設是 line-height 1.5 + 上下 padding，
      //    比值約 2.4；1.35 已經是「幾乎沒有行距」的位置，正常的表格碰不到。
      if (rh < fs * 1.35) add(n, '列高過緊', '列高 ' + Math.round(rh) + 'px vs 字級 ' + fs + 'px，行距幾乎為零，字會上下相黏');
      const holder = t.parentElement;
      if (holder && t.scrollHeight > holder.offsetHeight + 2)
        add(n, '表格溢出容器', '表格自然高 ' + t.scrollHeight + 'px > 容器 ' + holder.offsetHeight + 'px');
    });
    slide.querySelectorAll('td, li, p, .body').forEach(e => {
      if (!e.offsetHeight || !e.textContent.trim()) return;
      // 圖內文字排除：我們的 .svg 是**內嵌**進 HTML 的（render_deck.py b_diagram），
      // 所以 SVG 裡的字會被這個 querySelectorAll 掃到。但圖有自己的縮放比例
      //（viewBox → figure.diagram svg{max-height:100%} 等比縮），CSS 上的 18px
      // 不等於畫面上的 18px，套投影片的字級標準會誤報。→ references/diagram-craft.md §6
      // ⚠️ 排除不等於不管：圖內的字改由下面的「圖內有效字級過小」檢查（fontSize × 縮放比 k）守。
      if (e.closest('svg')) return;
      const fs = parseFloat(getComputedStyle(e).fontSize) || 99;
      if (fs < 12) add(n, '字級過小', '有 ' + fs + 'px 的正文，投影建議 >= 13px');
    });

    // ── 以下三項 新增：容器與內容高度不匹配 ─────────────────
    // 抓的是「塞得下、也不空，但容器與內容對不起來」——前四項都看不到的那一類。
    //
    // ⚠️ 內容高一律用 Range 量，不要逐一加總 children：
    //    td 裡常常是裸的 text node（沒有元素包住），加總 children 會算成 0。
    // ⚠️ .slide 若被外層套 transform:scale（預覽頁常見），getBoundingClientRect
    //    回傳的是縮放後的值，要除回去才能跟 offsetHeight（未縮放）比。
    const scale = (slide.getBoundingClientRect().width / 1600) || 1;
    const contentH = el => {
      const r = document.createRange();
      r.selectNodeContents(el);
      const h = r.getBoundingClientRect().height / scale;
      r.detach && r.detach();
      return h || parseFloat(getComputedStyle(el).fontSize) * 1.35;
    };

    // example 是新版機制頁的主要承載版型。改：右欄（.case-aside）已作廢，
    // 主圖**全寬**（使用者原話：「藍色背景的內容，直接放大暫全部版面」）。
    // 這裡量真實排版結果，避免 CSS 被後續修改後悄悄漂移回 70/30。
    slide.querySelectorAll('.case-layout').forEach(layout => {
      const main = layout.querySelector('.case-main');
      if (!main) { add(n, '例子版型缺件', 'case-layout 裡找不到 .case-main 主案例'); return; }
      if (layout.querySelector('.case-aside'))
        // 會擋：render_deck.py 已經不產這塊了，還在版面上代表這份 HTML 是舊的、
        // 或有人手改過 —— 讓它進 pptx 等於把作廢的版型交出去。
        out.push({n, type: '例子版型殘留側欄', block: true,
                  msg: '.case-aside 已作廢（規則與邊界要畫進主圖），版面上卻還有一個'
                       + ' —— 這份 HTML 是舊的，請重跑 render_deck.py。'});
      const share = layout.offsetWidth ? main.offsetWidth / layout.offsetWidth : 0;
      if (share < 0.98)
        add(n, '例子版型未全寬', '主案例只佔 ' + Math.round(share * 100) + '%，應為 100%（單欄全寬）');
    });

    slide.querySelectorAll('div').forEach(box => {
      if (!box.children.length || box.offsetHeight < 80) return;
      if (box.closest('svg')) return;
      const st = getComputedStyle(box);
      if (st.display !== 'flex' && st.display !== 'grid' && st.display !== 'block') return;
      const kids = [...box.children].filter(e => getComputedStyle(e).position !== 'absolute');
      if (!kids.length) return;
      // 子內容高度要看排列方向：並排（grid 多欄／flex row）取 max，
      // 堆疊（block／flex column）才相加。搞錯方向會把 .cols、.stats 全部誤判成溢出。
      const sideBySide =
        (st.display === 'grid' && st.gridTemplateColumns.split(/\s+/).filter(Boolean).length > 1)
        || (st.display.includes('flex') && st.flexDirection.startsWith('row'));
      const kidsH = sideBySide
        ? Math.max(...kids.map(e => e.offsetHeight))
        : kids.reduce((s, e) => s + e.offsetHeight, 0);
      const label = box.className || box.tagName;
      // 塞不下：容器高度被寫死或被 flex 壓縮，內容溢出蓋住下方（畫面上很明顯，程式碼上看不出來）
      if (kidsH > box.offsetHeight + 2)
        add(n, '子內容溢出', '<' + label + '> 內容需要 ' + Math.round(kidsH) +
            'px，容器只有 ' + box.offsetHeight + 'px');
      // 太空：容器撐大但內容沒跟著放大
      if (box.offsetHeight > kidsH * 1.9 && box.offsetHeight - kidsH > 90)
        add(n, '容器過空', '<' + label + '> 高 ' + Math.round(box.offsetHeight) +
            'px，子內容僅 ' + Math.round(kidsH) + 'px');
    });

    // ── 版面密度：**會擋**（--allow-sparse 才放行）─────────────────
    // 為什麼要換一個量法：舊的「容器過空」比的是「容器高 vs 子元素高」，
    // 而 example／diagram 頁的子元素是被 grid/flex **撐滿**的 figure ——
    // figure 高 634px、裡面的圖只畫了 234px，子元素高等於容器高 → 這條檢查
    // 對真正空的那幾頁**一次都沒有響過**（實測：只在 agenda／thread-intro 上響）。
    // 所以改量**畫面上真的有墨水的那塊**（最外層 svg／img ＋ 不在 svg 裡的文字葉節點）
    // 的外接矩形，比 .body 的面積。
    //
    // 門檻 0.65 的理由（實測，1600×900、.body 約 1456×634）：
    //   · viewBox 1420×540（diagram-craft §6 高度預算表的上緣）→ 佔 0.82（A3／A4 實測）
    //   · viewBox 1420×430（預算表下緣）→ 只佔 0.53（A1 實測）
    //   · 0.65 ≈ viewBox 1420×470，仍在預算表之內 —— 也就是「照預算把圖畫足」就會過，
    //     只用了一半版面才會被擋。實測擋下 A1 0.53／A2 0.43／A5 0.34／B3 0.50，
    //     放行 A3 0.82／A4 0.82／B2 0.83；B1 0.63 也擋（差 2 個百分點，正是使用者
    //     點名的第 11 頁那類「三個 block 連到四個 block」的稀疏圖）。
    //   ⚠️ 舊值（容器高 > 子內容 × 1.9）明顯太寬鬆，而且印了三輪沒有人理它 ——
    //      散文擋不住事情，只有會 exit 1 的東西擋得住。
    //   ⛔ 結構頁（cover／agenda／thread-intro）與 backup 頁豁免：它們本來就該疏。
    const struct = ['t-cover', 't-agenda', 't-thread-intro'].some(c => slide.classList.contains(c));
    const body = slide.querySelector(':scope > .body');
    if (!struct && !slide.dataset.backup && body && body.offsetWidth && body.offsetHeight) {
      const ink = [];
      body.querySelectorAll('svg, img').forEach(e => {
        if (e.tagName === 'svg' && e.closest('svg') !== e) return;   // 內層 svg 跳過
        ink.push(e);
      });
      body.querySelectorAll('*').forEach(e => {
        if (e.children.length || e.closest('svg') || !e.textContent.trim()) return;
        if (e.offsetHeight) ink.push(e);
      });
      const rs = ink.map(e => e.getBoundingClientRect()).filter(r => r.width && r.height);
      if (rs.length) {
        const w = (Math.max(...rs.map(r => r.right)) - Math.min(...rs.map(r => r.left))) / scale;
        const h = (Math.max(...rs.map(r => r.bottom)) - Math.min(...rs.map(r => r.top))) / scale;
        const fill = (w * h) / (body.offsetWidth * body.offsetHeight);
        if (fill < 0.65)
          out.push({n, type: '版面過空', block: true,
                    msg: '版面只用了 ' + Math.round(fill * 100) + '%（內容外接矩形 ' +
                         Math.round(w) + '×' + Math.round(h) + '，版面 ' + body.offsetWidth +
                         '×' + body.offsetHeight + '），門檻 65%。' +
                         '⛔ 不是「把圖放大」——圖是等比縮的，放大 viewBox 沒有用；' +
                         '要**多放事實**（真名、數量、限制、檔名）把格子填滿，或加高 viewBox 到預算表上緣。'});
      }
    }

    // ── 反方向：文字過密（FINDINGS N112，與上面的密度門檻**同批訂**）──
    // ⚠️ 上面那條只問「有沒有填滿」，於是最省力的填法就是**塞字** ——
    //    使用者第二輪的原話：「整個解釋都只是像文章寫在 block 的下面而已」。
    //    那正是 N56 記載的實測：加了單向的密度門檻，就把 builder 推到另一個極端。
    //    ⛔ 65% 那個數字**不動**（它有實測校準），改成在同一支腳本補上反方向。
    // 門檻 60 則的依據：現有 7 張圖的 <text> 則數是 15/20/30/40/44/45/45（含 A5 的
    //    value），上緣 45 → 60 留了三分之一的餘裕。⚠️ 這是「可改善」不擋截圖：
    //    則數多不一定是錯（一張真的很密的判準表），但要有人看一眼是事實還是句子。
    const tn = slide.querySelectorAll('.body svg text').length;
    if (tn > 60) add(n, '文字過密', '圖上有 ' + tn + ' 則 <text>（>60）——' +
        '密度門檻獎勵把格子填滿，但填的要是**事實**（真名、數量、限制、檔名），' +
        '不是把一句話斷成六則短標籤');

    // ── SVG 內的「有效字級」：新增 ────────────────────────────
    // 上面那條 `字級過小` 把整個 <svg> 排除掉了（圖有自己的縮放比例，套投影片標準會誤報），
    // 但排除之後**圖裡的字就完全沒有東西在守**。這一條補回來，量的是讀者真正看到的字級。
    //
    // 機制：`figure.diagram svg{max-width:100%;max-height:100%}` 會把圖**等比縮**進容器，
    //   有效字級 = fontSize × k，  k = 畫面寬 ÷ viewBox 寬（＝ min(容器寬/vb寬, 容器高/vb高)）
    //   → 調大 fontSize 只會讓 viewBox 一起變大、縮得更多，**視覺上完全沒變大**。
    //     真正有效的是**縮短比較長的那一邊**。→ references/diagram-craft.md §6 的高度預算表
    //
    // 門檻 13px 的理由：與上面正文的字級標準同一個數字，好記且不會兩套。
    //   來源（1280×720 的版型）用的是 10px；我們是 **1600×900**，同一個視覺大小要 ×1.25
    //   → 12.5px，進位取 13px。現況安全：6 張既有圖 viewBox 1420×430~540、k≈1.03，
    //   最小的 .annot 18px 換算後 18.5px，離門檻很遠 → 這條不該在正常的 deck 上觸發。
    slide.querySelectorAll('svg[viewBox]').forEach(svg => {
      if (svg.closest('svg') !== svg) return;              // 只看最外層 svg（marker 等內層跳過）
      const vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
      if (vb.length !== 4 || !(vb[2] > 0) || !(vb[3] > 0)) return;
      const r = svg.getBoundingClientRect();
      // ⚠️ .slide 帶著 transform:scale（預覽頁），getBoundingClientRect 是縮放後的值，要除回去
      const w = r.width / scale, h = r.height / scale;
      if (!(w > 0) || !(h > 0)) return;
      const k = Math.min(w / vb[2], h / vb[3]);
      let worst = null;
      svg.querySelectorAll('text').forEach(t => {
        if (!t.textContent.trim()) return;
        const fs = parseFloat(getComputedStyle(t).fontSize);
        if (!fs) return;
        const eff = fs * k;
        if (!worst || eff < worst.eff) worst = {fs: fs, eff: eff, s: t.textContent.trim()};
      });
      if (worst && worst.eff < 13)
        add(n, '圖內有效字級過小',
            '圖等比縮到 k=' + k.toFixed(2) + '（viewBox ' + vb[2] + '×' + vb[3] +
            ' → 畫面 ' + Math.round(w) + '×' + Math.round(h) + '），' +
            worst.fs + 'px 的字實際只有 ' + worst.eff.toFixed(1) + 'px（<13px）：「' +
            worst.s.slice(0, 20) + '」。⛔ 調大 fontSize 沒用（viewBox 會一起變大、縮更多），' +
            '要**縮短比較長的那一邊**：降低 viewBox 高度（查 diagram-craft.md §6 高度預算表）或拆頁。');
    });

    // ── 盒內墨水覆蓋率：**上下限都給**（6e 第 ⑤ 把量尺，補 N52 的洞）──────
    // 為什麼要這一把：上面那條 65% 量的是**整個版面**的外接矩形，而 N52 記著
    //   `shoot.py` 對「框多字少」是瞎的 —— 一頁可以「版面填滿了」但每個框都空。
    //   實測 B3：viewBox 486、9 個框只有 13 則 <text>（B1 是 6 框 28 則），密度 74% 照樣過關。
    //   ⭐ 盒內覆蓋率算得出來，把「目前只有 layout_reviewer 擋得住」的事變成機械看得見的。
    //
    // ⚠️ **只量大盒（≥400×128）**——這是量出來才知道的：小盒子的比值被單一個字的
    //   長度主宰。實測同樣 160×48 的盒，一個放短字 0.074、一個放長字 0.49，**差 6 倍**。
    //   ⛔ 不設尺寸門檻就會對「字短」開罵，而字短不是缺陷。400×128 ≈ 放得下 3 行。
    //
    // 門檻 [0.12, 0.45] 的理由（實測現有 7 張圖的 39 個盒，其中大盒 18 個）：
    //   大盒的分布是 0.093 / 0.102 / 0.102 / 0.125 / 0.147 / 0.156 / 0.196 … 0.348，
    //   中位數 0.25。下限 0.12 擋下最低那三個，逐個解釋得出來、且都是同一種病：
    //     A5 的 1420×160 橫幅只有 5 則字（0.093／0.102）、A4 的 1420×184 只有 3 則（0.102）
    //     ——⭐ 逐字就是 N52 的「框大字少」。
    //   ⛔ 上限 0.45 是 N56 的反方向（⛔ 不准只給下限）：只給下限，builder 會把盒子
    //     塞成文章去換綠燈 —— 上一場真的發生過（N112，使用者原話「像文章寫在 block 下面」）。
    //     大盒現況最高 0.348，所以上限現在不該響；它是**護欄**，不是門檻。
    // ⚠️ 一律「可改善」不擋截圖：比值是代理指標，一張真的很密的判準表是合法的。
    slide.querySelectorAll('svg[viewBox]').forEach(svg => {
      if (svg.closest('svg') !== svg) return;
      const boxes = [...svg.querySelectorAll('rect')]
        .filter(r => /^(box|grp)/.test(r.getAttribute('class') || ''))
        .map(r => ({x: +r.getAttribute('x'), y: +r.getAttribute('y'),
                    w: +r.getAttribute('width'), h: +r.getAttribute('height'),
                    c: r.getAttribute('class')}))
        .filter(r => r.w > 0 && r.h > 0);
      if (!boxes.length) return;
      const texts = [...svg.querySelectorAll('text')].map(t => {
        const b = t.getBBox();
        return {cx: b.x + b.width / 2, cy: b.y + b.height / 2, a: b.width * b.height};
      });
      // ⭐ PR 4（glyph）：**記號也是墨水**。點陣、tile、分段條、read、探針…是 rect／circle／
      //   polygon／path，不是 <text>；只數字的話一個畫滿小圖的盒會被判「過空」（實測 B1 的
      //   chain 步驟框：4 則字 ＋ 60 個記號，只數字是 7%）。
      //   ⛔ 不算：容器本身（box／grp）、分隔線（rule）、座標刻度與底條（tick／track —— 那是
      //   「軸」不是「內容」）、marker／defs 裡的東西。
      const marks = [...svg.querySelectorAll('rect,circle,polygon,polyline,path,line')].filter(e => {
        const c = e.getAttribute('class') || '';
        if (/^(box|grp|rule|tick|track)/.test(c)) return false;
        if (e.closest('marker') || e.closest('defs')) return false;
        return true;
      }).map(e => {
        const b = e.getBBox();
        return {cx: b.x + b.width / 2, cy: b.y + b.height / 2, a: b.width * b.height};
      });
      const ownerOf = (t) => {
        let own = null;                               // 屬於**最小**包住它的盒
        boxes.forEach(q => {
          if (q.x <= t.cx && t.cx <= q.x + q.w && q.y <= t.cy && t.cy <= q.y + q.h)
            if (!own || q.w * q.h < own.w * own.h) own = q;
        });
        return own;
      };
      const thin = [], fat = [];
      boxes.forEach(r => {
        if (r.w < 400 || r.h < 128) return;          // ⛔ 小盒不量，見上
        let inkT = 0, lines = 0, inkM = 0, nm = 0;
        texts.forEach(t => { if (ownerOf(t) === r) { inkT += t.a; lines++; } });
        marks.forEach(m => { if (ownerOf(m) === r) { inkM += m.a; nm++; } });
        // 下限看**全部**墨水（字＋記號）：空就是空。
        // 上限只看**字**：過滿那條是在擋「把句子塞進框裡換綠燈」（N112），記號不是散文。
        const ratio = (inkT + inkM) / (r.w * r.h), ratioT = inkT / (r.w * r.h);
        const d = '<' + r.c + '> ' + Math.round(r.w) + '×' + Math.round(r.h) +
                  '，' + lines + ' 則字' + (nm ? '、' + nm + ' 個記號' : '') +
                  '，覆蓋率 ' + Math.round(ratio * 100) + '%';
        if (ratio < 0.12) thin.push(d); else if (ratioT > 0.45) fat.push(d);
      });
      if (thin.length)
        add(n, '盒內過空', thin.length + ' 個大盒的墨水覆蓋率 <12%：' + thin.join('；') +
            '。⛔ 不是「把框縮小」—— 框的尺寸是構圖決定的；' +
            '要**在框裡多放事實**（真名、數量、限制、檔名），' +
            '或者這個框根本不該存在（它現在只裝得下一個標籤）。');
      if (fat.length)
        add(n, '盒內過滿', fat.length + ' 個大盒的墨水覆蓋率 >45%：' + fat.join('；') +
            '。⚠️ 這是「盒內過空」的反方向（N56）：⛔ 不要為了填滿把句子塞進框裡，' +
            '框裡要的是事實不是散文（N112）。');
    });

    // ── 欄內壓字：**N122 缺的那把量尺**（6e 裝上）─────────────────
    // ⚠️ 上面每一條量的都是**整頁**溢位或**整體**密度 —— 而 N122 的病是
    //   「字在框裡卻橫向壓出框外」：整頁沒有溢位、密度也漂亮，那一則字照樣疊上去。
    //   實測（6d）：zh 版 A3 判準欄的中譯穿進終點框 **31px**，英文版 0 處 ——
    //   ⭐ 欄寬照英文算，中譯較長就壓出去，而**沒有任何檢查看得到**。
    //
    // 兩個判準（來源：上一場量出那 31px 的兩支腳本，判準記在 FINDINGS N125）：
    //   ① 框內的字：字的右緣 > 它所在框的右緣 − 8px 內距
    //   ② 無框的字：橫向穿進某個框的左緣
    //
    // ⛔ **N56 的反方向，先答再裝**：只加這條會把 builder 推去**縮字級**換綠燈。
    //   出路寫進訊息裡並**排好順序**，而且縮字級那條路已經有人擋
    //   （上面「圖內有效字級過小」<13px 會叫）——⭐ 兩條互相咬住，不是單向門檻。
    slide.querySelectorAll('svg[viewBox]').forEach(svg => {
      if (svg.closest('svg') !== svg) return;
      const boxes = [...svg.querySelectorAll('rect')]
        .filter(r => /^(box|grp)/.test(r.getAttribute('class') || ''))
        .map(r => ({x: +r.getAttribute('x'), y: +r.getAttribute('y'),
                    w: +r.getAttribute('width'), h: +r.getAttribute('height'),
                    c: r.getAttribute('class')}))
        .filter(r => r.w > 0 && r.h > 0);
      if (!boxes.length) return;
      const hits = [];
      svg.querySelectorAll('text').forEach(t => {
        const s = t.textContent.trim();
        if (!s) return;
        const len = t.getComputedTextLength();
        const x = +t.getAttribute('x'), y = +t.getAttribute('y');
        if (!(len > 0) || !isFinite(x) || !isFinite(y)) return;
        const anchor = t.getAttribute('text-anchor');
        const x0 = anchor === 'middle' ? x - len / 2 : anchor === 'end' ? x - len : x;
        const x1 = x0 + len;
        let own = null;
        boxes.forEach(r => {
          if (r.x <= x && x <= r.x + r.w && r.y <= y && y <= r.y + r.h)
            if (!own || r.w * r.h < own.w * own.h) own = r;
        });
        if (own) {                                   // ① 框內的字壓出框右緣
          const lim = own.x + own.w - 8;
          if (x1 > lim + 1)
            hits.push('「' + s.slice(0, 24) + '」壓出 <' + own.c + '> 右緣 ' +
                      Math.round(x1 - lim) + 'px');
        } else {                                     // ② 無框的字橫向穿進別的框
          boxes.forEach(r => {
            if (r.y <= y && y <= r.y + r.h && x < r.x && x1 > r.x)
              hits.push('「' + s.slice(0, 24) + '」穿進 <' + r.c + '> 左緣 ' +
                        Math.round(x1 - r.x) + 'px');
          });
        }
      });
      if (hits.length)
        add(n, '欄內壓字', hits.length + ' 則字壓到框：' + hits.slice(0, 3).join('；') +
            (hits.length > 3 ? '…' : '') +
            '。⚠️ 整頁溢位檢查看不到這個（它量的是整頁）。出路照這個順序試：' +
            '① 把那則字換行或斷成兩則；② 改寫得更短（⛔ 不是縮寫成看不懂的代號）；' +
            '③ 搬進 notes 由講者口頭講。' +
            '⛔ **不要縮字級** —— 那是把病推給「圖內有效字級」那條檢查（<13px 會叫），' +
            '⛔ 也不要靠調欄寬蓋過去（N122 逐字寫著不要那樣做）。');
    });

    // ── 文字互壓（B17-13）：**會擋**（--allow-text-overlap 才放行）─────────
    // 為什麼要這一把：2026-09-06 實跑 layout_reviewer 判 FAIL 的 5 條 BLOCKING 同一個根因 ——
    //   中文譯文比英文長，`two_col_link`／`chain_gated` 的 label＋note 用**英文寬度**算位移，
    //   zh 版兩則字疊成字團。英文版逐頁正常、只有中文版壞，而上面每一條檢查都看不到：
    //   溢位量整頁、密度量外接矩形、欄內壓字量「字 vs 框」—— 沒有一條量「字 vs 字」。
    // 判準：同一張 SVG 裡兩則 <text> 的外接矩形相交，水平重疊 >2px 且垂直重疊超過各自高度的 40%
    //   （＝在同一行上真的疊到，不是上下兩行的邊緣碰到）。getBBox 是 SVG 使用者座標，
    //   兩版 HTML 都量得到，不受 .slide 的 transform 影響。
    // ⚠️ 會擋的理由（不走「先寬」）：判準精確、幾乎不會誤報，而它擋的正是使用者說
    //   「無法辨識」的那種字團；⛔ 不擋就等於回到只有 reviewer 的肉眼才看得到。
    slide.querySelectorAll('svg[viewBox]').forEach(svg => {
      if (svg.closest('svg') !== svg) return;
      const ts = [...svg.querySelectorAll('text')].map(t => {
        const b = t.getBBox();
        return {x: b.x, y: b.y, w: b.width, h: b.height, s: (t.textContent || '').trim()};
      }).filter(t => t.w > 0 && t.h > 0 && t.s);
      const hits = [];
      for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
        const a = ts[i], b = ts[j];
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (ox > 2 && oy > a.h * 0.4 && oy > b.h * 0.4)
          hits.push('「' + a.s.slice(0, 18) + '」×「' + b.s.slice(0, 18) + '」重疊 ' + Math.round(ox) + 'px');
      }
      if (hits.length)
        out.push({n, type: '文字互壓', block: true,
                  msg: hits.length + ' 處兩則字疊在一起：' + hits.slice(0, 4).join('；') +
                       (hits.length > 4 ? '…' : '') +
                       '。⚠️ 多半是中文譯文比英文長（B17-13）：① 把那則字改短或斷成兩則；' +
                       '② 該構圖的 note／gloss 欄改寫；③ 搬進 notes。' +
                       '⛔ 不要縮字級、不要在 SVG 上手改座標（spec 重跑就洗掉了）。'});
    });

    // 表格不會被容器壓縮：容器高度小於表格自然高度時會直接溢出蓋住下方區塊。
    // 逐列用 Range 量內容高，順便抓「列高遠大於內容」的個別列（既有的列高檢查只看平均）。
    slide.querySelectorAll('table').forEach((t, ti) => {
      t.querySelectorAll('tbody tr').forEach((tr, r) => {
        const cells = [...tr.children];
        if (!cells.length) return;
        const ch = Math.max(...cells.map(contentH));
        if (tr.offsetHeight > ch * 2.5)
          add(n, '列高過鬆', '表格' + (ti + 1) + ' 第 ' + (r + 1) + ' 列：列高 ' +
              Math.round(tr.offsetHeight) + 'px，內容只佔 ' + Math.round(ch) + 'px');
      });
    });
  });
  const seen = new Set();
  return out.filter(x => { const k = x.n + x.type; if (seen.has(k)) return false; seen.add(k); return true; });
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--outdir")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--allow-overflow", action="store_true")
    ap.add_argument("--allow-sparse", action="store_true",
                    help="明知主線頁版面過空仍要截（不建議；比照 --allow-overflow）")
    ap.add_argument("--allow-text-overlap", action="store_true",
                    help="明知圖內有兩則字疊在一起仍要截（不建議；B17-13 的字團正是這一種）")
    ap.add_argument("--only", help="只截這幾頁，逗號分隔的頁碼")
    a = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("[shoot] 需要 playwright：python3 -m pip install --user playwright "
                 "&& python3 -m playwright install chromium")

    src = os.path.abspath(a.html)
    outdir = a.outdir or os.path.join(export_dir(os.path.dirname(src)),
                                      slides_dirname(src))
    only = {int(x) for x in a.only.split(",")} if a.only else None

    with sync_playwright() as p:
        # 遠端／CI 環境常常有預裝的 Chromium 但版本跟 pip 的 playwright 對不上（它會叫你
        # `playwright install`）。給一個明確的執行檔就不必下載：WEEKLY_DECK_CHROMIUM=<binary>。
        exe = os.environ.get("WEEKLY_DECK_CHROMIUM")
        br = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H},
                         device_scale_factor=a.scale)
        # ⚠️ 關掉 deck.html 的播放器（assets/deck.js），讓頁面回到「1600×900 原尺寸、
        #    垂直排列、全部可見」的狀態 —— 也就是加播放器之前的樣子。
        #    非做不可的理由：下面 MEASURE_JS 量的是未縮放的 scrollHeight／offsetHeight，
        #    AUDIT_JS 的容器與圖內字級檢查也全部跟尺寸有關；播放器一旦套上
        #    transform:scale 並把非當前頁 display:none，這些數字會整組失準
        #    （隱藏的頁 offsetHeight 直接變 0）。
        #    add_init_script 在頁面任何腳本之前執行，所以播放器**根本不會啟動**，
        #    不是啟動後再關掉 —— 沒有殘留的 class 或 inline style。
        pg.add_init_script("window.__DECK_RAW__ = true;")
        pg.goto("file://" + src)
        pg.wait_for_function("document.fonts.ready.then(()=>true)")

        # 印出來的每一行同時收進 report —— `--check-only` 要把它寫成檔給
        # layout_reviewer 讀（N37）。⛔ 不要只印不收：口述的數字不是證據。
        report = []

        def say(msg, to_err=False):
            print(msg, file=sys.stderr if to_err else sys.stdout)
            report.append(msg)

        measures = pg.evaluate(MEASURE_JS)
        bad = [m for m in measures if m["dy"] > 1 or m["dx"] > 1]
        for m in bad:
            say(f"[溢位] 第 {m['n']} 頁 ({m['id']})："
                f"高度超出 {m['dy']}px、寬度超出 {m['dx']}px", to_err=True)
        if bad and not a.allow_overflow:
            br.close()
            tail = (f"\n[shoot] {len(bad)} 頁塞不下，未截圖。"
                    f"請壓縮內容或拆頁後重跑 render_deck.py。")
            if a.check_only:
                report.append(tail)
                write_check_report(src, report)
            sys.exit(tail)
        if not bad:
            say(f"[shoot] 溢位檢查通過（{len(measures)} 頁全部塞得下）")

        # 版面品質自檢：不擋，但要講出來（塞得下不等於排得好）
        audit = pg.evaluate(AUDIT_JS)
        blockers = [x for x in audit if x.get("block")]
        soft = [x for x in audit if not x.get("block")]
        if soft:
            say(f"\n[版面] {len(soft)} 項可改善（不擋截圖）：", to_err=True)
            for x in soft:
                say(f"  第 {x['n']} 頁 [{x['type']}] {x['msg']}", to_err=True)
            say("  → 判準：這塊空白能不能改放一項讀者需要知道的資訊？"
                "能就補內容，不能就把現有內容放大。", to_err=True)
        sparse = [x for x in blockers if x.get("type") == "版面過空"]
        overlap = [x for x in blockers if x.get("type") == "文字互壓"]
        if blockers:
            # ⚠️ 這一段是**會擋的**。理由：舊版把「容器過空」印成建議，實測連印三輪
            # 都沒有人理它，主圖照樣只用了版面的 20~53% 就進了交付物。
            # 散文擋不住事情，只有 exit 1 擋得住。
            # ⚠️ 抬頭那一行要含「主線內容過空」四個字 —— verify.py 的 read_shoot() 認的是它。
            say(f"\n[版面] {len(blockers)} 頁會擋（主線內容過空 {len(sparse)}、文字互壓 {len(overlap)}）：",
                to_err=True)
            for x in blockers:
                say(f"  第 {x['n']} 頁 [{x['type']}] {x['msg']}", to_err=True)
        if not audit:
            say("[版面] 自檢通過（留白、列高、字級、圖內有效字級、版面密度、文字互壓皆合理）")
        stop = (sparse and not a.allow_sparse) or (overlap and not a.allow_text_overlap)
        if stop:
            br.close()
            bits = []
            if sparse and not a.allow_sparse:
                bits.append(f"{len(sparse)} 頁主線內容過空（版面密度 <65%）—— 把事實補進圖裡"
                            f"（真名／數量／限制／檔名）後重跑；確定要照原樣截就加 --allow-sparse")
            if overlap and not a.allow_text_overlap:
                bits.append(f"{len(overlap)} 頁圖內有兩則字疊在一起（B17-13）—— 改短那則字或改寫 spec 後"
                            f"重跑 render_figure.py --all；確定要照原樣截就加 --allow-text-overlap")
            tail = "\n[shoot] 未截圖：" + "；".join(bits) + "。"
            say(tail, to_err=True)
            if a.check_only:
                write_check_report(src, report)
            sys.exit(1)
        if a.check_only:
            br.close()
            write_check_report(src, report)
            return

        if only is None and os.path.isdir(outdir):
            shutil.rmtree(outdir)
        os.makedirs(outdir, exist_ok=True)
        pg.evaluate("() => document.body.classList.add('shoot')")   # 隱藏預覽外掛資訊

        n = 0
        for m in measures:
            if only and m["n"] not in only:
                continue
            path = os.path.join(outdir, f"slide-{m['n']:02d}.png")
            pg.locator(".slide").nth(m["n"] - 1).screenshot(path=path)
            n += 1
        br.close()

    print(f"[shoot] 截圖 {n} 頁 → {outdir}（{W*a.scale}×{H*a.scale}）")


if __name__ == "__main__":
    main()
