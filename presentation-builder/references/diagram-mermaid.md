# Mermaid 流程圖

適用：節點是方框/菱形、連線是單純的上下或左右流向——**能用 mermaid 就用 mermaid**，
它會自己排版，不會有座標對不上的問題。

排不出來才改手刻（見 `diagram-svg.md`）：分支回圈要走特定路徑、節點裡要放 pill 或小圖、
要精準控制每個框的位置。

版型範例（Pipeline 流程圖、改前/改後比較）見 `SKILL.md` 的「版型」章節。

---

## 常踩的坑

0. **自己寫的頁面產生腳本，mermaid 初始化要照抄 `page-template.html` 的那段。**
   mermaid 決定節點框大小的方式，是把標籤塞進 DOM 後用 `getBoundingClientRect` 量；
   而 `.slide` 身上永遠帶著 `transform: scale(k)`（`slides.css` 用 container query 設的，
   deck 預設 k = 1040/1280 = 0.8125）。在縮放狀態下渲染，量到的尺寸就差 k 倍，
   **節點框比字小 23%，中文被裁掉——這就是「文字跑版」最常見的成因**。
   所以渲染期間一定要先把縮放拿掉：
   ```js
   mermaid.initialize({ startOnLoad: false, theme: 'base', flowchart: { curve: 'basis' },
                        themeVariables: { fontSize: '13px' } });
   document.body.classList.add('mermaid-measuring');   // slides.css 會把 .slide 的 transform 拿掉
   mermaid.run().finally(() => document.body.classList.remove('mermaid-measuring'));
   ```
   `deck.js` 與 `page-template.html` 都已內建這段；**不要用 `startOnLoad: true`**，
   那會在縮放還在的狀態下就渲染。用腳本大量產生投影片頁時（`_build_*_pages.py` 這類），
   TAIL 也要帶上這段，否則單頁預覽會跑版、甚至整張圖不渲染只印出原始碼。

1. **改字級要寫在圖表內容裡，不能只改頁面自己的 `<script>`。**
   單頁預覽時，頁面自己的 `mermaid.initialize({... fontSize: 'Npx' })` 有效；但彙整成 deck.html 後，所有頁面共用 `assets/deck.js` 裡「唯一一個」全域 `mermaid.initialize({... fontSize: '13px' })`，會蓋掉每頁自己的設定。所以要讓某張圖在 deck.html 裡也維持指定字級，必須把 init 指令直接寫進該圖表的內容第一行：
   ```
   <div class="mermaid" style="margin:0;width:100%;">
   %%{init: {"themeVariables": {"fontSize": "20px"}}}%%
   flowchart TB
       ...
   ```
   這個 `%%{init}%%` 指令是逐圖表生效，不受外層 `mermaid.initialize` 影響，單頁預覽跟 deck 彙整後都會一致。

2. **`.mermaid` 這個 div 要加 `width:100%`，否則不會撐滿容器。**
   `.mermaid` 預設只有 `display:flex;justify-content:center`（見 `slides.css`），沒有寬度設定。如果外層容器（例如兩欄並排的比較版型）用 `display:flex` 置中放圖表，`.mermaid` div 會 shrink-wrap 成 SVG 自己的原始大小再被置中——容器明明有空間，圖表卻沒撐滿，看起來字很小；若圖表原始大小反而比容器窄的可用寬度大，則會被壓縮到比預期小很多。兩種情況都要在 `.mermaid` 的 inline style 加上 `width:100%`：
   ```html
   <div class="mermaid" style="margin:0;width:100%;">
   ```
   加了之後，mermaid 產生的 SVG（本身已是 `width:100%`）才會真正貼合容器寬度，不管放大縮小都用滿可用空間。

3. **兩欄並排、其中一欄節點數較多時，字級難以在不壓縮的前提下對稱加大。**
   例如 flowchart 裡一排並列的節點數量不同（3 個 vs 4 個），在同樣欄寬下，節點多的那張圖需要的原始寬度更大，同樣字級會被壓縮得更小。優先用「加 `width:100%`」讓兩張圖各自撐滿欄寬；如果字級仍需要對稱視覺大小，可個別調整每張圖 `%%{init}%%` 裡的 fontSize 數值（欄寬相同時，節點數多的圖表通常要給稍小的 fontSize 才能跟節點少的圖表視覺大小一致），不要用不對稱欄寬去強行補償。

4. **圖表的長寬比要配合容器，`fontSize` 只決定形狀、不決定看起來多大。**
   SVG 是等比縮到容器內的，所以讀者看到的字級是
   `fontSize × min(容器寬/viewBox寬, 容器高/viewBox高)`。
   把 `fontSize` 調大只會讓 viewBox 一起變大，縮得更多，視覺上完全沒變大。
   真正有效的是**縮短比較長的那一邊**：
   - `flowchart TB` 的高度幾乎由「層數」決定，不是由字級決定。
   - **菱形 `{...}` 是高度殺手**：它要把標籤裝進菱形內，高寬各膨脹一倍左右。
     多行標籤的菱形尤其誇張——把 4 個菱形換成六角 `{{...}}` 並讓標籤變單行，
     實測 viewBox 從 706×1726 變成 705×650，同一個 632×586 的框裡
     有效字級從 5.1px 變成 13.4px。決策語意靠 `classDef` 顏色與 `-->|通過|` 邊標籤表達就夠。
   - 想要單行標籤又不想丟資訊，就把細節搬到圖下方的工具/註腳那一行。

5. **分支節點的宣告順序要跟左右排列一致，否則邊標籤會看起來接錯箱子。**
   mermaid 依宣告順序排同一層的節點，但**回頭邊（例如 `I -->|reset| B`）會把 `I` 拉走**，
   造成邊交叉、`|我們挑錯|` 這種標籤浮在別的節點正上方，讀者會誤讀。
   做法：分支邊按「希望的左→右順序」連續宣告，回頭邊寫在最後。

**改完圖一定要在瀏覽器上量一次，不要只看截圖。**
文字有沒有被裁、字會不會太小，肉眼在縮圖上看不準。deck 開好之後在 console 跑：

```js
document.querySelectorAll('.slide-outer').forEach((s, i) => {
  s.querySelectorAll('.mermaid svg').forEach(svg => {
    const vb = svg.getAttribute('viewBox').split(' ').map(Number);
    const box = svg.parentElement.getBoundingClientRect();
    const k = Math.min(box.width / vb[2], box.height / vb[3]);
    svg.querySelectorAll('foreignObject').forEach(fo => {
      const d = fo.querySelector('div'); if (!d) return;
      const ow = d.scrollWidth - +fo.getAttribute('width');
      const oh = d.scrollHeight - +fo.getAttribute('height');
      if (ow > 2 || oh > 2) console.warn('第' + (i+1) + '頁 文字爆框', d.textContent.trim());
    });
    console.log('第' + (i+1) + '頁 縮放 ' + k.toFixed(2));
  });
});
```

判讀：**爆框一律要修**（成因看第 0 點）；`縮放 × fontSize` 低於約 10px 就代表圖太細長，
照第 4 點縮短長邊，不要靠調 fontSize。
