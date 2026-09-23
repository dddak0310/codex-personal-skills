<!-- @for —— 這一節誰讀。`scripts/brief.py` 照它抽片段，所以標籤是**執行中的**，不是註解。⛔ 改節標題時要一起改。
     角色：finder / planner / builder / orchestrator。未標的節 = 全員都讀（前言與總則）。 -->
# 輸出目錄的形狀與路徑規矩

> **什麼時候讀這一份**（三種情況，其餘不必開）：
> ① **要寫一個過程產物、但不確定它該落在哪一層** —— 先看下面那棵樹，再照
>    `paths.work_file()` 那條規矩寫（⛔ 不要照樹自己拼路徑）。
> ② **`--since-last-deck` 找不到上一份 deck，或翻到的週報長得跟現在不一樣** ——
>    看「舊結構」那一節。
> ③ **`check_gate.py` 對某個舊目錄報「缺 layer1.md」** —— 同上，那是預期的。
>
> `SKILL.md` 只留三條會天天用到的規矩，其餘（完整目錄樹、舊結構相容）在這裡。

## 目錄長什麼樣（定案）

```
<週報輸出根>/<YYYY-MM-DD>/
├── deck.en.html          ★ 交付物（英文）
├── deck.zh.html          ★ 交付物（中文）
├── deck.json             單一事實來源，兩版都從它產
├── strings.zh.json       中文字串對照表
├── figures/*.svg         圖（被兩份 HTML 引用）
├── _work/                過程產物，按流程階段分四類
│   ├── 1_materials/      merge_groups.md/json、threads.md/json、materials.md、
│   │                     deck.draft.json、plan.todo.json
│   ├── 2_layer1/         layer1.md/json、gate1_view.md、gate1_answers.json、layer1_confirmed.json
│   ├── 3_layer2/         layer2.T*.md/json、gate2_view.md、gate2_answers.json
│   ├── 3b_specs/         逐頁構圖 spec 暫存檔（<slide id>.json）
│   ├── 4_slides/         slides.T*.json、compositions.T*.md/json、strings.T*.zh.json（逐線譯文片段）、
│   │                     shoot_check.<lang>.txt、verify.<線|all>.log、findings.T*.md、
│   │                     review_packet.md、layout_review.md
│   │                     ⛔ 不是日期目錄最上層（N14：兩個 builder 都寫錯地方；B17-14）
│   └── _briefs/          brief.<role>[.<thread>].md（派遣包；跨階段，故不編號）
└── _export/              **只有跑截圖／pptx 才會產生**
    ├── slides/*.png      deck.en.html 的截圖
    ├── slides_zh/*.png   deck.zh.html 的截圖（⛔ 不共用，會無聲覆蓋）
    └── weekly_report_<週>.pptx
```

三條規矩：
- **⭐ 交付物在最上層，過程產物一律進 `_work/`。** 底線開頭排序沉到底，
  打開目錄第一眼看到的就是兩份 HTML，不是 30 個中間檔。
- **`deck.json` 留在日期目錄本身**，⛔ 不要挪進 `_work/` ——
  `render_deck.py`／`check_deck.py`／`shoot.py`／`to_pptx.py` 全都從它的所在目錄
  推算 `figures/`、`strings.<lang>.json` 與輸出位置，挪走會整組錯位。
- **`--out` 只給日期目錄**，子資料夾由腳本自己開（形狀定義在 `scripts/paths.py`
  的 `WORK_STAGES` **與 `WORK_FILE_RULES`**，⛔ 只有那一份，不要在別處重寫路徑）。
  ⭐ **寫過程產物一律用 `paths.work_file(out, "<檔名>")`** —— 只說檔名，
  路徑由它決定；認不出來的檔名它會**報錯**而不是猜一個位置。
  上面那張圖是給人看的，⛔ **不要照著它自己拼 `_work/...`**（N14 就是那樣來的）。

⚠️ **舊結構是 `<週報輸出根>/<日期>/deck/`（多一層 `deck/`，且英文版叫 `deck.html`）。**
既有的 10 份舊週報**不搬移**；`--since-last-deck` 兩種結構都認得（新的優先），
但 `check_gate.py` 只服務進行中的那一份，對舊目錄會報「缺 layer1.md」——**那是預期的**。

> 週報輸出根 ＝ `python3 .claude/skills/weekly-deck/scripts/paths.py reports-root`，
> 預設 `<日誌 repo>/weekly`（與 `.data/`、`daily/` 並排），可用 `WEEKLY_DECK_REPORTS` 或
> `~/.config/weekly-deck/reports-root` 覆寫。⛔ **不要在流程裡寫死絕對路徑。**
> 安裝與設定見 `README.md` —— weekly-deck 是 daily-log 的後處理，**兩個 skill 必須成對安裝**。
