---
name: weekly-deck
description: "把一週的每日工作日誌（daily-log 產出的 .data/*.json）做成給教授看的週報投影片。三層流程、三個人工關卡，每一層一個 session：layer1 找主線 → 關卡① → layer2 逐頁規劃 → 關卡② → layer3 產 HTML（渲染、檢查、關卡③、選用 pptx）。在使用者說「做這週的週報」「產週報投影片」「把日誌做成簡報」時觸發，或使用者打 /weekly-deck [layer1|layer2|layer3|all]（Claude Code）／$weekly-deck（Codex）時執行。"
---

# Weekly Deck

輸入是**已經編輯過的每日日誌**（`/daily-log` 每天把 git 與對話整理成「問題→做法→結果→解讀」）。
本 skill 只做兩件事：**跨日合併成敘事**，以及**排成投影片**。⛔ 不重讀 session transcript。

```
.data/*.json ─ Step 1 三支腳本 ─→ merge_groups.md / threads.md / materials.md / deck.draft.json
  layer1  找主線（2~4 條）→ layer1.json → gate_view → ★ 關卡① → check_gate --confirm → layer1_confirmed.json
  layer2  逐頁規劃          → layer2.<線>.json → gate_view → ★ 關卡② → --confirm → build_deck --skeleton
  layer3  產頁              → specs ＋ slides.<線>.json ＋ strings.<線>.zh.json → render_figure --all
                            → verify --quiet（≤2 輪修）→ merge --outline → ★ 關卡③ → plan.feedback
                            → deck.en.html / deck.zh.html ＝ 交付物　　（shoot → pptx 選用）
```

## 三條凌駕一切的原則

1. **`deck.json` 一律寫英文，中文版靠 `strings.zh.json` 產生。兩版是平等的交付物**，都要在請使用者審閱之前產好，各自標 `EN`／`中文`。`point`／`from`／`to`／`notes`／`why_text` 與**使用者原話**（`user_points`、`answers`）可用中文，豁免表在 `deck_schema.md`「語言」。
2. **只留對講解有幫助的東西。** 沒有封面、頁碼、線標籤、「待決與下一步」頁、底部結論條；簡報從 outline 直接開始。新增任何元件前先問：這幫聽眾理解了什麼？
3. **三個關卡是把判斷挪到最便宜的時候做。** layer3 一頁畫錯要重畫，layer1 判錯只是改一行字。每一層結束就跑 `check_gate.py`，⛔ 沒過不進下一層。

## 入口：一層一個 session

| 打什麼 | 做什麼 | 開始前先跑 |
|---|---|---|
| `/weekly-deck layer1` | Step 1 ＋ layer1 ＋ 關卡① | — |
| `/weekly-deck layer2` | layer2 ＋ 關卡② ＋ 骨架 | `check_gate.py layer1 $OUT` |
| `/weekly-deck layer3` | 產頁 → 檢查 → 關卡③ →（選用）pptx | `check_gate.py layer2 $OUT` |
| `/weekly-deck all` | 三層連跑（單一 session；⚠️ 貴 3~4 倍，只給短週） | — |
| `/weekly-deck plan` | ＝ layer1 ＋ layer2（舊入口） | — |

⭐ **為什麼要切 session**：帳單 ＝ Σ(每一回合當下的 context)，context 只增不減。2026-09-06 的實跑
協調者從 Step 0 活到 pptx，後期每回合是前期的 4.5 倍。狀態本來就全在磁碟上，關卡就是自然的邊界；
新 session 從 `check_gate.py` 接手，使用者在關卡想多久都不再有代價。量測與論證見
`references/orchestrator-cost.md`。

**三條成本規矩**：① 一個 session 只做一層，改 skill／討論另開；② **協調者不讀大東西**（素材、
檢查程式原始碼、subagent 轉錄、自己產的 SVG）——要數字用腳本印（`check_deck.py --limits`、
`verify.py --quiet`）；③ **機械的寫檔交給腳本**（定案檔、骨架、outline、確認稿），⛔ 不手寫 JSON。

## 輸出目錄

`<週報輸出根>/<今天>/`（輸出根 ＝ `python3 $S/paths.py reports-root`）。三條規矩：
**交付物 `deck.en.html`／`deck.zh.html` 在最上層；`deck.json`／`strings.zh.json` 也留最上層**（四支腳本從它所在目錄推算路徑）；
**其餘過程產物一律 `paths.work_file(out, "<檔名>")`**，⛔ 不自己拼 `_work/…`。`_export/` 不跑截圖就不該存在。
完整目錄樹與舊結構相容 → `references/output-layout.md`。

## 角色：**同一個 agent 依序扮演**，只有多線才派 subagent

五個角色規格在 `references/subagent-*.md`，派遣包一律 `brief.py <role>` 打（角色清單的唯一定義是它的 `ROLE_SPEC`；`--show-refs` 看誰讀哪一份）。

| 角色 | 什麼時候由**你自己**做（讀那份 brief 後照規格做） | 什麼時候派 subagent |
|---|---|---|
| `thread_finder` | 一律自己做 | — |
| `slide_planner` | 只有 1 條線 | ≥2 條線：每線 1 個，平行 |
| `slide_builder` | 只有 1 條線 | ≥2 條線：每線 1 個，平行；返工派 **`fixer`**（新 agent＋修復包），⛔ 不 resume |
| `layout_reviewer` | — | 只在 `--review` 時派 1 個（Sonnet），輸入是 `review_packet.py` 的包 |

派遣訊息骨架、resume 與派新的損益點、試錯上限 **2 輪** → `references/delegation.md`（⛔ 上限數字只有那裡一份）。
自己扮演角色時，brief 裡「回報 DONE／BLOCKED」改成「寫檔、跑對應的 gate」；規格的其餘一字不減。
⛔ 不論誰做：`user_points`、`narrative`、每一則 `answers` 都是**使用者的原話**，不得代擬。

---

## layer1 — 找主線（★ 關卡①）

```bash
S=<skill 目錄>/scripts
OUT="$(python3 $S/paths.py reports-root)/$(date +%F)"
python3 $S/merge_items.py     --since-last-deck --out $OUT   # 跨日合併提名（⛔ 一定先跑）
python3 $S/cluster_threads.py --since-last-deck --out $OUT   # 物證分群
python3 $S/build_deck.py      --since-last-deck --out $OUT   # materials.md / deck.draft.json / plan.todo.json
python3 $S/brief.py finder --out $OUT                        # 你要讀的那一份（角色規格＋素材）
```

- 區間從**上一份 deck** 推（`--since-last-deck`）；要覆寫用 `--days 起 迄`，理由寫進 `meta.range_note`。`--last N` 只給第一份週報。
- **選材之前先合併**：`merge_items.py` 提名、你逐組裁決（寫得出一個共同目標的標題嗎）；分數只排序，上不上台由關卡① 的使用者決定。
- 讀 `brief.finder.md`，照 `subagent-thread-finder.md` 寫 `layer1.json` 與 `layer1.md`（每線「一句結論＋≤3 行支撐」）。粗選材用 `editorial_policy §1b＋§2`；⛔ 不硬串因果（你看得到的是時間順序）。

### 然後停下來問

```bash
python3 $S/gate_view.py layer1 $OUT          # → gate1_view.md（固定模板）＋ gate1_answers.json（空白）
```

用 `AskUserQuestion` 的**選擇題**問 `gate1_view.md` 列的固定七題：合併定案／**每條線「只講 3~4 個重點是哪幾個」**（⭐ 決定有哪幾頁；選項列候選重點但一定留「都不是，我自己說」）／主角與因果／從做不到變做得到／教授上次問了什麼、指定了什麼／**有沒有哪件事沒被列進候選但一定要講**（候選來自每日 headline，實測只涵蓋約八成）／不展開什麼、要不要鋪陳頁。
把**原話**逐字填進 `gate1_answers.json`（`narrative` 由問答→組句→確認得出，來歷寫 `narrative_source`；`arc` 四欄從答案收斂；`members_without_point` 的去處由使用者決定）。

```bash
python3 $S/check_gate.py layer1 $OUT --confirm $OUT/_work/2_layer1/gate1_answers.json   # 寫 layer1_confirmed.json ＋ 驗
```

🗣 選不出來／東西太多／說不出哪裡怪 → `references/gate-facilitation.md`。**一條線反覆做不好時**，先懷疑它只有一頁的量（同一份）。

---

## layer2 — 逐頁規劃（★ 關卡②）

```bash
python3 $S/check_gate.py layer1 $OUT                 # 新 session 先確認上一層是綠的
for T in <線id…>; do python3 $S/brief.py planner --thread $T --out $OUT; done
```

一條線：自己讀 brief 照 `subagent-slide-planner.md` 寫 `layer2.<線>.json`／`.md`。多線：每線派一個 planner。規格的主幹：

- **`method` 與 `result` 預設有頁，介紹／`problem` 預設沒有**（開或不開都填 `slot_reason`）。
  ⚠️ 這裡原本寫「只有 `method` 預設有頁」，與 `subagent-slide-planner.md` 的表相反 —— 實測三份產出 **21 張內容頁全是 `mechanism`、`result` 0 張**，整場只剩「這東西怎麼運作」。`result` 的觸發是「量到的數值」**或**「帶著一個新判斷」，兩條都不成立才拿掉。頁數 ≈ Σ user_points（result 在額度內擇一；單線 ≤7、全場 ≤15；`SLOT_EXEMPT` 的頁豁免對 user_point，清單用 `check_deck.py --limits` 印）。
- 每頁兩道判準、順序不可顛倒：**①** 講「這個東西現在是什麼／怎麼運作」而非「我怎麼弄成這樣」（一次性開發過程連口頭都不講 → `plan.dropped`；下週還會再發生的常設機制放行）。⚠️ **例外：意外發現／溯源調查／推翻既有定案不算「我怎麼弄成這樣」** —— 它們是**本週的結果**，`editorial_policy §2` 早就把它們判成主線。原本沒寫這個例外，判準① 在下游把 §2 已經放行的東西又砍一次（實測：一條線 70% 的實跑素材因此沒上台）；**②** 講得出一件具體的事（機制／決定＋依據／限制下做得到什麼）。
- **I/O 物品契約**：同線第 i 頁 `input` 逐字等於第 i−1 頁 `output`，物品名進 `plan.terms.objects`；沒有物品的頁用 `to`→`from` 承接。
- `method` 頁 `depth: mechanism`、**例子優先**（先選一個具體案例讓它跑過規則，主圖全幅）。
- 選材去處**全記不刪**：每個 sid 不是上頁就是 `plan.dropped`（合併不豁免，逐 sid）。
- ⑦ **削減回合**由 planner 提議（`trim_pass`），⛔ 不自己砍；使用者在關卡② 決定。
- 物品名的**中譯**一起提名（`terms_proposed_zh`），關卡② 凍結後 layer3 照表翻。

### 關卡②（B17-6：這是唯一決定「每頁內容」的一關）

```bash
python3 $S/gate_view.py layer2 $OUT          # → gate2_view.md ＋ gate2_answers.json（空白）
```

逐頁表**刻意不給長相**。`AskUserQuestion` 固定三題：① 逐頁看「講什麼」欄，**哪一頁的重心不對**（選項列頁號＋point，一定有「都對」）；② 哪一頁該用圖、哪一頁口頭帶過；③ 頁序與削減提議採不採納。名詞凍結表（en→zh）一併確認。
使用者對某頁的內容指示 → **planner 角色改 `layer2.<線>.json`**（原話進 `gate2_answers.json` 的 `page_notes`），改完才：

```bash
python3 $S/check_gate.py layer2 $OUT --confirm $OUT/_work/3_layer2/gate2_answers.json   # 翻 slide_plan_confirmed
python3 $S/build_deck.py --skeleton --out $OUT           # deck.json 骨架（slides: []）；要派 reviewer 加 --review
python3 $S/check_gate.py layer2 $OUT                     # ⛔ 沒過不進 layer3（它也驗骨架）
```

---

## layer3 — 產頁 → 檢查 → 關卡③

```bash
python3 $S/check_gate.py layer2 $OUT
for T in <線id…>; do python3 $S/brief.py builder --thread $T --out $OUT; done
```

一條線：自己讀 `brief.builder.<線>.md` 照 `subagent-slide-builder.md` 做。多線：每線派一個 builder（平行；跨線共用的名詞與同名物件畫法**派遣前**就在骨架的 `plan.terms` 裡，⛔ 不要等一邊做完再轉給另一邊）。
`model: sonnet` 給 builder 是**有條件**的選項（判準與實測在 `delegation.md`「模型分級」）：用了就一定 `--review`。

builder 的交件物：`_work/3b_specs/<頁id>.json`（構圖 spec，含 `budget`）→ `render_figure.py --all $OUT --thread <線>` 一次渲染（⛔ 多線平行時不給 `--thread` 會重寫別線的圖）→ `slides.<線>.json`（含 `honesty`）、`compositions.<線>.json`、`strings.<線>.zh.json`（`render_deck.py --dump-strings zh --thread <線> --strings-out …` 後一次填滿）→ `verify.py --out $OUT --thread <線> --quiet` 綠燈。
⛔ builder **不 Read 自己產的 .svg**、不 `cat` 全文 —— 看不看得懂是 shoot 與 reviewer 的事。畫圖的規矩（四步驟、八個 renderer、顏色三種角色、文字四種用途、數字逐字照抄）全在 builder 的規格與派遣包裡，⛔ 這裡不重抄。

### 機械檢查 → 一次退回

```bash
python3 $S/merge_slides.py $OUT/deck.json $OUT/_work/4_slides/slides.*.json --outline   # 併頁＋併譯文片段＋全場 outline
python3 $S/verify.py --out $OUT --quiet          # merge → check → render 兩版 → strings → shoot 兩版；七步一個回合
```

- 全場 outline 由 `--outline` 產（multi：一線一列；single：列 user_points，B17-4）。剩下沒翻的句子你直接補進 `strings.zh.json`（照 `plan.terms_zh`）。
- 有 ERROR **照樣往下跑**，findings 湊齊才退：`check_deck` ERROR ＋ `shoot` 版面 ＋（有的話）reviewer BLOCKING **合成一份** `_work/4_slides/findings.<線>.md`，一次退回。
- 退回 ＝ 派 **fixer**（`brief.py fixer --thread <線> --findings <檔>`），⛔ 不 resume、不重送完整派遣包；單線時你自己照修復包修。**最多 2 輪**，第 3 次停下來把「要求什麼／做不到什麼／三個選項」拋給使用者。
- `--review`（多線、或 builder 用 Sonnet、或使用者要求）：`python3 $S/review_packet.py $OUT` → `brief.py reviewer` → 派 1 個 reviewer（Sonnet）。它自己回填 `plan.layout_reviewed`；不派時骨架已寫 `{"skipped": …}`。
- `shoot.py --check-only` 是品質關卡不是 pptx 前置：溢位會被靜靜裁掉，⛔ 兩版都要量、都要過。

### ★ 關卡③ — 唯一讓使用者看畫面的一關

`verify.py` 全綠後、交付前，給 `deck.en.html`／`deck.zh.html` 的絕對路徑（兩版平等，⛔ 不替他選）。`AskUserQuestion` 固定三題：① 能不能上台講（能／改幾頁／整條線重來）；② 哪一頁**看不懂**或名詞前後不一致（選項列頁號＋point，一定有「都看得懂」）；③ 哪一頁太空或太滿（選項列 shoot_check 與 reviewer 點名的頁）。

### 回填（不可省）

- `plan.feedback`：他原本看到什麼、改成什麼、理由、**判準錯了還是本次特例**（`criterion_wrong`）。判準錯 → **提議**改 `references/`，⛔ 不自己改。這個機制是這個 skill 進步的唯一來源。
- `<週報輸出根>/_explanations.md`：§1 教授的提問與功課（答完才劃掉）、判成「不講」的指導方針；§2 這週定案的說法／名詞／圖法。**沒有就寫「本週無」**，⛔ 不整段省略。只有你握有原話與整份 deck，寫的人是你。
- `measure_effort.py <起> --log` 登記耗時；要交 `.pptx`／問「怎麼播」／交付後改頁 → `references/delivery.md`。

```bash
python3 $S/check_gate.py layer3 $OUT
```

---

## outline 頁（定義）

全場 **1 張**不掛 `thread` 的 `agenda`，由 `merge_slides.py --outline` 產：multi 一條線一列（`title`／`summary` 逐字取自關卡①）；single 直接列該線的 `user_points`（⛔ 不再有第二張，B17-4）。multi 時 method 頁 ≥3 的線另有一張掛 `thread` 的 `agenda`，**項數 ＝ 該線 `user_points` 條數、逐字**（截短只准抄前半句）。outline／agenda 是**結構頁**：不進承接鏈、不算內容頁、不對 user_point（唯一定義 `check_deck.STRUCT`）。

## 硬性規定（會擋的東西）

| 誰擋 | 什麼時候 | 驗什麼 |
|---|---|---|
| `check_gate.py layer1` | 關卡① 後 | `layer1_confirmed.json`：`confirmed_by`／`narrative`／`mode`／每線 `user_points`／`merged_groups`；頁數預估照 `mode` 用對的上限 |
| `check_gate.py layer2` | 關卡② 後 | 每頁對得上一條 `user_point`、每條 `user_point` 有頁；`point` 型別與字數；`from`／`to` 承接鏈；mechanism 頁有 `example`；`trim_pass`；`slide_plan_confirmed`；逐線檔對帳；`deck.json` 骨架 |
| `check_gate.py layer3` | 交付前 | 兩版 HTML 都在；逐線 `slides.<線>.json`；`must_numbers` 對帳（砍要具名留痕）；spec 新鮮度 |
| `check_deck.py` | `verify.py` 的 `check` 步 | 一頁一重點、承接、數字溯源（逐字；中文數字↔阿拉伯數字豁免）、版型容量、來源、`plan` 留檔、I/O 鏈、物品登記、頁數預算、深度、例子優先、outline、`layout_reviewed`、手繪配額、金字組合、`terms_zh`… 門檻一律 `--limits` 印 |
| `shoot.py --check-only` | `verify.py` 的 `shoot_*` 步 | 溢位（擋）、主線內容過空（擋）、文字互壓（擋；B17-13，兩版都量）、底部留白／列高／字級（列出不擋） |

> **不要靠自我宣稱。** 問模型「有照規定嗎」它多半答「有」。一律跑檢查程式；它們印得出來的數字，⛔ 不要憑印象寫進文件。

## 版型是起點，不是牢籠

`slide_types.md` 是現成可用的東西，不是限制；有更好的排法就寫新 SVG 或加 CSS 版型再登記回去。唯一不可協商的是上表的機械檢查與「圖 > 表 > 文字」。

## 只有要改這個 skill 時才讀

`references/BACKLOG.md`（延後的事）、`orchestrator-cost.md`（成本量測）、`rule-provenance.md`（每條規則在防哪一次失效；本檔瘦身時搬出去的理由段落也在那裡）。
