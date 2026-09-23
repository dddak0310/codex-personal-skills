/* 投影片排版自檢 — 貼進瀏覽器 console 執行（deck.html 或單頁預覽都可）
 *
 * 抓的是「看程式碼看不出來」的四類排版問題：
 *   1. 內容溢出 720px
 *   2. 底部大片留白（版面沒填滿）
 *   3. 容器撐大但內容沒跟著放大（表格列高遠大於內容高 → 字小、空白多）
 *   4. 正文字級過小（投影時看不清）
 *
 * 用法：build 完 deck.html，在瀏覽器打開後貼上執行，逐條修到沒有 warn。
 */
(() => {
  const H = 720;
  const issues = [];
  const push = (page, type, msg) => issues.push({ 頁: page, 類型: type, 說明: msg });

  document.querySelectorAll('.slide').forEach((slide, idx) => {
    const page = idx + 1;
    const cs = getComputedStyle(slide);
    const padBottom = parseFloat(cs.paddingBottom) || 0;

    // 1) 溢出
    if (slide.scrollHeight > H + 2) {
      push(page, '溢出', `內容超出投影片 ${Math.round(slide.scrollHeight - H)}px，底部會被裁掉`);
    }

    // 2) 底部留白：最後一個參與 flow 的子元素，其底邊離 slide 底部多遠
    const kids = [...slide.children].filter(el =>
      el.offsetHeight > 0 && getComputedStyle(el).position !== 'absolute' && el.tagName !== 'STYLE');
    const last = kids[kids.length - 1];
    if (last) {
      const gap = H - (last.offsetTop + last.offsetHeight) - padBottom;
      if (gap > 40) {
        push(page, '底部留白', `最後一個區塊下方空了 ${Math.round(gap)}px —— 放大內容或補資訊，不要留著`);
      }
    }

    // 3) 容器撐大但內容沒放大：表格列高 vs 該列實際內容高
    //    內容高要用 Range 量（td 裡的數字常是 text node，逐一加總 children 會漏算），
    //    且 .slide 帶著 transform:scale，getBoundingClientRect 的值要除回去才能跟 offsetHeight 比。
    const scale = (slide.getBoundingClientRect().width / 1280) || 1;
    const contentHeightOf = el => {
      const range = document.createRange();
      range.selectNodeContents(el);
      const h = range.getBoundingClientRect().height / scale;
      range.detach && range.detach();
      return h || parseFloat(getComputedStyle(el).fontSize) * 1.35;
    };
    slide.querySelectorAll('table').forEach((t, ti) => {
      t.querySelectorAll('tbody tr').forEach((tr, r) => {
        const cells = [...tr.children];
        if (!cells.length) return;
        const contentH = Math.max(...cells.map(contentHeightOf));
        const rowH = tr.offsetHeight;
        if (rowH > contentH * 2.5) {
          push(page, '列高過鬆', `表格${ti + 1} 第 ${r + 1} 列：列高 ${Math.round(rowH)}px，內容只佔 ${Math.round(contentH)}px` +
            `（比例 ${(rowH / contentH).toFixed(1)}×）—— 字級要跟著容器一起放大`);
        }
      });
    });

    // 3b) 一般容器：撐大但子內容很矮，或反過來塞不下而靜默溢出
    //     子內容高度要看排列方向：並排（grid 多欄 / flex row）取 max，堆疊（block / flex column）才相加。
    slide.querySelectorAll('div').forEach(box => {
      if (box.children.length === 0 || box.offsetHeight < 80) return;
      const st = getComputedStyle(box);
      if (st.display !== 'flex' && st.display !== 'grid' && st.display !== 'block') return;
      const kids = [...box.children].filter(e => getComputedStyle(e).position !== 'absolute');
      if (!kids.length) return;
      const sideBySide = (st.display === 'grid' && st.gridTemplateColumns.split(/\s+/).filter(Boolean).length > 1)
        || (st.display.includes('flex') && st.flexDirection.startsWith('row'));
      const kidsH = sideBySide
        ? Math.max(...kids.map(e => e.offsetHeight))
        : kids.reduce((s, e) => s + e.offsetHeight, 0);
      const label = box.className || box.tagName;

      // 塞不下：容器高度被寫死或被 flex 壓縮，內容溢出並蓋住下方區塊（畫面上很明顯，程式碼上完全看不出來）
      if (kidsH > box.offsetHeight + 2) {
        push(page, '子內容溢出', `<${label}> 內容需要 ${Math.round(kidsH)}px，容器只有 ${box.offsetHeight}px`);
      }
      // 太空
      if (box.offsetHeight > kidsH * 1.9 && box.offsetHeight - kidsH > 90) {
        push(page, '容器過空', `<${label}> 高 ${Math.round(box.offsetHeight)}px，子內容僅 ${Math.round(kidsH)}px`);
      }
    });

    // 3c) 表格不會被容器壓縮：容器高度小於表格自然高度時會直接溢出蓋住下方
    slide.querySelectorAll('table').forEach(t => {
      const holder = t.parentElement;
      if (holder && t.scrollHeight > holder.offsetHeight + 2) {
        push(page, '表格溢出容器', `表格自然高 ${t.scrollHeight}px > 容器 ${holder.offsetHeight}px —— 容器高度要 ≥ 表格自然高度`);
      }
    });

    // 4) 字級過小（排除註腳類 .foot / .source-note / .slide-label）
    slide.querySelectorAll('*').forEach(el => {
      if (el.children.length || !el.textContent.trim()) return;
      if (el.closest('.foot, .source-note, .slide-label')) return;
      if (el.closest('svg')) return;   // 圖內標籤自有縮放比例，不套投影片字級標準
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs && fs < 11.5) {
        push(page, '字級過小', `${fs}px：「${el.textContent.trim().slice(0, 24)}」`);
      }
    });
  });

  if (!issues.length) {
    console.log('%c✅ 排版自檢通過', 'color:#237804;font-weight:bold');
  } else {
    console.warn(`排版自檢發現 ${issues.length} 項：`);
    console.table(issues);
  }
  return issues;
})();
