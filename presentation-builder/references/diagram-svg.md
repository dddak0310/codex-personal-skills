# 手刻流程／回圈示意圖（HTML 方塊 + SVG 連線）

適用：mermaid 排不出來的版面（分支回圈要走特定路徑、要在節點裡放 pill／小圖、要精準控制位置），
以及 §0 描述的「訊息靠量值編碼」的圖。
**mermaid 畫得出來就用 mermaid**（見 `diagram-mermaid.md`）；這份只講**自己用絕對定位方塊 + SVG 連線**、
或整張 inline `<svg>` 手刻的做法。

§0 講**該不該畫、畫什麼**；§1 之後講**怎麼畫不出錯**。這類圖最常見的失敗是「箭頭跟文字重疊」
「箭頭不見」「線對不到框」——這三件事**都不是美感問題，是座標系與 CSS 作用域的問題**，
靠反覆微調數字修不好，要照下面的規則從結構改。

---

## 0. 什麼時候該手繪：四個觸發訊號

預設仍然是表格與 mermaid。但下面四種情況，**表格與 mermaid 會主動遺失訊息**，這時才手繪。
判準不是「這頁好不好看」，而是**「這頁的訊息是靠什麼編碼的」**。

| 訊號 | 具體長相 | 表格／mermaid 為什麼不夠 | 畫成什麼 |
|---|---|---|---|
| **兩個數字並排但不可比** | 「83.49% → 98.52%」其實換了母體 | 表格的預設語義是「同類項並列」，一旦不同類，表格等於在騙人 | 漏斗（母體收窄）＋ 兩條正確率堆疊條，把「分母變了」畫出來 |
| **數字之間的關係比數字本身重要** | 52.35 → 40.61 → 6.71：兩刀貢獻是 −11.7 vs −33.9，差三倍 | 三個數字並排看不出**不對稱**；長度才看得出來 | 等比例水平長條 ＋ 各段差額標註 |
| **訊息的本質是時間或順序** | 「完成信最多被拖延 300 秒」「四個 session 各自死在不同時間點」 | 寫在文字裡「300 秒」只是形容詞，畫在軸上才是個量 | 同一條時間軸上下對照；多主體用泳道，終點標 ✓／✕ |
| **多個項目擠在同一個狀態** | 待決 8 列中有 6 列都是「已 commit 未 push」 | 「都卡在同一格」才是訊息，表格會把它拆成 6 行各自獨立的文字，訊息被稀釋 | 管線圖＋閘門：所有項目的箭頭匯進同一個紅色關卡 |

反過來，**這些情況不要手繪**：節點 ≤3 個且只是拓樸關係（一源兩消費端）——mermaid 就夠了，
手繪只是換皮；索引性質的主題地圖——表格就是對的形式。

### 三條自檢

- **同尺寸測試**：把圖裡所有方塊改成一樣大、位置隨便排，意思有沒有變？**沒變 → 那不是圖，
  是加了框的表格**，退回用 `ruletable`。量值一定要落在長度、位置或軸上，不能只寫在框裡。
- **takeaway 裡的列舉是降級的訊號**：`.takeaway` 若出現「四個中只有一個走到底」「六項全部卡在 X」
  這種**列舉句**，代表有結構被壓成一句話。那通常就是本頁最強的訊息，考慮升格成圖。
- **每個元素都要帶真實識別字**：秒數、commit hash、筆數、repo 名要直接印在圖上。
  不帶數字的示意圖不如表格。

### 成本護欄

手繪一張要算座標、要 preview 截圖驗證（§7），**一份 deck 最多 2–3 張**，挑訊息最強的那幾張畫，
其餘維持表格／mermaid。不要每頁都想畫圖——整份 deck 每頁都是圖，跟每頁都是表格一樣沒有重點。

### 兩種手繪型態

- **整張 inline `<svg>`**（本節四個訊號多屬此類）：長條、時間軸、漏斗、閘門這類**幾何即語義**的圖，
  直接一個 `<svg viewBox="0 0 W H">` 畫到底，不需要 HTML 方塊。座標規則同 §1，
  `viewBox` 寬取 slide 可用寬（見 `figures.md` §1 的對照表）。
  已在 deck 裡用過的實例：`20260717/04-why-label.html`、`20260807/27-confusion-bar-grid.html`。
- **HTML 方塊 + SVG 連線**（§1 之後的主題）：節點裡要放清單、pill、多行文字時用這種，
  文字排版交給 HTML，只有線走 SVG。

---

## 1. 鐵則：一套座標系，全部用 px

畫布容器與 SVG 必須 1:1 對應，節點用 px 定位：

```html
<div class="board">                          <!-- position:relative; height:492px（固定，不要 flex:1） -->
  <svg class="lines" viewBox="0 0 1196 492"  <!-- 寬高 = board 的 px 寬高 -->
       preserveAspectRatio="xMidYMid meet">  <!-- 絕不用 none -->
  </svg>
  <div class="card" style="left:280px;top:54px;width:262px;height:252px"></div>
</div>
```

三個具體禁令：

- **節點不要用 `%` 定位。** `%` 是相對 board，SVG 是相對 viewBox，只要兩者比例有一點差異，
  線頭就永遠差幾十 px，怎麼調都對不準。
- **board 不要用 `flex:1` 撐高。** 高度不確定就無法事先算 SVG 座標。先做高度預算（見 §5）
  再寫死 `height`。
- **`preserveAspectRatio` 不要用 `none`。** 它會把圖非等比拉伸，箭頭變扁、圓角變形，
  而且 viewBox 與 CSS px 從此不再等價。

board 寬度就是 slide 內容寬（1280 − 左右 padding）。`viewBox` 的寬高直接抄這兩個數字。

## 2. 箭頭：marker 的兩個必踩坑

```html
<defs>
  <marker id="ar-blue" markerUnits="userSpaceOnUse"
          markerWidth="13" markerHeight="13" refX="11" refY="6.5" orient="auto">
    <path d="M0,0 L13,6.5 L0,13 Z" fill="#2f54eb"/>
  </marker>
</defs>
<path class="edge blue" d="M550 180 L576 180" marker-end="url(#ar-blue)"/>
```

**坑 1：`markerUnits` 預設是 `strokeWidth`。** 沒寫的話箭頭實際大小 = `markerWidth × stroke-width`。
線寬 5 就是 65px 的巨大三角形，一定會壓到旁邊的字——這就是「箭頭和文字重疊」最常見的成因。
**一律寫 `markerUnits="userSpaceOnUse"`**，這樣 `markerWidth` 就是實際 px。

**坑 2：`.lines path { fill:none }` 會把箭頭殺掉。** `<marker>` 裡的三角形也是 `.lines` 的後代 path，
會一起被選到；CSS 的 `fill:none` 勝過 marker 上的 `fill="…"` presentation attribute，
於是箭頭渲染成透明——線在、箭頭不見。

**線一律掛 class，CSS 只選 class：**

```css
.lines .edge { fill:none; stroke-linecap:round; stroke-linejoin:round; stroke-width:4 }
.lines .edge.gray  { stroke:#98a2b3 }
.lines .edge.blue  { stroke:#2f54eb }
.lines .edge.green { stroke:#52c41a }
.lines .edge.dashed{ stroke-dasharray:10 7 }
```

## 3. 節點與連線的座標怎麼算

**同一排的節點統一 `top` 與 `height`**，橫向箭頭的 y 就只有一個值：`y = top + height/2`。
高度不齊就得每條線各算一次 y，錯一條就歪一條。

寬度排版先列式再填數字，總和必須等於 board 寬：

```
左邊距 + Σ節點寬 + Σ間隙 + 右邊距 = viewBox 寬
20 + (218+262+262+232) + (42+42+96) + 22 = 1196
```

橫向箭頭兩端各離節點邊 6–10px：節點右緣 238 → `M246 180 L272 180`（下一個節點左緣 280）。

**間隙要先分配給箭頭，再考慮標籤。** 42px 的間隙塞不下「通過」這種標籤——pill 會把整條箭頭
蓋光，只剩箭尾露出來。要嘛把該段間隙加寬到 90px 以上，要嘛把標籤移到線的正上方
（同一 x 範圍、y 往上退 40px 以上，見 §4）。

## 4. 回圈邊：走廊 + 直角，不要斜穿

回頭邊斜著從一個節點拉到另一個節點，一定會壓過中間的節點與文字。正確走法是**繞到節點列外側的
一條專用走廊**，全程直角、轉角用 `Q` 收圓角：

```
M 來源節點底邊中心x, 節點底+8      ← 垂直下降
L 同x, 走廊y-20
Q 同x, 走廊y  同x-20, 走廊y        ← 圓角轉彎
L 目標x+20, 走廊y                  ← 水平回走
Q 目標x, 走廊y  目標x, 走廊y-20
L 目標x, 目標節點底+12             ← 垂直上升，箭頭朝上
```

實例：`M715 314 L715 415 Q715 435 695 435 L431 435 Q411 435 411 415 L411 318`

- 起訖的 x 用節點的**中心 x**（`left + width/2`），線才會從框正中出入。
- 走廊 y 放在節點列下方，離節點底邊 100px 上下；走廊下方再留 30–50px 才到 board 底。
- 回圈用虛線（`stroke-dasharray`）與主流程區隔，語意更清楚。

## 5. 分支標籤：白底 pill 蓋在線上，線不穿過文字

「通過／不通過」這類標籤不要當成 SVG `<text>` 疊在線上（沒有背景、線會從字中間穿過）。
用 HTML 元素做成白底 pill，`z-index` 壓在 SVG 之上，正好蓋住線的一小段：

```css
.edge-label { position:absolute; z-index:2; display:flex; align-items:center; justify-content:center;
              border-radius:999px; background:#fff; border:1.5px solid …; white-space:nowrap }
```

pill 要**置中於它標註的那段線**：水平回廊上就用 `(左x + 右x)/2`，寬度不要吃到兩端的轉角
（兩側各留 15px 以上）。放不下就改放線的正上方，別硬擠。

## 6. 高度預算：先算，再寫死 board 高度

slide 是 1280×720。以 `padding:24px 42px 20px` 的 flex column 為例：

| 項目 | 高 |
|---|---|
| 上下 padding | 44 |
| h2（32px / 1.2） | 39 |
| 副標（16px / 1.65） | 27 |
| 統計卡列 | 52 |
| 來源註 | 18 |
| flex gap ×4 | 40 |
| **剩給 board** | **≈ 500** |

`position:absolute` 的 `.slide-label` 不是 flex item，不佔高度。算完取整數（例如 492）寫進
`.board{height:…}` 與 `viewBox`，兩處必須是同一個數字。

## 7. 驗證：一定要看渲染結果

座標對不對、有沒有壓字，**看程式碼看不出來**。改完必截圖，並放大看每個箭頭端點：

```bash
python3 ~/.claude/skills/html-preview/scripts/serve_preview.py <頁面.html>
```

拿到網址後用瀏覽器截圖，再 zoom 到連線區域逐條確認：

1. 每條線的**兩端都有箭頭或明確起點**，箭頭沒被 pill 蓋掉
2. 沒有任何線穿過文字
3. 線頭離節點邊 6–10px，不貼死也不飄開
4. board 底部留白 < 60px（太多表示走廊或節點高度該往下調）

改完頁面記得重跑 `build.py` 更新 `deck.html`。
