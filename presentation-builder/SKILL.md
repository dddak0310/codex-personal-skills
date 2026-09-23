---
name: presentation-builder
description: >
  Build and edit weekly, monthly, and issue slide decks, then export to PPTX. Each slide is its own
  lightweight HTML page; a builder consolidates a folder into a deck.html with navigation and PPTX export.
  Trigger on presentation, slides, slide deck, ppt, pptx, 投影片, 簡報, 做成投影片, 匯出 PPTX,
  新增／編輯投影片或 slide page, 週報、月報、月會、進度報告、月會報告、weekly report,
  monthly report, issue report／issue 簡報, or 彙整／合併這週的投影片. Do not use for 工作日誌、
  工作紀錄、日誌整理、daily log, work log, or collecting/summarizing a day’s sessions, even when
  the result should be slides; use daily-work-log for those. An explicitly supplied weekly report
  date takes precedence. See references/weekly-report.md, references/monthly-report.md, and
  references/issue-report.md. Output goes under the resolved report root (e.g. REPORT_ROOT/YYYYMMDD-w/).
---

## 報告根目錄與工作日誌

## 選擇邊界

- 僅在使用者明確要跨週／跨月收攏內容，或要製作週報、月報、月會、issue 簡報、投影片／PPTX 時，使用本 skill。
- 不要用本 skill 處理「工作日誌」「工作紀錄」「日誌整理」「今天做了什麼」、單日 session 蒐集或單日 summary；即使最後想做投影片，也應先選 `daily-work-log`。
- `daily-work-log` 產生日報投影片時可能載入本 skill 的版型與 builder；那是呈現依賴，不代表本 skill 應接管日誌或 session 工作流。

這個 skill 的 `REPORT_ROOT` 只管理週報、月會與 issue 簡報；`daily-work-log` 有自己的
`DAILY_WORKLOG_ROOT`，每天使用一個來源日期目錄。不要把日報套用本節的週五日期或
`create_folder.sh` 規則。

所有週報、月會與 issue 簡報的資料夾都放在同一個 `REPORT_ROOT`。由
`scripts/report_root.sh` 依序解析：

1. 當次命令的 `WEEKLY_DECK_ROOT`；
2. 個人設定檔 `~/.config/presentation-builder/root`；
3. 從 shared `skills` repo 的 sibling layer 自動尋找 `${USER}-worklogs`；若環境布局不同，才用
   `WORKLOGS_PROJECTS_ROOT` 指定 sibling layer。

因此每個人都會把報告放在自己的 `${USER}-worklogs` repo，而不會共用其他人的工作日誌或把開發者
專屬絕對路徑寫進共享 skill。找不到自己的 repo 時會直接停止，不會靜默寫回舊的 meeting 目錄；
需要處理歷史目錄時，請用當次 `WEEKLY_DECK_ROOT` 明確指定。開始新報告時先跑：

```bash
REPORT_ROOT="$(bash ~/.codex/skills/presentation-builder/scripts/report_root.sh)"
```

新建週報使用 `${REPORT_ROOT}/YYYYMMDD-w/`，新建月報使用 `${REPORT_ROOT}/YYYYMMDD-m/`；既有純日期或舊命名資料夾只維持讀取與 build 相容，不重新命名。放進 Git 工作日誌時，提交簡報頁與產出的
`deck.html`；`data/` 下的 raw TSV/CSV/JSON、檢體／個案原始輸出與本機 preview symlink 不應直接
提交，必要證據應先做去識別化摘要。

### 週報與日報的目錄邊界

- **週報**：一個 `${REPORT_ROOT}/YYYYMMDD-w/` 代表整週，預設使用當週週五；若使用者明確指定報告
  日期（例如 `20260828`），就沿用該日期，不自行改成執行環境日期或下一個週五。同週新增或修改
  頁面都沿用這個目錄。
- **月會／issue 簡報**：一個目錄代表一份報告，日期或月份依對應 reference 的規則決定。
- **日報**：由 `daily-work-log` 建立 `${DAILY_WORKLOG_ROOT}/YYYYMMDD/`，每天一個來源日期目錄；
  這個 builder 可以被日報借用來 build 與 preview，但不負責決定日報目錄，也不應呼叫週報的
  `create_folder.sh`。

## 報告規則（動手前先讀對應的）

- **週報 / 進度報告** → `references/weekly-report.md`：週五日期慣例、資料夾與匯出檔名規則、
  固定基礎頁、數字怎麼放（量測值／衍生值／常數三類）、物種名不縮寫、截圖版面自檢。
- **月會 / 月報** → `references/monthly-report.md`：**做法和週報完全不同（兩階段：先盤點候選、
  等使用者選定主題才動手做投影片），開始前必讀，不要照週報流程做。**
- **單一 issue 簡報**（bug fix / 規則調整）→ `references/issue-report.md`：最多 5 頁、
  problem→solution→before/after 結構、省略版本/MR/CI 等工程細節。
- **APGPAS 網頁／HTML 報告的 browser 畫面** → `references/browser-screenshot.md`：先取得
  使用者可見的畫面、固定 16:9 尺寸、去識別化，再以圖片放入投影片；不要把登入中的 live page
  或 iframe 當成 PPTX 的可靠內容來源。
頁面上要放圖表時另有一組（依圖的類型分檔，**動手前必讀對應那份**，路線選擇見「工作流程」裡的決策表）：

- **mermaid 流程圖** → `references/diagram-mermaid.md`：初始化必須在去縮放狀態下跑（文字爆框主因）、
  `%%{init}%%` 逐圖字級、`.mermaid` 要 `width:100%`、菱形是高度殺手、分支宣告順序、爆框檢測腳本。
- **手刻方塊 + SVG 連線**（mermaid 排不出來時） → `references/diagram-svg.md`：座標系必須 px 對 px、
  marker 的 `markerUnits` 與 `fill:none` 兩個必踩坑、回圈走廊畫法、分支標籤放法、高度預算與截圖驗證。
- **寫腳本產資料圖**（覆蓋圖、pileup、結構示意）→ `references/figures.md`：canvas 寬度與
  `max-height` 的綁定關係、圖表誠實性自檢、數字出處寫法。
- **單向線性流程**（`.ap-lane` 現成 class）不需要讀上面任何一份，直接看本檔的版型 2。
- **一般截圖／影片／Before-After** 直接看本檔的版型 1／5／6；若截圖來自 APGPAS 網頁或
  HTML 報告，先讀 `references/browser-screenshot.md`。

## 工作流程

**新增/修改一頁**

0. 若當週報告資料夾還不存在，先建立（本週五日期加 `-w` 與 `data` 子資料夾）。這一步只適用週報；
   日報依 `daily-work-log` 的來源日期規則建立自己的目錄：

   ```bash
   bash ~/.codex/skills/presentation-builder/scripts/create_folder.sh
   ```

   若使用者已指定本次週報日期，可傳入 `WEEKLY_DECK_DATE=YYYYMMDD`，或使用 `--date YYYYMMDD`；例如
   `WEEKLY_DECK_DATE=20260828 bash ~/.codex/skills/presentation-builder/scripts/create_folder.sh`。

1. 從 `page-template.html` 複製到 `${REPORT_ROOT}/<YYYYMMDD-w>/NN-slug.html`（`NN` 兩位數是初始順序）。
2. 只動 `<!-- SLIDE:START -->`～`<!-- SLIDE:END -->` 之間的 `.slide-outer` 區塊，其餘保留。
3. 單頁可直接用瀏覽器預覽（有縮放 + mermaid），但沒有導覽/匯出——那是 deck 才有。
   單頁的樣式表走 `assets/slides.css`，`assets` 是資料夾裡指向 skill assets 的 symlink
   （`create_folder.sh` 建立，`serve_preview.py` 會補建）。**不要改成 `../../.claude/...`**：
   預覽 server 的根目錄是報告資料夾的上一層，爬出去的路徑會 404，整頁沒有版面，
   排版問題就要拖到彙整成 deck 才看得到。`deck.html` 不受影響，它是內嵌 CSS 的。

**要展示 APGPAS 網頁或 HTML 報告畫面**

先讀 `references/browser-screenshot.md`。這類畫面要先在瀏覽器取得使用者實際看到的
page state，再以去識別化的 PNG 放到報告資料夾 `data/`；固定 1280×720 或裁成 16:9，並在
投影片預覽時確認文字仍可讀。PPTX 應依賴本地圖片，不應依賴登入狀態、live iframe 或外部
網路；需要展示滾動、動畫或互動時，改用影片版型或現場 browser demo。

**要調整頁面順序時，用 `order.txt`，不要改檔名。**

```bash
python ~/.codex/skills/presentation-builder/build.py "${REPORT_ROOT}/<YYYYMMDD-w>" --init-order
```

產生 `order.txt`（一行一個檔名），之後**搬動裡面的行**就是改順序。檔名前綴只是建立時的
初始排序，一旦有 `order.txt` 就以它為準。

為什麼要這樣：簡報在製作過程中本來就會改順序，靠 `NN` 前綴表示順序有兩個毛病——改順序
要連帶改檔名（連結、引用全部要跟著動），而且兩個人同一天各加一頁很容易撞到同一個號碼
（實際發生過 `12-pd6-*` 與 `12-tb-*` 撞號）。`order.txt` 把「順序」和「檔名」拆開，
改順序不用碰檔案。

行為：
- 沒有 `order.txt` → 維持原本的檔名排序，舊資料夾不受影響。
- `order.txt` 列了不存在的檔案 → **直接報錯**（代表有人改名或刪檔），不會默默略過。
- 有頁面沒列進 `order.txt` → 附在最後並印出提醒，頁面不會憑空消失。
- build 完會印出「順序來源：order.txt / 檔名排序」，一眼看得出目前吃哪一種。

> `<!-- SLIDE:START/END -->` 是 builder 唯一的擷取依據，務必保留。
> **頁面專屬 `<style>` 必須放在 SLIDE 標記裡面**，否則 build.py 不會帶進 deck.html。`<head>` 的 `<style>` 只對單頁瀏覽有效，deck 模式下會失效（顏色、版型全部消失）。

**要在頁面上放圖表 → 動手前先讀對應的那份（硬性）**

圖表的坑都是結構性的（座標系、CSS 作用域、量測時機），**微調數字修不好**，
沒讀就動手一定會反覆卡在「箭頭壓字」「文字爆框」「圖對不上框」。先選路線：

| 圖長什麼樣 | 走哪條 | 讀哪份 |
|---|---|---|
| **單向線性流程**（A→B→C，可多 lane，節點內要放清單／數字／色塊） | `.ap-lane` / `.ap-node` / `.ap-arr` 現成 class | 本檔「版型 2」 |
| **有分支或判斷**，但排版單純上下左右 | mermaid | `references/diagram-mermaid.md` |
| 分支**回圈**要走特定路徑、節點裡要放 pill 或小圖、要精準控位 | 手刻方塊 + SVG 連線 | `references/diagram-svg.md` |
| 訊息本身靠**長度、位置、時間軸**編碼（誰比誰長、誰卡在哪一格、誰先誰後） | 手刻 SVG（inline，非腳本） | `references/diagram-svg.md` §0 |
| 資料圖：覆蓋度、pileup、比例分佈、結構示意 | 寫腳本產 SVG | `references/figures.md` |
| **APGPAS 網頁／HTML 報告 browser 畫面** | 先依 browser 截圖流程取得資產，再放 `<img>` | `references/browser-screenshot.md` + 本檔版型 1／6 |
| 截圖、影片、Before/After 對比 | 直接放 `<img>` / `<video>` | 本檔「版型」1／5／6 |

**由上往下選，能用上面那條就不要用下面那條**——越往下越要自己管座標，越容易畫壞。
線性流程不需要 mermaid（版型 2 的節點能塞的東西比 mermaid 多）；mermaid 排得出來就不要手刻。

**唯一的例外（也是唯一該主動往下選的情況）**：mermaid 與版型 2 的節點大小由**文字長度**決定，
跟數值無關，所以「52.35s vs 6.71s」「卡了 300 秒」「六項全部堵在 push」這種靠量值講的訊息，
它們**結構上就畫不出來**——硬用只會得到一張「有框的表格」。這時要直接跳到 `diagram-svg.md` §0。

**彙整成 deck**（使用者說「彙整 / 合併 / 匯出」時）

```bash
python ~/.codex/skills/presentation-builder/build.py "${REPORT_ROOT}/<YYYYMMDD-w>"
```

週報封面不要手寫 `01-cover.html`。標準封面由 `build.py --titlecover`
產生，包含「進度報告、日期、報告者」；新建週報資料夾使用 `YYYYMMDD-w`，builder 會自動解析其中日期，並匯出為 `進度報告YYYYMMDD-<OS使用者名>`。`build.py`
完成彙整後會自動執行 `scripts/validate_report.py`，檢查封面格式、日期、報告者、
頁面 marker 與 deck 頁數；驗證失敗時 build 會直接停止並列出原因。

若只想手動檢查既有 deck：

```bash
python ~/.codex/skills/presentation-builder/scripts/validate_report.py \
  "${REPORT_ROOT}/YYYYMMDD-w" \
  --titlecover --presenter "Hung-Lin, Chen"
```

**排版自檢（build 後必做，不能只看程式碼）**

版面有沒有填滿、字會不會太小、內容有沒有被裁掉，**讀 HTML 一律看不出來**，必須看渲染結果。
在瀏覽器打開頁面或 deck 後，把 `scripts/layout_audit.js` 整份貼進 console 執行：

```bash
cat ~/.codex/skills/presentation-builder/scripts/layout_audit.js
```

它會列出四類問題：**溢出 720px**、**底部大片留白**、**容器撐大但內容沒放大**（表格列高
遠大於內容高）、**正文字級過小**。逐條修到通過為止；修法見「版型設計原則」第一節。

沒有瀏覽器 console 可用時，改用截圖並**放大檢視**（不要只看縮圖判斷——縮圖上字小看起來很正常）。

**彙整後預覽（必做）**

- build 完後，**一定要讓使用者能直接在瀏覽器看 deck**，不要只回傳會顯示原始碼的檔案路徑。
- deck 更新後，**一定要在 app 內可開啟的瀏覽器 URL 上預覽給使用者看**；不要只說「已更新」或只貼本機檔案路徑。
- 若 ambient UI 已顯示 in-app browser 正在看某個 preview URL，**優先重用同一個 port**，不要另外再開新 port。
- 若沒有既有的 browser port，使用 preview helper 啟動 / 重用個人 preview server：

```bash
python ~/.codex/skills/presentation-builder/scripts/serve_preview.py "${REPORT_ROOT}/<date>"
```

- 若要明確重用目前 browser 的 port：

```bash
python ~/.codex/skills/presentation-builder/scripts/serve_preview.py \
  "${REPORT_ROOT}/<date>" --port <current-localhost-port>
```

- **遠端 server 注意事項**：
  - 如果 agent 跑在遠端機器上，**不要回傳 `localhost` 或 `127.0.0.1`**，因為使用者 app 端打不開。
  - 應回傳使用者可連到的 server IP / hostname。
  - 目前這台共享 server 預設使用 `192.168.2.57`，所以 preview URL 應是 `http://192.168.2.57:<port>/...`。
  - 如需覆寫，使用：

```bash
python ~/.codex/skills/presentation-builder/scripts/serve_preview.py \
  "${REPORT_ROOT}/<date>" --public-host <server-ip-or-hostname>
```

- **Port 規範**：
  - 不要每做一次報告就開一個新的隨機 port。
  - 不要假設整個團隊共用同一個固定 port；報告是個人工作目錄，preview server 也應以**個人可重用**為原則。
  - helper 會先重用既有 port；若該 port 被別的程序占用且不是這份報告的 server，才會在保留區間內找下一個可用 port。

**修改投影片頁或 skill 資源後，立即重跑 build**

只要修改了任何 `.html` 頁面、`deck.js`、`slides.css`、或 `build.py`，就要重跑 build 讓 `deck.html` 反映最新內容：

```bash
# 取最近一個報告資料夾（若使用者沒指定）
REPORT_ROOT="$(bash ~/.codex/skills/presentation-builder/scripts/report_root.sh)"
LATEST=$(ls -d "${REPORT_ROOT}"/[0-9]* 2>/dev/null | sort | tail -1)
python ~/.codex/skills/presentation-builder/build.py "$LATEST"
```

若使用者已明確指定資料夾則直接用那個路徑，不必取 `$LATEST`。

- 收 `*.html`（排除 `deck.html`、底線開頭檔）；有 `order.txt` 就照它排，否則依檔名排序。
- 預設不加封面；加 `--titlecover` 才插入進度報告封面。
- 產出 `<date>/deck.html`（單一可攜檔，內嵌 CSS/JS）。
- 開啟即投影片模式：←→ / 空白 / Esc 切頁，↓ 匯出 PPTX。
- **只想要某幾頁時**：切到該頁按右上「⧉ 複製本頁」或快捷鍵 `c`，把當前頁截成 PNG。安全連線（https / localhost / 直接開 `file://` 的 deck.html）會直接複製到剪貼簿可貼進 Slack / 文件；透過 http 區網 IP（如 preview server 的 `192.168.2.57:<port>`）瀏覽器不允許寫剪貼簿，會自動改成下載該頁 PNG。要「複製到剪貼簿」就用 localhost 或先下載可攜版 HTML 用 `file://` 開。
- 常用旗標：`--presenter`、`--title`、`--name`（PPTX 檔名）、`--date`、`--titlecover`。
- **報告者名字（presenter）自動依當前使用者解析**，不要寫死某個人：`--presenter` 明確指定 > `$DECK_PRESENTER` > `presenters.json`（依 OS 使用者名對應正式英文名）> OS 使用者名。要讓自己顯示正確英文名，在 `presenters.json` 補一筆 `"<OS使用者名>": "<正式英文名>"`（例：`"hunglin": "Hung-Lin, Chen"`）。
- preview helper 以報告資料夾的上一層為 root，health check 走本機 `127.0.0.1`，但對使用者回傳**可連線的公開 URL**；在目前遠端 server 預設回傳 `http://192.168.2.57:<port>/<date>/deck.html`。

---

## 技術規格

**尺寸**：固定 **1280 × 720 px（16:9）**。`.slide-outer` 維持 aspect-ratio 自動縮放，`.slide` 固定 1280×720，transform 由 JS 設定。

**左上角章節 label**：每頁 `.slide` 放 `<div class="slide-label">章節名稱</div>`，同章節多頁填相同文字。

**Padding**：預設 `52px 60px 40px`；內容密集時用 `28px 40px 20px`（多數版型採此值）；疊加多區塊時用 `20px 36px 16px`。

**檔案結構**：

```
${REPORT_ROOT}/YYYYMMDD-w/        ← 新建週報
${REPORT_ROOT}/YYYYMMDD-m/        ← 新建月報
   01-xxx.html  02-yyy.html …   ← 每頁一個輕量 HTML
   deck.html                    ← build.py 產出
skill assets（不要動）:
   assets/slides.css            ← 全部樣式（含版型 class）
   assets/deck.js               ← 頁數切換 / 縮放 / 投影片 / PPTX 匯出
   page-template.html           ← 單頁模板
   build.py                     ← 彙整 builder
```

---

## 語意 class 速查

以下 class 定義於 `slides.css`，在 `.slide` 內直接用：

| class | 用途 |
|-------|------|
| `b.old` / `b.new` | 紅字（舊/問題）/ 綠字（新/改善） |
| `.old-c` / `.new-c` | 表格欄紅/綠加粗 |
| `.lead` | 頁面說明文字（灰色，15px） |
| `.takeaway` | 結論框（綠底）；加 `.warn` 變黃底注意框 |
| `.ruletable` | 規則表格；`tr.drop` 刪除線紅底，`tr.hl` 黃底強調 |
| `.drop-badge` / `.smrn-badge` | 紅/綠小 badge |
| `.divider` | 水平虛線分隔 |
| `.row` | `display:flex; align-items:center; gap:8px` |
| `.cols` / `.col` | 左右欄容器 / 等寬欄位 |
| `code` | 行內程式碼（灰底） |
| `.num` | 圓點編號（目前隱藏） |
| `.info-card.red/green/blue/yellow` | 左色帶資訊卡片（詳見版型 1） |
| `.vdivider` | 垂直虛線分隔（詳見版型 4） |
| `.before-label` / `.after-label` | 改前/改後紅綠 label |
| `.ap-*` | Pipeline 節點系列（詳見版型 2） |

**配色語意**：紅 = 舊/問題/移除，綠 = 新/改善/保留，黃 = 注意。

---

## 版型設計原則

### 填滿版面：撐大容器的同時要放大內容（最常犯）

`flex:1`、`height:100%` 只會把**容器**撐大，**不會**放大裡面的字。只做前者的結果是
「框很大、字很小、中間一片空白」——版面看起來滿了，實際資訊密度極低。

一頁 1280×720 在投影時是很大的畫布。決定某個區塊要佔多少高度後，**同一次就把該區塊的
字級一起調上去**：

| 區塊 | 合理字級 |
|---|---|
| 主標題 `h2` | 27–32px |
| 副標／導言 | 15–17px |
| 表格數據（本頁主角時） | 19–24px |
| 表格一般儲存格 | 15–17px |
| 卡片內文 | 13–16px |
| 圖說、來源註 | 10–12px |

自檢問句：**這塊空白能不能改放一項讀者需要知道的資訊？** 能就補內容，不能就把現有內容放大。
反覆調不出來時，通常是這個區塊本來就該再塞一組資訊（多一列、多一張卡、多一組數字）。

搭配 `scripts/layout_audit.js` 驗證（見「工作流程」的排版自檢）。

### 標題（slide-label／h2）整份 deck 固定一套，不要逐頁調（第二常犯）

`.slide-label` 和 `h2` 是翻頁時讀者第一眼對齊的錨點，**位置（`.slide` 的 top/left padding）
跟字級要整份 deck 完全一致**，不因單頁內容多寡而改動。開始做一份新 deck（或接手既有 deck
加頁）時，先定下 `.slide` 的 padding 與 `h2 { font-size }` 這兩個數字，之後每一頁的
`<div class="slide" style="padding:...">` 和 `<h2 style="font-size:...">` 都原樣沿用。

最常見的破功情境：某一頁內容特別多（表格列數多、卡片多），為了塞進 1280×720，把**標題**
跟著往上擠、字級跟著縮小（padding-top 從 26px 改 18px、h2 從 19px 改 16px）。
**不要動標題**——翻頁時標題位置/大小跳動，讀者會覺得排版「隨機」；內容才是該收斂的對象。

加頁或修頁前，**先看一下同份 deck 其他頁目前的 `.slide` padding 和 `h2` 字級**
（`grep -o 'class="slide" style="padding:[^;]*' *.html` 、`grep -o '<h2 style="font-size:[0-9.]*px'`
掃一輪既有頁面），直接沿用那組數字，不要另外起一組。

**標題以下的內文/表格/卡片字級可以依內容密度調整**（表格列數多的頁本來就該比列數少的頁字級
小一點），不需要為了跟其他頁一致而把資訊硬拆成多頁——先確認是不是真的塞不下（用
`scripts/layout_audit.js` 驗證），塞得下就維持一頁，只調整內文字級，不用動標題也不用拆頁。

### 左右 vs 上下

**看內容本身的形狀**：

- **橫長型**（寬截圖、影片、表格、Mermaid 流程）→ 選**上下**，佔滿全寬
- **方塊型 / 較窄**（說明卡片、短表格、小圖）→ 選**左右**，並排利用水平空間

版型 6（Before/After 截圖）是橫長型，選上下。版型 1（圖 + 說明卡片）的卡片是窄型，放右側剛好。

### 版型可以疊加

一頁骨架通常是：**標題 → 主體 → 補充**。每個區塊可套不同版型，用 `flex:1` 分配高度、實線 `<div style="height:1px;background:#e5e7eb;">` 分隔。

常見組合：

| 組合 | 說明 |
|------|------|
| 版型 3 | 上下兩個 Mermaid + 底部 ruletable |
| 版型 5 ＋ 版型 6 | 上半影片 ＋ 下半 Before/After 圖 |
| 版型 4 ＋ ruletable | 上半左右欄比較 ＋ 底部規則彙整 |
| 版型 1 ＋ 版型 6 | 右欄說明卡片 ＋ 左側改前改後疊圖 |

疊加骨架：

```html
<div class="slide" style="padding:20px 36px 16px;display:flex;flex-direction:column;gap:8px;">
  <div class="slide-label">章節</div>

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;gap:4px;">
    <h2 style="font-size:15px;margin:0;">區塊 A 標題</h2>
    <!-- 版型 X -->
  </div>

  <div style="height:1px;background:#e5e7eb;flex-shrink:0;"></div>

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;gap:4px;">
    <h2 style="font-size:15px;margin:0;">區塊 B 標題</h2>
    <!-- 版型 Y -->
  </div>
</div>
```

> 比例不一定 1:1，可用 `flex:2` / `flex:1` 調整上下比重。

---

## 版型

### 版型 1：圖片 + 側欄說明卡片

左側大圖（`flex:2`），右側 `.info-card` 卡片（`flex:1`）。適合截圖配文字摘要。

```html
<div class="slide" style="padding:28px 40px 20px;display:flex;flex-direction:column;gap:10px;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:18px;margin:0 0 4px;">標題</h2>

  <div style="flex:1;display:flex;gap:20px;align-items:flex-start;">
    <div style="flex:2;display:flex;align-items:center;justify-content:center;">
      <img src="data/xxx.png" style="max-width:100%;max-height:460px;object-fit:contain;
           border:1px solid #e5e7eb;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.1);">
    </div>

    <div style="flex:1;display:flex;flex-direction:column;gap:10px;align-self:center;">
      <div class="info-card red">
        <div class="card-title">問題標題</div>
        問題說明文字……
      </div>
      <div class="info-card green">
        <div class="card-title">目標</div>
        目標說明文字……
      </div>
    </div>
  </div>
</div>
```

`.info-card` 顏色：`red`（問題/警告）、`green`（目標/結果）、`blue`（資訊）、`yellow`（注意）。

---

### 版型 2：Pipeline 流程圖

用 `.ap-lane` 包 `.ap-node`，節點間用 `.ap-arr` 連接。適合呈現多步驟資料流，可分 Write Path / Read Path 雙 lane。

**流程圖的第一選擇**：純 CSS flex，不用管座標，節點內能塞清單／數字／色塊（比 mermaid 能放的多）。
限制是**只走單一方向**——需要分支判斷改用 mermaid，需要回圈改手刻（見上面的圖表決策表）。

**Lane 骨架**：

```html
<div class="slide" style="padding:26px 40px 16px;display:flex;flex-direction:column;gap:9px;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:17px;margin:0 0 2px;">Pipeline 標題</h2>

  <div class="ap-lane" style="background:#eef4ff;border:1px solid #c5d8f8;flex:1;">
    <div class="ap-lane-lbl" style="color:#3b82f6;">
      Write Path <span style="font-weight:400;font-size:9px;color:#93c5fd;text-transform:none;letter-spacing:0;">離線計算</span>
    </div>
    <div style="display:flex;align-items:stretch;gap:0;flex:1;">
      <!-- 節點 → 箭頭 → 節點 → 箭頭 → … -->
    </div>
  </div>

  <div class="ap-lane" style="background:#f0fdf4;border:1px solid #bbf7d0;flex:1;">
    <div class="ap-lane-lbl" style="color:#16a34a;">
      Read Path <span style="font-weight:400;font-size:9px;color:#86efac;text-transform:none;letter-spacing:0;">查詢輸出</span>
    </div>
    <div style="display:flex;align-items:stretch;gap:0;flex:1;">
      <!-- 同上 -->
    </div>
  </div>
</div>
```

**節點顏色建議（按順序）**：藍 `#3b82f6` → 靛 `#6366f1` → 紫 `#8b5cf6` → 琥珀 `#f59e0b` → 青 `#0891b2` → 綠 `#16a34a` → 紅 `#dc2626`

**箭頭**（顏色與下個節點上邊框色相同）：

```html
<div class="ap-arr">
  <div class="ap-arr-bar" style="background:#3b82f6;">
    <div class="ap-arr-head" style="border-left:11px solid #3b82f6;"></div>
  </div>
  <div class="ap-arr-lbl">reads</div>
</div>
```

**節點填法（四種，依資料性質選擇）**：

① 純文字型 — 說明步驟做什麼、輸出什麼、有哪些結果碼：

```html
<div class="ap-node" style="border-top:3.5px solid #3b82f6;">
  <div class="ap-title" style="color:#1d4ed8;">
    <div class="ap-badge" style="background:#3b82f6;color:#fff;">①</div>步驟名稱
  </div>
  <div class="ap-sub">跨 seq_id 統計，套用品質門檻</div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">
    <span class="ap-code" style="background:#d1fae5;color:#065f46;">00 通過</span>
    <span class="ap-code" style="background:#fee2e2;color:#991b1b;">01 過濾</span>
  </div>
  <div class="ap-chip" style="background:#dbeafe;color:#1e40af;">輸出表名</div>
</div>
```

② 大數字型 — 強調關鍵指標（sum_00、count、score 等）：

```html
<div class="ap-node" style="border-top:3.5px solid #f59e0b;">
  <div class="ap-title" style="color:#92400e;">
    <div class="ap-badge" style="background:#f59e0b;color:#fff;">④</div>統計結果
  </div>
  <div style="background:#fef3c7;border-radius:8px;padding:8px;text-align:center;
              flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;">
    <div style="font-size:22px;font-weight:900;color:#78350f;line-height:1;">sum_00</div>
    <div style="font-size:9px;color:#92400e;">通過 Code 00 的樣本數</div>
  </div>
  <div class="ap-chip" style="background:#fef9c3;color:#78350f;font-family:monospace;">table_name</div>
</div>
```

③ 資料流 bar 型 — 橫條示意過濾前後的 reads 數量變化：

```html
<div class="ap-node" style="border-top:3.5px solid #3b82f6;">
  <div class="ap-title" style="color:#1d4ed8;">
    <div class="ap-badge" style="background:#3b82f6;color:#fff;">①</div>過濾步驟
  </div>
  <div style="display:flex;gap:8px;align-items:center;flex:1;">
    <div style="flex:1;">
      <div style="font-size:8.5px;color:#ef4444;font-weight:600;margin-bottom:3px;">All reads</div>
      <div class="ap-rb" style="width:88%;background:#fca5a5;"></div>
      <div class="ap-rb" style="width:72%;background:#93c5fd;"></div>
      <div class="ap-rb" style="width:60%;background:#fca5a5;"></div>
    </div>
    <div style="font-size:18px;color:#93c5fd;flex-shrink:0;">→</div>
    <div style="flex:1;">
      <div style="font-size:8.5px;color:#3b82f6;font-weight:600;margin-bottom:3px;">Non-human</div>
      <div class="ap-rb" style="width:80%;background:#93c5fd;"></div>
      <div class="ap-rb" style="width:55%;background:#6ee7b7;"></div>
    </div>
  </div>
  <div class="ap-chip" style="background:#dbeafe;color:#1e40af;">去除人類 DNA</div>
</div>
```

④ DB / API 方框型 — 節點代表外部系統，顯示工具名稱與輸出欄位：

```html
<div class="ap-node" style="border-top:3.5px solid #6366f1;">
  <div class="ap-title" style="color:#4338ca;">
    <div class="ap-badge" style="background:#6366f1;color:#fff;">②</div>比對 DB
  </div>
  <div style="display:flex;gap:8px;align-items:center;flex:1;">
    <div style="flex:1;">
      <div class="ap-rb" style="width:85%;background:#a5b4fc;"></div>
      <div class="ap-rb" style="width:62%;background:#a5b4fc;"></div>
    </div>
    <div style="font-size:18px;color:#a5b4fc;flex-shrink:0;">→</div>
    <div style="flex:1.1;background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:8px;
                padding:7px 8px;text-align:center;">
      <div style="font-size:11px;font-weight:700;color:#4338ca;margin-bottom:3px;">DB 名稱</div>
      <div style="font-size:8.5px;color:#6b7280;margin-bottom:5px;">工具 / 演算法</div>
      <div style="font-size:8.5px;font-weight:600;background:#c7d2fe;border-radius:4px;
                  padding:2px 0;color:#3730a3;">輸出欄位 A</div>
    </div>
  </div>
  <div class="ap-chip" style="background:#e0e7ff;color:#3730a3;">output_field</div>
</div>
```

⑤ 示意圖型 — 節點在說明「一個轉換動作」（篩選、合併、展開、翻轉…）而非數字或表格時，
用一張小 SVG 畫「處理前 → 處理後」，不要只寫一句話描述它做了什麼。簡報的讀者是用看的，
一整排卡片如果只有標題＋一行敘述文字，卡片會被拉得很高、文字撐不滿，看起來就是一大片留白
（`layout_audit.js` 的「容器過空」規則抓的是 div 巢狀關係，抓不到「卡片裡塞的文字量不足以
撐滿高度」這種情況——這條必須拿螢幕截圖或瀏覽器目視確認，不能只看程式碼）：

```html
<div class="ap-node" style="border-top:3.5px solid #db2777;">
  <div class="ap-title" style="color:#9d174d;">
    <div class="ap-badge" style="background:#db2777;color:#fff;">④</div>Set Cover（核心）
  </div>
  <!-- viewBox 用直式比例（寬:高 ≈ 100:120），貼近卡片實際可用空間；
       預設 preserveAspectRatio="xMidYMid meet" 不要加 "none"，避免圖形被拉伸變形。
       上半部畫處理前的狀態，中間一個向下箭頭，下半部畫處理後的狀態——
       這個「上下對照」版面本身就是縱向卡片最自然的用法，不需要額外文字重述。 -->
  <svg viewBox="0 0 100 120" style="flex:1;width:100%;height:100%;min-height:0;display:block;">
    <rect x="4" y="4" width="34" height="8" rx="1" fill="#db2777" opacity="0.18"/>
    <rect x="26" y="14" width="34" height="8" rx="1" fill="#db2777" opacity="0.18"/>
    <line x1="50" y1="44" x2="50" y2="62" stroke="#db2777" stroke-width="2.5"/>
    <path d="M44,56 L50,66 L56,56 Z" fill="#db2777"/>
    <rect x="6" y="80" width="42" height="13" rx="2" fill="#db2777"/>
    <rect x="50" y="80" width="44" height="13" rx="2" fill="#db2777" opacity="0.8"/>
  </svg>
  <div class="ap-chip" style="background:#fce7f3;color:#9d174d;">最少 probe 蓋滿覆蓋率</div>
</div>
```

- **lane 高度不要交給 `flex:1` 無限撐開**：`.ap-lane` 若吃掉整頁剩餘高度，節點會被拉得非常
  高（實測過一次 7 節點的 lane 被撐到 480px 高），SVG 的 `flex:1` 會把畫布撐高但內容仍照
  `viewBox` 比例置中，上下留下大片空白——這不是「內容不夠」，是「容器比內容野」。改用固定
  `height`（例如 `height:328px;flex:none;`）把 lane 限制在跟 SVG viewBox 相稱的高度，
  釋出的版面空間拿來加一排補充卡片或加大結論框，而不是留給瀏覽器自己撐開。
- **每個節點的示意圖只畫一個轉換動作**，不要在同一張圖裡塞多個步驟；步驟之間本來就有
  `.ap-arr` 箭頭銜接，圖裡再畫一次會重複。
- 純文字仍然是常態：像①②型（純文字、大數字）用在描述「輸出什麼欄位」「達成什麼指標」這種
  本來就是數字/文字的內容，不必為了畫圖而畫圖。只有節點在講「動作」時才換成示意圖型。

---

### 版型 3：改前 / 改後 比較

上下各一個 Mermaid 流程圖，`.before-label` / `.after-label` 標記，`.divider` 分隔，底部接 ruletable 補充細節。

```html
<div class="slide" style="padding:36px 48px 24px;display:flex;flex-direction:column;gap:0;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:19px;margin:0 0 8px;">重構標題</h2>

  <div style="margin-bottom:10px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
      <div class="before-label">改前</div>
      <div class="mermaid" style="flex:1;margin:0;">
flowchart LR
    A["舊元件"] --> B["結果"]
    classDef calc fill:#fff1f0,stroke:#d4380d,color:#820014;
      </div>
    </div>
    <hr class="divider">
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="after-label">改後</div>
      <div class="mermaid" style="flex:1;margin:0;">
flowchart LR
    A["新元件"] --> B["結果"]
    classDef new fill:#f6ffed,stroke:#389e0d,color:#135200;
      </div>
    </div>
  </div>

  <table class="ruletable" style="font-size:12px;">
    <thead><tr><th>規則</th><th class="old-c">原版</th><th class="new-c">新版</th></tr></thead>
    <tbody>
      <tr><td>Rule 1</td><td class="old-c">舊做法</td><td>新做法</td></tr>
      <tr class="drop"><td>Rule 2</td><td class="old-c">已移除</td><td><span class="drop-badge">移除</span></td></tr>
      <tr class="hl"><td colspan="2">最終</td><td><span class="smrn-badge">採用</span></td></tr>
    </tbody>
  </table>
</div>
```

---

### 版型 4：左右兩欄比較

兩欄各有標題列、內容、結果框，中間插 `.vdivider`。適合情境 A / 情境 B 並排對比。

```html
<div class="slide" style="padding:28px 44px 20px;display:flex;flex-direction:column;gap:10px;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:18px;margin:0 0 2px;">兩種情境比較</h2>

  <div style="display:flex;gap:20px;flex:1;min-height:0;">
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:6px;">
      <div style="font-size:12px;font-weight:700;color:#1677ff;padding:5px 10px;background:#e6f4ff;border-radius:4px;">
        情境 A：說明
      </div>
      <!-- 內容：table / info-card 等 -->
      <div style="font-size:11px;background:#f0f5ff;border:1px solid #adc6ff;border-radius:4px;padding:6px 10px;">
        消歧義指標：<b>判斷依據</b>
      </div>
      <div style="font-size:12px;background:#f6ffed;border:1px solid #b7eb8f;border-radius:4px;padding:8px 12px;display:flex;gap:16px;">
        <div><span style="color:#6b7280;font-size:11px;">欄位 A</span><br><b>值 A</b></div>
        <div style="width:1px;background:#b7eb8f;"></div>
        <div><span style="color:#6b7280;font-size:11px;">欄位 B</span><br><b>值 B</b></div>
      </div>
    </div>

    <div class="vdivider"></div>

    <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:6px;">
      <div style="font-size:12px;font-weight:700;color:#722ed1;padding:5px 10px;background:#f9f0ff;border-radius:4px;">
        情境 B：說明
      </div>
      <!-- 同上結構，換色系 -->
    </div>
  </div>
</div>
```

---

### 版型 5：影片展示

整頁或半頁放影片。加 `data-pptx-video` 讓 PPTX 匯出時嵌入 mp4（而非截靜態圖）。

```html
<div class="slide" style="padding:28px 44px 20px;display:flex;flex-direction:column;gap:6px;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:17px;margin:0;">功能展示標題</h2>
  <p style="font-size:11px;margin:0;color:#374151;">說明文字</p>
  <div style="display:flex;align-items:center;justify-content:center;flex:1;min-height:0;">
    <video src="data/demo.mp4" autoplay loop muted playsinline
      data-pptx-video
      style="max-width:100%;max-height:100%;border:1px solid #e5e7eb;border-radius:4px;"></video>
  </div>
</div>
```

---

### 版型 6：Before/After 圖片對比

截圖是橫長型，選上下疊放。`.before-label` / `.after-label` 標記，中間加過渡說明文字。

```html
<div class="slide" style="padding:28px 44px 20px;display:flex;flex-direction:column;gap:8px;">
  <div class="slide-label">章節</div>
  <h2 style="font-size:17px;margin:0;">改動驗證標題</h2>
  <p style="font-size:11px;margin:0;color:#374151;">說明文字</p>

  <div style="display:flex;flex-direction:column;gap:4px;flex:1;min-height:0;overflow:hidden;">
    <div class="before-label">改前 → 原始狀態說明</div>
    <img src="data/before.png" style="width:100%;border:1px solid #e5e7eb;border-radius:4px;object-fit:contain;">
    <div style="text-align:center;font-size:13px;color:#6b7280;">↓ 改動後</div>
    <div class="after-label">改後 → 預期結果說明</div>
    <img src="data/after.png" style="width:100%;border:1px solid #e5e7eb;border-radius:4px;object-fit:contain;">
  </div>
</div>
```

---

### 版型 7：表格內比例 bar（num/total + 橫向色條）

表格每格除了數字，還要讓讀者一眼看出「佔比」時用。每格是 `數字/總數` 文字 + 一條寬度＝比例的
色條（bar 的 track 背景是淺色，fill 是深色，`width:{pct}%`）。

```html
<td style="text-align:right;padding:4px 8px;">
  <div style="font-size:11px;color:#374151;">53/66</div>
  <div style="background:#fee2e2;border-radius:3px;height:5px;margin-top:2px;overflow:hidden;">
    <div style="width:80%;background:#dc2626;height:100%;"></div>
  </div>
</td>
```

**這個版型一定要搭配固定欄寬，否則 bar 長度沒有可比性**：純 HTML table 沒有 `width` 時，欄寬會
依內容自動撐開，同一個 80% 在窄欄位跟寬欄位畫出來的 bar 實際像素長度不一樣，肉眼比不出誰比例高。
外層 `<table>` 加 `table-layout:fixed`，並用 `<colgroup>` 明確指定每欄寬度（可用百分比）：

```html
<table style="table-layout:fixed;width:100%;">
  <colgroup><col style="width:26%;"><col style="width:14.8%;">...</colgroup>
  ...
</table>
```

多張表要並排比較時（例如 FP 表跟 FN 表），兩張表的 `<colgroup>` 也要給同一組寬度，
bar 長度才能跨表比較。
