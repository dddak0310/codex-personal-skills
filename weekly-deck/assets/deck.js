/* weekly-deck 播放器 —— 讓 deck.html 可以直接上台講，不必轉 pptx。
   零外部依賴（不載 CDN、不用 npm），由 render_deck.py 內嵌進 HTML，file:// 直接開得起來。

   ── 兩種狀態 ─────────────────────────────────────────────────────────
   播放模式（預設）：一次一頁、transform:scale 貼合視窗、鍵盤與按鈕翻頁。
   raw 模式        ：完全不啟動，維持「1600×900 原尺寸、垂直排列、全部可見」，
                     也就是加播放器之前的樣子。

   ⚠️ **raw 模式是給 shoot.py 用的，不是可有可無的開關。**
      shoot.py 量的是未縮放的 offsetHeight / getBoundingClientRect，
      而且它的容器檢查（子內容溢出、容器過空、圖內有效字級）全部跟尺寸有關。
      只要有 transform:scale，那些數字就會失準 → 溢位與版面自檢會整組報廢。
      所以播放器**只在「看」的時候作用**，量測時必須完全退場。

   進 raw 模式的三種寫法（任一成立即可，shoot.py 用第一種）：
      window.__DECK_RAW__ = true      （playwright 的 add_init_script，最早生效）
      網址帶 ?raw=1
      <body class="raw">
   ── 快捷鍵見 SKILL.md「怎麼播」一節 ────────────────────────────────── */
(function () {
  'use strict';

  var RAW = (typeof window.__DECK_RAW__ !== 'undefined' && window.__DECK_RAW__) ||
            /[?&]raw=1\b/.test(location.search) ||
            (document.body && document.body.classList.contains('raw'));
  if (RAW) return;                       // ⛔ 這裡就結束：不注入樣式、不建 UI、不改任何節點

  var W = 1600, H = 900;
  var slides = [].slice.call(document.querySelectorAll('.slide'));
  if (!slides.length) return;

  var idx = 0;              // 目前頁（0-based）
  var notesOn = false;      // 講者備忘是否展開
  var gridOn = false;       // 總覽網格是否開著
  var blackOn = false;      // 黑屏
  var NOTES_H = 240;        // 備忘面板高度（會從可用高度扣掉，圖不會被蓋住）

  /* ── 播放器樣式：全部寫在這裡，⛔ 不動 deck.css 的 .slide 版面規則 ──────
     所有選擇器都掛在 body.deck-play 底下，raw 模式不會有這個 class。 */
  var css = [
    'body.deck-play{overflow:hidden;height:100vh;background:#15172B}',
    'body.deck-play .slide{position:absolute;top:0;left:0;margin:0;',
    '  transform-origin:top left;display:none;box-shadow:0 10px 40px rgba(0,0,0,.5)}',
    'body.deck-play .slide.dp-on{display:flex}',
    /* 控制列：圖示與數字，⛔ 不放任何需要翻譯的字 */
    '.dp-bar{position:fixed;right:18px;bottom:14px;z-index:40;display:flex;align-items:center;',
    '  gap:8px;padding:6px 10px;border-radius:99px;background:rgba(20,22,44,.72);',
    '  color:#fff;font:600 18px/1 system-ui,sans-serif;backdrop-filter:blur(4px);',
    '  opacity:.35;transition:opacity .18s}',
    '.dp-bar:hover,body.dp-hint .dp-bar{opacity:1}',
    // 備忘展開時控制列往上讓位，否則會壓在備忘文字上（實測）
    'body.dp-notes-on .dp-bar{bottom:' + (NOTES_H + 14) + 'px}',
    '.dp-bar button{all:unset;cursor:pointer;width:34px;height:34px;border-radius:50%;',
    '  display:flex;align-items:center;justify-content:center;font-size:20px;color:#fff}',
    '.dp-bar button:hover{background:rgba(255,255,255,.18)}',
    '.dp-bar button[disabled]{opacity:.28;cursor:default;background:none}',
    '.dp-num{padding:0 8px;font-variant-numeric:tabular-nums;letter-spacing:.04em}',
    /* 語言標記：兩版是平等的交付物，⛔ 沒有哪一版是「正式版」。
       但實驗室有外籍生、兩版會同時流通，全螢幕播放時看不到檔名 ——
       所以要在頁面上一眼看得出手上這份是哪一版。
       ⚠️ 這是唯一允許出現在播放器 UI 上的「文字」，因為它**指認語言本身**
       （EN／中文），不需要、也不應該被翻譯。 */
    '.dp-lang{padding:2px 9px;margin-right:2px;border-radius:999px;font-size:12px;',
    '  font-weight:700;letter-spacing:.04em;background:rgba(255,255,255,.16)}',
    /* 點畫面左／右半邊翻頁：透明感應區，避開右下角控制列 */
    '.dp-tap{position:fixed;top:0;height:100vh;width:38vw;z-index:20;cursor:pointer}',
    '.dp-tap.l{left:0} .dp-tap.r{right:0}',
    /* 講者備忘：⚠️ 預設隱藏，且只在播放模式存在 */
    '.dp-notes{position:fixed;left:0;right:0;bottom:0;z-index:30;height:' + NOTES_H + 'px;',
    '  display:none;padding:20px 26px 22px;overflow:auto;background:#0F1124;color:#E7EAF7;',
    '  font:400 19px/1.55 system-ui,"Noto Sans TC",sans-serif;white-space:pre-wrap;',
    '  border-top:3px solid #F2B705}',
    'body.dp-notes-on .dp-notes{display:block}',
    /* 總覽網格 */
    // ⚠️ align-items:start 不可省：格子的內容是 position:absolute 的縮圖，
    //    自然高度是 0；沒有它，列高會被算成 0 而讓 aspect-ratio 失效，上下兩列會疊在一起。
    '.dp-grid{position:fixed;inset:0;z-index:50;display:none;overflow:auto;padding:26px;',
    '  align-items:start;align-content:start;',
    '  background:rgba(10,11,26,.94);grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}',
    'body.dp-grid-on .dp-grid{display:grid}',
    // ⚠️ 用 height:0 + padding-bottom:56.25% 撐出 16:9，**不要用 aspect-ratio**：
    //    格子裡的縮圖是 position:absolute（自然高 0），實測 aspect-ratio 算出來的高度
    //    不會回饋給 grid 的列高 → 列高只有 152px、格子卻是 223px，上下兩列會疊在一起。
    //    百分比 padding 是對自己的寬度算的，會正常參與列高計算。
    '.dp-cell{position:relative;cursor:pointer;border:3px solid transparent;border-radius:6px;',
    '  overflow:hidden;background:#fff;height:0;padding-bottom:56.25%}',
    '.dp-cell.cur{border-color:#F2B705}',
    '.dp-cell .slide{position:absolute;top:0;left:0;display:flex;transform-origin:top left;',
    '  box-shadow:none;pointer-events:none}',
    '.dp-cell .dp-i{position:absolute;right:0;bottom:0;z-index:2;padding:2px 9px;',
    '  background:rgba(20,22,44,.8);color:#fff;font:700 15px/1.5 system-ui,sans-serif}',
    /* 黑屏 */
    '.dp-black{position:fixed;inset:0;z-index:60;background:#000;display:none}',
    'body.dp-black-on .dp-black{display:block}'
  ].join('\n');
  var st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  var el = function (tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };

  /* ── UI（全部由 JS 建，raw 模式下這些節點根本不存在）────────────────── */
  var tapL = el('div', 'dp-tap l'), tapR = el('div', 'dp-tap r');
  var notes = el('div', 'dp-notes');
  var black = el('div', 'dp-black');
  var grid = el('div', 'dp-grid');
  var bar = el('div', 'dp-bar');
  var bPrev = el('button', null, '&#8249;');      // ‹
  var bNext = el('button', null, '&#8250;');      // ›
  var num = el('span', 'dp-num', '1 / ' + slides.length);
  // 語言標記由 render_deck.py 寫在 <html data-lang-label>；沒有就不顯示。
  var langLabel = document.documentElement.getAttribute('data-lang-label');
  var lang = langLabel ? el('span', 'dp-lang', langLabel) : null;
  var bGrid = el('button', null, '&#9638;');      // ▦ 總覽（G）
  var bNotes = el('button', null, '&#9776;');     // ☰ 備忘（N）
  // 全螢幕：⛶（U+26F6）在多數系統字型裡缺字會變豆腐框，改畫四個角（零依賴，任何環境都畫得出來）
  var bFull = el('button', null,
    '<svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8"><path d="M1.5 5.5v-4h4M14.5 5.5v-4h-4M1.5 10.5v4h4M14.5 10.5v4h-4"/></svg>');
  [bPrev, bNext, num, lang, bGrid, bNotes, bFull].forEach(function (x) {
    if (x) bar.appendChild(x);
  });
  [tapL, tapR, notes, grid, black, bar].forEach(function (x) { document.body.appendChild(x); });
  document.body.classList.add('deck-play');

  /* ── 縮放：維持 16:9 等比，備忘展開時從可用高度扣掉面板 ───────────────── */
  function layout() {
    var vw = window.innerWidth;
    var vh = window.innerHeight - (notesOn ? NOTES_H : 0);
    var k = Math.min(vw / W, vh / H);
    var tx = (vw - W * k) / 2, ty = (vh - H * k) / 2;
    var s = slides[idx];
    if (s) s.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + k + ')';
  }

  function go(i) {
    idx = Math.max(0, Math.min(slides.length - 1, i));   // 首尾不 wrap
    slides.forEach(function (s, k) { s.classList.toggle('dp-on', k === idx); });
    num.textContent = (idx + 1) + ' / ' + slides.length;
    bPrev.disabled = idx === 0;
    bNext.disabled = idx === slides.length - 1;
    notes.textContent = slides[idx].getAttribute('data-notes') || '';
    if (gridOn) markGrid();
    layout();
  }

  function setNotes(on) {
    notesOn = on;
    document.body.classList.toggle('dp-notes-on', on);
    layout();
  }

  /* 總覽網格：用 cloneNode 縮圖，⚠️ 一定要清掉 id（不清會與本尊撞 id）。
     觀察到的實務上限約 20 頁 —— 再多就得捲動，「回到剛剛那頁」反而更慢。 */
  function buildGrid() {
    grid.innerHTML = '';
    slides.forEach(function (s, i) {
      var cell = el('div', 'dp-cell');
      var c = s.cloneNode(true);
      c.removeAttribute('id');
      c.classList.add('dp-on');
      c.removeAttribute('data-notes');
      cell.appendChild(c);
      cell.appendChild(el('div', 'dp-i', String(i + 1)));
      cell.addEventListener('click', function () { setGrid(false); go(i); });
      grid.appendChild(cell);
    });
    // 縮圖比例要等版面算完才量得到，故延到下一個 frame
    requestAnimationFrame(function () {
      [].forEach.call(grid.children, function (cell) {
        var k = cell.clientWidth / W;
        cell.firstChild.style.transform = 'scale(' + k + ')';
      });
      markGrid();
    });
  }

  function markGrid() {
    [].forEach.call(grid.children, function (cell, i) {
      cell.classList.toggle('cur', i === idx);
    });
  }

  function setGrid(on) {
    gridOn = on;
    document.body.classList.toggle('dp-grid-on', on);
    if (on) buildGrid();
  }

  function setBlack(on) {
    blackOn = on;
    document.body.classList.toggle('dp-black-on', on);
  }

  function toggleFull() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen)
      document.documentElement.requestFullscreen();
  }

  bPrev.onclick = function () { go(idx - 1); };
  bNext.onclick = function () { go(idx + 1); };
  bGrid.onclick = function () { setGrid(!gridOn); };
  bNotes.onclick = function () { setNotes(!notesOn); };
  bFull.onclick = toggleFull;
  tapL.onclick = function () { if (!gridOn) go(idx - 1); };
  tapR.onclick = function () { if (!gridOn) go(idx + 1); };
  black.onclick = function () { setBlack(false); };

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key;
    if (k === 'Escape') { if (gridOn) { setGrid(false); e.preventDefault(); } return; }
    if (blackOn) { setBlack(false); e.preventDefault(); return; }   // 黑屏時任何鍵先恢復
    if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'Spacebar') { go(idx + 1); e.preventDefault(); }
    else if (k === 'ArrowLeft' || k === 'PageUp') { go(idx - 1); e.preventDefault(); }
    else if (k === 'Home') { go(0); e.preventDefault(); }
    else if (k === 'End') { go(slides.length - 1); e.preventDefault(); }
    else if (k === 'n' || k === 'N') { setNotes(!notesOn); e.preventDefault(); }
    else if (k === 'g' || k === 'G') { setGrid(!gridOn); e.preventDefault(); }
    else if (k === 'f' || k === 'F') { toggleFull(); e.preventDefault(); }
    else if (k === '.') { setBlack(true); e.preventDefault(); }
  });

  window.addEventListener('resize', function () { layout(); if (gridOn) buildGrid(); });
  document.addEventListener('fullscreenchange', layout);

  go(0);
  document.body.classList.add('dp-hint');       // 開場先把控制列顯出來，三秒後淡回去
  setTimeout(function () { document.body.classList.remove('dp-hint'); }, 3000);

  window.deckPlayer = {go: go, layout: layout, notes: setNotes, grid: setGrid, count: slides.length};
})();
