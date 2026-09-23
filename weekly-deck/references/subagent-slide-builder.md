# Slide Builder Contract（layer3，每主線一個）

## Role

把**一條主線**確認過的逐頁表變成真的投影片：寫 `slides[]` 片段、產圖、
填 `notes`。同一條主線的所有頁都在你手上——**頁與頁之間的一致性是你的責任**。

**不得**改變頁數、順序、`point`、`depth`、`body` 型態、`must_numbers`——那些是使用者在關卡② 確認過的。
需要改 → 回報 `BLOCKED` 說明理由，不要自己動。

## Required inputs

1. `<out>/_work/3_layer2/layer2.<thread>.json`（**你這條主線的**，使用者已確認）
   ＋ `<out>/_work/2_layer1/layer1_confirmed.json`（關卡① 的定案，看主線的定義與 `user_note`）
2. `deck.json` 的 `plan.terms`
3. `references/composition-vocabulary.md`
4. `references/presentation_rules.md`
5. `references/slide_types.md`
6. **已產出的構圖清單**（其他主線用了哪些構圖、同名物件長什麼樣）
7. 該主線每頁 `deep_dive` 列的原檔
8. `<週報輸出根>/_explanations.md`（若存在：講過的概念沿用同一套說法與圖）
   （⛔ **不是** `weekly_reports/_explanations.md` —— 那是舊版面的相對路徑，在新結構上會靜默找不到；輸出根 ＝ `python3 scripts/paths.py reports-root`，派遣時由協調者給絕對路徑）

## Preflight

- ⛔ **第一件事：確認你在對的 repo**（N86）。先照派遣訊息的「環境設定」那一行設定環境，
  再跑一次並**逐字比對**：

  ```bash
  python3 $S/paths.py reports-root       # 要等於派遣訊息「工作目錄」的上一層
  ```

  不一致 → **立刻 `BLOCKED`**，⛔ 不要自己挑一個看起來對的。
  ⚠️ 沒設定環境就跑，得到的是**別的 repo 的路徑，而且不會報錯** ——
  上一次盲測在 subagent 內拿到的是 `<平時那個日誌 repo>/weekly/`，
  只因為協調者剛好給了絕對路徑才沒有把週報寫進別人的 repo（`delegation.md` 環境設定那欄）。
- `layer2.<thread>.json` 存在，且**它自己的頂層** `slide_plan_confirmed` 為 `true`。
  ⛔ **不要去 `deck.json` 的 `plan.slide_plan_confirmed` 找** —— 那是**全域**旗標，
  蓋不住「A 線確認了、B 線還沒」；逐線的定案只有逐線那一份說了算（FINDINGS N19）。
  該欄仍是 `false` 或不存在 → `BLOCKED`，請協調者補上關卡② 的定案。
- 日期目錄最上層有 `deck.json`（協調者在派你之前寫的骨架，`slides` 可能還是 `[]`）——
  **自驗那一步要它**。不在 → `BLOCKED`，⛔ 不要自己造一份（N61）。
- 每頁都有 `composition.gate`。缺 → `BLOCKED`（守門提問沒答就開始畫，等於硬套）。

## Procedure

### 1. 投影片上的文字只有四種合法用途，且**每則都要標出是哪一種**

`label`（東西的名字）／`value`（數字）／`annot`（這張圖怎麼讀，**每頁 ≤2**）／
`def`（名詞定義，**每頁 ≤1**）。`label`／`value` **不得成句**；
⛔ **淺色只給 `annot` 與 `def`**。⛔ 舊的 `t-sm`／`t-md`／`t-lg` 已作廢。
完整字彙表與理由：`presentation_rules.md`。`check_deck.py` 會擋。

⭐ **額度算整張投影片，不分寫在哪裡**：`annot ≤2`／`def ≤1` 不是「每張 .svg ≤2」，
是**每頁 ≤2** —— 圖裡的 `<text>` 與 deck.json 欄位渲染出來的字**合併計數**。
把旁白從圖裡搬到 `sub` 或 `caption` **不會**過關，兩邊算同一份額度。

| deck.json 欄位 | 用途 | 寫的時候要注意 |
|---|---|---|
| `sub` | `annot` | 佔掉這頁的 annot 額度。寫「怎麼讀」，不寫「說明了什麼」 |
| `body.caption`（圖說） | `annot` | 同上。構圖本身讀得懂就**不要寫**（§2c-2） |
| 表格的 `caption` | `annot` | 同上 |
| `stats` 的 `k`／`v` | `label`／`value` | `k` 是那個數字的名字，**不得成句** |
| `flow` 步驟的 `d` | `label` | 步驟框的一部分，**不得成句**；要寫成句子代表它是旁白，搬進 `notes` |

⚠️ 一頁若已經有 `sub` ＋ 圖說，圖裡就只剩 0 則 annot 的額度。
**先決定那 2 則要花在哪裡**，不要三處各寫一句再回頭刪。

#### ⭐ 交付前自檢：逐一盤問主圖上的每個 `label`／`value`

**每產完一張圖，把圖上的每一則 `label`／`value` 列出來，各寫一句「聽眾拿它做什麼」。**
答不出來的**當場拿掉**（好材料搬進 `notes`，那是講者的東西不是版面的東西）。
判準與被砍掉的三類實例逐字見 `presentation_rules §2c-2`，⛔ 不在這裡複製。

> **為什麼要加這一條**：§2c-2 早就寫對了，但**沒有任何角色在執行它**——
> 上一次盲測 `A1_two_layers.svg` 放上 `420 words per item`／`395-609 words per item`、
> `A2_scan_chain.svg` 放上 `2 sessions · 745 turns · 447 KB`，
> 而這兩組正是 §2c-2 表格裡**逐字點名**被砍掉的實例（FINDINGS G1）。
> 「規則寫在文件裡」擋不住事情，**要有人逐則問過**。

**同一輪再問第二遍：這個東西，聽眾可以自己打開來看嗎？**
打得開（檔名、目錄、副檔名、skill／subagent 名）→ ⛔ 不准用功能描述頂替（`Presentation layer`、
`Pick what to say`、`1 planner per thread` 都是實測實例），當場換成真名；
打不開、要讀原始碼才看得到（`W_PARTICIPATION`、`items[]`、`NOT_HUMAN`、`MAX_TITLE`）
→ ⛔ 當場換成白話解釋（同樣是實測實例）。**東西的名字用真名，動作與判準的解釋用白話。**
判準、例外與正反例逐字見 `presentation_rules §1d-0`，⛔ 不在這裡複製。
換上真名之後那一格會自然變密，這正是版面填不滿的解（`presentation_rules §6`）。

**同一輪再問第三遍：這個名字是不是我從 I/O 契約複製過來的？**
⚠️ 本檔（與 `subagent-layout-reviewer.md`）寫的契約路徑 —— `layer2.<thread>.json`、
`slides.<thread>.json`、`compositions.<thread>.json`、`.data/<date>.json`、
`daily/<date>.html` —— **在契約裡是對的**：那是寫給你讀、由你代換的樣板。
⛔ **但它們不得原樣上投影片。** `<thread>`／`<date>` 對聽眾是個空洞，
實測**看的人讀不出那是什麼** —— 會被當成程式碼，或以為那一格沒有渲染成功。
上版面前**每一個**這種名字都要過 `presentation_rules §1d-0` 的**第三層**那一節，
照那裡寫的正解改寫，⛔ 判準與正解不在這裡複製。
⚠️ 適用範圍同 §1d-0：標題、`slide-label`、表頭，**以及圖裡每一個方框名**
（實測 4 張圖中招，全部是從契約直接抄過去的 label）。


① 名詞定義　② 圖表標註　③ 沒有它圖就讀不懂的必要補充。

- **結論句一律不上投影片**，寫進 `notes` 的「【口頭結論】」。
- **caption／圖說只能寫「這張圖表怎麼讀」**，不能寫「這張圖表說明了什麼」——
  推論與結論搬進 `notes`。⚠️ 這是最容易漏的一類。
- 標題要**說出這頁在講什麼**，且要**讀起來像從上一頁的結論繼續講下去**
  （承接靠標題扛，因為 `from`／`to` 不上投影片）。用動作句，不用名詞短語。
- **`notes` 是講者唯一的口頭稿，一頁至少要撐得起一分鐘。** 固定四個標籤，
  【口頭結論】必寫，其餘有就寫（`check_notes_substance` 會驗有沒有具體錨點）：

  ```
  【口頭結論】這一頁講完要說出口的那句話（＝ slide 的 `to`）
  【細節】     日誌 `details` 的內容 —— materials.md 的「細節：」那幾行，
               尤其是「哪一版壞了、怎麼發現的、代價是什麼」這種過程
  【數字】     版面容不下而被砍掉的量測與佐證（數字溯源仍然要對得上）
  【為什麼】   這個做法的理由、比較過的選項、答不出來所以沒畫上去的東西
  ```

  ⛔ 只寫一句抽象的【口頭結論】＝ 講者上台無話可講（實測失效：七頁平均 28 字元，
  使用者得自己補 8,677 字）。⛔ 但 `notes` 也不是垃圾桶——
  進 `notes` 的門檻見 `subagent-slide-planner.md`「`notes` 不是垃圾桶」。

### 2. 產圖：照 `composition` 走，不要自由發揮

```
composition.comp 有 renderer  →  python3 scripts/render_figure.py spec.json -o figures/<name>.svg \
                                     --budget <去 diagram-craft.md §6 查表得到的 px>
沒有 renderer                 →  手寫 SVG，照 composition.spec_hint 的內容畫，
                                 viewBox="0 0 1420 <同一張表查到的高>"，
                                 並標 "composition.handwritten": true
```

⚠️ **高度預算逐頁不同**（有沒有 `topic`／`sub`），⛔ 不要憑印象填 540 ——
那個舊數字來自已停用的 `takeaway`（N67）。查表：
`diagram-craft.md §6` 的表是唯一出處，寬則全域固定 **1420**（N68）。

**layer2 已經填好 `relation`／`comp`／`gate`／`spec_hint`／`off_vocabulary`；
你要補的是 `spec`（座標級的構圖 JSON）與 `handwritten`，以及色值。**

⛔ **色值的部分先答一句：這張圖的主張是哪一句？** 然後按**由強到弱**挑手段：
**位置／大小（放大、放中間、放第一個）→ 標題 → 一處金字**。
⛔ **沒有第四項** —— 框、線、長條的顏色**只做分類**（`bad`／`good`／`null`／`ctl`），
不做強調。`box-hl`／`grp-hl`／`arrow-hl`／`bar-hl` 與 `tone:"hl"`／`focus`
**都已廢除**，寫了會當場報錯。判準見 `presentation_rules §5`、畫法見 `diagram-craft §6c`。

⭐ 會被 `layout_reviewer 3c` 逐頁擋下來的三條：
**① 沒有強調形狀**（含「用分類色假冒強調」）；
**② 金字全圖只能一種 class 組合**；
**③ 這處金要答得出「拿掉它，觀眾會少知道什麼」** ——
⛔ 標在本來就最大／最中間的東西上，或並列的同類裡只標一半，都答不出來。
⚠️ 反方向：⛔ **不是「每頁都要有一處金」** —— 金色**上限 1、沒有下限**。
要答得出的是「三秒內眼睛落在哪」，答案可以是**位置或標題**。

⚠️ `handwritten: true` **不需要寫理由**——多數構圖還沒有 renderer，手寫是常態。
⛔ 但**有 renderer 的那八個**（`read_pileup`／`haplotype_split`／`chain` 系列／
`group_blocks`／`two_col_link`／⭐ `funnel`＝`funnel_named`／`transform_pair`／
`before_after`）**不准手寫**，一律走 `render_figure.py`。
⭐ **上一份 deck 的手繪已經降到 0 張** —— `diagram-craft §0` 的 2–3 張額度整個空出來，
⛔ 不要因為額度空著就回去手寫。

### ⭐ 出貨的圖必須**重跑得出來**（`check_spec_reproduces()`，**ERROR**）

`python3 scripts/render_figure.py <spec> -o <svg>` 重跑一次，
必須**逐 byte** 重現你交的那張圖。三件事因此被擋住：

| 擋住的 | |
|---|---|
| spec 還留著 `<date>`／`<thread>` 這種佔位符 | ⚠️ 重跑一次就把定案的真字串洗掉 |
| **手改了 SVG 沒回寫 spec** | ⭐ 佔位符掃描抓不到這一種 |
| **spec 改了但圖沒重跑** | 同上 |

⭐ **幾何完全相同、只有字串不一樣時，「圖看起來一樣」騙得過眼睛** ——
⛔ **判準是逐 byte，不是看圖。**
⭐ 每份 spec 要填 `"budget": <px>`（去 `diagram-craft §6` 的表查）——
那是它**唯一的記錄處**，⛔ 不要只靠命令列 `--budget`，否則下一個人重跑只能猜。
落點：`paths.work_file(<out>, "<頁 id>.json")`（`_work/3b_specs/`），⛔ 不要自己拼路徑。
要寫理由的是 `off_vocabulary: true`（那是 layer2 標的，代表字彙裡沒有這種構圖），
而那句理由已經在 `why_off_vocabulary` 裡，你不必重寫。

⚠️ **不准改構圖。** 覺得該換 → `BLOCKED`，不要自己換（構圖是關卡② 確認過的主體型態）。

手寫 SVG 的規矩（`slide_types.md` §「寫 SVG 的規矩」）：
- 一定要有 `viewBox`，不要寫死 `width`/`height`
- **面積要反映重點**——重點的東西要大，陪襯的要小
- 圖上有門檻／目標線一定要標數值
- 顏色語意全場一致（`render_figure.py` 的 `PALETTE` 是唯一定義）
- ⭐ **顏色有三種角色，你只需要填其中一種**（`presentation_rules §5`，2026-09-05 使用者裁決）：

  | 角色 | 回答 | 誰做 |
  |---|---|---|
  | **區別**「這是並列的哪一個」 | `box-c1`~`c12` | ⭐ **renderer 自動配**（依名字雜湊）—— ⛔ 你不必也不能填 |
  | **分類**「這是哪一類」 | `bad`／`good`／`null`／`ctl` | ⭐ **只有這一種要你填 `tone`** |
  | **強調**「看這裡」 | 只剩**字**（`svg .hl`） | 一圖一個角色 |

  ⛔ **不要為了「讓框看起來不一樣」去填 `tone`** —— 那是區別，renderer 已經做了；
  拿 `bad`／`good` 去做區別會讓觀眾把那個框讀成「壞的／通過了」。
  ⭐ **填 `tone` 之前先答**：這個框是**舊的／失效的**（`bad`）還是**新的／通過的**（`good`）？
  答不出來就**不要填**。
- ⛔ **不得在 `<text>` 上寫 inline `font-size`／`font-weight`／`letter-spacing`**
  （`check_deck.py` 的 `check_inline_type()`，逐則 **ERROR**）。層級用**角色 class**：
  `label.section`（盒內分段標題）／`label.term`／`label.gloss`（定義列左右欄）／
  `label.num`（序號）—— 表在 `slide_types.md` 的 class 表與 `presentation_rules §2`。
  ⭐ **層級只准有一個來源**：字彙。自己挑一個字級 = 這張圖跟別張長得不一樣，
  而那是**看圖看不出來、要 diff style 字串才發現**的不一致。
  缺角色就 `BLOCKED` 說明缺哪一級，⛔ 不要自己在圖上補 style。
  ⚠️ `font-family`（等寬）不在禁令裡。

### 2b. ⭐ 表格有「代價／造成什麼」欄時：逐列自檢（N72）

**這一欄的每一列都要有一個數得出來的量**：頁數、輪數、筆數、時間、次數。
判準的唯一定義在 `slide_types.md`「`table`：『造成什麼／代價』欄每列至少一個可數的代價」。

**交件前把那一欄逐列列出來**，每列指出那個數字是什麼：

- ✅「7 頁規劃只有 2 頁是要的」「checker 誤判 7/8 頁」「一張圖改 4 輪」
- ❌「只對了一半」「花了不少時間」「規格和我想的不一樣」 ← 敘述句，聽眾比不出輕重

**數不出來的那一列 → 降到 `notes` 口頭講**，⛔ 不要留在表上湊列數。
⚠️ 數字一樣受數字溯源約束（§4）：逐字照抄來源，不得計算。
⚠️ 來源裡真的沒有可數的量 → 那一列**不要留在表上**；⛔ 不要為了過這一條去湊一個數字。

> **為什麼寫進契約**：`check_capacity()` 只量列／欄／字數，**看不到欄的語意** ——
> 這條規則以前兩邊都沒有執行者。而它是**已知會復發**的形狀：
> 人工成品的同一張表每一列都有數字，上一次盲測的對應那張中欄
> **一個數字都沒有**（FINDINGS G4）。

### 3. 跨頁一致性（這是主線粒度的理由）

在你手上的這幾頁裡，同一個物件必須：
- 用**同一個名字**（`plan.terms`）
- 用**同一個顏色與形狀**
- 位置盡量一致（同一個東西不要一頁在左、一頁在右）

還要對照「已產出的構圖清單」——**別的主線已經畫過的東西，你要沿用它的長相**。

#### ⚠️ 契約到這裡為止 —— 其餘是讀物，不是交件條件（N76／N77，批次 5f 定案）

`presentation_rules.md` 你**幾乎整份都會讀到**（只有〈1c. 三種內容有固定的講法〉
是 planner 的），裡面還有幾條談跨頁與逐頁的規則。它們是**寫作習慣**，⛔ **不列進上面的 Completion criteria**：

| 規則 | 為什麼不進契約 |
|---|---|
| §2f 同一個例子貫穿多處、換例子要回頭檢查別處 | 沒有機械可驗，而它要的是「寫的時候順手」，不是交件時對表 |
| §1d 指涉詞只能指向前一頁明確命名過的東西 | 同上 |
| §9 同一個數字出現多處時指向同一個 `source` | 數字**溯源**已經擋住「憑空造數字」；「指向同一個 source」擋的是往後的分岔，機械看不到 |
| §2e／§2e-1 機制頁逐元件三件事、上行證據下行做法 | 契約已經用整頁粗篩問過（「聽眾能不能說出這一步在做什麼判斷」），逐元件那層由 `layout_reviewer` 的第 4 項看 |
| §1b-2 動作句適用範圍（欄位名尤其常犯） | 契約只涵蓋標題；其餘是編輯目標 |
| §6 圖表頁的非 SVG 正文 ≤160 字元 | 規則自己就寫著「是編輯目標，不擋」 |

> ⭐ **為什麼刻意不補進契約**：這幾條**兩邊都沒有執行者**（既無程式、也無角色檢查清單），
> 而 B2 的裁決是「**只指派會出事的**，判準＝有實測災情紀錄或已知復發形狀」。
> 這六條沒有。⛔ 把它們寫成交件條件只會讓 Completion criteria 長到沒有人逐條對，
> 反而稀釋掉真正會擋的那幾條 —— 那正是 N50／N56 記著的失效。
> **讀到就照著寫，⛔ 但不要在 `DONE` 裡宣稱「已逐條檢查」。**

### 4. 數字：只能逐字照抄

投影片上（含 SVG 的 `<text>`）每個數字必須**逐字出現在來源日誌 JSON**。

- ⛔ 不得計算、不得換算、不得四捨五入。**單位換算也算改寫**
  - ⭐ **唯一例外**：中文數字 ↔ 阿拉伯數字（二十→20、千分之一→1e-3）不算改寫，
    因為 `deck.json` 一律寫英文而日誌是中文的。**界線：位數與單位沒變的是書寫系統，位數變了的是換算**：

    ```
    二十 → 20        ✅ 位數與單位都沒變 → 同一個值的兩種寫法
    千分之一 → 1e-3  ✅ 同上
    3,664 萬列 → 36,640,000   ⛔ 位數變了 → 這是換算，仍然擋
    ```

    原規則要防的是後者（憑印象換算錯），⛔ 不要因為這條例外就把前者也放寬。
    `check_deck.py` 的 `cn_numbers()` 已實作（只做 0~999 與「N 分之一」，刻意不做「萬」「億」）。
    （這一段 2026-09-06 從 `SKILL.md` 搬來，那邊不再有數字那一節。）
- **數字來自 `docs/` 原檔時，把該檔路徑列進 slide 的 `extra_sources`** ——
  `check_deck.py` 會把那些檔一併納入可溯源的數字池。
  ⛔ 不要因為「日誌裡沒有這個數字」就放棄整頁（受控演練時 layer2 實際誤判過一次）。
- ⚠️ 檢查的實情：它把來源**全文抽成數字集合**再比對，所以抓得到「憑空造的數字」，
  但**抓不到「數字用錯地方」**（`9/34` 會被拆成 `9` 和 `34`）。通過不代表用對了。
- 換算不了又非放不可 → **不要放那個數字**，改由講者口頭講。

需要哪張表就**回去讀來源 JSON 複製**，不要憑記憶重打。

### 5. `depth` = `mechanism` 的頁

若 `deck.json.plan.example_first` 為 true，機制頁一律產 `type: "example"`：把 layer2 的
`example.before → example.operation → example.after` 畫成**佔滿整個版面**的外部 SVG 主圖
（`body` 只有 `src`，⛔ 沒有 `aside`）。規則與邊界**畫進圖裡**（門檻標在操作那一格、
邊界畫成不適用的那一支），⛔ 不得只放進 `notes`。
不得把案例改寫成三個泛稱方框；constructed example 要保留示意標示。

這頁必須看得到**一條具體規則**（算式、門檻、判準表）。
自問：**聽眾照這頁講的，能不能說出這一步在做什麼判斷、依據是什麼？**
說不出來 → 缺的那一步就是還沒放上去的東西。
⚠️ ⛔ 不是「能不能自己重做一次」——那會把深度推到實作規格。上限：⛔ 不放欄位名、
JSON 鍵名、函式名、腳本參數（除非那個名字本身就是這頁的主張）；一頁圖上有名字的
元件 ≤ 7 個。完整的兩端判準見 `subagent-slide-planner.md §3a`（唯一定義在那裡）。

⛔ 只有動詞沒有規則（「我們整理了／篩選了／驗證了」）= 空洞，reviewer 會 FAIL。

### 5b. ⭐ 交付前自檢：圖表誠實性 6 問（每張主圖，N71）

6 問的唯一定義在 `presentation_rules.md §8`。⛔ 它**不能由 `shoot.py` 或
`check_deck.py` 代勞** —— 機器看得到版面，看不到語意，所以這一條只有你先做、
`layout_reviewer` 再覆核。

**每張主圖畫完，逐條問一次，逐問寫一句答案**（篩選條件／有沒有平均異質的東西／
軸標籤講的是什麼還是哪裡／多重比對的深度／邊界被截斷的資料／對照組在不在同一張圖）。

- ⛔ **「沒有篩選、沒有平均」也要寫出來**，不能整段省略 ——
  省略與「答不出來」在回報上長得一模一樣。
- **被篩掉的資料量超過一成 → 在圖說寫出來**（篩掉幾筆、依據是什麼）。
- 答不出來的那一條，就是這張圖還要補的圖說。

⭐ **答案寫兩個地方，⛔ 缺一不可**（N117 ②）：

1. **寫進該頁的 `honesty` 欄**（`slides.<thread>.json`）—— 六個 key 逐問一句：

   ```jsonc
   "honesty": {
     "filter":       "沒有篩選：這張圖用的是該日誌的全部 7 個項目",
     "averaging":    "沒有平均：三個數字各自是單一次量測",
     "axis_label":   "縱軸講的是「什麼」（層別），不是「哪裡」",
     "multiplicity": "只比一組，沒有多重比對",
     "truncation":   "沒有截斷：區間兩端都畫出來了",
     "control":      "對照組（規則改之前）就在同一張圖的左欄"
   }
   ```
   ⛔ 「沒有篩選、沒有平均」**也要逐字寫出來** —— 省略與「答不出來」在檔案上長得一模一樣。
2. 逐張寫進 `DONE` 回報（見 Final response），給 `layout_reviewer` 覆核。

> ⚠️ **為什麼一定要落地成欄位**：舊版只要求「寫進 `DONE`」—— 那是**對話**，
> 檔案上零痕跡。於是 `check_gate` 的 `check_spec_fresh()` 時間戳一舊，
> **根本沒有東西可以逐條對帳**：實測協調者只回填了一個欄位，mtime 一新，
> 那 2 個 ERROR 當場消失、關卡轉綠，而三件交件義務只做了第一件（N117 ②）。
> ⭐ 現在 layer3 逐條問「檔案上有沒有證據」，⛔ 不是問「你有沒有確認過」。

⛔ 缺答案本身就是 reviewer 的 BLOCKING。

### 6. 語言與中文譯文（⭐ 2026-09-06 起譯文由**你**交）

`deck.json` 與 `figures/*.svg` **一律寫英文**。
`point`／`from`／`to`／`notes`／`why_text` 是我們自己的敘事與講稿，可用中文。
⛔ **不要產第二份 `deck.json`**——中文版由 `strings.zh.json` 字串對照表產生。

**這條線的中文譯文是你的交件物之一**（`deck_assembler` 已拿掉：寫英文的人手上就有全部脈絡，
多付的只是 output token；一個獨立的翻譯 agent 在 2026-09-06 的實跑花了 20.4M tokens）：

```bash
python3 $S/render_deck.py <out>/deck.json --dump-strings zh --thread <線id> \
        --strings-out <paths.work_file(out, "strings.<線id>.zh.json")>     # 只收你這條線的字串，值留空
```

然後**一次 Write 整份**把值填滿（⛔ 不要逐條 Edit —— 每一次 Edit 都是一個回合）：
譯文／`"="`（刻意不翻：樣本名、工具名、純數字）／`""`（未翻，落回英文）。三條硬性規則：

1. ⭐ **物品名照表翻**：派遣包「名詞」那張表（`plan.terms.objects` → `plan.terms_zh`）是關卡② 凍結的，
   ⛔ 不得另譯 —— 「同一件事一直用同一個名詞」是使用者明列最在意的四件事之一（N31）；
   `check_deck.py` 的 `check_terms_zh` 會對帳。
2. ⭐ **原話優先**：key 命中 `deck.json` 的 `plan.quotes[].en` 時，值**逐字填 `quotes[].zh`**，⛔ 不得回譯（N33）。
3. **數字非對稱**：不得憑空生出原句沒有的數字（ERROR）；把 `1,000` 寫成「一千」不算竄改。

⚠️ `--dump-strings` 會把複合字串拆出**重複條目**（`18 external tools · 8` 與 `18 external tools` 與 `8`），
三者的譯法要一致（N32）。`merge_slides.py` 會把各線的片段併進全場的 `strings.zh.json`；
剩下不屬於任何一條線的句子（全場 outline、標題）由協調者補。

## Required outputs

⛔ **三份輸出都用 `paths.work_file(<out>, "<檔名>")` 取路徑，不要自己拼 `_work/…`**
（`scripts/paths.py`）。舊版把路徑寫死在散文裡，兩個 builder 都把
`compositions.A/B.json` 寫在**日期目錄最上層**、其中一個還自行開了 `_work/_specs/`
（FINDINGS N14）。⚠️ 手寫 SVG 的 spec 暫存檔同理：`paths.work_file(out, "<slide id>.json")`
（→ `_work/3b_specs/`），⛔ 不要自己開目錄。

1. `paths.work_file(<out>, "slides.<thread>.json")`（→ `_work/4_slides/`）：這條主線的投影片。
   **形狀二選一皆可**（`merge_slides.py` 兩種都收）：
   - `{"thread": "T1", "slides": [ … ]}`　←（建議，`check_gate.py` 也讀得懂）
   - 或裸陣列 `[ … ]`
   ⚠️ 舊版這一句只寫「`slides[]` 陣列片段」，兩種讀法都講得通，結果
   `check_gate.py` 期待 dict、`merge_slides.py` 期待裸陣列 —— 實跑當場 TypeError。
   （欄位定義見 `references/deck_schema.md`）
2. `<out>/figures/*.svg`：這條主線用到的圖
3. `paths.work_file(<out>, "compositions.<thread>.json")`：這條主線用了哪些構圖、
   同名物件的長相（交給下一個 builder 與 layout reviewer 對照一致性用）。
4. ⭐ `paths.work_file(<out>, "strings.<thread>.zh.json")`：這條線的中文譯文片段（§6）。

   ⭐ **schema 定死如下**（⛔ 只有這一份；`check_deck.py` 的 `check_manifest()`
   吃的就是它）：

   ```jsonc
   {
     "thread": "A",
     "figures": [{                       // ⛔ 欄位名就是 figures，不得改叫 compositions
       "slide":   "A1",                  // 這張圖屬於哪一頁
       "file":    "figures/A1_two_layers.svg",   // ⛔ 欄位名就是 file，不得改叫 figure
       "comp":    "group_blocks",        // 用了哪個構圖
       "handwritten": false,
       "objects": {                      // ⛔ 物件名 → 一句它的長相（顏色／形狀／位置）
         "daily log": "左欄最上面那一格（一般色）"
       }
     }]
   }
   ```

   ⭐ **`objects` 的 key 必須逐字等於該 SVG `<text>` 裡出現的字串**，
   ⛔ **不得寫描述**（「左邊那個來源框」不行）。
   > **為什麼要定死**：兩條線各寫各的 schema（`figures[]/file/objects{}` vs
   > `compositions[]/figure/objects_drawn[]`），而且物件名寫成描述性文字 →
   > `check_manifest()` 只能停在 **WARN**，對不上也擋不住。實測後果：manifest 宣稱
   > A1 有 `daily log` 並叫 B 線「reuse this look」，而那個字串在兩張 SVG 的
   > `<text>` 裡**都不存在**（FINDINGS N36）。
   > ⚠️ **現況：`check_manifest()` 對舊 schema 仍只發 WARN，不會擋**（既有兩份
   > manifest 都還是舊形狀）。⛔ **不要因為「反正只是 WARN」就照舊寫** ——
   > 本節的形狀是定案，舊形狀只是還沒被升成 ERROR。

   ### ⭐ `objects` 的 value：⛔ **維持一句散文，不要結構化**（任務 6d／L4-2）

   ⛔ **不要**把它改成 `{shape, color, pos}` 三個欄位。裁決記錄見 `FINDINGS.md`
   **N123**：外觀（形狀／顏色角色／位置）**全部從 SVG 推導得出來**，
   手寫一份等於製造第二份會漂的手抄本，而且**比對宣告 ≠ 比對畫面**
   （兩頁都宣告 `shape:"box"` 就過關，SVG 裡一個 `grp` 一個 `box` 也照樣過）。

   ⭐ 那句散文剩下的唯一工作是寫**「為什麼長這樣」** —— ⭐ 而「為什麼」
   正是唯一推導不出來的東西。

   ### ⭐ `shared_terms` 要升級：宣告**身分**（`check_object_consistency` 在讀）

   ```jsonc
   "shared_terms": {
     "daily · .html": {
       "why": "呈現層那一份的真名",                  // 原本的散文，保留
       "aka": { "A1": "daily · .html · .md",         // ⭐ 同一個東西在各頁的實際字串
                "A3": "daily · .html" },
       "role_exempt": { "A3": "刻意的角色轉換＋理由（⛔ 留白不算豁免）" }
     }
   }
   ```

   ⭐ **為什麼只有這一欄要人寫**：「A3 的 `daily · .html` 跟 A1 的
   `daily · .html · .md` 是同一個東西」是**語意**，字串比對永遠追不到。
   ⛔ 其餘一律推導。**向下相容**：value 是字串 = 舊寫法，照舊認、不報錯。

   ### ⭐ 交件前自己先答兩題（L4-1／L4-2，兩條都是 ERROR）

   1. **`composition.relation` 宣告的那個關係，在圖上看得見嗎？**
      `sequence` 要方向記號（箭頭**或編號**）、`narrowing` 要寬度遞減、
      `compare` 要共用軸、`correspondence` 要連線、`partition` 要 ≥2 個群容器、
      `transform` 要分類色或箭頭。→ `composition-vocabulary.md` Step ④
   2. **這一頁的物件，在別頁上長得一樣嗎？**（只比 `lead`／`section` 的出現）
      → 同上 Step ⑤

## Completion criteria

- 三份輸出都存在。
- 頁數、順序、`point`、`depth`、`body` 與 `layer2.<thread>.json` 完全一致。
- ⭐ **每頁的 `must_numbers` 逐字帶過來**（N101）：那是 `slide_planner` 步驟 ⑥ 挑的
  「這頁一定要出現的數字」，⛔ 不得自己增刪改。**而且要真的畫在頁上** ——
  `check_deck.py` 兩個方向都驗：少畫了會 WARN，全 deck 一頁都沒帶也會 WARN。
  畫不上去 → 依下一條那張表分流，⛔ **兩條路都不准從清單裡刪掉它**。

  > **為什麼特別點名**：實測 `layer2.A/B.json` 的 8 頁**全部**有 `must_numbers`，
  > 而交出來的 `deck.json` **13 頁一頁都沒有** —— 鏈斷在這裡，而且**完全靜默**。
  > 後果有兩層：① 使用者在關卡② 指名的數字沒畫，零報；
  > ② `check_unit_numbers()` 的豁免清單恆空 → 那條檢查對每一頁都叫，等於報廢。
- ⭐ **砍掉可以，⛔ 靜默砍掉不行**（N117 ①）：到了版面才判斷某個 `must_numbers`
  不該畫，**依理由分兩條路**（⛔ 沒有第三條；`check_gate.py layer3` 逐個對帳）：

  | 理由 | 走哪 | 誰決定 |
  |---|---|---|
  | **`presentation_rules §2c-2`：聽眾拿它做不了什麼**（佐證性的規格數字、旁支統計） | 寫進**該頁**的 `must_numbers_dropped[]` | ⭐ 你自己判、自己留痕 |
  | **版面放不下**（⚠️ 那是頁面預算，不是這個數字沒用） | 照舊寫 `open_questions` | 協調者／使用者 |

  ```jsonc
  "must_numbers": ["150", "420", "60"],       // ⛔ 逐字照抄，一個都不刪
  "must_numbers_dropped": [                    // 上面那份的**子集**
    {"number": "420",                          // ⛔ 必須出現在 must_numbers 裡
     "why":    "佐證性的規格數字：聽眾不會拿平均字數做任何決定",  // §2c-2 那一問
     "where":  "notes 第 2 句"}                 // 搬去哪（notes／口頭／哪一頁）
  ]
  ```

  > **關卡 layer3 驗六件**（`check_must_numbers()`，⛔ 前五件是 **ERROR**）：
  > ① 清單本身跟 `layer2.<thread>.json` **逐字對得上**（少一個、多一個都擋）；
  > ② 宣告砍掉的必須在清單裡；③ `why`／`where` 都要有；
  > ④ **宣告砍掉卻畫在頁上**；⑤ 整批同一句 `why`（那是「把清單掃掉」的指紋）；
  > ⑥ 帳目閉合的每一則 → **一條具名 WARN**。
  >
  > ⭐ **第 ⑥ 件你要先知道**：留痕**買不到安靜** —— 砍越多 WARN 越多，
  > 關卡也**不會**因為你填了它而轉綠（比照 `wont_fix`／`role_exempt`）。
  > ⛔ 它不是「宣告一下就過關」的萬用出口：它換到的只是**讓你的判斷被看見**，
  > 代價是它會被 `layer2` 那一邊與**版面實況**兩頭對帳。
  > ⚠️ 反過來也是錯的：⛔ 不要為了避開 WARN 就把聽眾用不到的數字硬塞回版面 ——
  > 那正是 §2c-2 在治的病，而 `layout_reviewer` 的 3a 會把它判成 BLOCKING。
- 每頁有 `id`、`type`、`thread`、`point`、`from`／`to`、`source`。
- 文字版型（`points`／`cols`／`issues`）都有 `why_text`。
- 沒有 `takeaway` 欄位（結論不上投影片）。
- 有「代價／造成什麼」欄的表格，**每一列都有一個可數的量**（§2b）。
- 每張主圖都做過**圖表誠實性 6 問**，答案寫進該頁的 `honesty` 欄**與** `DONE`（§5b）。
  ⛔ 只寫 `DONE` 不算：那是對話，`check_gate` layer3 看的是**檔案上有沒有證據**（N117 ②）。
- ⭐ **自驗綠燈**：檔案產完**不算交件**，還要自己跑

  ```bash
  python3 $S/render_figure.py --all <日期目錄> --thread <線>           # 寫完所有 spec 一次渲染；⛔ 只渲染自己這條線
  python3 $S/verify.py --out <日期目錄> --thread <你這條線的 id> --quiet   # 全文落地，終端只剩摘要
  ```

  拿到 exit 0（摘要表最後一行 `✅ 跑過的步驟全綠`）才算完成。
  ⛔ 紅燈就自己修完再交，⛔ 不要交出去等協調者跑同一支腳本退回來。
  ⭐ `--quiet` 一律加；要看某一步的全文就 `grep` 那份 log 的那一段，⛔ 不要 `cat`。
  ⛔ **不要 Read 自己產出的 .svg** —— 看得懂不懂是 `shoot.py` 與 layout_reviewer 的事，
  讀回一張 SVG 就是幾千 token 留到收尾的每一個回合。要確認字串就 `grep -c '<text' <svg>`。
  （選項清單在 `verify.py` 自己的 `--help`，⛔ 不在這裡複製。）

> **為什麼把它寫進交件條件**：這些檢查**你自己也跑得動**，而協調者跑它是在
> Step 4，退回來就是一整輪返工。實測本場 A 線 builder 被 resume 4 次，
> **其中第 1、2 次就是「builder 交件 → 協調者跑 `check_deck` → 退回」**
> （FINDINGS §「每個 subagent 的工具呼叫次數」：A 線累計 64 次工具呼叫，
> 單輪首派只有 46 次）。⭐ **你多跑一個回合，換掉的是協調者那邊的一整輪** ——
> 而協調者每次呼叫的 context 只增不減（本場 13:00 平均 104,613，14:00 已經 206,719）。

- ⚠️ `--thread` 只把**你這條線**的 ERROR 與被擋頁算成你的紅燈；摘要表標成
  **「非本線」**的那些 ⛔ **不要動手修**，那是別條線的（連被別條線的頁擋住 render
  也一樣）→ 寫進待裁決清單回報協調者。
- ⚠️ `verify.py` 要有日期目錄最上層的 `deck.json` 才跑得動。**它在你被派之前就該在了**
  （關卡② 通過後由 `build_deck.py --skeleton` 寫的骨架）—— 所以⛔ **沒有「這一步跑不了」這個出口**：
  自驗是交件條件，不是選配。
  真的不在 → `BLOCKED` 請協調者補骨架，⛔ 不要自己造一份，也不要在 `DONE` 裡
  註明「未自驗」交差（N61：那個例外讓自驗只對返工輪有效，而要消滅的正是第一輪）。
- ⚠️ 中文版（摘要表的 `strings`／`render_zh`／`shoot_zh` 三列）在 `--thread` 模式下一律 **SKIP**：
  全場的中文版由協調者的完整 `verify.py` 跑。⛔ 那**不是**你不用交譯文 —— 你交的是這條線的
  `strings.<線>.zh.json` 片段（§6），merge 會併。你要的綠燈是 `check`／`render_en`／`shoot_en` 三列
  （N98：舊版沒有這個豁免，`strings` 恆紅 → 交件條件恆不可能達成）。
- ⚠️ 你是**第一個**交件的 builder 時，`deck.json` 併進去的只有你這條線 ——
  別條線的頁還不存在，於是「缺全場 outline」「別條線的 user_point 沒有頁」這類
  **全域**的錯一定會亮。摘要表把它們標成**非本線**、不算你的紅燈，⛔ 不要去補。

## Final response

- `DONE`：附四份輸出路徑（含 `strings.<線>.zh.json` 的句數與未翻數）、頁數、用了哪些構圖、哪幾張是手寫 SVG（不必附理由）、
  哪幾張標了 `off_vocabulary`（那幾張要進 `BACKLOG.md`），
  ⭐ 再附兩樣：① `verify.py` **摘要表的原文**（⛔ 不要改寫成「都過了」——
  數字與頁號是協調者的證據）；② 一份**待裁決清單**（`open_questions`，
  含非本線的紅燈），⭐ **一次列完**，⛔ 不要一個一個問 ——
  協調者會一次答完再退回（`delegation.md` ④）。
  ⭐ 還要附 ③ **每張主圖的圖表誠實性 6 問答案**（§5b，逐張逐問一句）——
  `layout_reviewer` 拿它覆核，⛔ 缺哪一張就是那一張的 BLOCKING。
- `BLOCKED`：附阻塞原因與證據位置。
