---
name: daily-work-log
description: >
  Compile one day’s (or a specified date’s) Claude Code and Codex sessions into a
  thematic daily work log or daily review deck under `${DAILY_WORKLOG_ROOT}/YYYYMMDD/`
  (default: `$HOME/meeting/`). Use for 日報、工作日誌、工作紀錄、日誌整理、今天做了什麼、
  daily report, daily log, work log, or collecting and summarizing sessions for a day.
  Do not use for an explicit 週報、月報、weekly report, monthly report, or period roll-up;
  use weekly-deck-builder for those.
---

## 這個 skill 在做什麼

## 選擇邊界

- 當使用者要找、整理或回顧**當日／指定日期的工作日誌、工作紀錄或 session** 時，使用本 skill，即使最後要輸出投影片。
- 不要因為「日誌」最後會做成投影片就直接選 `weekly-deck-builder`；本 skill 是日報與 session 收集的 owner。
- 使用者明確要求跨一週／一個月的收攏、週報、月報或月會時，改用 `weekly-deck-builder`。
- 日報需要投影片版型、build 或 preview 時，才把 `weekly-deck-builder` 載入為呈現依賴；它不接管日報的 session 收集與 task summary。

`~/.claude/projects/*/*.jsonl`（Claude Code）和 `~/.codex/sessions/YYYY/MM/DD/*.jsonl`
（Codex）各自散落成很多 session 檔，同一個主題常常橫跨好幾個 session（中斷重開、平行跑、
不同工具）。這個 skill 分四步：

1. **腳本撈原始逐字稿**（機械式，不判斷重要性）——收集當天所有 session 的使用者發言與
   Claude/Codex 回覆，依時間序排列並過濾系統雜訊。
2. **逐任務寫 summary**——先判斷有多少個實質任務；每個任務只寫一句成果摘要與完成狀態，
   不急著分主題，也不把重開 session、追問或失敗嘗試重複算成新任務。
3. **比較後合併主題**——比較任務的共同目標、資料流、交付物、使用者結果與依賴關係，確認
   哪些任務合起來是在推進同一件事；repo、session、日期或相似關鍵字本身不是合併理由。
4. **依主題寫成日報**——用代表證據、決策、完成狀態與待決事項產生投影片，而不是逐題重播對話。

第 2–4 步不能只靠腳本，需要理解跨 session、跨 repo、甚至跨日期的工作脈絡。

## 與 weekly-deck-builder 的責任邊界

這個 skill 負責「整理每天的工作內容」；`weekly-deck-builder` 只負責投影片版型、彙整、驗證、
預覽與 PPTX 匯出。兩者可以一起使用，但目錄與日期規則不同：

- 被呼叫整理某個來源日期時，日報使用一個自己的
  `${DAILY_WORKLOG_ROOT}/YYYYMMDD/` 目錄；`YYYYMMDD` 是來源日期，不是當週週五。
- 使用者明確指定的報告／來源日期優先於執行環境的日期或既有目錄；例如指定 `20260828`，就使用
  `20260828/`，不要自行改成其他日期。
- `DAILY_WORKLOG_ROOT` 可由當次環境變數指定，未指定時使用 `$HOME/meeting`。
- 同一天重跑或補頁時沿用同一個日期目錄，不清空既有內容；下一天建立下一個日期目錄。
- 只借用 `weekly-deck-builder` 的頁面樣式、`build.py` 與 `serve_preview.py`。**不要**在日報流程
  呼叫它的 `create_folder.sh` 或 `report_root.sh`，因為那兩者遵守週報的週五日期規則。

## session 紀錄 hook（每位使用者、每個 agent 各裝一次）

`hooks/session-log.py` 使用 Claude Code 與 Codex 都有的 `SessionStart` +
`UserPromptSubmit` 事件，將「今天在哪些 cwd／branch 聊了哪些 session」寫入
`$DAILY_WORKLOG_ROOT/session-log/YYYYMMDD.jsonl`（`DAILY_WORKLOG_ROOT` 預設 `$HOME/meeting`）。一個 session 一行，
唯一鍵為 `(tool, session_id)`；`tool` 必為 `claude` 或 `codex`，所以同一份日誌能安全地
混合兩端資料。`source` 保留 hook 生命周期來源（例如 `startup`、`resume`、`backfill`），
不拿來表示 agent。

hook 是 harness 設定，不是 SKILL.md 本身；安裝器只會在使用者自己的設定加上這兩個事件，
既有 hooks 不動，寫入前備份。預設仍是 Claude，明確指定 `--client codex` 才會安裝 Codex：

```bash
~/.claude/skills/daily-work-log/hooks/install.sh --client claude
~/.codex/skills/daily-work-log/hooks/install.sh --client codex
~/.codex/skills/daily-work-log/hooks/install.sh --client codex --dry-run
~/.codex/skills/daily-work-log/hooks/install.sh --client codex --uninstall
```

Claude 寫入 `~/.claude/settings.json`；Codex 寫入 `~/.codex/hooks.json`，不修改
`~/.codex/config.toml`。Codex 第一次載入非 managed hook 時需透過 `/hooks` 檢閱並信任它。
安裝後不必重開 session，`UserPromptSubmit` 會接手已開啟的 session。

補安裝之前的紀錄（從兩種 transcript 回填，依 `(tool, session_id)` upsert，可重跑）：

```bash
~/.claude/skills/daily-work-log/hooks/backfill-session-log.py --date 2026-08-24 --tool all
```

回填會同時掃 Claude 與 Codex；Codex session 依其 `session_meta.payload.session_id` 記錄，
不使用帶有 rollout timestamp 的檔名，因此可與 live hook 的 session ID 直接對應。它也會掃目標
日期相鄰的 UTC 目錄再以本地日期過濾，避免時區跨日漏列。

沒裝 hook 的人不影響日報主流程——`extract_transcripts.py` 仍可掃原始 transcript；hook 只是
提供 branch、輪數與可快速查詢的當日索引。

## 用法

```bash
REPORT_DATE=2026-08-19
REPORT_DIR="$HOME/meeting/${REPORT_DATE//-/}"
mkdir -p "$REPORT_DIR/data"
python3 ~/.claude/skills/daily-work-log/scripts/extract_transcripts.py \
  --date "$REPORT_DATE" --max-chars 3000 \
  > "$REPORT_DIR/data/transcript_full.txt"
```

- `--date` 預設今天，格式 `YYYY-MM-DD`，可指定任何一天回顧。
- `--tool claude|codex|all` 只看某個工具，預設 `all`。
- `--manifest-out PATH` 可覆寫 session manifest 位置；省略時必定寫入
  `${DAILY_WORKLOG_ROOT:-$HOME/meeting}/<YYYYMMDD>/data/session-manifest.json`，其中 `<YYYYMMDD>` 來自 `--date`。
- `--max-chars N`（預設 4000）控制每則訊息截斷長度。**寫進日報的具體案例（錯誤訊息、JSON
  回應、數字表格、程式碼片段）幾乎都超過 500 字元的預設截斷點**——先用小的
  `--max-chars`（例如 500）掃一輪拿到 session 邊界與大致話題，**但真正動筆寫任何一頁之前，
  一定要把該 session 用夠大的 `--max-chars`（2000–4000 以上）重撈，或直接用 Read 工具分段
  讀完那個 session 的原始輸出**——只看截斷後的摘要會漏掉頁面最需要的東西：具體 chip_id、
  before/after 的實際數字、錯誤訊息全文。這是第一版日報和第二版日報效果差最多的地方。

輸出是純文字，依 session 分段，每段有 `[tool] session <id> cwd=... 起訖時間 (N turns)`，
然後是 `🧑 USER` / `🤖 ASSISTANT` 交錯的原始文字。**這只是素材，不要直接丟給使用者**——
下一步要自己讀過、整理。

每次抽取都會預設寫出 `data/session-manifest.json`；指定 `--manifest-out` 才改寫到其他位置。
它只保存 session 的來源工具、ID、原始檔定位、時間範圍與 turn 數，不保存逐字稿，也不會被放進
HTML。這是後續 task、投影片與月報回查細節的唯一 session 清單。

## Subagent 分工（有 subagent 能力時必用）

把大量、可獨立檢查的第一輪閱讀交給輕量 subagent；主 agent 保留跨批次判斷。這裡的目的不是讓
subagent 直接寫日報，而是先完整產生可合併的 task candidates。

### 模型選擇

- **Codex runtime**：指定 `gpt-5.6-luna`，使用 low 或 medium reasoning。
- **Claude Code runtime**：優先指定 Sonnet 5；若 runtime 沒有該精確識別字，使用它實際提供的
  Sonnet alias／Sonnet 等級模型，不要自行猜一個 model id。
- 不要為這種第一輪掃描自行升級到昂貴 frontier model；指定模型不可用時，由主 agent 接手或明確
  記錄 fallback，不要靜默換模型。

### 可以委派的工作

1. **逐批掃描 session，提出 task candidates**：讀完整的指定逐字稿，找出實質任務並填寫
   `task-summaries.md` 所需欄位。
2. **主題確定後找代表證據**：一個 subagent 負責一個已定義主題，回原始逐字稿找數字、case、
   錯誤輸出、流程與最後決定。
3. **Coverage 初檢**：依 session manifest 檢查是否有整段素材尚未被任何 task candidate 涵蓋。

### 不可委派的工作

主 agent 必須親自做以下判斷：跨 subagent 去重、決定 task 邊界、合併主題、寫主題 summary、
處理互相矛盾的結論、日期 × 主題 coverage、選擇最終頁面與整份敘事。subagent 不得自行建立
`theme-map.md`、HTML、`order.txt`，也不得因為覺得內容不重要就省略 task。

### 切分與輸出規則

1. 主 agent 先確認抽取器預設建立的 `data/session-manifest.json`：日期、session id、來源工具、
   原始檔定位、時間範圍與 turn 數。這個 manifest 是 page source 的驗證依據，不可手動臆造 session。
2. 多日素材優先一個日期一批；單日 session 很多時，以不重疊的 session id 分批。每個 session
   只能有一個第一輪 owner，避免重複計數；同時保留最多可用 worker 數給主 agent 統整。
3. 每個 subagent 只回傳結構化 task candidates，不直接寫共享檔案，避免平行覆寫。
4. 主 agent 收齊全部輸出後，回原文解決重複、衝突與狀態不明，再親自寫入
   `data/task-summaries.md`。

給 task-summary subagent 的最小指令：

```text
只讀指定的逐字稿批次。列出每個實質任務的日期/session、任務名稱、一句成果 summary、
目標/使用者結果、影響範圍、交付物/決定、狀態，以及可回查的證據位置。
不要分主題、不要做投影片、不要寫檔、不要把追問或重開 session 重複算成新任務，
也不要因為任務看起來小就省略。若結論或完成狀態不確定，明確標成待主 agent 複核。
```

## 寫日報的步驟

### 1. 取得並讀完素材

1. 先建立 `${DAILY_WORKLOG_ROOT:-$HOME/meeting}/<YYYYMMDD>/data/`，再跑腳本取得指定日期的全部逐字稿；
   腳本會自動建立 `data/session-manifest.json`，且後者必須在任何 task、主題或頁面產出之前存在。
2. 依上面的 Subagent 分工切成互不重疊的批次，讓輕量 subagent 先提出 task candidates；主 agent
   收齊後才跨批次去重，並針對需要判斷的 session 回讀原文。
3. 把中斷重開、先問後實作、Claude/Codex 之間接續的同一件事視為同一任務。
4. 時間戳記是 UTC，寫報告前加 8 小時換算成台北時間。多日報告保留來源日期，不讓最新一天
   蓋掉前幾天。單日日報使用來源日期作為輸出日期；多日回顧若使用者沒指定報告日期，使用來源範圍
   的最後一天並在 `theme-map.md` 標明完整來源範圍；週報仍遵守 `weekly-deck-builder` 的週五規則。

### 2. 先逐任務寫簡短 summary

在 `data/task-summaries.md` 建立任務表。**一列是一個實質任務，不是一個 session 或一個問題。**
Overview、待辦彙整、重複確認與沒有形成結果的探索，不要當成新任務。

每列至少包含：

| 欄位 | 寫法 |
|---|---|
| 日期／來源 session | 保留可回查的日期與 session id |
| 任務名稱 | 用名詞短語描述工作對象，不沿用情緒化問題句 |
| 一句 summary | `[動作／成果] + [影響範圍] + [完成狀態或限制]` |
| 目標／使用者結果 | 這個任務最後想讓誰得到什麼能力或結果 |
| 影響範圍 | 涉及的服務、repo、資料表、API 或使用端 |
| 交付物／決定 | 程式、資料契約、量測結論、操作能力或已拍板規則 |
| 狀態 | 只用：完成、定案、釐清、已量測、僅設計、未完成、待決 |
| 證據位置 | 使用 `來源工具:session_id` 加時間戳或原文段落；session 必須存在於 `session-manifest.json`，先定位、不在 summary 展開細節 |

Summary 只回答「這個任務把什麼推進到什麼狀態」。不要在這一步塞錯誤訊息、解法過程、測試數、
commit 或所有技術細節；那些稍後作為證據。先把每個任務寫完，**不要邊讀邊建立投影片或預設主題**。

### 3. 比較任務，再決定是否為同一主題

逐列比較 `task-summaries.md`。兩個任務符合下列至少兩項，且合併後能回答同一個高階問題時，
才歸入同一主題：

- 推進同一個最終目標或同一個使用者結果。
- 位於同一條資料流、生命週期或前後依賴鏈。
- 共同形成同一個交付物、契約、決策或操作能力。
- 一個任務是另一個任務的驗證、風險分析、消費端延伸或必要前置。

不要因為「同一 repo」「同一天」「都在修 bug」或名稱相似就合併；反過來，同一條完整資料流即使
跨 repo、跨 session、跨日期，也應考慮合併。若兩個任務需要讀者做不同決策、產生獨立成果或沒有
依賴關係，就分開。

把結果寫進 `data/theme-map.md`：

| 主題 | 主題 summary | 包含的 task | 為何屬於同一主題 | 代表證據 | 未完成事項 |
|---|---|---|---|---|---|

主題 summary 要比 task summary 高一層，描述多個任務共同完成的能力或推進結果。再加 coverage
checklist，逐一列出每個 task 是「納入哪個主題」或「為何排除」。多日報告另外做日期 × 主題檢查，
每個來源日期都必須有代表內容或明確排除理由。

### 4. 排敘事順序後才產頁

先寫一句當日／期間主線，再依內容安排：全貌 → 核心規則或架構 → 實作與交付 → 驗證與量測 →
使用者看得到的結果 → 待決事項。這是預設敘事，不是固定模板；不要照 session 時間排序。

## 產出：主線 → 主題章節 → 代表證據，放進 `${DAILY_WORKLOG_ROOT}/<來源日期>/`

日報的呈現載體是 **weekly-deck-builder 的 slide 頁**。動手前先讀 `weekly-deck-builder` skill，
依它的版型、build、排版自檢與 preview 流程執行。投影片要回答「今天把哪些工作主題推進到什麼
狀態」，不是「今天問過哪些問題」。

- 有 3 個以上主題時，先做一頁「今日主線／主題地圖」。
- 每個主題通常使用 1–2 頁；task、問題、bug、追問只是主題素材，不自動取得一頁。
- 忙碌的一天通常收斂成約 6–10 頁，但不為湊頁數拆任務，也不為壓頁數犧牲主題與證據。
- 純行政雜務不獨立成頁；需要保留時集中放「其他」。

1. **決定資料夾**：`${DAILY_WORKLOG_ROOT:-$HOME/meeting}/<YYYYMMDD>/`，`YYYYMMDD` 是使用者指定或
   `--date` 對應的來源日期（不套用週報「當週週五」的慣例）。若資料夾已存在（同一天重複產出、或當天稍晚要
   補頁）就沿用，不要清空既有內容：

   ```bash
   DAILY_WORKLOG_ROOT="${DAILY_WORKLOG_ROOT:-$HOME/meeting}"
   DAILY_DIR="${DAILY_WORKLOG_ROOT}/<YYYYMMDD>"
   mkdir -p "${DAILY_DIR}/data"
   asset_target="$(realpath --relative-to="${DAILY_DIR}" "$HOME/.claude/skills/weekly-deck-builder/assets")"
   ln -sfn "${asset_target}" "${DAILY_DIR}/assets"
   ```

2. **每個主題使用 1–2 個 `NN-slug.html`**：檔名前綴只是識別字；用 `order.txt` 依敘事關係
   排序，不按任務發生時間排列。單頁骨架：
   - `slide-label`：使用穩定的主題章節，例如「執行流程」「模型判定」「佈版治理」「消費端呈現」；
     同主題跨 repo 仍用同一 label。
   - `h2`：寫這頁提供的答案、成果或現況，不逐字使用使用者問句。
   - `<p class="lead">`：交代本頁在主題中的位置與重要性，不重播對話開場。
   - 中段：用流程、畫面、比較或數據呈現主題的代表證據。
   - `.takeaway`：寫主題層級的成果、決定或剩餘限制，不只寫單一 bug 已修好。

### 每個主題要放什麼代表證據

一個主題只有 summary、沒有案例，讀者無法判斷結論是否站得住腳。從逐字稿挑 1–3 項最能支持
主題 summary 的代表證據，不必為每個 task、追問、修正或錯誤訊息各開一頁。證據盡量保留原始
數字、識別字與輸出，不改寫成散文：

| 頁面在講什麼 | 去逐字稿裡找什麼 | 放上頁面的東西 |
|---|---|---|
| 一個 bug 被修好 | 使用者貼的**實際錯誤訊息／JSON 回應**（`status: failed`、traceback、curl 輸出） | 改前／改後兩個 `<pre>` 區塊並排，原樣貼錯誤／回應內容，不要摘要成文字 |
| 一個數據異常被查出根因 | 助手算出來的**實際數字表格**（列數、百分比、比例），通常在回覆裡以 markdown table 出現 | `ruletable` 照抄那個表格，異常的那一列用 `hl`／`old-c` 標出來 |
| 一個機制／流程被搞懂或改掉 | 助手畫的呼叫鏈（`A → B → C`）或使用者追問「這是誰觸發的」得到的答案 | `mermaid` flowchart，用 `classDef` 把「改前」「改後」或「問題點」上色 |
| 一個設定／命名決定 | 使用者列出的選項、助手給的對照表（現況 vs 建議、A repo vs B repo） | `ruletable`，欄位就是真實的檔名/欄位名/repo 名，不要抽象化 |
| 一組數字之間有**不對稱**或**母體不同** | 前後量測值（`52.35s → 40.61s → 6.71s`）、換了篩選條件後重算的比率（`83.49%` vs `98.52%`） | 手繪 inline SVG：等比例長條標出各段差額；母體不同就畫漏斗，別讓兩個數字並排冒充同類項 |
| 訊息的本質是**時間**或**阻塞** | 「最多卡 300 秒才寄信」「四個 session 並行、只有一個走到底」 | 手繪 inline SVG：同一條時間軸上下對照（改前／改後），多主體用泳道、終點標 ✓／✕ |
| **多個項目卡在同一個狀態** | 待決清單裡好幾列的狀態欄長得一樣（都是「已 commit 未 push」） | 手繪 inline SVG 管線圖＋閘門：箭頭全部匯進同一格。「都卡在同一格」才是訊息，表格會把它拆散 |
| 反覆討論、中間有被使用者糾正的錯誤結論 | 使用者說「你為甚麼亂下結論」「你確定嗎」這類糾正句，和助手認錯後重新給的結論 | 值得寫進 `.takeaway`：先講清楚哪個結論被推翻、真正的結論是什麼，這種轉折本身就是內容 |

後三列的手繪 SVG **動手前先讀 `weekly-deck-builder/references/diagram-svg.md` §0**（判斷規則與座標系）。
判準是「這頁的訊息靠什麼編碼」，不是「這頁好不好看」：

- **mermaid 的節點大小由文字長度決定，跟數值無關**，所以量值（幾秒、幾倍、幾項）它結構上畫不出來。
  反之只是 `A→B→C` 的拓樸關係，mermaid 就夠了，不要多花工。
- **同尺寸測試**：把圖裡所有方塊改成一樣大、位置隨便排，意思有沒有變？沒變就不是圖，
  是加了框的表格，退回 `ruletable`。
- **`.takeaway` 裡出現列舉句**（「四個中只有一個走到底」「六項全部卡在 X」）代表有結構被壓成一句話，
  那通常是本頁最強的訊息，考慮升格成圖。
- 成本護欄：手繪要算座標又要 preview 截圖驗證，**一份日報最多 2–3 張**，挑訊息最強的畫；
  每頁都是圖跟每頁都是表格一樣沒有重點。

**具體數字、chip_id、seq_id、taxid、檔名、行號** 這些識別字都要照抄原文，不要改寫或省略——
少了它們，頁面看起來就是空話。反過來，探索過程中失敗的嘗試、來回確認的閒聊（「好」「確認一下」）
不用放，那些在 task summary 階段就該濾掉了。

### 待決事項頁（一定要有這頁，別漏掉）

除了主題章節，**最後固定加一頁彙整「還沒決定、還沒做完」的事**——這頁對使用者
的價值往往比逐頁的技術細節更高，因為它是明天一早要接著做什麼的清單。

**去哪裡找待決事項**：在逐字稿裡專門找這些訊號，不要只憑印象覺得「應該還有事沒做完」：

- 助手問「要不要...」「要我...嗎」「這個你決定」之後，**使用者沒有在當天稍後回答**，或
  回答了但助手自己說「等你確認」「還沒動」
- 助手明講「**還沒做的**」「待你決定」「這是另一個決定」
- 兩個 repo／兩處程式碼**應該一致但目前不一致**（例如訓練端改了、serving 端沒跟著改），
  這種「發現了但沒收斂」的落差本身就是待決事項，就算沒人明講「這個還沒決定」
- 助手給出的結論帶著保留（「很可能是過擬合」「這是相關不是因果」），代表這個數字/結論
  還不能直接拿去用，需要人決定要不要信

**這頁怎麼分類、怎麼排版**：不要用扁平 bullet list，用 `ruletable` 依「性質」分組（每組
至少標一個 `hl` 醒目列），常見三類：

| 類別 | 判準 |
|---|---|
| 要拍板的決定 | 有兩個以上選項、影響範圍大，明確需要使用者選一個方向 |
| 部署／執行前必做 | 已經知道要做什麼、只是還沒做（rsync、rebuild、跑 migration） |
| 已知但未排 | 討論中被指出的問題，還沒決定何時處理、誰處理 |

每一列要寫「項目」+「狀態卡在哪」，卡在哪這欄才是價值所在（不是重複項目名稱）。

3. **建立頁面來源索引（必做，不進 HTML）**：所有 `NN-slug.html` 寫完後、build 前，建立
   `data/page-sources.json`。每個頁面必須列出實際採用的 session；例如第 1 頁使用兩個 session：

   ```bash
   python3 ~/.claude/skills/daily-work-log/scripts/write_page_sources.py \
     --manifest "${DAILY_DIR}/data/session-manifest.json" \
     --report-dir "${DAILY_DIR}" \
     --output "${DAILY_DIR}/data/page-sources.json" \
     --page "01-today-map.html=codex:<session-id>,claude:<session-id>"
   ```

   複數頁面就重複 `--page`。來源只能填 manifest 中存在的 `來源工具:session_id`；不確定來源時回讀
   原逐字稿後再填。`page-sources.json` 不可嵌入頁面、不可被 deck builder 讀取，也不可因為頁面摘要
   而省略來源 session。這份檔案是之後查詢「第 1 頁來自哪些 session」以及月報回查的入口。

4. **彙整**：

   ```bash
   python ~/.claude/skills/weekly-deck-builder/build.py "${DAILY_DIR}"
   ```

   不要加 `--titlecover`（使用者偏好預設不加封面）。
5. **內容、來源與排版自檢**：先核對 `data/task-summaries.md`、`data/theme-map.md`、
   `data/page-sources.json` 與實際頁面：每個頁面都必須剛好有一筆 page source、至少一個有效
   session，且每個 task 已納入主題或有排除理由；也不能退回「每個問題一頁」。再檢查表格欄位多或
   `.info-card` 內文長時
   還是可能溢出 720px（weekly-deck-builder 是截圖不滾動，溢出的內容不會進 PPTX）。用瀏覽器
   打開逐頁確認，或跑 `layout_audit.js`（見 weekly-deck-builder SKILL.md 的排版自檢章節）；
   溢出就精簡文字或縮小非標題區塊字級，不要砍內容。
6. **預覽給使用者**：起/沿用 preview server，回傳可點開的網址（不要只回檔案路徑）：

   ```bash
   python ~/.claude/skills/weekly-deck-builder/scripts/serve_preview.py "${DAILY_DIR}"
   ```

## 循環使用

這個 skill 設計成每天都能重跑一次：隔天只要再喊一次觸發詞（或明講日期），流程完全一樣，
不需要記得上次怎麼做。若使用者想要「每天自動生成」而不是手動觸發，那是另一件事（要用
`schedule` skill 建立排程），這個 skill 本身只負責「被呼叫時，把指定日期整理成日報」，
不要自作主張幫使用者建排程。

## 注意事項

- 腳本只做機械過濾（雜訊 prefix/marker），**不做語意判斷**；重複開的 session（同一問題
  問了兩三次）腳本不會幫你合併，那是步驟 2 你自己讀的時候要做的事。
- `cwd` 欄位在 Claude Code 端幾乎都是 `/home/jerry`（session 是從 home 目錄啟動的），不能
  拿來判斷這個 session 是在講哪個 repo——要看對話內容裡提到的路徑/repo 名稱。
- Codex session 檔名已經按日期分資料夾，比對日期很準；Claude Code session 檔沒有照日期
  分檔，腳本是逐行看 timestamp 做過濾，檔案本身可能橫跨好幾天。
