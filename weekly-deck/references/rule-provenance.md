<!-- @for —— 這一節誰讀。`scripts/brief.py` 照它抽片段，所以標籤是**執行中的**，不是註解。
     角色：orchestrator。⛔ 這一份**不進任何 subagent 的派遣包**。 -->
# 規則的來歷：每一條在防哪一次實測失效

> **什麼時候讀這一份**：⭐ **只有你要改／放寬／刪掉 `SKILL.md` 的某一條規則時。**
> 出一份週報從頭到尾用不到它 —— 跟 `BACKLOG.md`、`orchestrator-cost.md` 同一類。
>
> **它為什麼存在**：`editorial_policy.md` 開頭那句「**每一條都附理由** —— 說明這條規則
> 在防哪一種錯，**否則會被不知情地改回去**」。重構 `SKILL.md` 時把規則留在主檔、
> 把**理由與實測數字**搬到這裡，⛔ **不是刪掉**。
> 想改某條規則之前，先在這裡 `grep` 它的段名，看看它當初是被什麼撞出來的。
>
> **怎麼查**：下面每一塊都標了它在**重構前**的 `SKILL.md` 行號與段名。
> 段名對得上現行 `SKILL.md` 的節標題（少數節後來拿掉了「（後補）」這種後綴）。

## 目錄（24 個段落，依原 `SKILL.md` 行號排序）

- 〈三條凌駕一切的原則〉 SKILL.md 原第 102–105 行
- 〈派遣時**把路徑給 subagent**，你自己不必讀〉 SKILL.md 原第 162–164 行
- 〈⭐ 選材之前先合併（後補）〉 SKILL.md 原第 192–192 行
- ⭐ 選材之前先合併（後補）
- 〈排序信號：只排序，不決定上不上台〉 SKILL.md 原第 221–226 行
- 〈區間怎麼決定：從**上一份 deck** 推，不要手填〉 SKILL.md 原第 238–243 行
- 〈區間怎麼決定：從**上一份 deck** 推，不要手填〉 SKILL.md 原第 245–246 行
- 〈⭐ 問之前先填 `plan.narrative_candidates`，問完填 `plan.rebuttals`（N78）〉 SKILL.md 原第 316–316 行
- ⭐ 問之前先填 `plan.narrative_candidates`，問完填 `plan.rebuttals`（N78）
- 〈⭐ 第一題是最重要的一題（後補）〉 SKILL.md 原第 330–330 行
- ⭐ 第一題是最重要的一題（後補）
- 〈outline 頁：全場 1 張 ＋ 每條線 1 張（定義）〉 SKILL.md 原第 417–419 行
- 〈outline 頁：全場 1 張 ＋ 每條線 1 張（定義）〉 SKILL.md 原第 429–431 行
- 〈layer2 — 逐頁規劃（★ 關卡②）〉 SKILL.md 原第 437–442 行
- 〈關卡② 的逐頁表〉 SKILL.md 原第 502–504 行
- 〈關卡② 的逐頁表〉 SKILL.md 原第 509–514 行
- 〈⭐ 派 `slide_builder` 之前：先寫 `deck.json` 骨架（N61）〉 SKILL.md 原第 518–523 行
- 〈⭐ 派 `slide_builder` 之前：先寫 `deck.json` 骨架（N61）〉 SKILL.md 原第 538–546 行
- 〈畫圖不是一個動詞，是四個步驟〉 SKILL.md 原第 603–606 行
- 〈畫圖不是一個動詞，是四個步驟〉 SKILL.md 原第 611–613 行
- 〈⭐ 唯一的例外：書寫系統不同，不算改寫（後補，FINDINGS F10）〉 SKILL.md 原第 656–657 行
- ⭐ 唯一的例外：書寫系統不同，不算改寫（後補，FINDINGS F10）
- 〈⭐ 填值的是 `deck_assembler`，⛔ 不是協調者自己填（見下）〉 SKILL.md 原第 688–693 行
- 〈⭐ 派遣的順序（唯一定義，`delegation.md` 的「輪」數的就是這個）〉 SKILL.md 原第 765–774 行
- 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`（⛔ 不要一行一行手打）〉 SKILL.md 原第 789–796 行
- 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`（⛔ 不要一行一行手打）〉 SKILL.md 原第 831–834 行
- 〈骨架：`method` 是唯一預設有頁的格〉 SKILL.md 原第 447–450 行
- 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`〉 SKILL.md 原第 828–829 行

---

### 〈三條凌駕一切的原則〉 SKILL.md 原第 102–105 行

⚠️ **每一層結束就跑 `check_gate.py`，不要等到 Step 4。**（後補）
在此之前唯一會擋的是 `check_deck.py`，而它跑在**三個關卡全部之後**，
驗的卻正是關卡①② 的產物 → 流程上可以一路做完再回頭補填 `plan`，
**關卡①② 在機械上並不存在，只是散文**。這正是使用者覺得關卡都沒跳出來的來源。

### 〈派遣時**把路徑給 subagent**，你自己不必讀〉 SKILL.md 原第 162–164 行

⚠️ 角色清單的**唯一定義**是 `brief.py` 的 `ROLE_SPEC` —— 以前有 3／4／5 三種答案在流通，
而 `deck_assembler` 是唯一打包不出派遣包的角色，它的 5 項 Required inputs 只能手打；
**手打路徑正是舊路徑一路被抄進派遣訊息的成因**（`brief.py` 檔頭）。

### 〈⭐ 選材之前先合併（後補）〉 SKILL.md 原第 192–192 行

### ⭐ 選材之前先合併（後補）

### 〈排序信號：只排序，不決定上不上台〉 SKILL.md 原第 221–226 行

⚠️ **不要直接搬 `daily-log` 的公式**：那套是 `3×參與度 + 2×落地 + 1×延續 + 類別加權`，
而權重最高的**參與度來自 transcript**，週報端拿不到（也禁止重讀）。
這裡改用只有週報看得到的三個信號：**當日排名**（`items[]` 已照當天分數排序，
順序本身把日層級的分數帶過來了）、**跨日天數**、**落地規模**。
⛔ `kind` 不計分（`editorial_policy §1b`：工具的名字不決定去處）；
⛔ 教授交代不計分，它是第一順位，做法是印在最上面手動置頂，不是塞進分數裡稀釋掉。

### 〈區間怎麼決定：從**上一份 deck** 推，不要手填〉 SKILL.md 原第 238–243 行

⚠️ **不要自己填日期。** 實測查到過：這個 skill 一度**完全沒有游標**——
`--days` 的兩個日期一直是呼叫的人從對話裡推的。
當時確實有一份獨立的游標檔，但**沒有任何腳本讀過它**，於是它停在某一天之後
再也沒被推進，而週報照樣一份一份出——**沒有人發現**。
⛔ **不要另開第二份游標檔**（已知坑：同一事實寫在兩個地方，必定分岔）。
上一份 `deck.json` 的 `meta.range` 本來就記著「上次涵蓋到哪一天」，deck 又不會刪。

### 〈區間怎麼決定：從**上一份 deck** 推，不要手填〉 SKILL.md 原第 245–246 行

⚠️ **`--last N` 不可靠**：實際週報間隔是 5、7、8、7、8、**13**、8、7 天。
固定 7 天在那個 13 天的間隔上會漏掉 6 天。只保留給第一份週報。

### 〈⭐ 問之前先填 `plan.narrative_candidates`，問完填 `plan.rebuttals`（N78）〉 SKILL.md 原第 316–316 行

### ⭐ 問之前先填 `plan.narrative_candidates`，問完填 `plan.rebuttals`（N78）

### 〈⭐ 第一題是最重要的一題（後補）〉 SKILL.md 原第 330–330 行

### ⭐ 第一題是最重要的一題（後補）

### 〈outline 頁：全場 1 張 ＋ 每條線 1 張（定義）〉 SKILL.md 原第 417–419 行

**項數 ＝ 該條線的 `user_points` 條數**（`check_deck.py` 比對的就是這個），
⛔ **不是「該線的內容頁數」** —— `slide_types.md` 舊版寫成內容頁數，兩處分岔，
實測那一次是 5 對 4（FINDINGS N24）。**這一句是唯一定義，`slide_types.md` 已改成指路。**

### 〈outline 頁：全場 1 張 ＋ 每條線 1 張（定義）〉 SKILL.md 原第 429–431 行

⚠️ **這件事以前沒有規格**：首次實跑實際產了這個結構，但那是臨場做的，
而且當時三處互相矛盾（`SKILL.md` 說開場頁已移除、`check_deck.py` 的說明說「線超過 2 頁
要有開場頁」、實作用 `agenda` 繞過 `thread-intro` 的禁令）。三處已一併修正。

### 〈layer2 — 逐頁規劃（★ 關卡②）〉 SKILL.md 原第 437–442 行

**每條主線派一個 `slide_planner`**，平行跑。派遣包一條線一個：
```bash
for T in T1 T2 T3; do python3 $S/brief.py planner --thread $T --out $OUT; done
```
**3 條線就是 3 個 planner，各產一個 `_work/3_layer2/layer2.<線id>.json`。**
⛔ 不准把兩條線寫進同一個檔 —— `check_gate.py layer2` 會擋（見硬性規定第 14 條）。

### 〈關卡② 的逐頁表〉 SKILL.md 原第 502–504 行

欄位定義唯一見 `subagent-slide-planner.md` 的 Required outputs（那是產它的人讀的規格）。
⛔ 這裡不再抄一份欄位表 —— 舊版抄了一份，而且已經比那邊少了
「對應的 user_point」「形狀」「沒選的機制」三欄（已知坑 #13）。

### 〈關卡② 的逐頁表〉 SKILL.md 原第 509–514 行

確認後把**每一個** `_work/3_layer2/layer2.<線id>.json` 頂層的 `slide_plan_confirmed`
設為 `true` —— ⭐ **那是 `slide_builder` Preflight 讀的唯一權威欄位**。
（`deck.json` 的 `plan.slide_plan_confirmed` 是抄過去的**全域**旗標；
⛔ 不要叫 builder 去看它 —— 逐線的定案只有逐線那一份說了算，
全域旗標蓋不住「A 線確認了、B 線還沒」—— N19。
⚠️ **不再是「deck.json 那時還不存在」**：骨架現在就在下一節先寫好了，N61。）

### 〈⭐ 派 `slide_builder` 之前：先寫 `deck.json` 骨架（N61）〉 SKILL.md 原第 518–523 行

`deck.json` 以前要到 Step 4 才生成，於是 `slide_builder` 的**自驗綠燈**
（`verify.py --out <日期目錄> --thread <線id>`）**首次交件時跑不了** ——
`verify.py` 沒有日期目錄最上層的 `deck.json` 就 `sys.exit`。
⛔ **而首次交件那一輪正是自驗要消滅的東西**：上一場 builder A 被 resume 4 次，
**第 1、2 次的原因就是「builder 交件 → 協調者跑 `check_deck.py` → 退回」**，
而那些檢查 builder 自己也跑得動。只有返工輪跑得動的自驗 ＝ 這條規則只發揮一半效果。

### 〈⭐ 派 `slide_builder` 之前：先寫 `deck.json` 骨架（N61）〉 SKILL.md 原第 538–546 行

- ⛔ **`slides` 一定是空的。** 不要把 `deck.draft.json` 的候選頁留在裡面 ——
  那是**篩選前**的候選頁，不是 builder 產的頁（`merge_slides.py` 檔頭那條警告講的就是這個）。
  `merge_slides.py` 認得「第一次合併時 `slides` 是空的」，會把 builder 的頁**整批加進去**。
- ⛔ **全場 outline 頁不在骨架裡。** 它是 `deck_assembler` 的產出，
  **協調者不得自己寫**（N25／F14）——那條規則沒有因為骨架提前而改變。
- 於是 Step 4 只剩**整形**：`merge_slides.py` 填 `slides`，你視需要縮 `point`、
  把 `output` 改成 `null`。⛔ 它不再是「生成整份 deck.json」的那一步。
- ⚠️ 骨架在了，`slide_builder` 的自驗就**沒有例外可講**：`deck.json` 不在 → 它回報
  `BLOCKED`，⛔ 不是自己造一份（`references/subagent-slide-builder.md` 的 DONE 一節）。

### 〈畫圖不是一個動詞，是四個步驟〉 SKILL.md 原第 603–606 行

⭐ **決定要畫之後，先查那份的「Step ⓪b 路由」再動手** —— 它決定**用哪個工具畫**
（`pipeline` 版型／`render_figure.py`／手刻 SVG／退回表格），由上往下選。
少了這一關每張圖都會直接掉到「手刻」那格：首次實跑那份 10 頁有 6 張手寫 SVG，
圖來回改了四輪。⛔ 路由表不在這裡複製一份（同一事實寫兩處必定分岔）。

### 〈畫圖不是一個動詞，是四個步驟〉 SKILL.md 原第 611–613 行

⚠️ **有 renderer 的八個**：`read_pileup`／`haplotype_split`／`chain`（＝`chain_gated`）／
`group_blocks`／`two_col_link`／⭐ `funnel`（＝`funnel_named`）／`transform_pair`／`before_after`。
⭐ **手繪已經降到 0 張** —— `diagram-craft §0` 的 2–3 張額度整個空出來，留給真正沒見過的圖。

### 〈⭐ 唯一的例外：書寫系統不同，不算改寫（後補，FINDINGS F10）〉 SKILL.md 原第 656–657 行

⚠️ **單位換算也算改寫。**「3,664 萬列」寫成 `36,640,000` 會被擋。
### ⭐ 唯一的例外：書寫系統不同，不算改寫（後補，FINDINGS F10）

### 〈⭐ 填值的是 `deck_assembler`，⛔ 不是協調者自己填（見下）〉 SKILL.md 原第 688–693 行

⭐ **「填值」有主人**：`deck_assembler`（`references/subagent-deck-assembler.md`）。
輸入 `strings.zh.json` ＋ `deck.json` 的 `plan.terms.objects` 與 `plan.quotes`，
輸出填好的 `strings.zh.json` ＋ `_work/4_slides/assemble_note.md` 的中英對照表。
⚠️ 上一次盲測 169 句是協調者自己填的，而四個 `subagent-*.md` 都不含翻譯、
也沒有任何機制保證同一個具名產物在 169 句裡譯名一致（FINDINGS N31）——
而「同一件事一直用同一個名詞」是使用者明列最在意的四件事之一。

### 〈⭐ 派遣的順序（唯一定義，`delegation.md` 的「輪」數的就是這個）〉 SKILL.md 原第 765–774 行

- **結構頁 body 缺欄位**（`check_deck.py` 檢查項 11）：`render_deck.py` 會停在那一頁，
  訊息指名頁與欄位（`第 12 頁（id=BSEP、type=thread-intro）：body 缺少必填欄位 'label'、'title'`）
  → 補那一頁再 render。**其餘 ERROR 都不擋 render**（實測：3 頁 `point` 超長 ＋ 1 個
  `input` 未登記，共 4 個 ERROR，兩版 render 都 exit 0）。
- **會改變版面的 ERROR**（要拆頁／換版型／重畫圖）碰到**超過 1/3 的內容頁**：
  reviewer 會去審一批即將重畫的圖，等於白審 → 先修這一輪再派它。
  ⭐ **判準是種類不是總數**：`point` 超長／`from` 不逐字／數字溯源／`source` 這幾類
  只改字不動版面，reviewer 的四項（全域一致性、面積、標籤用途、mechanism 深度）
  照樣審得準 → 一律合併，⛔ 不要為了它們多走一輪。
  （⚠️ `point` 超長與 `from` 不逐字現在擋在關卡②，走到這裡時應該已經沒有了。）

### 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`（⛔ 不要一行一行手打）〉 SKILL.md 原第 789–796 行

**為什麼是一支腳本**：⭐ **規格的形狀決定行為**。這裡以前寫成六行分開的指令，
協調者就一行一行跑 —— **每一行是一個 API 回合，每個回合都把當下整段 context 重送一次**
（`成本 = Σ(每一回合當下的 context)`，context 只增不減）。實測：這條序列一場跑 6 次 ×
4~6 個回合 ≈ **30 個回合**，換成腳本是 **6 個回合**，多出來的那 24 個回合買到的東西是 0。
⚠️ 舊版這裡有一條「跑檢查時不要接 pipe（`| tail`、`| grep`），exit code 會變成 pipe
尾端的」的警告 —— 那條**假設你手動一行一行跑**。`verify.py` 直接拿每一支的 returncode
（不經 shell、不接 pipe，等價於 `set -o pipefail`），這個坑在腳本裡不存在；
**你自己另外手跑某一支時它仍然成立**（要看尾巴就分兩次跑，或 `set -o pipefail`）。

### 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`（⛔ 不要一行一行手打）〉 SKILL.md 原第 831–834 行

**兩個檔案一起交給使用者**：`deck.zh.html` 與 `deck.en.html`。
⛔ **不要說哪一份是「正式版」，也不要替他選** —— 兩版平等，兩份一起交。
⛔ **不要手改 `deck.en.html`／`deck.zh.html`**——版面問題改 `assets/deck.css`（一次改全部頁），
內容問題改 `deck.json`。

### 〈骨架：`method` 是唯一預設有頁的格〉 SKILL.md 原第 447–450 行

**四格都預設有頁會製造脈絡頁** —— 3 條線自動生出 3 張鋪陳頁 ＋ 3 個 problem 格，
16 頁裡 9 頁是背景、動機、成果清點。四格是「一場完整演講」的形狀，
而**週報是延續中的對話**，教授上週就在場。

### 〈⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`〉 SKILL.md 原第 828–829 行

⚠️ `merge_slides.py` 是**必經**的一步，不要手動合併 —— builder 每輪都會把你縮短過的
`point` 與改成 `null` 的 `output` 帶回舊值（首次實跑手動重套了 6 次）。

---

## 2026-09-06 補：B14 九個規格缺口的來歷

⚠️ **這九條的來歷不是「跑週報時撞到」，而是一次 C 層驗證**：讓一個**沒有這個 skill 任何
記憶**的 agent **只讀 `SKILL.md`**（一份 reference 都沒開）重建整條流程，它把流程全部
重建對了，另外指出這九個洞。逐條比對過重構前的 `SKILL.md` —— ⛔ **九個全部是既有問題，
不是重構造成的**。完整清單見 `BACKLOG.md` B14。

**為什麼值得修**（用這個 repo 自己的量測）：`orchestrator-cost.md` 量到「中途插進來修 skill」
佔協調者帳單 **18.9M（26%）**，根因是 `delegation.md` 自己寫過的那句 ——
「第 1、2 次返工的**根因不是溝通不良**，是**規格自己互相矛盾**」。
對照：把 `SKILL.md` 再砍 400 行只省 2.01M。**修缺口的期望效益高一個數量級。**

### 〈⛔ 不在必讀之列〉— 「權威在程式裡，而程式會把它印給你」（②）

**原本會怎麼壞**：`SKILL.md` 多處寫「唯一定義在 `verify.py` 的 `STEPS`／`check_deck.LIMITS`／
`shoot.py`」，同一份又寫「⛔ 不要讀 `scripts/*.py`」→ 讀起來是矛盾，於是走上第三條路：
**憑印象把數字寫進來**（N67 的「憑印象填 540」就是這樣來的），或違規把整支 python
載進協調者的 context（協調者的 context **每一回合都完整重送**，成本要乘上整場回合數）。

**查證**（2026-09-06）：`verify.py --help` 會把七步印出來（`--stop-after` 的 choices）；
`check_deck.LIMITS["point"]` 在擋你時把上限印在訊息裡（`103 > 90 字`）。
→ ⭐ **這其實不是矛盾**，是一句從沒被寫下來的原則。補那一句就解了。

### 〈版型是起點，不是牢籠〉— 刪掉重複的「試錯上限 2 次」（④）

**原本會怎麼壞**：Step 0 的表自己註明「⛔ 上限的數字只有 `delegation.md` 那裡有一份」，
但這一節又寫了一次數字 —— **正是它要防的雙寫**。`delegation.md` 改上限時這份不會跟著改，
而協調者整場都帶著 `SKILL.md` → 以過期的那份為準。
→ 刪數字、留指標。`delegation.md` 本來就在協調者的必讀清單第一列，拿得到。

### 〈⭐ outline／agenda 是結構頁，不是內容頁〉（⑥）

**原本會怎麼壞**：檢查項 11a 要「Σ`pages` == 實際主線內容頁數」、第 14 條要「每頁都要
對得上一條 `user_point`」，而各線 outline 是**逐字抄 `user_points` 的結構頁**、全場 outline
由 assembler **事後**加入且不在骨架裡 → 要嘛把它們算進去讓 Σ 永遠對不上，
要嘛替結構頁硬編一條 `user_point`。

**查證**：`check_deck.py` 的 `STRUCT = {"cover", "agenda", "thread-intro"}`，
第 767 行註解寫著「結構頁本來就不進逐頁內容檢查」。⛔ 零決策，照抄程式的既有行為即可。

### 〈⭐ ⑦ 削減回合：planner 自己做，你在關卡② 一併呈現〉（⑧）

**原本會怎麼壞**：`trim_pass` 在 `SKILL.md` **全文 grep = 0**，而 `check_gate.py layer2`
會為它 `exit 1` → 協調者無從預期，跑到關卡② 才炸，整條線返工。
規格其實**早就完整存在**於 `subagent-slide-planner.md §7`（三個提問 ＋
`{reviewed, proposals, kept}` 輸出格式），**缺的只是 `SKILL.md` 沒把它接進 layer2 流程**。

**為什麼一定要有這一步**：①~⑥ 是生成程序（一個 `user_point` 一頁），**本身沒有任何
往下收的力量**，頁數只會等於重點數。使用者的話：「只要有講到重點，基本上是不會需要
那麼多投影片的」。
**為什麼 planner 只能提議**：靜靜砍掉一頁 = 靜靜砍掉他要講的東西；`kept` 必填，
否則使用者分不出「檢查過並保留」與「根本沒被想過」。
〔2026-09-06 使用者裁決：planner 做、關卡② 呈現，⛔ 不移到協調者或 layer3〕

### 〈Step 4 派遣的順序〉— `deck_assembler` 插進第 3 步（①）

**原本會怎麼壞**：layer3 開頭只寫「每線一個 builder ＋ 1 個 layout_reviewer」，
Step 4 的派遣順序（**唯一定義**）也沒有它 → **什麼時候派它，一處都沒說**。
後果是它負責的兩個必要產物沒有主人：全場 outline（協調者只好違規自己寫，正是 N25／F14
上次盲測踩到的）與 `strings.zh.json` 填值（缺了 `verify.py` 的 `strings` 步會**永遠**
擋住中文版）。

**硬限制**：它的 Preflight 要求 `deck.json` 的 `slides` 非空 → ⛔ 不可能跟 builders 同一輪。
〔2026-09-06 使用者裁決：**單獨一輪，插在第 2、3 步之間**〕
**為什麼不跟 `layout_reviewer` 同一輪**（省一個回合的那個選項）：那樣 reviewer 審的 HTML
還沒有全場 outline、中文版還是半英文 → **那一頁與整個 zh 版等於沒人審過**，
而 reviewer 是唯一擋得住稀疏版面的角色（N52：機械檢查對「框多字少」是瞎的）。

### 〈★ 關卡③ — 讓使用者看長相〉（③）

**原本會怎麼壞**：流程圖標著「★ 關卡③ 瀏覽器翻」，但 layer3 整節**沒有任何**停下來問
使用者的步驟或問法 —— 關卡① 有六題表、關卡② 有逐頁表，**關卡③ 是唯一沒有主持腳本的**。
後果：把兩個 HTML 丟出去就當結束。而「彈出來的選單看得出這是一個關卡，一段普通文字
看不出來」是這份 skill 自己寫過的話 → 使用者不知道輪到他，`plan.feedback` 空著。

**為什麼問法要固定成三題選擇題**：關卡② **刻意不給任何長相**（那時看 HTML 會讓人開始
評論視覺，而視覺是 layer3 的事）→ **關卡③ 是唯一該讓他看長相的一關**，
問法不能比另外兩關隨便。⭐ 第 2 題問「看不懂／名詞不一致」而不是「好不好看」：
名詞前後不一致是使用者明列最在意的四件事之一，而**只有翻完整份的人看得出來**
（各 `slide_builder` 看不到彼此的頁，這是「一條線一個 subagent」粒度的已知代價）。
〔2026-09-06 使用者裁決：固定三題選擇題，⛔ 不用開放式問句〕

### 〈Step 0 必讀〉— `paths.py explanations` 的 `exit 1` 是正常（⑦）

**原本會怎麼壞**：`paths.py explanations` 不存在時 `exit 1`，而收尾又要求「不可省地寫它」
（N79）→ 協調者把 `exit 1` 讀成出錯，停下來問使用者、或自己先建一個空檔。
〔2026-09-06 使用者裁決：**不建**，明寫 `exit 1` ＝ 這週沒有累積的未答提問；
第一次建立的時機是**收尾那一步**，因為那時才有內容可寫〕
⚠️ 與 **B8**（「`_explanations.md` 已過期」）是同一件事的兩半。

### 〈`build_deck.py` 的 `QUESTIONS`／`plan_todo()`〉— 補回六題表的第 1、2 題（⑤）

⚠️ **這一條不是文件矛盾，是安全網破洞。** `plan.todo.json` 的存在理由是
「把『記得要問』變成『有一個檔案空著』」，但把它的四題與 `SKILL.md` 六題表逐題對起來
（2026-09-06 實測）：

```
todo1 = 六題表第 3 題（這週的主角是哪一件事）
todo2 = 六題表第 4 題（讓什麼從做不到變成做得到）
todo3 = 六題表第 5 題（教授上次問了什麼／指定方向）
todo4 = 六題表第 6 題（不想展開／要不要鋪陳頁）
⛔ 缺 第 1 題（這幾項是同一件事嗎 —— 合併的定案）
⛔ 缺 第 2 題（這條線只講 3~4 個重點是哪幾個 —— 存成 user_points）
```

**缺的第 2 題，正是 `SKILL.md` 用一整節叫它「⭐ 第一題是最重要的一題」的那一題** ——
它**直接決定有哪幾頁**。`grep -n "3~4 個重點\|user_points\|同一件事嗎" scripts/build_deck.py`
當時**零命中**。⛔ **那個防呆清單，剛好漏掉最該防的那一題。**
沒問它的後果 `SKILL.md` 自己記著：「使用者要的四個重點裡，**兩個因為不在敘事句裡被排除、
一個連候選都沒進去**」。

**修法與兩個注意**：
· 第 2 題是**逐條主線各問一次**，而 `build_deck.py` 跑在 layer1 **之前**、還不知道有幾條線
  → 樣板裡留成 `_per_thread: true` 的「每條主線各一題」形狀，⛔ 不要寫死成一題。
· `check_deck.py` 只要求 `plan.answers` 至少 3 題且每則 `a` 非空 —— ⛔ 補題**不會**讓那條
  檢查變嚴，**防呆效果來自「檔案上看得到一個空格」**，不是來自 checker。


---

## 2026-09-06 PR 2：`SKILL.md` 從 64 KB 瘦到 16 KB —— 搬出來的東西都在下面

**為什麼**：協調者每一個回合都重送整份 `SKILL.md`。實跑 18.1M tokens 的協調者帳單裡，
開場那 ~7 萬 token（SKILL.md ＋ delegation.md ＋ deck_schema.md）× 一兩百個回合就是四成。
而 64 KB 裡有四節是 builder 的規則（`subagent-slide-builder.md` 已有同一份）、
Step 4 一節有一半是「為什麼」、18 行是「唯一定義在 X、這裡不重抄」這種只在說明自己不重複的話。

**這不是砍判準**：規則留在執行它的地方（角色規格、`check_deck.py --limits`、各 gate 的訊息），
理由與歷史搬到這裡。⛔ 要改某條規則之前，先在下面 grep 它的段名，看它當初是被什麼撞出來的。

**同一批一起改的流程決定**（理由在 `orchestrator-cost.md`「2026-09-06 生產跑」）：
- 一層一個 session（入口 `layer1`／`layer2`／`layer3`）；狀態全在磁碟、`check_gate.py` 接手。
- 單線的週不派 subagent，協調者自己扮演角色；≥2 線才平行派 planner／builder。
- `deck_assembler` 拿掉：outline 由 `merge_slides.py --outline` 產（逐字複製，無判斷）；
  譯文由 builder 交 `strings.<線>.zh.json`，名詞中譯在關卡② 凍結（`plan.terms_zh`）。
- `layout_reviewer` 改 opt-in（`--review`），輸入是 `review_packet.py` 的包；
  三項純機械的判準搬進 `check_deck.py`（手繪配額、金字組合、樣板佔位符）。
- 關卡①② 的確認稿由 `gate_view.py` 排固定模板（借 asiapathogenomics `weekly-deck-builder` 的做法），
  定案檔由 `check_gate.py --confirm` 與 `build_deck.py --skeleton` 寫。
- 返工派 `fixer`（新 agent ＋ 修復包），不 resume。

### 附錄：瘦身前的 `SKILL.md` 全文（2026-09-06 之前的版本，逐字）

> 下面是舊版全文。節標題若被其他檔案指路（「SKILL.md Step 4」「數字那一節」），在這裡還找得到。



# Weekly Deck

輸入是**已經編輯過的每日日誌**，不是研究現場。`/daily-log` 每天已經把 git、
對話紀錄整理成「問題→做法→結果→解讀」。本 skill 只做兩件事：
**跨日合併成敘事**，以及**排成投影片**。

```
.data/*.json ──merge_items─────> merge_groups.md    ★ 跨日合併提名 ＋ 排序信號
             ──cluster_threads──> threads.md        物證：碰過同一批檔案的項目
             ──build_deck──────> materials.md       素材（已按合併組分節）
                                 deck.draft.json
   ─────────────────────────────────────────────────────────────────
   layer1  找主線（2~4 條）          → layer1.md      ★ 關卡① bullet list
              ↓ check_gate layer1（會擋）
   layer2  逐頁規劃 + I/O 契約       → layer2.*.md    ★ 關卡② 逐頁表
              ↓ check_gate layer2（會擋）
   layer3  產 HTML                   → deck.zh.html   ★ 關卡③ 瀏覽器翻
   ─────────────────────────────────────────────────────────────────
                    ↓ check_deck（機械檢查）→ render 兩版
                    ↓ shoot --check-only（量溢位 + 版面自檢，⛔ 必跑）
                    ↓ layout_reviewer（跨主線版面審查）
                    ↓ 三方 findings 合成**一輪**退回 builder（順序見 Step 4）
                       deck.en.html / deck.zh.html ＝ 交付物（直接開來上台講）
                    ↓ shoot（截圖）→ to_pptx        ← 選用，要交檔才做
                                 _export/weekly_report_<週>.pptx
```

輸出目錄：`<週報輸出根>/<今天>/`，三條規矩：

- **⭐ 交付物（`deck.en.html`／`deck.zh.html`）在最上層，過程產物一律進 `_work/`。**
- **`deck.json` 留在日期目錄本身**，⛔ 不要挪進 `_work/` —— 四支腳本都從它的所在目錄
  推算 `figures/`、`strings.<lang>.json` 與輸出位置，挪走會整組錯位。
- **`--out` 只給日期目錄**，子資料夾由腳本自己開。⭐ **寫過程產物一律用
  `paths.work_file(out, "<檔名>")`** —— 只說檔名，路徑由它決定；認不出來的檔名它會
  **報錯**而不是猜一個位置。⛔ 不要自己拼 `_work/...`（N14 就是那樣來的）。

> 📂 **完整目錄樹、`_work/` 的四個階段、以及舊結構（多一層 `deck/`）的相容規則
> → `references/output-layout.md`。** 要寫過程產物卻不確定它落在哪一層、
> 或 `--since-last-deck` 翻到長得不一樣的舊週報時才需要開它。

> 週報輸出根 ＝ `python3 .claude/skills/weekly-deck/scripts/paths.py reports-root`，
> 預設 `<日誌 repo>/weekly`。⛔ **不要在流程裡寫死絕對路徑。**
> 安裝與設定見 `README.md` —— weekly-deck 是 daily-log 的後處理，**兩個 skill 必須成對安裝**。

## 三條凌駕一切的原則

**① `deck.json` 一律寫英文，中文版靠字串對照表產生。**
⛔ **兩版是平等的交付物，沒有哪一版是「正式版」** —— 實驗室多數人講中文版，
但有外籍生，兩版會同時流通。用哪一版報告由講者當場決定。
⚠️ **但每一版都要標出自己是哪一版**：`render_deck.py` 會在 `<html data-lang-label>`
寫上 `EN`／`中文`，播放器把它顯示在控制列。全螢幕時看不到檔名，沒有這個標記就分不出來。
⚠️ **兩版都要在請使用者審閱之前產好** —— 他不見得看哪一版，兩份一起交。
`point`／`from`／`to`／`notes`／`why_text` 可用中文。

**② 只留對講解有幫助的東西，其餘全部拿掉。**
已據此移除的：封面頁、週敘事頁、頁碼、線標籤、`thread-intro` 版型的線開場頁、
「待決與下一步」頁、底部結論條。**簡報從 outline 頁直接開始。**
新增任何元件前先問：這幫聽眾理解了什麼？

⚠️ **「移除線的開場頁」指的是 `thread-intro` 那個版型**（它現在只剩 backup 分隔頁一個用途），
⛔ **不是說各線不能有 outline** —— 各線的 outline 用 `agenda` 版型，見下方「outline 頁」。

**③ 三個關卡不是拖慢，是把判斷挪到最便宜的時候做。**
layer3 一頁畫錯要重畫，layer1 判錯只是改一行字。
目標不是「減少使用者的 effort」而是**減少返工**——這兩件事在頭幾週是反向的。

⚠️ **每一層結束就跑 `check_gate.py`，不要等到 Step 4。**
在此之前唯一會擋的是 `check_deck.py`，而它跑在**三個關卡全部之後**，
驗的卻正是關卡①② 的產物 → **關卡①② 在機械上並不存在，只是散文**。

---

## 兩種啟動方式

| 打什麼 | 做到哪裡 |
|---|---|
| `/weekly-deck` | 全程跑完 |
| **`/weekly-deck plan`** | **只做到 layer2 關卡② 為止**就停 |

`plan` 寫進 `deck.json` 之後就凍結，之後跑 `/weekly-deck` 直接沿用、不再重問。

---

## Step 0 — 必讀

⚠️ **這張表分兩半，⛔ 不要整份讀完再開始。**
協調者的 context **每一回合都會被完整重送**，subagent 的只重送它自己那幾回合 ——
所以協調者多讀 1 KB 的成本要乘上整場的回合數，subagent 只乘它自己的。

### 你（協調者）現在就要讀

| 檔案 | 用途 |
|---|---|
| **`references/delegation.md`** | subagent 派遣協定（主線粒度、**試錯上限**、共同輸入）⛔ 上限的數字只有那裡有一份 |
| `references/deck_schema.md` | `deck.json` 欄位定義（關卡② 通過後先寫骨架，Step 4 只做整形） |
| `<週報輸出根>/_explanations.md`（若存在） | 未答的教授提問 → 必講且排最前；重複的概念沿用同一套說法 |
| 上一份 `<週報輸出根>/*/deck.json` | 上次講到哪、留了哪些 backup、`plan.feedback` |

⭐ **後兩項的路徑用腳本問，⛔ 不要自己 glob、也不要自己判新舊結構**：

```bash
python3 $S/paths.py last-deck        # 上一份 deck.json 的絕對路徑（新結構優先，舊結構也認）
python3 $S/paths.py explanations     # _explanations.md 的絕對路徑（不存在時 exit 1）
```

⭐ **`explanations` 那一行 `exit 1` 是正常結果，不是錯誤**：代表這週沒有累積的未答教授提問。
⛔ **不要為它停下來問使用者，也⛔ 不要自己先建一個空檔** —— 它第一次被建立的時機是
**收尾那一步**（「同一時間也要寫 `_explanations.md`」），因為那時才有內容可寫。
⚠️ `last-deck` 的 `exit 1` 同理：代表這是第一份 deck。

### 派遣時**把路徑給 subagent**，你自己不必讀

⛔ 讀了等於整場每回合重送一次。需要引用其中某一條規則時，去 `grep` 那一行，不要整份載入。

誰讀哪一份由 `brief.py` 的 `INLINE_REFS` 決定 —— `python3 $S/brief.py --show-refs`。
⛔ 這裡不抄第二份。

⭐ **五個角色的派遣包都用 `brief.py` 打，⛔ 不要手打路徑**（N65）：

```bash
python3 $S/brief.py finder              --out $OUT
python3 $S/brief.py planner  --thread A --out $OUT
python3 $S/brief.py builder  --thread A --out $OUT
python3 $S/brief.py reviewer            --out $OUT   # 跨主線，不吃 --thread
python3 $S/brief.py assembler           --out $OUT   # 同上
```

⚠️ 角色清單的**唯一定義**是 `brief.py` 的 `ROLE_SPEC`。**手打路徑正是舊路徑一路被抄進
派遣訊息的成因**（`brief.py` 檔頭）。

### ⛔ 不在必讀之列

| 檔案 | 什麼時候才讀 |
|---|---|
| `references/BACKLOG.md`、`references/orchestrator-cost.md` | **只有要改這個 skill 時。** 它們回答「別去做已經決定延後的事」「判準該不該瘦身」，那是開發需求，不是出週報的需求 |
| `references/rule-provenance.md` | **只有要改某一條規則時**（想知道它在防哪一次實測失效） |
| `references/output-layout.md`、`gate-facilitation.md`、`delivery.md` | 走到對應情況才讀，各檔開頭第一段就寫著是哪些情況 |
| `scripts/*.py` | 那是拿來**跑**的，不是拿來讀的。⚠️ 例外：某一頁要講某支腳本的機制時，去讀那一支 |

⭐ **一條沒被寫下來過的原則：規格的權威在程式裡，而程式會把它印給你 ——
所以「唯一定義在某支腳本裡」⛔ 不等於「你要去讀原始碼」。**

本檔多處寫著某條規則的唯一定義在腳本裡（機械序列在 `verify.py` 的 `STEPS`、
`point` 上限同源 `check_deck.LIMITS`、「容器過空」門檻見 `shoot.py`、
逐線對帳在 `check_gate.check_per_thread()`）。那不是矛盾，是分工：

| 想知道 | ⛔ 不要做 | ⭐ 這樣拿 |
|---|---|---|
| 機械序列有哪七步 | 讀 `verify.py` | `python3 $S/verify.py --help`（`--stop-after` 的 choices 就是七步）|
| `point` 上限幾個字 | 讀 `check_deck.py` | 照寫，被擋時訊息會把上限印出來（`103 > 90 字`）|
| 「容器過空」門檻多少 | 讀 `shoot.py` | 跑 `shoot.py --check-only`，被擋的頁與門檻都在輸出裡 |
| 逐線檔少了哪一條 | 讀 `check_gate.py` | 跑 `check_gate.py layer2/layer3`，它指名是哪條線 |
| 任何門檻／豁免清單（`SLOT_EXEMPT`、`STRUCT`、`LIMITS`、頁數上限、`slide_plan` 的合法 body） | 讀 `check_deck.py` | `python3 $S/check_deck.py --limits` 一次印完 |

**⛔ 絕不可以做的是第三條路：憑印象把數字寫進來。** 那正是 N67
（「憑印象填 540」）與各種過期數字的成因。

---

## Step 1 — 抽素材

```bash
S=.claude/skills/weekly-deck/scripts
OUT="$(python3 $S/paths.py reports-root)/$(date +%F)"   # ⛔ 不要寫死路徑；子資料夾腳本自己開
python3 $S/merge_items.py     --since-last-deck --out $OUT   # → _work/1_materials/merge_groups.md
python3 $S/cluster_threads.py --since-last-deck --out $OUT   # → _work/1_materials/threads.md
python3 $S/build_deck.py      --since-last-deck --out $OUT   # → _work/1_materials/materials.md
```

`build_deck.py` 一次產**三份**：`materials.md`（素材）、`deck.draft.json`（候選頁骨架，
頂層形狀＝`deck.json` 的形狀）、`plan.todo.json`（★ **待問使用者的六題，`a` 全部空著**）。
⭐ `plan.todo.json` 是「把『記得要問』變成『有一個檔案空著』」——
它的六題與下面 layer1「然後停下來問」那張六題表**逐題一一對應**（同一組問題的兩份載體），
答案最後都要進 `plan.answers`（`check_deck.py` 會要求每一則 `a` 非空）。
⚠️ **第 2 題帶 `_per_thread`：它是「每一條主線各問一次」。** `build_deck.py` 跑在 layer1
**之前**、還不知道有幾條線，所以檔案裡只放得下一則模板 —— 關卡① 判出幾條線就**複製成幾則**，
⛔ 不要壓成全場一題（它決定有哪幾頁，見下面「第一題是最重要的一題」）。
⚠️ **沒有任何一支腳本會讀它**（N104）—— 它是給**你**用的清單，⛔ 不是產物。

### ⭐ 選材之前先合併

**`merge_items.py` 一定要先跑。** 它做的事是 `daily-log` 的合併判準漏掉的那一半：

> `daily-log` 的合併判準（`selection-signals.md` Step 2-2）**只在單日內生效**。
> 同一件事做三天，就會產生三個獨立 item，**週報端沒有任何一步會把它們併回去**。

| | 做什麼 | 粒度 |
|---|---|---|
| `merge_items.py` | 這幾個 item **是不是同一件事** | item ↔ item |
| `cluster_threads.py` | 這些事**屬於哪一條主線** | 主線 |

兩支互補，不重疊。⛔ **不要只跑其中一支。**

**它只提名，不裁決。** 機械驗得了的只有兩種物證（主要模組相同 ＋ 改的是同一批檔）；
`daily-log` 的四條判準是語意的，要 LLM 逐組確認、使用者拍板。
⚠️ **沒有 `artifacts` 的項目一定落單** —— 純討論、純量測、純讀論文都不會留下檔案。
那不是雜訊，是機械看不見的那一半，跟 `threads.md` 的孤兒一樣要補掛。

### 排序信號：只排序，不決定上不上台

`merge_groups.md` 每組有一個 `score`。**它只用來排候選的順序。**
上不上台由關卡① 的使用者決定（`user_points` 那條已經把決定權給他了）。

⚠️ **不要直接搬 `daily-log` 的公式**：那套的權重最高項是**參與度**，來自 transcript，
週報端拿不到（也禁止重讀）。這裡改用只有週報看得到的三個信號：**當日排名**
（`items[]` 已照當天分數排序）、**跨日天數**、**落地規模**。
⛔ `kind` 不計分（`editorial_policy §1b`：工具的名字不決定去處）；
⛔ 教授交代不計分，它是第一順位，做法是印在最上面手動置頂，不是塞進分數裡稀釋掉。

沿用 `daily-log` 的兩條紀律：**印原始信號不只印分數**（看得出為什麼才推翻得了）、
**分數不寫回日誌 JSON**。

### 區間怎麼決定：從**上一份 deck** 推，不要手填

`--since-last-deck` 會讀**日期最大的那一份** `deck.json`（舊結構也認得，新的優先），
起日 = 它的 `meta.range[1] + 1 天`，迄日 = 今天。底線開頭的目錄一律排除。

⚠️ **不要自己填日期，也不要另開第二份游標檔**（已知坑：同一事實寫在兩個地方，必定分岔）。
上一份 `deck.json` 的 `meta.range` 本來就記著「上次涵蓋到哪一天」，deck 又不會刪。

**要覆寫區間**（例如某幾天已經口頭報過）→ 用 `--days <起> <迄>`。
腳本會把它跟推導值比對，**有缺口或重疊就印警告**——
刻意跳過的話，把理由寫進 `deck.json` 的 `meta.range_note`，不要讓它無聲消失。
⚠️ **`--last N` 不可靠**（實際週報間隔 5~13 天不等），只保留給第一份週報。

**三份都要讀。** `merge_groups.md` 是合併提名與排序，`threads.md` 是物證（碰過同一批
檔案的項目），`materials.md` 是內容（已按合併組分節）。

### ⚠️ 但 `materials.md` 只是起點

**日報是壓縮過的**——保留結論、丟掉機制。凡是要講「**怎麼做的**」「**有哪些**」
「**為什麼會這樣**」的頁面，日誌的摘要一定不夠。
`materials.md` 最後一節「可深入的原料」列出日誌 `artifacts` 指到的檔案路徑，
**規劃到哪一頁需要細節就去讀對應的檔。**
⚠️ 派遣包裡的那一節**只收你這條線的 sid** —— 被略過的列數與原檔絕對路徑就寫在該節下面，
要全貌就去讀原檔（⛔ 不要以為「包裡沒有」＝「沒有原料」）。

> **日誌告訴你「發生了什麼」，`docs/` 才有「長什麼樣」。**

### 不要重讀 session transcript

`/daily-log` 每天已經掃過。週報再讀一次是重複付費，而且很貴（一週可能數百 KB）。
**今天的工作若還沒寫日誌**：先跑 `/daily-log` 補成 JSON，
**不要把今天的內容直接寫進 deck.json**——日誌是事實來源，繞過它會讓投影片上
有日誌裡沒有的東西（數字溯源檢查也會擋）。

---

## layer1 — 找主線（★ 關卡①）

派遣 `thread_finder`，依 `delegation.md` 的骨架。
⭐ **必要輸入用 `brief.py` 打包，⛔ 不要在派遣訊息裡手打一長串路徑**：
```bash
python3 $S/brief.py finder --out $OUT   # → $OUT/_work/_briefs/brief.finder.md
```

它做四件事：**逐組確認 `merge_groups.md` 的合併提名**（寫得出一個共同目標的標題嗎？
寫不出來就拆回去）→ 用 `threads.md` 的物證分群 → 補孤兒（**必須說出共用什麼**）→
給每群一個教授聽得懂的名字，判 `single` / `multi`。

⚠️ **合併要在分群之前做完。** 順序顛倒的話，主線裡仍然是一堆平行的零件。

⚠️ **layer1 做的是「粗選材」**（這一項有沒有去處），用 `editorial_policy §1b ＋ §2`。
**§0 的「在敘事裡有沒有角色」此時不適用**——那句敘事還不存在，而且只有使用者寫得出來。
細選材（排序、份量、降不降 backup）在 layer2 做。分工見 `editorial_policy §0a`。

**抽象的層級要對。** 十幾個 item 可能全部都是「建立 X 工具」與「建立 Y 工具」的零件——
主線是**那兩件事**，不是十幾個零件。⛔ 反例：把 4 個平行的工作各列一條主線，
其實它們是同一件事的不同面向。

**`threads` 最多 4 條**；判出來超過就把第 5 條以後放 `overflow_threads`，
連同「合併進哪條／降 backup／擠掉誰」三個選項問使用者。
⛔ **不准為了不超過 4 條而硬掛**——掛不掛由 evidence 決定，數量是結果不是配額。

### 然後停下來問

`thread_finder` 會回一份 `questions_for_user`。用 `AskUserQuestion` 問，
把**原話**填進 `plan.answers`（`check_deck.py` 要求至少 3 題）。固定問：

| 問題 | 決定什麼 |
|---|---|
| **這幾項是同一件事嗎？**（列出被提名合併、以及被拆開的組）| 合併的定案 |
| ⭐ **每一條線：「這條線如果只講 3~4 個重點，是哪幾個？」** | **這條線會講什麼**（存成 `threads[].user_points`）|
| 這週的主角是哪一件事？（選項要含「多個主角／兩條線並行」） | 敘事重心、`plan.mode`、排序 |
| 這週讓什麼從「做不到」變成「做得到」？ | 結論——⚠️ 要允許「不需要單一結論」 |
| 教授上次問了什麼還沒回答？**還有哪些是他指定的方向？** | 排最前的是哪幾條線 |
| 有哪些你這次不想展開？**有沒有哪個概念他還不熟、需要先鋪陳一頁？** | 哪些降級 backup／口頭；⭐ 要不要加**鋪陳頁**（`slot: buildup`）|

### ⭐ 問之前先填 `plan.narrative_candidates`，問完填 `plan.rebuttals`

**寫它們的人是你**：

| 欄位 | 什麼時候寫 | 寫什麼 |
|---|---|---|
| `plan.narrative_candidates` | **問使用者之前** | 每日 headline **逐條**列出來，供他改寫。⛔ 不要自己先挑一句 —— `editorial_policy §0`：「agent 先列候選一句話清單，**讓使用者寫敘事**」 |
| `plan.rebuttals` | 敘事定案**之後**、派 planner 之前 | `{claim, rebuttal, answer}`：主線的主張／教授最可能的反駁（用他的口吻）／怎麼擋。**擋不住就回頭改主張** |

⚠️ **`rebuttals` 是這份 skill 唯一的對抗性自檢** —— 少了它，「這個主張站不站得住」
只會在**台上**被問到。`check_deck.py` 對兩者各發一則 WARN（⛔ 只驗有沒有寫，
驗不了寫得好不好；那一半只有你和使用者做得到）。

### ⭐ 第一題是最重要的一題

**沒有它，選材的濾網會變成 agent 自己編的那句敘事。**

問法：把 layer1 找到的候選重點列成選項，但**一定要留「都不是，我自己說」**。
答案逐字存進 `layer1_confirmed.json` 的 `threads[].user_points`
（⭐ 那個檔的**完整 schema** 唯一定義在 `subagent-thread-finder.md`
「關卡① 的定案檔」那一節），planner 的每一頁都要對得上其中一個
（`subagent-slide-planner.md §0c`）。

⛔ **`user_points` 不得由 agent 代擬**——與「敘事一句話不得代擬」同一條理由，
但這一題**更關鍵**，因為它直接決定有哪幾頁。

⚠️ **`advisor` 欄位空的不代表教授沒交代**——那一欄只有使用者補得了，一定要問。
⚠️ **因果關係由使用者判定，不由 agent 推斷。** agent 看得到的是時間順序，
把時間順序讀成因果最容易犯，而且串起來看起來很順，所以更危險。

**敘事一句話的正確介面是「問答 → 組句 → 確認」，不是「請你寫一句」**
（那是空白頁難題，對方答不出來）。每個元素都要追溯得到他的某個答案，
寫進 `plan.narrative_source`。

```bash
python3 $S/check_gate.py layer1 $OUT      # ⛔ 沒過不要進 layer2
```

**關卡① 交給使用者看的是 `layer1.md`**：每條主線「主線名 → 一句結論 → 最多三行支撐 → 〔來源日期〕」，
底下附「判成不上主線」的表，以及 `overflow_threads`（若有）與要先確認的事。
三分鐘看完，改一行就生效。

### 關卡怎麼問：**預設用 `AskUserQuestion` 的選擇題**

彈出來的選單看得出「這是一個關卡」；一段普通文字看不出來。三個關卡都適用。

> 🗣 **一題要他決定太多事、選項太抽象、表太長、或他說「東西太多／不知道重點該放哪／
> 說不出哪裡怪」時 → `references/gate-facilitation.md`。**
> 那份也收「一條線連續兩輪被說『怪』該怎麼辦」。
> ⛔ 這時**不要**用「給更多選項」去解決「選不出來」，也不要再列盤點表。

## outline 頁：全場 1 張 ＋ 每條線 1 張（定義）

```
Outline                  ← 全場 1 張，列各主線的名字 ＋ 一句它在做什麼
  ├ T1 outline           ← 該線 method 頁 ≥3 時必有
  │   T1 的方法頁 …
  └ T2 outline
      T2 的方法頁 …
```

| 頁 | 規則 |
|---|---|
| **全場 outline** | **必有 1 張**（不掛 `thread` 的 `agenda`）。**單一主線的週也要有** —— 讓聽眾知道今天只有一件事 |
| **各線 outline** | 該線 **method 頁 ≥3** 時必有一張掛 `thread` 的 `agenda`。⭐ **內容逐字抄該線的 `user_points`，一條一列** |

⭐ **各線 outline 的內容不是 agent 寫的。** 它就是把使用者在關卡① 講的那幾句話列出來 ——
所以 agent 不必判斷、也不准增刪。

**項數 ＝ 該條線的 `user_points` 條數**（`check_deck.py` 比對的就是這個），
⛔ **不是「該線的內容頁數」**。**這一句是唯一定義，`slide_types.md` 已改成指路。**

⭐ **`user_points` 是中文原話時就原樣中文上頁**，⛔ 不要為了「`deck.json` 一律英文」
把它翻掉 —— 原話豁免英文規則，豁免表與英文版的處置唯一見
`deck_schema.md`「語言」節。

⭐ **全場 outline 由 `deck_assembler` 產**（`references/subagent-deck-assembler.md`）——
它跨主線，不屬於任何一個 `slide_builder`；⛔ **協調者不得自己寫**（N25／F14）。
⚠️ 短線（<3 頁）不給自己的 outline，由全場 outline 帶到即可，否則結構頁佔比失衡。

### ⭐ outline／agenda 是**結構頁**，不是內容頁（唯一定義）

⭐ **兩張 outline 都不算「主線內容頁」，也不必對得上任何一條 `user_point`。**
唯一定義是 `check_deck.py` 的 `STRUCT = {"cover", "agenda", "thread-intro"}` ——
結構頁本來就不進逐頁內容檢查。所以：

| 規則 | outline 算不算 |
|---|---|
| 第 11a 條 `Σ plan.slide_plan[].pages == 實際主線內容頁數` | ⛔ **不算**，⛔ 也不要為它在 `slide_plan` 開一列 |
| 第 14 條「每頁都要對得上一條 `user_point`」 | ⛔ **不算**（各線 outline 反而是把**整份** `user_points` 逐字列出來）|
| 第 11 條頁數預算（主線 ≤15、單線 ≤7） | ⛔ **不算**（與 backup 同樣不計）|

⚠️ **全場 outline 由 `deck_assembler` 事後加入，本來就不在你寫的骨架裡** ——
骨架的 `slides: []` 少了它**不是**遺漏。

---

## layer2 — 逐頁規劃（★ 關卡②）

**每條主線派一個 `slide_planner`**，平行跑。派遣包一條線一個：
```bash
for T in T1 T2 T3; do python3 $S/brief.py planner --thread $T --out $OUT; done
```
**3 條線就是 3 個 planner，各產一個 `_work/3_layer2/layer2.<線id>.json`。**
⛔ 不准把兩條線寫進同一個檔 —— `check_gate.py layer2` 會擋（見硬性規定第 13 條）。

### 骨架：`method` 是唯一預設有頁的格

```
鋪陳／背景 → problem → method → result
   0 頁       0 頁      有頁     0 頁     ← 預設
```

**四格都預設有頁會製造脈絡頁** —— 四格是「一場完整演講」的形狀，
而**週報是延續中的對話**，教授上週就在場。

每一頁要過**兩道判準，順序不可顛倒**：

> **① 這一頁講的是「這個東西現在是什麼／怎麼運作」，還是「我怎麼把它弄成這樣」？**
> 後者（開發過程、校正、實跑判錯）**預設連口頭都不講** → `plan.dropped` 標「不講」。
> ⛔ **不是丟進 `notes`** —— `notes` 會進備忘稿也會被 `/lecture-script` 讀去寫講稿。
>
> **② 過了 ① 之後，這一頁講得出一件具體的事嗎？** 三種形狀任一種都算：
> ⓐ 它現在怎麼運作（機制）　ⓑ 一個決定 ＋ 它的依據　ⓒ 在什麼限制下還做得到什麼。

⚠️ **判準 ① 的例外**：一次性的**開發過程**要擋，常設的**自我修正機制**要放行。
分辨的問題是「**下週還會不會再發生一次**？」會 → 它是機制，屬於「現在怎麼運作」。

> 📌 **完整規格（含 `notes` 的兩道門檻、B9 的否證經過、成果清點的界線）在
> `references/subagent-slide-planner.md`，那裡是唯一的一份。**
> ⛔ 不要把那份的內容複製回這裡 —— 已知坑 #13：同一事實寫在兩個地方必定分岔。

### I/O 物品契約

同一條主線內，第 i 頁的 `input` **逐字等於**第 i−1 頁的 `output`，
且物品名必須登記在 `plan.terms.objects`（`check_deck.py` 兩條都會擋）。

> **守門提問**：前一頁的產出，真的是這一頁的輸入嗎？
> 不是 → 那只是時間順序，這兩頁接不起來。

沒有物品的頁（鋪陳、結論）留空，改用 `to`（這頁講完聽眾帶走的那句結論）承接，
`from` 逐字等於前一頁的 `to`。**換線不必接。**

⚠️ `from`／`to`／`input`／`output` 都**不上投影片**，所以承接要靠**標題**扛：
**下一頁的標題要讀起來像從上一頁的結論繼續講下去。**

### 深度與頁數

- `method` 格預設 `depth: mechanism`——要講到**規則本身**（判準、公式、門檻、分數怎麼算），
  不必到程式碼。**先選一個具體例子，讓它跑過規則，再抽出講法**；主圖是那個例子，
  佔滿整個版面（沒有側欄），規則與邊界畫在圖裡。例子不足可用明示為 constructed 的示意，
  真的沒有可跑案例才 `example_exception` 並降級理由。完整欄位與順序唯一見
  `subagent-slide-planner.md §0`。
- 主線 ≤15 頁、單一主線 ≤7 頁（backup 不計）。⚠️ 頁數 ≈ Σ（每條線的 user_points 數 ＋ result）——
  **它是使用者在關卡① 給的量，不是 agent 決定的**。撞上限先回關卡① 減 user_points
  或降一條線 backup，⛔ 不要砍 method 頁。
  ⚠️ **B17-2**：那條算式只是預估，result 頁要在上限的**額度內**擇一 —— 一條線給滿 7 個
  重點就沒有 result 頁的位置（`check_gate.py layer1` 會照 `mode` 用對的上限印給你）。
  另外 `buildup`／`problem`／`intro`／`result` 這幾種 slot 的頁**豁免第 14 條**（不必對到
  一條 `user_point`，但要填 `slot_reason`）—— 清單用 `check_deck.py --limits` 印，⛔ 不要憑印象。
- **砍伐順序**：先砍成果清點與「決策的依據」類 → 再砍 `overview` 頁。
  ⛔ **`mechanism` 頁與真正必要的鋪陳頁最後才砍。**
- 超過上限時交**一份壓在上限內的計畫** ＋ 三個選項，⛔ 不要交超頁的計畫讓使用者自己砍。

### ⭐ ⑦ 削減回合：**planner 自己做，你在關卡② 一併呈現**

⚠️ **`slide_planner` 的 Procedure 是 ①~⑥ 生成 ＋ ⑦ 回頭刪**，而 ①~⑥ 只會讓頁數
**等於 `user_points` 數**，沒有任何往下收的力量 —— ⑦ 就是那個力量。

| 誰做 | 在哪一步 | 產物 |
|---|---|---|
| `slide_planner`（每條線自己做自己的） | layer2，生成完 ①~⑥ **之後** | `layer2.<線id>.json` 的 `plan.trim_pass`（`{reviewed, proposals, kept}`）|
| **你** | 關卡② | 把 `proposals` 併進逐頁表**當一欄**，讓使用者一句話決定 |
| 使用者 | 關卡② | 每則 proposal 採納或不採納 |

- ⛔ **planner 只能提議，不能自己砍頁** —— 靜靜砍掉一頁 = 靜靜砍掉他要講的東西。
- ⛔ **你也不得代為決定**（`delegation.md`：協調者不得自行補寫角色遺漏的內容）。
- `reviewed` 要等於該線的內容頁數；`kept`（檢查過但決定不動的）**不可省** ——
  否則使用者分不出「被檢查過並保留」與「根本沒被想過」。
- **提議零項也合法**，但那時 `kept` 要列滿所有頁。
- ⛔ 缺 `plan.trim_pass` → **`check_gate.py layer2` 直接 `exit 1`**（`check_trim_pass`）。

⚠️ **完整規格、三個提問、輸出格式的唯一定義在 `references/subagent-slide-planner.md §7`**，
⛔ 這裡不重抄 —— 那份在「派遣時給 subagent、你自己不必讀」的清單裡，
你只需要知道**它會交回什麼、你要拿它做什麼**。

### 關卡② 的逐頁表

欄位定義唯一見 `subagent-slide-planner.md` 的 Required outputs（那是產它的人讀的規格）。
⛔ 這裡不再抄一份欄位表（已知坑 #13）。

⚠️ **關卡② 刻意不給任何長相。** 這時候看 HTML 會讓使用者開始評論視覺，
而視覺是 layer3 的事，這時候評論等於白做。

確認後把**每一個** `_work/3_layer2/layer2.<線id>.json` 頂層的 `slide_plan_confirmed`
設為 `true` —— ⭐ **那是 `slide_builder` Preflight 讀的唯一權威欄位**。
（`deck.json` 的 `plan.slide_plan_confirmed` 是抄過去的**全域**旗標；
⛔ 不要叫 builder 去看它 —— 逐線的定案只有逐線那一份說了算，
全域旗標蓋不住「A 線確認了、B 線還沒」，N19。）

### ⭐ 派 `slide_builder` 之前：先寫 `deck.json` 骨架（N61）

`slide_builder` 的**自驗綠燈**（`verify.py --out <日期目錄> --thread <線id>`）
沒有日期目錄最上層的 `deck.json` 就跑不動，⛔ **而首次交件那一輪正是自驗要消滅的東西**。
所以骨架在**這裡**就寫好，⛔ 不要拖到 Step 4：

| 欄位 | 從哪裡來 |
|---|---|
| `meta` | `_work/1_materials/deck.draft.json`（`build_deck.py` 已填好 `week`／`range`／`title`） |
| `arc` | 關卡① 那幾題的答案（`plan.answers`）收斂出來的，四欄都必填 |
| `plan` | `answers`／`narrative`／`mode`／`terms`／`dropped`／`slide_plan`（逐線抄 `layer2.<線id>.json`）／`slide_plan_confirmed: true` |
| `threads` | `_work/2_layer1/layer1_confirmed.json`（含每條線逐字的 `user_points`） |
| `slides` | ⭐ **`[]`（空陣列）** —— 留給 `merge_slides.py` 填 |

⚠️ `deck.draft.json` 的**頂層形狀就是 deck.json 的形狀**（`meta`／`plan`／`arc`／`threads`／`slides`），
所以骨架是「拿它來填，然後把 `slides` 清成 `[]`」，不是從零打一份。

- ⛔ **`slides` 一定是空的。** 不要把 `deck.draft.json` 的候選頁留在裡面 ——
  那是**篩選前**的候選頁。`merge_slides.py` 認得「第一次合併時 `slides` 是空的」，
  會把 builder 的頁**整批加進去**。
- ⛔ **全場 outline 頁不在骨架裡。** 它是 `deck_assembler` 的產出，
  **協調者不得自己寫**（N25／F14）。
- 於是 Step 4 只剩**整形**：`merge_slides.py` 填 `slides`，你視需要縮 `point`、
  把 `output` 改成 `null`。⛔ 它不再是「生成整份 deck.json」的那一步。
- ⚠️ 骨架在了，`slide_builder` 的自驗就**沒有例外可講**：`deck.json` 不在 → 它回報
  `BLOCKED`，⛔ 不是自己造一份（`references/subagent-slide-builder.md` 的 DONE 一節）。

```bash
python3 $S/check_gate.py layer2 $OUT      # ⛔ 沒過不要進 layer3（它也驗骨架在不在）
```

⚠️ `check_deck.py` 會驗 **Σ pages == 實際主線內容頁數**；
`check_gate.py layer2` 則驗**每一頁對得上一條 `user_point`、每一條 `user_point` 都有頁**
——這兩條 `check_deck.py` 也驗，但它要等到 Step 4 才跑，那時頁已經畫好了。

### 選材的去處：全記，不刪

**「不講」的實作是 `plan.dropped` 裡的去處 ＋ 理由**，不是默默消失。
`check_deck.py` 會對帳——日誌裡的每一項，不是上了投影片就是被明確篩掉，漏一個 exit 1。

⚠️ **合併不豁免對帳。** 一組上台時，`source` 要列出組內**全部**成員的 sid；
一組被篩掉時，`plan.dropped` 也要**逐個 sid** 記，不能只記組 —— 否則合併會變成
「讓項目無聲消失」的新管道，而那正是這條對帳規則當初要擋的東西。

⚠️ 日誌會忠實記下工具類工作，`materials.md` 裡一定有一批。
但 `editorial_policy §1` 的分野要逐條對：**§1a 這份簡報自己的長相／維護瑣事 → 不講**；
**§1b 研究基礎建設（含研究紀錄怎麼產生、報告方法怎麼定）→ 是研究方法，可以上主線**。
⛔ **工具的名字不決定去處，產物的效果決定**——判準是「會不會改變研究的正確性或產能
＋ 這週有沒有量到的證據」，兩問都要過。

---

## layer3 — 產投影片（★ 關卡③）

**每條主線派一個 `slide_builder`**（`brief.py builder --thread <線id>`），平行跑，
各產一個 `_work/4_slides/slides.<線id>.json`（`check_gate.py layer3` 會擋），
然後**依序**派兩個跨主線角色：**1 個 `deck_assembler`**（全場 outline ＋ 中文譯文）、
再 **1 個 `layout_reviewer`**（審版面）。
⚠️ **三者的先後與時機唯一定義在 Step 4「派遣的順序」**，⛔ 這裡不重抄。

⭐ **這兩個角色派遣時要指定 `model: sonnet`**（Agent 工具的 `model` 參數）——
兩把量尺（`check_deck.py` ERROR 數、`shoot.py` 被擋頁數）與最大的模型**平手**。
⛔ `thread_finder` 與 `slide_planner` **不要降** —— 判錯的成本是返工整條線。
⚠️ 但下面那個 `layout_reviewer` 的回合**不能為了省而拿掉**：Sonnet 的圖偏稀疏，
而擋這件事的機械檢查是瞎的（**N52**：`shoot.py` 量墨水外接矩形、SVG 等比縮放
→ 框多字少必定過關），只有 reviewer 擋得住。判準與實測數字見
`references/delegation.md` 的「模型分級」。
⛔ **不要一交件就派 reviewer，也不要一有 `check_deck` 的 ERROR 就退回 builder** ——
派遣時機與「三方 findings 合成一輪」的規則**唯一定義在 Step 4**。

> ⚠️ **不要退化成「每頁一個 subagent」。** 各頁看不到彼此 → 同一個名詞在第 3 頁和
> 第 7 頁畫法不同，關卡③ 才會看到，要重畫兩張。

### 畫圖不是一個動詞，是四個步驟

```
① 關係抽取 ← LLM   ② 構圖選擇 ← 查表   ③ 填 JSON ← LLM   ④ 算座標 ← code
```

**不要問**「這頁該畫什麼圖」，**要問**「這頁的 `point` 裡有哪些**有名字的東西**？
它們之間是八種關係中的哪一種？」完整規格見 `references/composition-vocabulary.md`。

⭐ **決定要畫之後，先查那份的「Step ⓪b 路由」再動手** —— 它決定**用哪個工具畫**
（`pipeline` 版型／`render_figure.py`／手刻 SVG／退回表格），由上往下選。
少了這一關每張圖都會直接掉到「手刻」那格。⛔ 路由表不在這裡複製一份。

三個免費的副產物：抽出兩個不相干的關係 = **該拆頁**；抽不出關係 = 正當退回表／文字；
抽到字彙外的關係 = **手寫 SVG 的唯一合法入口**（記進 `BACKLOG.md`）。

⚠️ **有 renderer 的八個**：`read_pileup`／`haplotype_split`／`chain`（＝`chain_gated`）／
`group_blocks`／`two_col_link`／⭐ `funnel`（＝`funnel_named`）／`transform_pair`／
`before_after`。⭐ **手繪已經降到 0 張** —— `diagram-craft §0` 的 2–3 張額度整個空出來，
留給真正沒見過的圖。

⭐ **圖上的顏色有三種角色**（唯一出處 `presentation_rules.md §5`，2026-09-05 使用者裁決）：
**區別**（`box-c1`~`c12`，⭐ renderer 依名字雜湊**自動配**，⛔ 不必填 spec）／
**分類**（`bad`／`good`／`null`／`ctl`，明寫 `tone`）／**強調**（⭐ 只剩**字**）。
⛔ 不要拿分類色去做區別 —— 那會讓觀眾把框讀成「壞的／通過了」。

⚠️ **下面這段是 `slide_builder` 要跑的動作**（同一條也寫在
`references/subagent-slide-builder.md` 的 Procedure 2）——⛔ **協調者不畫圖、不跑
`render_figure.py`**。寫在這裡是讓你知道 **builder 被要求了什麼**，好在它交件時看得懂
`figures/*.svg` 與 spec 為什麼要一一對應。⛔ 也不必自己去讀 `diagram-craft.md`，
那份在「派遣時給 subagent、你自己不必讀」那張表裡。

```bash
# ⭐ 高度預算去 `diagram-craft.md §6` 的表查（看這頁有沒有 topic／sub；
#    ⛔ 不要憑印象填 540 —— 那是 takeaway 停用前的舊值，N67），填進 spec 的 `budget`。
python3 $S/render_figure.py spec.json -o $OUT/figures/<name>.svg
  # ⭐ 高度預算寫在 spec 檔的 `budget` 欄位（唯一記錄處），⛔ 不再靠命令列傳。
  # ⭐ **出貨的圖必須重跑得出來**：`check_deck.check_spec_reproduces()` 會照 spec
  #    重跑一次並要求**逐 byte** 相同（ERROR）。改了圖就把 spec 改成一樣、
  #    改了 spec 就重跑一次。⛔ 判準不是「圖看起來一樣」。
python3 $S/render_figure.py --demo <outdir>      # 每個 comp 產一張範例圖
```

⚠️ 手繪 SVG 沒有 `--budget` 可傳，直接把查到的數字寫進 `viewBox="0 0 1420 <高>"`。
寬**一律 1420**（⛔ 不是 1456 —— 那是投影片可用寬，不是圖寬，見 `diagram-craft.md §1`）。

### 其餘規則

- 主體優先序 **圖 > 表 > 文字**。文字版型必須有 `why_text`。**條列不是預設，是下下策。**
- **圖上每則文字都要標用途**（`check_deck.py` 會擋）：`label` 東西的名字／`value` 數字／
  `annot` 這張圖怎麼讀（**≤2**）／`def` 名詞定義（**≤1**）。
  `label`／`value` **不得成句**；⛔ **主線內容頁上，淺色只給 `annot` 與 `def`**。
  ⭐ **上限算的是整張投影片**：SVG 的 `<text>` 與 deck.json 欄位渲染出來的字
  （`sub`、圖說 `body.caption`、表格 `caption`）**合併計數**。
  **把旁白從圖裡搬到 `sub` 或 `caption` 不會過關。**
  `stats` 的 `k` 與 `flow` 步驟的 `d` 歸 `label`，不得成句；
  `agenda` 與 `issues` 的 `d` 刻意豁免（結構頁／backup 頁）。
  字彙表與「為什麼不用字數上限或圖文比例」見 `presentation_rules.md`。
  ⛔ 舊的大小字彙 `t-sm`／`t-md`／`t-lg` 已作廢 —— 它問「多大」，問不出「這是旁白」。
- **結論句不上投影片**，寫進 `notes` 的「【口頭結論】」
- **caption 只能寫「這張圖表怎麼讀」**，不能寫「說明了什麼」——
  **而且它佔掉這頁的 `annot` 額度**（這一句是讓規則真的有成本的關鍵）
- **面積要反映重點**——重點的東西要大
- 日誌的 `details` 一律進 `notes`
- ⛔ 不要做「待決與下一步」頁

### 數字：只能逐字照抄，不得計算、不得改寫

⚠️ **單位換算也算改寫。**「3,664 萬列」寫成 `36,640,000` 會被擋。

**⭐ 唯一的例外：書寫系統不同，不算改寫。** 日誌是中文寫的（「二十個特徵」
「千分之一」），而 **`deck.json` 一律寫英文** —— 投影片上只能是 `20`／`1e-3`。
兩條規則會直接打架，而且是**每一份中文日誌都必然發生**。

```
二十 → 20        ✅ 位數與單位都沒變 → 是同一個值的兩種寫法
千分之一 → 1e-3  ✅ 同上
3,664 萬列 → 36,640,000   ⛔ 位數變了 → 這是換算，仍然擋
```

**界線：位數與單位沒變的是書寫系統，位數變了的是換算。**
原規則要防的是後者（憑印象換算錯），⛔ 不要因為這條例外就把前者也放寬。
`check_deck.py` 的 `cn_numbers()` 已經實作這條（只做 0~999 與「N 分之一」，
⛔ 刻意不做「萬」「億」，那些是量級單位）。

換算不了又非放不可時，去確認有沒有來源檔寫著你要的格式，掛上 `extra_sources`；
都沒有就**不要放那個數字**，改由講者口頭講。

### 中文版：只複製字串，不複製結構

```bash
python3 $S/render_deck.py $OUT/deck.json --dump-strings zh   # 收集待翻字串
# ⭐ 填值的是 `deck_assembler`，⛔ 不是協調者自己填（見下）
python3 $S/render_deck.py $OUT/deck.json --lang zh           # → deck.zh.html
```

⭐ **「填值」有主人**：`deck_assembler`（`references/subagent-deck-assembler.md`）。
輸入 `strings.zh.json` ＋ `deck.json` 的 `plan.terms.objects` 與 `plan.quotes`，
輸出填好的 `strings.zh.json` ＋ `_work/4_slides/assemble_note.md` 的中英對照表。
⚠️ 四個 `subagent-*.md` 都不含翻譯、也沒有任何機制保證同一個具名產物在上百句裡譯名一致
（FINDINGS N31）——而「同一件事一直用同一個名詞」是使用者明列最在意的四件事之一。

⛔ **不要產第二份 `deck.json`**——結構共用一份，否則兩版的數字會分岔。

**譯文的數字規矩是非對稱的**：不得憑空生出原句沒有的數字（ERROR）；
但可以把數字寫成中文字（`1,000` → 「一千」），那不是竄改。

> 📦 **`plan.dropped` 裡有 `where = backup` 的項目時 → `references/delivery.md`
> 的「backup 頁的產出條件與上限」**（0 項就不做分隔頁；≥1 項是一張 `thread-intro`
> 分隔頁 ＋ 每項最多一頁；`口頭`／`不講` 一律 0 頁）。

---

## Step 4 — 機械檢查 → 渲染 → 版面審查 → **一次**退回

⚠️ **這一步不生成 `deck.json`，只整形它。** 骨架（`meta`／`arc`／`plan`／`threads` ＋
`slides: []`）在**派 builder 之前**就寫好了，唯一定義在 layer2 那節
「派 `slide_builder` 之前：先寫 `deck.json` 骨架」（N61）。骨架不在 → 回頭補，
⛔ 不要在這裡才第一次把它拼出來 —— 那樣 builder 的自驗整輪都跑不了。

### ⭐ 派遣的順序（唯一定義，`delegation.md` 的「輪」數的就是這個）

⚠️ 這裡定義的是**輪**（誰在什麼時候被派出去），⛔ **不是機械序列的步驟清單** ——
那份唯一定義在 `scripts/verify.py` 的 `STEPS`，這裡不重抄（N70）。

```
1. 派 builders（平行）→ 各交回 slides.<線>.json ＋ figures/*.svg
2. 跑 `scripts/verify.py --out <日期目錄> --stop-after check` —— 機械序列（步驟見 `STEPS`）
   ⚠️ 這一整步**不花 subagent**。有 ERROR 也照樣往下跑，把錯誤**收集起來**，
   ⛔ 先不要退回 builder。
   ⭐ **這一輪停在 `check` 就好**：中文版還沒有譯文（`strings` 必然擋），
   而 outline 頁要等第 3 步才進來 —— 現在就 render／shoot 是驗一份還會變的東西。
3. 派 1 個 `deck_assembler`（跨主線）—— 它產**全場 outline 頁**（不掛 `thread` 的
   `agenda`）與 **`strings.zh.json` 的中文譯文**，那兩樣**不屬於任何一個 builder**，
   ⛔ **協調者不得自己寫**（N25／F14、N31）。
   ⚠️ **它一定在 merge 之後**（Preflight 要求 `deck.json` 的 `slides` 非空），所以⛔ 不能
   跟 builders 同一輪；也⛔ 不要跟 reviewer 同一輪 —— 那樣 reviewer 審的 HTML 少了
   全場 outline、中文版還是半英文，**那一頁與 zh 版等於沒人審過**。
   派它之前先把 `strings.zh.json` 生出來（⚠️ 第 2 步的 `strings` 是在暫存副本上數句數，
   ⛔ 不落地交付物）：
   ```bash
   python3 $S/render_deck.py $OUT/deck.json --dump-strings zh   # → $OUT/strings.zh.json
   python3 $S/brief.py assembler --out $OUT                     # 派遣包
   ```
   ⭐ 它交件後**重跑一次** `python3 $S/verify.py --out $OUT --no-merge`
   （deck.json 多了一頁、strings 填好了 → `strings`／`render_zh` 這時才過得了），
   ⛔ 不要帶 `--merge`（會把 builder 的舊值蓋回來）。
4. 派 1 個 layout_reviewer —— 它這時才拿得到 SVG、兩版 HTML 與
   `_work/4_slides/shoot_check.<lang>.txt`（`shoot.py --check-only` 自己落地的實測輸出）
   ⭐ 它交件時**自己回填** `deck.json` 的 `plan.layout_reviewed`（含每條 NIT 的去處）——
   ⛔ **協調者不代填**（`delegation.md`：不得自行補寫角色遺漏的內容）。
   ⚠️ 它只寫得了那**一個 key**，`deck.json` 的其他欄位仍然禁止它碰。
   ⛔ 缺這一欄，多線 deck 的 `check_deck.py` 是 **ERROR** ——
   ⭐ 真的刻意不派 reviewer，就在 `deck.json` 寫
   `plan.layout_reviewed = {"skipped": "理由"}`（**具名**的逃生口，理由會被印出來）。
5. check_deck 的 ERROR ＋ shoot 的版面 findings ＋ reviewer 的 BLOCKING
   **合成一份，一次退回 builder** ← 這才是第 1 輪返工
   ⭐ 退回**之前**先決定兩件事（N88）：
   ① **resume 原 agent 還是派新的？**（損益點在 3 個回合；判準表在
      `delegation.md`「resume 同一個 subagent，還是派一個新的」，⛔ 那張表只有那裡有一份）
   ② 各 agent 回報的 `open_questions` **一次答完再退**，⛔ 不要遇到一個處理一個
```

> **為什麼**：reviewer 確實**不能**在 builder 交件前跑（它審的是畫出來的 SVG 與實測版面），
> 但它可以在**錯誤還沒修完**的時候跑 —— 這兩件事以前被混為一談，代價是 builder A
> 累計 64 次工具呼叫、8.87M tokens、被 resume 4 次。

⛔ **兩個例外，先修再往下**：

- **結構頁 body 缺欄位**（`check_deck.py` 檢查項 11）：`render_deck.py` 會停在那一頁，
  訊息指名頁與欄位 → 補那一頁再 render。**其餘 ERROR 都不擋 render。**
- **會改變版面的 ERROR**（要拆頁／換版型／重畫圖）碰到**超過 1/3 的內容頁**：
  reviewer 會去審一批即將重畫的圖，等於白審 → 先修這一輪再派它。
  ⭐ **判準是種類不是總數**：`point` 超長／`from` 不逐字／數字溯源／`source` 這幾類
  只改字不動版面 → 一律合併，⛔ 不要為了它們多走一輪。
  （⚠️ `point` 超長與 `from` 不逐字現在擋在關卡②，走到這裡時應該已經沒有了。）

> ⚠️ 上面的順序**容許**帶著 ERROR 往下 render／shoot，⛔ 但不容許**不知道**有 ERROR ——
> 這一節講的是後者。

### ⭐ 這一整條序列用一支腳本跑完：`scripts/verify.py`（⛔ 不要一行一行手打）

```bash
python3 $S/verify.py --out $OUT                       # 一個回合跑完七步，最後印一張摘要表
python3 $S/verify.py --out $OUT --stop-after check    # 只跑到機械檢查
python3 $S/verify.py --out $OUT --no-merge            # deck.json 已整形過、沒有新的 slides.*.json 要併
python3 $S/verify.py --out $OUT --allow-untranslated  # 明知有待翻句仍要出中文版
python3 $S/verify.py --out $OUT --thread A --quiet    # ⭐ 給 slide_builder 自驗：只算自己那條線的紅燈；
                                                      #    --quiet 把七步全文落地到 _work/4_slides/verify.A.log，終端只剩摘要
```

**為什麼是一支腳本**：⭐ **規格的形狀決定行為**。這裡以前寫成六行分開的指令，
協調者就一行一行跑 —— **每一行是一個 API 回合，每個回合都把當下整段 context 重送一次**。
實測 30 個回合換成腳本是 6 個回合，多出來的那 24 個回合買到的東西是 0。
⚠️ `verify.py` 直接拿每一支的 returncode（不經 shell、不接 pipe），
所以「接 pipe 會讓 exit code 變成 pipe 尾端的」那個坑在腳本裡不存在；
**你自己另外手跑某一支時它仍然成立**（要看尾巴就分兩次跑，或 `set -o pipefail`）。

**它按順序做這七步** —— 腳本只是把你本來要打的指令合成一個回合，⛔ 判斷還是你的：

| 步驟 | 做什麼 | 失敗了會怎樣 |
|---|---|---|
| `merge` | `merge_slides.py`：併各主線的 `slides.<線>.json`，**保留你在 deck.json 上的整形** | **停** —— deck.json 沒併成，後面全部在驗一份舊的 |
| `check` | `check_deck.py`：機械檢查 | **記下 ERROR／WARN 數與每條抬頭，照樣往下** |
| `render_en` | → `deck.en.html` | 只擋 `shoot_en`，另一版不受影響 |
| `strings` | `render_deck.py --dump-strings zh` 數**待翻句數**（在暫存副本上跑，⛔ 不動交付物的 `strings.zh.json`） | 待翻 ≠ 0 → **擋中文版**，⛔ 不靜默產出一份半英文的 HTML |
| `render_zh` | → `deck.zh.html` | 只擋 `shoot_zh` |
| `shoot_en`／`shoot_zh` | `--check-only` 量溢位與版面。**兩版都要量，中英行高不同** | 記下被擋的頁號，照樣往下 —— findings 要湊齊才一次退回 |

⚠️ `merge_slides.py` 是**必經**的一步，不要手動合併 —— builder 每輪都會把你縮短過的
`point` 與改成 `null` 的 `output` 帶回舊值。
⚠️ `shoot --check-only` 的實測輸出由 `shoot.py` 自己落地成
`_work/4_slides/shoot_check.<lang>.txt`（`layout_reviewer` 要讀它，
⛔ 不要改用 `| tee`，也不要口述數字給它 —— N37）。

摘要表每一步一列，任一步紅了都指得出是**哪一步、哪一頁**，例如：

```
merge       OK      0      併入 2 份：slides.A.json、slides.B.json
check       FAIL    1      1 ERROR / 14 WARN
                           · A2: point 超過上限（103 > 90 字）
                           ⛔ 先不要退回 builder，等 shoot 與 layout_reviewer 的 findings 湊齊再一次退
strings     FAIL    1      276 句中 **2 句待翻** → 中文版會落回英文原文
render_zh   SKIP    -      strings.zh.json 還有 2 句待翻 —— ⛔ 不產半英文的 HTML
shoot_en    OK      0      5 項可改善（不擋）　→ _work/4_slides/shoot_check.en.txt
```

### ⭐ `deck.en.html`／`deck.zh.html` 就是交付物（定案）

**兩個檔案一起交給使用者。**
⛔ **不要說哪一份是「正式版」，也不要替他選** —— 兩版平等。
⛔ **不要手改 `deck.en.html`／`deck.zh.html`**——版面問題改 `assets/deck.css`（一次改全部頁），
內容問題改 `deck.json`。
⚠️ **英文版的檔名帶 `.en`**（不是 `deck.html`）——兩版會同時流通，檔名就要看得出是哪一版。

實驗室大多數人**直接開 HTML 上台講**，不轉 pptx。所以 HTML 自己就是簡報播放器：
一次一頁、自動縮放貼合視窗、鍵盤翻頁。播放器是 `assets/deck.js`，由 `render_deck.py`
**內嵌**進 HTML → 單檔用 `file://` 開就能講，零外部依賴。

⚠️ **`notes` 預設不顯示，也不會被截圖截到。** 它以 `data-notes` 屬性掛在 `<section>` 上，
**不進 DOM**（不是隱藏節點）——隱藏節點會被 `shoot.py` 的版面自檢當成真的容器去量。

### ⛔ `shoot.py --check-only` 一律要跑，而且要過

> ⚠️ **`shoot.py` 不是為了 pptx 存在的，它是品質關卡。**
> 溢位（`.slide` 是 `overflow:hidden`，塞不下會被**靜靜裁掉**）與版面自檢
> 只有量渲染後的實際尺寸才看得到，看程式碼看不出來。
> **不論要不要轉 pptx，這一步都要跑而且要過。**（`verify.py` 的 `shoot_en`／`shoot_zh` 兩步）

`shoot.py` 查兩層：**溢位**（會擋，除非 `--allow-overflow`）與**版面品質**
（底部留白 >150px、表格列高 >字級×3.2、表格溢出容器、正文字級 <12px、
子內容溢出、圖內有效字級 <13px；不擋但逐條列出）。
⭐ **例外：「容器過空」對主線內容頁會擋**（門檻見 `shoot.py`）。
⛔ 擋住時不要縮圖去閃過，填料的辦法見 `presentation_rules.md §6`。

⚠️ **`shoot.py` 一律把播放器關掉**（`window.__DECK_RAW__`），量測用的是未縮放的
`scrollHeight`／`offsetHeight`；播放器一旦套上 `transform:scale` 並把非當前頁 `display:none`，
那些數字會整組失準。改播放器之後**一定要重跑 `--check-only` 比對輸出有沒有變**。

> 🎬 **要交一個 `.pptx` 檔、使用者問「這個怎麼播」、或交付後他要改某一頁
> → `references/delivery.md`。** 那份收播放器按鍵表、Step 5 的截圖與 pptx 指令、
> 以及「修改時對 deck.json 做原子操作，不要重生成整份」。

---

## 版型是起點，不是牢籠

`slide_types.md` 的版型清單是現成可用的東西，不是限制。有更好的排法就自己排——
寫一段新 SVG、或在 `assets/deck.css` 加一個新版型，然後登記進 `slide_types.md`。
**不要為了套現成版型而把內容講差。**

唯一不可協商的是下面的機械檢查，以及「圖 > 表 > 文字」的優先序。

⚠️ **同一條線反覆做不好時，先懷疑它只有一頁的量**（連續兩輪被說「怪」而說不出哪裡怪）
→ `references/gate-facilitation.md`。同一個道理用在 subagent 上：**同一條線試錯到上限就停下來
拋給使用者**，⛔ 不要無限重派。上限的**數字只有 `delegation.md`「試錯上限」那裡有一份**，
⛔ 這裡刻意不複製（複製過的那一份正是它要防的雙寫）。

---

## 硬性規定

### 關卡（`scripts/check_gate.py`，每層結束就跑，會擋）

| 關卡 | 驗什麼 |
|---|---|
| `layer1` | `_work/2_layer1/` 有 `layer1.md` 與 `layer1_confirmed.json`；有 `confirmed_by`、`narrative`；**每條線有 `user_points`**；線 ≤4；跑過 `merge_items.py` 就要有 `merged_groups` |
| `layer2` | `_work/3_layer2/` 有 `layer2*.md`；**每一頁對得上一條 `user_point`（逐字）**；**每一條 `user_point` 都有頁**；mechanism 頁有可追的 example（或具體例外）<br>⚠️ **還有六項也會 ERROR**（原本這張表整組漏列，其中 `trim_pass` 在 `SKILL.md` 全文 grep = 0，協調者無從預期 gate2 會為它 `exit 1`）：<br>· `point` 型別與**字數上限**（同源 `check_deck.LIMITS["point"]`）<br>· **`from`／`to` 承接鏈**（`check_chain`：除開場頁外都要有 `from`，且逐字等於前一頁的 `to`）<br>· **`trim_pass`**（`check_trim_pass`：⑦ 削減回合跑過的留痕，`reviewed` 要等於該線頁數）<br>· **`deck.json` 骨架**（`check_deck_skeleton`：`meta`／`arc`／`plan`／`threads` ＋ `slides: []`，`threads` id 要對得上關卡① 定案）<br>· **spec 新鮮度**（`check_spec_fresh`）<br>· **逐線檔對帳**（`check_per_thread`，見下方第 13 條）|
| `layer3` | `deck.en.html` 與 `deck.zh.html` **兩版都在**（`<out>` 給日期目錄）<br>⚠️ 另有兩項會 ERROR：`deck.json` 要在；**逐線檔對帳**與 **spec 新鮮度**（對 `slides.<線id>.json`／`slide_builder`）|

⚠️ 它驗得了「檔在不在、欄位齊不齊、順序對不對」，**驗不了「答案是不是真的出自使用者」**
——那沒辦法用程式驗。所以 `answers` 一律逐字抄原話並標日期，讓造假至少留下痕跡。

### 內容（`scripts/check_deck.py`，Step 4 跑，會擋）

1. **一頁一重點** —— 每頁要有 `point`，不得塞兩個
2. **承接／拋出連貫** —— 第 i 頁的 `from` = 第 i-1 頁的 `to`（同主線內）
3. **數字溯源** —— 投影片上的數字必須逐字出現在來源日誌
4. **版型容量** —— 表格列／欄數、條列項數、字數上限
5. **來源可追溯** —— `source` 必填且該日誌真的存在
6. **週敘事** —— 單線週 `arc` 四欄齊全；多線週每條線要有 `summary`
7. **主體型態** —— 文字版型必須有 `why_text`
8. **選材決策留檔** —— `plan.narrative`／`mode` 必填；每個日誌項不是上投影片就是寫進 `plan.dropped`
9. **I/O 物品鏈** —— 同主線內 `input` 逐字等於前一頁 `output`
10. **物品登記** —— `input`／`output` 的名字必須在 `plan.terms.objects` 裡
11. **頁數預算** —— 主線 ≤15 頁、單線 ≤7 頁（backup 不計）。⚠️ 控制點在關卡①，不在這裡
11a. **`plan.slide_plan`** —— 必填，且 **Σ`pages` == 實際主線內容頁數**。
    欄位定義（`{point, pages, body}`）見 `deck_schema.md` 的 `plan` 區塊 ——
    ⚠️ 它以前**只寫在 `check_deck.py` 原始碼裡**，寫的人只能去讀 checker（N21）
12. **深度** —— `depth: mechanism` 的頁必須看得到一條具體規則
12a. **例子優先** —— 新版 `plan.example_first: true` 時，mechanism 頁必須有來源可追的
    `before → operation → after` 案例，並用 `type: example` 呈現為**全幅主圖**
    （⛔ 無 `aside`；規則與邊界畫在圖裡，不得只寫進 `notes`）
13. **逐線派遣（layer2／layer3）** —— ⚠️ **這一條不在 `check_deck.py`**（它只讀合併後的
    `deck.json`，對逐線檔名零命中）。實作在 **`check_gate.py` 的 `check_per_thread()`**，
    由關卡②③ 跑（N105）。⛔ 只跑 Step 4 的 `check_deck.py` **一個角色都沒有在執行它**。
    **一條主線一個 subagent**：3 條線就是 3 個
    `slide_planner` ＋ 3 個 `slide_builder`，各產一個 `layer2.<線id>.json` /
    `slides.<線id>.json`。少一條線的檔 → 擋；某條線的檔裡出現**別條線的
    `user_point`** → 擋（那代表寫它的人手上有全部主線的素材，不是隔離的 subagent）。
    ⛔ **粒度是「一條線一個」，不是「一頁一個」** —— 各頁看不到彼此，同一個名詞
    會在不同頁被畫成不同樣子，關卡③ 才會發現、要重畫兩張。
    ⚠️ 驗得了「有沒有逐線隔離」，⛔ **驗不了「是不是真的同時平行跑」**
    （沒有腳本看得到 orchestrator 的工具呼叫）。不要把它寫成「保證平行」。
14. **`user_points` 對帳** —— 每頁都要對得上 `threads[].user_points` 的一條（逐字）；
    **每一條 user_point 也都要有頁**；頁序不同於 user_points 的順序時要寫 `page_order_note`
    ⚠️ 這一條與第 11a 條**都只算內容頁**，`cover`／`agenda`／`thread-intro` 是結構頁不進來
    —— 唯一定義在「outline／agenda 是結構頁」那節，⛔ 這裡不重抄。

> **不要靠自我宣稱。** 問模型「有照規定嗎」它多半答「有」。一律跑檢查程式。
> 而 `check_deck.py` 管不到「塞不塞得下」——那由 `shoot.py` 實際量測，
> 因為 `.slide` 是 `overflow:hidden`，內容超出時會被**靜靜裁掉**。

---

## ★ 關卡③ — 讓使用者看長相（唯一一關看得到畫面）

⚠️ **關卡① 問「講什麼」、關卡② 問「怎麼排」且刻意不給長相 —— 關卡③ 是唯一該讓他
看到畫面的一關。** ⛔ 不要把兩個 HTML 丟出去就當作結束：一段普通文字看不出「這是一個關卡」
（見「關卡怎麼問」），使用者不會知道現在輪到他，`plan.feedback` 就會空著。

**時機**：Step 4 的紅燈都清掉、`verify.py` 全綠之後，交付**之前**。

**給他什麼**：`deck.en.html` 與 `deck.zh.html` 的絕對路徑（直接開就能翻頁），
⭐ **兩版平等，⛔ 不要替他選哪一份是正式版**。有 `_export/slides/` 的截圖就一併附上。

**問法：`AskUserQuestion` 固定三題**（⛔ 不要改成一句開放式問句）：

| 題 | 問什麼 | 選項怎麼給 |
|---|---|---|
| 1 | **這份現在能不能上台講？** | 能／要改幾頁／整條線要重來 |
| 2 | **哪一頁看不懂，或哪個名詞前後不一致？** | 選項列頁號＋該頁的 `point`；一定要有「都看得懂」|
| 3 | **有沒有哪一頁太空或太滿？** | 選項列 `shoot_check.<lang>.txt` 標出來的那幾頁 ＋ `layout_reviewer` 的 NIT ＋「都可以」|

- ⭐ **第 2 題問的是「看不懂」不是「好不好看」** —— 名詞前後不一致是使用者明列最在意的
  四件事之一，而那**只有翻完整份的人看得出來**（各 builder 看不到彼此的頁）。
- ⭐ **選項要具體到頁號**。給「有沒有哪裡要改」這種開放式問句，答案會是「還好」。
- 答案逐字回填 `plan.feedback`（見下一節），⛔ 不要摘要成自己的話。
- 🗣 他說「東西太多／說不出哪裡怪」→ `references/gate-facilitation.md`。

---

## 使用者給完回饋後，回填 `plan.feedback`（不可省）

記下：他原本看到什麼、改成什麼、理由、以及這是**判準錯了**還是**本次特例**。

- **判準錯了** → 下次一定會再犯，**提議**修改對應的 `references/`
- **本次特例** → 記著就好，不要動判準

⛔ **不要自己改判準**——提出來，等使用者確認。

> 沒有這一步，回饋會蒸發，下週會犯同樣的錯。上一版實跑那次 13 條回饋裡有
> **11 條被判定為判準錯**，全部已經變成 `references/` 裡的永久規則——
> 這個機制是這個 skill 進步的唯一來源。

順手把耗時登記進 `<週報輸出根>/_effort_log.md`（目標 1 小時）。

### ⭐ 同一時間也要寫 `<週報輸出根>/_explanations.md`（不可省，N79）

⛔ **這個檔全 repo 只有「讀」沒有「寫」** —— `brief.py` 把它打包給每個 subagent、
你在 Step 0 也讀它，但**沒有任何腳本、沒有任何角色的 Required outputs 產它**。
`editorial_policy §2`「⚠️ 但方針**仍要記進 `_explanations.md`**——它持續生效、影響往後每一週」，
而**寫它的人就是你** —— 只有協調者同時握有使用者的原話與整份 deck。

⚠️ **不寫的後果是跨週的**：下一週那條硬規則「未答的教授提問**排最前**」
（`brief.py`「§1 一個字都不准切 —— 硬規則」）**沒有資料來源**，
而下一場開 session 的人會以為「本來就沒有提問」。
已登記為 BACKLOG B8：該檔「最後更新停在幾週前，『待回答』區是空的」。

**這一輪要回填三種東西**（沒有就寫「本週無」，⛔ 不要整段省略 ——
省略與「沒有」在檔案上長得一模一樣）：

| 記進哪 | 寫什麼 |
|---|---|
| §1 **教授的提問與功課** | 這次問了什麼、答了沒。⭐ **答完才劃掉**，沒答完的留著（下週排最前） |
| §1 同上 | 使用者判成「不講」的**指導方針**（`editorial_policy §2`：⛔ 常見錯法是把指導方針本身做成一頁去講）—— 不上台講，但它持續生效 |
| §2 **解釋資產** | 這週定案的說法、比喻、名詞慣例、以及畫成什麼樣的圖（下週同一個概念**沿用同一套**） |

⛔ **不要把它寫成本週週報的摘要** —— 它是**跨週**的檔，只收「下一週還要用到的東西」。

---

## 成本：⭐ **貴的是「session 開太久」，不是判準寫太長**

**三條規矩（照這個順序，效益由大到小）**

1. **⭐ 一個 session 只做一件事。** 跑週報就只跑週報；改 skill 另開一個；討論另開一個。
   實測混在一起讓協調者多付約 **31%**。
2. **不要中途停超過一小時。** prompt cache 的 TTL 到期後整段 context 要重新寫入。
3. **協調者不要把大東西讀進自己的 context。** 檢查程式的原始碼、幾十個 ERROR 的完整輸出、
   subagent 的轉錄檔 —— 這些讀一次要付整場的錢。**用腳本印摘要**（`grep -c`、分類統計），
   不要 `cat` 全文。

⛔ **不要為了省 token 去砍判準** —— 淨效果是更貴。
⭐ 對的做法是**切得更準**（依角色／依主線／依相關性），判準一個字都不刪，
只是不要送給用不到它的人 —— 那正是 `brief.py` 在做的事。

> 💰 **完整的量測表、可歸因帳單怎麼算、以及這個 skill 跟已退役的五段式舊流程的關係
> → `references/orchestrator-cost.md`。⛔ 只有要改這個 skill 時才需要**，出一份週報用不到。
