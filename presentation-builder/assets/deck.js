/* 進度報告投影片 — 彙整 deck 的執行時功能：頁數切換 / 進出投影片 / 匯出 PPTX。
   支援新版 .slide-outer/.slide 與舊版 .block 兩種結構。
   依賴 head 已載入 mermaid、html2canvas、pptxgenjs。檔名取 window.DECK_NAME。 */
(function () {
  mermaid.initialize({ startOnLoad: false, theme: 'base', flowchart: { curve: 'basis' }, themeVariables: { fontSize: '13px' } });

  // 支援新版 .slide-outer 與舊版 .block
  const newSlides = Array.from(document.querySelectorAll('.slide-outer'));
  const oldBlocks = Array.from(document.querySelectorAll('.block'));
  const useNew = newSlides.length > 0;
  const slides = useNew ? newSlides : oldBlocks;

  const STORAGE_KEY = 'deck_idx_' + (window.DECK_NAME || location.pathname);
  let idx = Math.min(+(localStorage.getItem(STORAGE_KEY) || 0), slides.length - 1);
  let slideMode = false, navCollapsed = false;

  /* ── 縮放：將 .slide 填滿 .slide-outer（scroll 模式） ── */
  function scaleSlideInOuter(outer) {
    const inner = outer.querySelector('.slide');
    if (!inner) return;
    const scale = outer.offsetWidth / 1280;
    inner.style.transform = `scale(${scale})`;
    inner.style.top = '0';
    inner.style.left = '0';
  }

  /* ── 縮放：將 .slide 填滿視窗置中（slide 模式，扣掉導覽列高度） ── */
  function scaleSlideFullscreen(outer) {
    const inner = outer.querySelector('.slide');
    if (!inner) return;
    const vw = window.innerWidth, vh = window.innerHeight;
    const navEl = document.getElementById('nav');
    const navH = (!navCollapsed && navEl) ? navEl.offsetHeight : 0;
    const availH = vh - navH;
    const scale = Math.min(vw / 1280, availH / 720);
    const tx = (vw - 1280 * scale) / 2;
    const ty = (availH - 720 * scale) / 2;
    inner.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    inner.style.top = '0';
    inner.style.left = '0';
  }

  function scaleAll() {
    if (!useNew) return;
    if (slideMode) {
      const active = slides[idx];
      if (active) scaleSlideFullscreen(active);
    } else {
      slides.forEach(scaleSlideInOuter);
    }
  }

  window.addEventListener('resize', scaleAll);

  function renderDots() {
    const dots = document.getElementById('dots');
    if (!dots) return;
    dots.innerHTML = '';
    slides.forEach((_, i) => {
      const d = document.createElement('div');
      d.className = 'dot' + (i === idx ? ' on' : '');
      d.onclick = () => go(i);
      dots.appendChild(d);
    });
  }

  function go(i) {
    idx = Math.max(0, Math.min(slides.length - 1, i));
    localStorage.setItem(STORAGE_KEY, idx);
    slides.forEach((s, k) => s.classList.toggle('active', k === idx));
    document.getElementById('prev').disabled = idx === 0;
    document.getElementById('next').disabled = idx === slides.length - 1;
    document.getElementById('count').textContent = (idx + 1) + ' / ' + slides.length;
    renderDots();
    window.scrollTo({ top: 0 });
    if (slideMode && useNew) scaleSlideFullscreen(slides[idx]);
  }

  function setMode(on) {
    slideMode = on;
    document.body.classList.toggle('slides', on);
    document.getElementById('modeBtn').textContent = on ? '◼ 退出投影片' : '▶ 投影片模式';
    if (!on) {
      // 退出時重置導覽列收合狀態
      navCollapsed = false;
      const navEl = document.getElementById('nav');
      if (navEl) navEl.classList.remove('nav-collapsed');
      const navToggleBtn = document.getElementById('navToggle');
      if (navToggleBtn) { navToggleBtn.textContent = '▼'; navToggleBtn.title = '收合導覽列'; }
    }
    if (on) {
      go(idx);
    } else {
      // 回到 scroll 模式時重新縮放所有 slide
      if (useNew) slides.forEach(scaleSlideInOuter);
    }
  }

  document.getElementById('prev').onclick = () => go(idx - 1);
  document.getElementById('next').onclick = () => go(idx + 1);
  document.getElementById('modeBtn').onclick = () => setMode(!slideMode);

  const navToggleBtn = document.getElementById('navToggle');
  if (navToggleBtn) {
    navToggleBtn.onclick = () => {
      navCollapsed = !navCollapsed;
      const navEl = document.getElementById('nav');
      if (navEl) navEl.classList.toggle('nav-collapsed', navCollapsed);
      navToggleBtn.textContent = navCollapsed ? '▲' : '▼';
      navToggleBtn.title = navCollapsed ? '展開導覽列' : '收合導覽列';
      if (slideMode && useNew) scaleSlideFullscreen(slides[idx]);
    };
  }
  document.addEventListener('keydown', (e) => {
    if (!slideMode) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { go(idx + 1); e.preventDefault(); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { go(idx - 1); e.preventDefault(); }
    if (e.key === 'Escape') setMode(false);
    if ((e.key === 'c' || e.key === 'C') && !e.ctrlKey && !e.metaKey) { copyCurrentSlide(); e.preventDefault(); }
  });

  /* ── 把單一 slide 以 1:1 原尺寸截圖成 canvas；影片區域挖白（回傳其相對位置供後續嵌入）。
     匯出 PPTX 與「複製本頁」共用同一套擷取邏輯，畫質一致。 ── */
  async function renderSlideToCanvas(s) {
    let captureEl = s;
    let restoreTransform = null;

    // 找出 [data-pptx-video] 元素，截圖前從 DOM 移除，截完再插回
    const videoEls = [...s.querySelectorAll('[data-pptx-video]')];
    videoEls.forEach(v => { v._nextSibling = v.nextSibling; v._parent = v.parentNode; v.remove(); });

    // html2canvas 不支援 object-fit:contain，會把圖片直接拉伸塞進 box 造成變形/壓縮。
    // 截圖前手動算出等比例縮放後的實際顯示尺寸，暫時覆寫成固定 width/height，截完再還原。
    const fitImgs = [...s.querySelectorAll('img')].filter(img => {
      const fit = getComputedStyle(img).objectFit;
      return fit === 'contain' && img.naturalWidth && img.naturalHeight;
    });
    const fitImgSnapshots = fitImgs.map(img => {
      const prevCss = img.style.cssText;
      const boxW = img.clientWidth;
      const boxH = img.clientHeight;
      const scale = Math.min(boxW / img.naturalWidth, boxH / img.naturalHeight);
      img.style.objectFit = 'none';
      img.style.width = (img.naturalWidth * scale) + 'px';
      img.style.height = (img.naturalHeight * scale) + 'px';
      img.style.display = 'block';
      img.style.margin = '0 auto';
      return { img, prevCss };
    });

    if (useNew) {
      // 對 .slide 以 1:1 原尺寸截圖，得到最高畫質
      const inner = s.querySelector('.slide');
      if (inner) {
        restoreTransform = inner.style.transform;
        inner.style.transform = 'none';
        captureEl = inner;
      }
    }

    const canvas = await html2canvas(captureEl, {
      scale: 1.5,
      backgroundColor: '#ffffff',
      useCORS: true,
      width: useNew ? 1280 : undefined,
      height: useNew ? 720 : undefined,
    });

    if (restoreTransform !== null) {
      captureEl.style.transform = restoreTransform;
    }
    videoEls.forEach(v => { v._parent.insertBefore(v, v._nextSibling); });
    fitImgSnapshots.forEach(({ img, prevCss }) => { img.style.cssText = prevCss; });

    // 把影片區域從截圖 canvas 挖白，避免後續影片層重疊
    const ctx = canvas.getContext('2d');
    const slideW = captureEl.offsetWidth || 1280;
    const slideH = captureEl.offsetHeight || 720;
    const base = captureEl.getBoundingClientRect();
    const videoRects = videoEls.map(v => {
      const vr = v.getBoundingClientRect();
      return {
        v,
        rx: (vr.left - base.left) / slideW,
        ry: (vr.top - base.top) / slideH,
        rw: vr.width / slideW,
        rh: vr.height / slideH,
      };
    });
    for (const { rx, ry, rw, rh } of videoRects) {
      ctx.clearRect(rx * canvas.width, ry * canvas.height, rw * canvas.width, rh * canvas.height);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(rx * canvas.width, ry * canvas.height, rw * canvas.width, rh * canvas.height);
    }
    return { canvas, videoRects };
  }

  /* ── 輕量提示條（複製 / 下載結果回饋，避免 alert 打斷） ── */
  function toast(msg, isErr) {
    let t = document.getElementById('deckToast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'deckToast';
      t.style.cssText = 'position:fixed;left:50%;top:20px;transform:translateX(-50%);z-index:9999;'
        + 'padding:10px 18px;border-radius:8px;font-size:14px;font-weight:600;color:#fff;'
        + 'box-shadow:0 4px 14px rgba(0,0,0,.25);transition:opacity .25s;pointer-events:none;';
      document.body.appendChild(t);
    }
    t.style.background = isErr ? '#dc2626' : '#16a34a';
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.style.opacity = '0'; }, 2400);
  }

  /* ── 複製當前頁成 PNG 圖片：優先寫入剪貼簿；非安全內容（如 http 區網 IP）不支援時，
     自動 fallback 成下載單頁 PNG。快捷鍵 c。 ── */
  async function copyCurrentSlide() {
    const btn = document.getElementById('copyImgBtn');
    if (btn) { btn.disabled = true; btn.textContent = '擷取中…'; }
    try {
      const { canvas } = await renderSlideToCanvas(slides[idx]);
      const blob = await new Promise(res => canvas.toBlob(res, 'image/png'));
      const pageNo = String(idx + 1).padStart(2, '0');
      // 剪貼簿寫圖需要安全內容（https / localhost / file://）；http 區網 IP 下不可用
      if (navigator.clipboard && window.ClipboardItem && window.isSecureContext) {
        try {
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
          toast('已複製第 ' + (idx + 1) + ' 頁到剪貼簿');
          return;
        } catch (e) { /* 落到下載 fallback */ }
      }
      // fallback：下載單頁 PNG
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (window.DECK_NAME || 'slide') + '-' + pageNo + '.png';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
      toast('此環境不支援複製到剪貼簿，已改下載第 ' + (idx + 1) + ' 頁 PNG');
    } catch (e) {
      console.error(e);
      toast('複製失敗：' + e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⧉ 複製本頁'; }
    }
  }

  const copyImgBtn = document.getElementById('copyImgBtn');
  if (copyImgBtn) copyImgBtn.onclick = copyCurrentSlide;

  async function exportPptx() {
    const btn = document.getElementById('exportBtn');
    const wasSlides = slideMode;
    btn.disabled = true; btn.textContent = '輸出中…';
    if (wasSlides) setMode(false);
    await new Promise(r => setTimeout(r, 80));
    try {
      const pptx = new PptxGenJS();
      pptx.defineLayout({ name: 'W16x9', width: 13.333, height: 7.5 });
      pptx.layout = 'W16x9';
      const PW = 13.333, PH = 7.5;

      // 自動產封面投影片（native text，可在 PowerPoint 編輯）；只在匯出 PPTX 時產生，
      // deck.html 本身（瀏覽/編輯用的中間產物）不會有這張封面 slide。
      // 但若 deck.html 是用 --titlecover 建置的，第一頁已經是靜態封面（data-titlecover="1"），
      // 這裡就不再重複加一張，避免匯出的 PPTX 開頭出現兩張「進度報告」封面。
      const hasStaticCover = slides[0] && slides[0].dataset.titlecover === '1';
      if (!hasStaticCover) {
        const cover = pptx.addSlide();
        cover.background = { color: 'FFFFFF' };
        cover.addText('進度報告', { x: 0, y: 2.2, w: PW, h: 1.1, align: 'center', fontSize: 44, bold: true, color: '1f2329' });
        cover.addText(window.DECK_DATE || '', { x: 0, y: 3.45, w: PW, h: 0.65, align: 'center', fontSize: 22, color: '6b7280' });
        cover.addText(window.DECK_PRESENTER || '', { x: 0, y: 4.2, w: PW, h: 0.65, align: 'center', fontSize: 22, bold: true, color: '344054' });
      }

      // 嘗試把影片 src fetch 成 base64；file:// 下 Chrome 會失敗則 fallback
      async function fetchVideoBase64(src) {
        try {
          const resp = await fetch(src);
          if (!resp.ok) return null;
          const buf = await resp.arrayBuffer();
          const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
          return 'data:video/mp4;base64,' + b64;
        } catch { return null; }
      }

      for (const s of slides) {
        const { canvas, videoRects } = await renderSlideToCanvas(s);
        const img = canvas.toDataURL('image/png');
        const slide = pptx.addSlide();
        slide.background = { color: 'FFFFFF' };
        slide.addImage({ data: img, x: 0, y: 0, w: PW, h: PH });

        // 把影片嵌入 PPT（放在挖空的位置）
        for (const { v, rx, ry, rw, rh } of videoRects) {
          const mediaData = await fetchVideoBase64(v.src || v.currentSrc);
          if (mediaData) {
            slide.addMedia({ type: 'video', data: mediaData, extension: 'mp4',
              x: rx * PW, y: ry * PH, w: rw * PW, h: rh * PH });
          } else {
            // fetch 失敗（file:// CORS）：截當前幀作 fallback
            const fc = document.createElement('canvas');
            fc.width = v.videoWidth || 640; fc.height = v.videoHeight || 360;
            fc.getContext('2d').drawImage(v, 0, 0, fc.width, fc.height);
            slide.addImage({ data: fc.toDataURL('image/png'),
              x: rx * PW, y: ry * PH, w: rw * PW, h: rh * PH });
          }
        }
      }
      await pptx.writeFile({ fileName: (window.DECK_NAME || 'progress-report') + '.pptx' });
    } catch (e) {
      console.error(e);
      alert('匯出失敗：' + e.message);
    } finally {
      if (wasSlides) setMode(true);
      btn.disabled = false;
      btn.textContent = '↓ 匯出 PPTX';
    }
  }

  document.getElementById('exportBtn').onclick = exportPptx;

  /* ── 匯出可攜版 HTML：圖片依實際顯示尺寸重新編碼（縮圖+壓縮）並內嵌成 data URI，
     CDN 的 mermaid / html2canvas / pptxgenjs 也內嵌成腳本內容，整份檔案可離線、脫離資料夾單獨搬動 ── */
  async function blobToDataURL(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // 用已經載入好的 <img> 元素，依「實際顯示尺寸」（乘 2 保留清晰度，不超過原始尺寸）
  // 重新畫到 canvas 輸出成 JPEG，避免直接內嵌原始大圖把 HTML 撐得過大
  function liveImgToDataURL(liveImg) {
    try {
      const dispW = liveImg.clientWidth || liveImg.naturalWidth || 1;
      const dispH = liveImg.clientHeight || liveImg.naturalHeight || 1;
      const w = Math.max(1, Math.min(Math.round(dispW * 2), liveImg.naturalWidth || dispW * 2));
      const h = Math.max(1, Math.min(Math.round(dispH * 2), liveImg.naturalHeight || dispH * 2));
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      c.getContext('2d').drawImage(liveImg, 0, 0, w, h);
      return c.toDataURL('image/jpeg', 0.85);
    } catch (e) { return null; } // canvas 被跨源污染（tainted）等情況，交給呼叫端 fallback
  }

  async function exportPortableHtml() {
    const btn = document.getElementById('exportPortableBtn');
    btn.disabled = true; btn.textContent = '輸出中…';
    try {
      const clone = document.documentElement.cloneNode(true);

      // 圖片內嵌成 data URI（依畫面顯示尺寸縮圖 + JPEG 壓縮，避免檔案過大）
      const liveImgs = document.querySelectorAll('img');
      const cloneImgs = clone.querySelectorAll('img');
      for (let i = 0; i < cloneImgs.length; i++) {
        const src = cloneImgs[i].getAttribute('src');
        if (!src || src.startsWith('data:')) continue;
        let dataUrl = liveImgToDataURL(liveImgs[i]);
        if (!dataUrl) {
          try {
            const resp = await fetch(new URL(src, location.href).href);
            if (resp.ok) dataUrl = await blobToDataURL(await resp.blob());
          } catch (e) { /* 放棄，保留原連結 */ }
        }
        if (dataUrl) cloneImgs[i].setAttribute('src', dataUrl);
      }

      // 外部 <script src> 內嵌成內容（含 CDN 的 mermaid / html2canvas / pptxgenjs），離線也能開
      const scripts = clone.querySelectorAll('script[src]');
      for (const s of scripts) {
        const src = s.getAttribute('src');
        try {
          const resp = await fetch(src);
          const text = await resp.text();
          const inline = document.createElement('script');
          inline.textContent = text;
          s.replaceWith(inline);
        } catch (e) {
          console.warn('腳本內嵌失敗，保留原連結（需連網才能運作）:', src, e);
        }
      }

      const html = '<!DOCTYPE html>\n' + clone.outerHTML;
      const blob = new Blob([html], { type: 'text/html' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (window.DECK_NAME || 'deck') + '_portable.html';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error(e);
      alert('匯出可攜版失敗：' + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = '⇓ 匯出可攜版 HTML';
    }
  }

  const exportPortableBtn = document.getElementById('exportPortableBtn');
  if (exportPortableBtn) exportPortableBtn.onclick = exportPortableHtml;

  /* mermaid 量標籤用的是 getBoundingClientRect，會吃到 .slide 的 transform: scale()。
     渲染期間先把縮放拿掉（見 slides.css 的 .mermaid-measuring），量完再還原，
     否則節點框會照縮放比例做小，文字爆框被裁掉。 */
  document.body.classList.add('mermaid-measuring');
  mermaid.run().finally(() => {
    document.body.classList.remove('mermaid-measuring');
    if (useNew) slides.forEach(scaleSlideInOuter);
    renderDots();
    setMode(true);
  });
})();
