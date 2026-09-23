<!-- @for —— 這一節誰讀。`scripts/brief.py` 照它抽片段，所以標籤是**執行中的**，不是註解。⛔ 改節標題時要一起改。
     角色：finder / planner / builder / orchestrator。未標的節 = 全員都讀（前言與總則）。 -->
# 交付之後：怎麼播、怎麼改、要不要轉 pptx

> **什麼時候讀這一份**（四種情況，其餘不必開）：
> ① **使用者問「這個怎麼播」「怎麼看講者備忘」「怎麼全螢幕」** → 「怎麼播」那張按鍵表。
> ② **使用者要交一個 `.pptx` 檔，或對方一定要 PowerPoint** → 「Step 5」。
> ③ **交付後使用者說「第 5 頁刪掉」「這兩頁對調」** → 「修改時做原子操作」。
> ④ **`plan.dropped` 裡有 `where = backup` 的項目** → 「backup 頁的產出條件與上限」。
>
> ⚠️ **`shoot.py --check-only` 不在這一份裡** —— 它是 Step 4 的品質關卡、
> 不論要不要轉 pptx **一律要跑而且要過**，所以留在 `SKILL.md`。
> 這一份只收「真的要轉檔才做」的那半。

## 目錄

- 怎麼播
- 截圖 → pptx（**選用**，原 `SKILL.md` Step 5）
- 修改時：對 deck.json 做原子操作，不要重生成整份
- backup 頁的產出條件與上限

---

## 怎麼播

| **`G`** | **總覽網格**：所有頁的縮圖，點一下跳過去；`Esc` 關閉 |
| **`F`** | 全螢幕（也可以點右下角的 ⛶ 按鈕）|
| **`.`** | 黑屏／恢復（讓聽眾看你、不看投影片）；任何鍵或點一下都恢復 |

右下角有控制列：`‹` `›` ＋ 頁碼 `3 / 10` ＋ ▦（總覽）☰（備忘）⛶（全螢幕）。
⛔ 控制列**只用圖示、箭頭與數字**——`deck.en.html` 與 `deck.zh.html` 是同一份 `deck.json` 產的，
UI 上出現任何單字都會變成第三個要翻譯的表面。

⚠️ **`notes` 預設不顯示，也不會被截圖截到。** 它以 `data-notes` 屬性掛在 `<section>` 上，
**不進 DOM**（不是隱藏節點）——隱藏節點會被 `shoot.py` 的版面自檢當成真的容器去量。




## 截圖 → pptx（**選用**，原 `SKILL.md` Step 5）

> ⚠️ **`shoot.py` 不是為了 pptx 存在的，它是品質關卡。**
> 溢位（`.slide` 是 `overflow:hidden`，塞不下會被**靜靜裁掉**）與版面自檢
> 只有量渲染後的實際尺寸才看得到，看程式碼看不出來。
> **不論要不要轉 pptx，Step 4 的 `--check-only` 一律要跑，而且要過。**
> 會擋的有三種：溢位、主線內容過空、**文字互壓**（兩則 `<text>` 的外接矩形相交；B17-13，zh 版最常見）。
> 只有最後一種有逃生口 `--allow-text-overlap`，而且是「確定要照原樣截」時才加 —— 它不會讓 `verify.py` 變綠。

```bash
python3 $S/shoot.py $OUT/deck.en.html       # 溢位擋關 + 逐頁截圖 @2x → _export/slides/
python3 $S/shoot.py $OUT/deck.zh.html       # 中文版 → _export/slides_zh/（要中文 pptx 才跑）
python3 $S/to_pptx.py $OUT/deck.json        # → _export/weekly_report_<週>.pptx
#   中文版：to_pptx.py $OUT/deck.json --slides $OUT/_export/slides_zh -o $OUT/_export/..._zh.pptx
```

`shoot.py` 查兩層：**溢位**（會擋，除非 `--allow-overflow`）與**版面品質**
（底部留白 >150px、表格列高 >字級×3.2、表格溢出容器、正文字級 <12px、
子內容溢出、圖內有效字級 <13px；不擋但逐條列出）。
⭐ **例外：「容器過空」對主線內容頁會擋**（門檻見 `shoot.py`）——
上一次盲測它只印不擋，連印三輪沒有人理，主圖只吃掉整頁四成。
⛔ 擋住時不要縮圖去閃過，填料的辦法見 `presentation_rules.md §6`。

⚠️ **`shoot.py` 一律把播放器關掉**：它在 goto 之前用
`pg.add_init_script("window.__DECK_RAW__ = true;")` 進 raw 模式，
`deck.js` 讀到就**直接 return**——不注入樣式、不建 UI、不改任何節點，
頁面維持「1600×900 原尺寸、垂直排列、全部可見」。
**非這樣不可**：量測用的是未縮放的 `scrollHeight`／`offsetHeight`，
播放器一旦套上 `transform:scale` 並把非當前頁 `display:none`，那些數字會整組失準
（隱藏的頁 `offsetHeight` 直接變 0）。改播放器之後**一定要重跑 `--check-only`
比對輸出有沒有變**。

**pptx 兩版都產得出來**（`to_pptx.py` 吃哪一份截圖就產哪一版），要哪一版由使用者決定。
⚠️ 但**多數人不會轉 pptx** —— HTML 就是交付物（定案）。
⚠️ 截圖式 pptx 的文字在 PowerPoint 裡不可編輯，使用者已知並接受；`notes` 進備忘稿補回可搜尋的文字。

改一頁之後只重截那頁：`shoot.py deck.en.html --only 5`
（但 `to_pptx.py` 要求圖片數與頁數相符，改完頁數就要完整重截）。




## 修改時：對 deck.json 做原子操作，不要重生成整份

使用者說「第 5 頁刪掉」「這兩頁對調」時，**只動對應片段**，然後重跑 check → render。
重生成整份會把他已經確認過的其他頁也改掉，那是最惹人厭的失敗模式。
改完記得把承接／I/O 的鏈重新接上（`id` 不必連號）。




## backup 頁的產出條件與上限

標 `"backup": true`，排在一張 `thread-intro` 分隔頁之後。
backup 豁免承接／拋出，但仍需 `point`、`source`、數字溯源。

**產出條件與上限**（⭐ 以前完全沒規定，「降 backup」既可以是 0 頁也可以是 2 頁，
兩種都不違規 —— FINDINGS G5）：

```
plan.dropped 裡 where = backup 的項目
  0 項  → 不做分隔頁，也沒有 backup 頁
  ≥1 項 → 一張 thread-intro 分隔頁 ＋ **每項最多一頁**
`where = 口頭 / 不講` → **一律 0 頁**（口頭的寫進相關那頁的 notes）
```

- backup 頁**不計入頁數預算**（主線 ≤15／單線 ≤7）。
- ⛔ `where: backup` 卻一頁都不做 → 回頭把那一項改成 `口頭` 或 `不講`，
  不要讓 `backup` 變成第二個「不講」。
**這樣「怕漏講所以什麼都塞上去」的壓力就消失了**——教授問到再翻。
