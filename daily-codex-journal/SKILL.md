---
name: daily-codex-journal
description: 將指定日期（預設今天）的多個 Codex 任務／session 整理為繁體中文 HTML 日誌與可機器讀取的階層式記憶索引，並發布至 CCU-Bioinformatics-Lab/chingwei-daily。當使用者要求每日回顧、Codex 工作紀錄、session 索引或更新長期工作記憶時使用。
---

# Daily Codex Journal

把一天內多個 Codex 任務視為獨立 session，產生可供人閱讀的日誌與可供 Codex 跨日檢索的記憶資料。GitHub repo `CCU-Bioinformatics-Lab/chingwei-daily` 是正式來源；另外在目前工作區的 `outputs` 保留 HTML 副本，不保留 JSON 索引副本。

## 蒐集與識別 session

1. 以使用者本地時區解讀日期，優先使用環境提供的 Codex 任務工具列出並唯讀讀取該日可存取的任務。不要修改、續跑、封存或喚醒其他任務。
2. 一個 Codex task/thread 對應一個 session；同一 thread 的多個 turn 不得拆成不同 session。同一天可有任意數量 session。
3. 納入當日建立、當日有實質工作，或結果屬於當日的 session，包括成功、失敗、部分完成、取消及未完成。
4. 對可取得的原始 thread ID 計算 SHA-256；公開 `session_ref` 使用 `S-<thread 建立日 YYYYMMDD>-<雜湊前 8 個小寫十六進位字元>`。同一 thread 跨日必須沿用相同 `session_ref`。不要公開原始 thread ID、project ID、host ID、工作區絕對路徑或其他內部識別資訊。
5. 只有來源明確顯示延續、分支或依賴時才設定 `continuation_of`、`parent_session_ref` 或 `related_sessions`；否則使用 `null` 或空陣列，不得以標題相似自行建立關係。
6. 若無法取得 thread ID，使用 `S-<日期>-unknown-<序號>`，並將 `identity_confidence` 設為 `unconfirmed`。若無法列出其他任務，清楚記錄限制並至少整理目前 session。

## 實質工作過濾

先以完整 session 判斷是否值得進入長期記憶，再整理內容。不可因 session 很長就納入，也不可因失敗、取消或沒有檔案就排除。

將 session 分為 `high`、`medium`、`low` 記憶價值，只納入 `high` 與 `medium`：

- `high`：產生或發布重要成果；完成可重用的研究、分析、設計或決策；解決重大問題；或留下會影響後續工作的失敗、風險與學習。
- `medium`：明確推進既有專案，完成可驗證更新、重要診斷、方案比較、規則調整或具體後續計畫。
- `low`：沒有新增持久成果或決策，例如問候、致謝、單純確認、只要求開啟／查看頁面、重複追問、短暫狀態詢問、沒有後續影響的一般知識問答或純閒聊。

判斷規則：

- 使用者明確要求「記住／納入日誌」時，即使內容簡短也納入。
- 失敗、取消及未完成只要包含實質嘗試、影響、學習或後續行動，就必須納入，不得以過濾為名隱藏。
- 同一 session 同時含有實質工作與瑣碎回合時保留 session，但摘要只寫有記憶價值的內容。
- 不以主題類型、對話字數、turn 數或是否建立檔案作為唯一判準。
- 無法確認是否有持久價值時預設排除，並把不確定性計入過濾統計，不得捏造摘要。
- HTML 頂部與 manifest 記錄評估、納入、排除數量及排除原因分類；不逐筆公開被排除的瑣碎內容或原始識別資訊。

## session 記錄

依可確認的開始時間排列；未知時間置後並標示「無法確認」。每個 session 都要保存：

- `session_ref`、標題、日期與可確認的時間範圍
- 使用者原始目標
- Codex 採取的高層次行動，不記錄 API、CLI、瀏覽器操作、重試、內部工具或其他不必要的實作細節
- 最終結果與狀態：成功、失敗、部分完成、取消或未完成
- 重要成果／檔案，以 repo 相對路徑或公開網址表示，不公開本機絕對路徑
- 問題、限制、學習與後續行動
- 專案或主題標籤，以及有證據支持的 session 關係

失敗與不理想結果不得隱藏；無法從來源確認的內容使用「無法確認」或 JSON `null`，不可捏造。

## 記憶資料

生成或更新 JSON 前，讀取 [references/memory-schema.md](references/memory-schema.md)。正式輸出為：

- `journals/YYYY/MM/codex-journal-YYYY-MM-DD.html`：當日多 session 視覺日誌
- `memory/YYYY/MM/YYYY-MM-DD.json`：當日 session manifest
- `memory/index.json`：全域日期、session、專案與關係索引
- `README.md` 的「工作日誌指引」區塊：各日期的日誌連結與一句成果簡介

更新同日期資料時按 `session_ref` 合併，不得重複建立 session。更新 `memory/index.json` 時先讀取現有檔案，只變更本次日期與相關 session，不得覆蓋其他日期或未知欄位。

## README 工作日誌指引

- 每次發布每日紀錄時，讀取現有 `README.md`，同步新增或更新 `## 工作日誌指引` 區塊；只修改這個區塊，保留其他內容與未知段落。
- 每個已有日誌的日期只保留一筆，使用相對連結指向 `journals/YYYY/MM/codex-journal-YYYY-MM-DD.html`，並按日期由新到舊排列。
- 每筆簡介使用繁體中文單句，從該日日誌的成果與主題歸納，不列實作細節，不捏造資訊；無法確認時明確寫「簡介無法確認」。
- 若同日期日誌更新，必須同步刷新該日期簡介，不可建立重複條目。

## HTML

- 每日 HTML 必須使用 `$visual-html-builder` 製作。開始前完整讀取該 Skill 的 `SKILL.md`、`references/visual-design.md` 與 `references/implementation-validation.md`，並依其資訊分析、視覺設計、無障礙與驗證流程執行。
- 本 Skill 的固定檔名、同日期合併、session anchor、狀態語意、隱私與發布規則優先於 `$visual-html-builder` 的一般輸出命名規則；JSON、全域 index 與 README 仍依本 Skill 處理，不交由 HTML 視覺化流程改寫。
- 生成前建立暫時的事實溯源清單，把標題、統計、每個 session 結果、每日結論與後續行動連回可確認的 session 來源。此清單只供內容驗證，除非使用者要求，不另行發布。
- 依資料選擇最小且有助理解的視覺結構。通常依序呈現標題與範圍、最多 3–4 個關鍵統計、資料與過濾限制、session 索引、按時間排列的工作內容，以及每日總結；資料不足時不要強行加入圖表。
- 使用繁體中文、`lang="zh-Hant"`、UTF-8、responsive viewport 與內嵌 CSS；不要依賴外部 CDN。
- 頂部顯示日期、納入的 session 總數、各狀態統計、資料範圍、過濾統計及限制。
- 先提供可點擊的 session 索引，再按時間顯示 session 卡片；每張卡片的 anchor 使用 `session_ref`。
- 以文字與顏色共同標示狀態：成功綠、失敗紅、部分完成橙、取消灰、未完成藍。
- 頁尾包含「今日成果」「今日問題」「經驗與學習」「明日待辦」，且只能由 session 內容歸納。
- 所有互動都必須改善查找或理解，使用有標籤的原生控制，支援鍵盤與手機；不得只靠顏色傳達狀態。頁面須支援淺色、深色、`prefers-reduced-motion`、至少 320px 寬度與列印。
- 不公開原始 thread ID、雜湊全文、憑證、私人資料、本機路徑、不宜公開的研究資訊或實作操作細節。所有動態文字須正確 HTML escaping。

## 發布與驗證

1. 先讀取 repo 中同日期 HTML、manifest、全域 index 與 README；已存在時合併更新。
2. 在暫存位置產生 HTML、manifest、index 與 README 更新。HTML 依 `$visual-html-builder` 的實作與驗證規範實際開啟並逐項記錄「通過／失敗／未驗證」，至少檢查必要章節、事實溯源、anchor、統計、互動、JavaScript 錯誤、鍵盤、桌面與 320px 手機、淺色與深色、減少動畫及列印；無法執行的項目必須標為「未驗證」，不可宣稱通過。另檢查 JSON 可解析、符合 schema、`session_ref` 唯一且跨檔案一致；README 日期唯一、排序正確、連結有效；所有 artifact 連結使用 repo 相對路徑或公開網址。
3. 對公開內容執行敏感資訊與實作細節檢查。需要建立或更新 GitHub 檔案時，遵守當下工具的外部寫入確認要求。
4. 將檔案提交至 `CCU-Bioinformatics-Lab/chingwei-daily`。每日 HTML 的 commit message 必須使用繁體中文摘要，簡潔包含日期、session 數量與主要成果，不使用只有「更新日誌」等缺乏資訊的文字；manifest、全域 index 與 README 的 commit message 也使用繁體中文並清楚說明用途。
5. 成功後以 GitHub 內容重新驗證 HTML、manifest、index 與 README。
6. 將驗證完成的 HTML 複製到目前工作區的 `outputs/codex-journal-YYYY-MM-DD.html`，並確認內容與 GitHub HTML 一致；不得在本機保留 manifest 或全域 index 的正式副本。
7. GitHub 與本機 HTML 都確認成功後才刪除其他暫存檔。若 GitHub 寫入失敗，保留暫存檔並清楚說明未發布；不得把尚未提交的內容描述為已完成。
8. 最終回覆提供 GitHub HTML、當日 JSON、全域 index、README 與本機 HTML 的可點擊連結，並說明評估／納入／排除的 session 數量、資料限制與是否完成發布。
