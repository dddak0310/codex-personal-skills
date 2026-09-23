# deck.json 欄位定義

`deck.json` 是週報投影片的**唯一事實來源**。HTML、PNG、pptx 都是它的產物，
改內容一律改這份再重跑，不要手改下游。

```jsonc
{
  "meta": {
    "week":  "2024-03-08",                 // 週報日期（也是 pptx 檔名）
    "range": ["2024-03-04", "2024-03-07"], // 涵蓋的日誌區間
                                           // ★ 下一份週報的起日就是從這裡 +1 天推出來的
                                           //   （scripts/_range.py --since-last-deck）。
                                           //   寫錯會讓下一週漏掉或重複，比看起來重要。
    "range_note": "若刻意跳過某幾天（已口頭報過…），理由寫在這裡",
    "title": "研究進度週報 2024-03-08"
  },

  // 週層級的 PMRC。四欄都必填（check_deck.py 會擋）。
  // ⚠️ 這是**給模型用的規劃欄位，不會變成投影片**。它逼你先想清楚這週的問題與結論
  // 再開始排頁；但「本週的問題與結論」不該做成一頁——那是講者的備忘，不是聽眾要看的。
  "arc": {
    "problem":    "這週要解決的問題是什麼",
    "motivation": "為什麼非解不可（不解會怎樣）",
    "results":    "做出了什麼",
    "conclusion": "所以呢／下一步"
  },

  // 選材與敘事的決策留檔。判準見 editorial_policy.md。
  // check_deck.py 會擋：narrative／mode 必填，且日誌裡的每一項
  // 不是出現在某張 slide 的 source，就是出現在 dropped（含去處與理由）。
  "plan": {
    // ★ Step 2 的提問紀錄。至少 3 題，a 要填**使用者的原話**。
    // check_deck.py 會擋——這是唯一結構上跳不掉的關卡。
    "answers": [
      { "q": "這週的主角是哪一件事？", "a": "〈使用者的原話〉" }
    ],
    // ★ 關卡② 的逐項確認表。**必填**（check_deck.py 會擋），一條主線一列。
    //   ⚠️ 以前它的 schema **只寫在 `check_deck.py` 原始碼裡**，本區塊完全沒有
    //   這個欄位 —— 寫的人只能去讀 checker 才寫得出來（FINDINGS N21）。
    //   來源：`_work/3_layer2/layer2.<線id>.json`，Step 4 由協調者彙整過來。
    "slide_plan": [
      { "point": "這條線要講什麼（一句）",
        "pages": 3,                       // 這條線的**主線內容頁數**（不含 outline／backup）
        "body":  "diagram | example | table | stats | flow | cols | points | pipeline" }
        // ⛔ 合法值的唯一定義是 `check_deck.SLIDE_PLAN_BODIES`（`check_deck.py --limits` 會印）
    ],
    // ★ 使用者在關卡② 拍板後才設 true。⚠️ 逐線的權威欄位是
    //   `layer2.<線id>.json` 頂層的同名欄位（`slide_builder` 讀那個，見 N19）；
    //   這裡是 Step 4 彙整時抄過來的全域旗標。
    "slide_plan_confirmed": true,
    "narrative": "本週敘事一句話 —— ★ 由**使用者**寫，或由他的 answers 組出並經他確認",
    "narrative_source": "這句是怎麼來的（使用者自己寫／由第 1、3 題的答案組出並確認）",
    "narrative_candidates": ["每日 headline 逐條列出，供使用者改寫"],
    "mode": "single | multi",
    "terms": {
      "core_metric":   "核心指標叫什麼、公式是什麼（定了凍結）",
      // ⛔ `sample_labels` **已刪除**（N78）：沒有生產者、沒有檢查讀它，
      //    而「同一件事只准用一個名詞」真正有機制執行的是下面的 `objects`。
      // ⛔ `banned` **已刪除**（N74／N78，批次 5f）：`grep banned scripts/` 零命中 ——
      //    **沒有人寫它，也沒有人讀它**，而同一個 terms 區塊的姊妹欄位
      //    （`objects`／`core_metric`）都有檢查在用。留著一個空欄位的代價是
      //    「禁用語看起來有人管」，於是沒有人再去補真正的防線。
      //    ⭐ 真正在執行「同一件事只准用一個名詞」的是下面的 `objects`（check_deck.py 會擋）。
      // ★ I/O 物品的登記處。slide 的 input／output 只能用這裡出現過的名字，
      //   check_deck.py 會擋。這是「同一件事只准用一個名詞」第一次有機制執行——
      //   從前它只是 presentation_rules 裡的一條原則。
      "objects": ["候選清單", "特徵表", "去噪器", "測試集"]   // 具名產物，換成你這場的
    },
    // ⭐ 物品名的中譯（PR 2）：關卡② 跟 `terms.objects` 一起凍結（planner 提名 `terms_proposed_zh`，
    //   使用者在 gate2 確認），layer3 各 builder 照表翻；`check_deck.check_terms_zh` 對帳。
    //   ⛔ 沒有這張表就會有 N31：同一個東西在上百句譯文裡兩個譯名。
    "terms_zh": {"候選清單": "候選清單", "feature table": "特徵表"},
    "rebuttals": [
      { "claim": "主線的主張", "rebuttal": "教授最可能的反駁（用他的口吻）",
        "answer": "怎麼擋。擋不住就回頭改主張" }
    ],
    // ⛔ 這裡原本有 `plan.buildup`（`{concept, serves, pages}`）——**已刪除**（N78）。
    //    它從來沒有生產者：沒有任何角色被要求填，也沒有任何檢查讀它。
    //    ⚠️ 而且它跟真正在用的兩樣東西**撞名**，讓人以為三者是一套：
    //      · `slide_plan[].slot: "buildup"`（check_gate.py 的 EXEMPT 在用）
    //      · `layer2.<線id>.json` 的 `buildup_note`（planner 的交件欄位）
    //    鋪陳頁的登記處是上面那兩個，⛔ 不要再加回一個平行的清單。
    "dropped": [
      // `where` 三選一。⭐ **三者對頁面的意思是定死的**（G5：以前完全沒規定，
      //   於是「降 backup」既可以是不做頁、也可以是做兩頁，兩種都不違規）：
      //   `不講` → 0 頁　　`口頭` → 0 頁（寫進相關那頁的 `notes`）
      //   `backup` → **一張 `thread-intro` 分隔頁 ＋ 每項最多一頁**，
      //              且 `backup: true` 的頁**不計入頁數預算**（見「頁數預算」）。
      //   ⛔ `where: backup` 卻一頁都不做 → 那一項要改成 `口頭` 或 `不講`，
      //      不要讓「backup」變成第二個「不講」。
      { "source": "2024-03-04#2", "where": "不講 | 口頭 | backup",
        "why": "理由（覆寫預設時尤其要寫）" }
    ],
    // 使用者原話被英譯過一手的句子，登記在這裡讓中文版還原原話（見「語言」節）
    "quotes": [ { "en": "…", "zh": "他真正說的那一句", "source": "2026-08-30#2" } ],
    "feedback": [
      { "was": "我原本判什麼", "now": "使用者改成什麼",
        "why": "他的理由", "criterion_wrong": true }
    ],

    // ⭐ layer3 版面審查的紀錄。**寫的人是 `layout_reviewer` 自己**
    //   （`subagent-layout-reviewer.md` Required outputs 第 2 項）——
    //   ⛔ 不是協調者代填（`delegation.md`：協調者不得自行補寫角色遺漏的內容）。
    //
    //   ⚠️ **為什麼這一欄要有 schema**：它以前只活在 `check_deck.py` 的一條 WARN
    //   訊息裡 —— **只有消費者、沒有生產者、也沒有 schema**，於是那條 WARN
    //   從第一次實跑到現在**沒有任何一場回填過**，
    //   而下一場開 session 的人會以為從來沒 review 過。
    //   ⛔ 這跟 N78 砍掉的 `plan.buildup` 是同一個病的兩面
    //   （那條沒人讀 → 刪掉；這條有人讀 → 補生產者）。
    //   缺這一欄，多線 deck 現在是 **ERROR**（`check_deck.py` 檢查項 0e）。
    "layout_reviewed": {
      "verdict": "PASS | FAIL",          // 逐字對上 layout_review.md 的抬頭
      "at": "2026-09-04",                // 審查當下的日期
      "blocking": 4,                     // 對上 layout_review.md 的 [BLOCKING] 條數
      // ⭐ **NIT 也要有去處** —— 現況是 BLOCKING 有人管、NIT 從來沒有。
      //   ⛔ 條數必須等於 `layout_review.md` 裡 `[NIT]` 的條數：少一條 ERROR，
      //      ⛔ 不准只挑好答的那幾條寫。
      //   ⚠️ **這裡不是 `plan.dropped`**：那一欄是**選材**的對帳（沒進主線的素材
      //      ＋去處＋理由），`where` 對頁數的意思是定死的，而且它的去處
      //      **由使用者決定、不得由 agent 代填**（thread-finder §5a）。
      //      NIT 的去處本來就該由 reviewer／builder 填 ——
      //      ⛔ 借那一欄會讓兩條規則當場互相否定。
      "nits": [
        { "finding": "<逐字抄該條 NIT 的抬頭>",
          "status": "fixed | wont_fix | open",
          // `fixed` 必填：**可驗的東西**（檔名＋字串／class／數字）。
          // ⛔「已修正」「已處理」不算證據。
          "evidence": "figures/B3_dispatch.svg 已無 box-bad（10 個框全是 box/box-c*）",
          // `wont_fix` 必填。⚠️ **每一則會被印成一條具名 WARN** ——
          // 比照 `role_exempt`：⛔ 不修不是修好了，它只是把判斷寫在看得見的地方。
          // ⭐ 所以「NIT 全部寫進去處」會讓 WARN 數**變大**，⛔ 不會讓它消失。
          "why": "後出的規則（§1d-0 第三層）否定了原建議：<date> 是契約樣板，上版面是 BLOCKING",
          // `open` 必填：**誰接手**。⛔ 不寫 owner = ERROR ——
          // 那正是這一整條在治的病（規則寫了、執行規則的人沒被指定）。
          "owner": "shoot.py" }
      ]
      // ⛔ 刻意不跑 layout_reviewer：整個欄位寫成 {"skipped": "理由"}。
      //    ⚠️ 這是**具名**的逃生口（理由會被印出來），⛔ 不是「留白就算了」。
      //    舊的多線 deck 也用這一行補。
      //
      // ⚠️ **已知缺口，⛔ 本批刻意沒做**：這份紀錄寫在 reviewer 那一輪，
      //    而圖之後還會被退回 builder 重畫 → 記錄會過期。`at` 是日後接
      //    新鮮度檢查（`check_spec_fresh` 那一族）的掛點，⛔ 現在還沒有人在驗它。
    }
  },

  "threads": [{
    "id": "可信度",
    "title": "我們的效能數字可不可信",
    "summary": "多線週必填：這條線做了什麼、怎麼做（一句）",
    "page_order_note": "頁序與 user_points 順序不同時，寫理由（否則 check_deck 發 WARN）",
    "user_points": [
      "⭐ 關卡① 使用者親口列出「這條線只講 3~4 個重點是哪幾個」，逐字抄，順序就是頁序",
      "⛔ 不得由 agent 代擬；空的話 slide_planner 必須回報 BLOCKED"
    ]
  }],

  "slides": [ /* 見下 */ ]
}
```

## slide 的共同欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `id` | ✓ | `S1`、`B1`…。不必連號 |
| `type` | ✓ | 版型，見 `slide_types.md` |
| `thread` | 內容頁 | 屬於哪條線，顯示在頁首左上 |
| `point` | 內容頁 | **這頁唯一的重點**。兩個重點就拆頁。**字數上限見 `check_deck.py` 的 `LIMITS["point"]`**，⛔ 這裡不再寫死數值（見下方⚠️） |
| `from` | 內容頁 | **上一頁的結論**。必須逐字等於前一頁的 `to`（換線時重置） |
| `to` | 內容頁 | **這頁講完聽眾帶走的那句結論**。⚠️ 是**結論**，⛔ 不是拋出一個問題 |
| `source` | 內容頁 | `["2024-03-07#1"]`。格式 `YYYY-MM-DD#N`／`#R<N>`（記錄層）／`#issueN`／`#headline` |
| `user_point` | 內容頁 | ⭐ 這頁對應到 `threads[].user_points` 的哪一個（逐字）。**對不上就不該有這一頁** |
| `input` | | 這頁的**輸入物品**。同主線內必須逐字等於前一頁的 `output`；名字要在 `plan.terms.objects` 裡 |
| `output` | | 這頁的**產出物品**。鋪陳頁與結論頁沒有物品，留空即可，改用 `to` 承接 |
| `depth` | 內容頁 | `overview`／`mechanism`／`detail`。**`method` 格預設 `mechanism`**，見下 |
| `example` | `mechanism` 頁 | `{kind,before,operation,after,sources,disclosure?}`。先以案例跑規則的規劃證據；`constructed` 必填 `disclosure`。若不適用，填具體 `example_exception` |
| `composition` | 圖解頁 | 構圖決策，見 `composition-vocabulary.md`。**兩層合填**：<br>layer2 給 `{relation, comp, gate, spec_hint, off_vocabulary}`；<br>layer3 補 `{spec, handwritten}`。<br>`off_vocabulary: true` 要有 `why_off_vocabulary`（新構圖候選，進 BACKLOG）；<br>`handwritten: true` **不需要理由**（第一批只有 2 個 renderer，手寫是常態） |
| `slot` | 內容頁 | `buildup`／`problem`／`method`／`result`／`intro`。**只有 `method` 預設有頁**，其餘各格用了要寫 `slot_reason`。<br>⭐ **豁免的語意只有一個**（N99）：非 `method` 的格**不必對應一個 `user_point`**（它是支撐結構，不是使用者指名要講的重點）。⛔ 它**不是**「不必交 example」—— 那是後果：這些頁的 `depth` 預設就不是 `mechanism`。<br>⛔ 集合的唯一定義在 `check_deck.py` 的 `SLOT_EXEMPT`，`check_gate.py` 用 import 拿，**這裡不再另列一份** |
| `title` | | 頁面標題。上限見 `LIMITS["title"]` |
| `sub` | | 標題下的副題。上限見 `LIMITS["sub"]` |
| `body` | ✓ | 依 `type` 而定，見 `slide_types.md` |
| ~~`takeaway`~~ | | ⛔ **已移除**（N67）。渲染、CSS、字數上限、高度預算**都已拆掉** ——不是「填了不會顯示」，是填了 `check_takeaway()` 直接擋。結論寫進 `notes` 的「【口頭結論】」 |
| `notes` | | 講稿／執行細節 → pptx 備忘稿，**不上投影片** |
| `backup` | | `true` = 備用頁 |
| `extra_sources` | | 這頁的數字除了日誌，還來自哪些檔（`docs/…`、`…meta.json`）。日誌是壓縮的，機制與清單常常只在原檔裡——列在這裡，數字溯源就會一併比對那些檔 |
| `why_text` | 文字版型 | 用 `points`／`cols`／`issues` 時必填：**為什麼這件事沒有圖或表可放**。沒填會被擋 |
| `tone` | | `dark`／`soft`，覆蓋版型的預設底色 |
| `backup` | | `true` = 備用頁。豁免承接／拋出，仍需 `point`、`source`、數字溯源 |

> ⚠️ **字數上限一律指路 `check_deck.py` 的 `LIMITS`，⛔ 不在文件裡再寫一次數字。**
> 舊版這張表寫 `point ≤ 46 字`，而 `LIMITS["point"]` 是 **90** —— 兩處**已經分岔到 2 倍**，
> 而文件那個 46 **從來沒有被執行過**（`title`／`sub` 同病：文件 34／60，程式 80／96）。
> 實測後果：上一次盲測 9 個頁面的 `point` 是 84~161 字、全部超過 90，
> 但 layer2 逐頁表與關卡② 都不驗字數 → **一路拖到 `check_deck.py` 才爆**（7 個 ERROR），
> 兩個 builder 各多返工一輪（FINDINGS F17／N18／N20）。
> 現在 `check_gate.py` 直接 `from check_deck import LIMITS`，關卡② 就擋得住了 ——
> **一份定義、兩處執行**。
> ⭐ **上限 90／80／96 由使用者於 2026-09-04 裁決維持，文件端不再寫死數值。**

## `body` 的兩個新結構

### `type: "example"` —— 全幅案例機制頁

```json
"body": { "src": "figures/S3_example.svg" }
```

⭐ **只有 `src`（或內嵌 `svg`）—— 主圖佔滿整個版面，沒有側欄。**
舊版右側有 30% 的 `aside:{title,rule,boundary}` 黃底欄，使用者 2026-09-04 裁決拿掉：
「規則那格根本不需要，只需要左邊那一塊內容，放大佔據整個版面就可以了。」
⛔ 不要再產 `body.aside`（附帶效果：FINDINGS N29 那個 annot 額度被版型自己吃滿的矛盾從根上消失）。

⚠️ **拿掉的是欄位，不是那兩則內容。** `depth: mechanism` 明訂「這頁必須看得到一條具體規則」
（`check_deck.py` 的深度檢查），所以原本要寫進 `aside.rule`／`aside.boundary` 的規則與邊界
**必須畫進主圖裡**（門檻標在操作那一格上、邊界畫成不適用的那一支）。
⛔ 不得刪除，⛔ 不得只塞進 `notes` —— `notes` 不上投影片。

⚠️ 與上表 `example`（`plan` 側的規劃欄位）不是同一個東西：那是規劃紀錄，**保留**。

當 `plan.example_first: true` 時，所有 `depth: mechanism` 頁必須使用此版型，除非有具體
`example_exception`。SVG 畫案例的 before／operation／after。

### `type: "pipeline"` —— 單向流程

```jsonc
"body": {
  "lanes": [{                       // ≤ 3 條（建議 2）
    "label": "Build path",          // lane 的名字         → 用途 label
    "note":  "offline",             // 名字的補語，不得成句 → label
    "tone":  "good",                // good / bad / hl，可省
    "nodes": [{                     // ≤ 5 個
      "n":     "1",                 // 圓形 badge 上的步驟編號
      "t":     "Dedup BAM",         // 節點的名字（必填）   → label
      "arrow": "sites",             // **流進**這個節點的東西的名字 → label
                                    //   ⛔ 第一個節點不得有 arrow（它前面沒有箭頭）
      "d":     "Global QNAME dedup",// 一句短標籤，不得成句 → label
      "items": ["處理組原始檔", "對照組原始檔"],        // ≤ 4 項 → label
      "codes": [{"t": "C5 kept", "tone": "good"}], // ≤ 4 個色塊；字串亦可 → label
      "v":     "0.889",             // 一個大數字           → value
      "chip":  "dedup.bam",         // 這一步的產出物名，釘在節點底部 → label
      "tone":  "hl"                 // good / bad / hl，可省
    }]
  }]
}
```

**用途歸類**：這個版型的文字**全部是 `label`，只有 `v` 是 `value`** ——
理由（語意／額度／顏色三條）寫在 `check_deck.py` 的 `collect_json_purpose()`。
代價是它們一律套「不得成句」，**這正是要的**：節點框裡不准塞散文。
容量上限的**唯一定義**是 `check_deck.py` 的 `LIMITS`（會擋的是它）；
`slide_types.md` 寫的是同一組數字的副本＋依據（N63）。

### 表格儲存格的比例 bar

`rows` 的儲存格除了字串，也可以是物件：

```jsonc
{"caption": "…", "columns": [...],
 "colw": ["34%", "33%", "33%"],     // ⚠️ 有 bar 就**必須**給，否則 check_deck.py 擋
 "rowclass": ["", "drop", "hl"],    // 與 rows 等長；drop=移除（紅底刪除線）、hl=重點（金底）
 "rows": [["C5 CoLoRSdb",
           {"v": "35/66", "pct": 53, "tone": "good"},   // v → 用途 value；pct 是幾何不是文字
           {"v": "31/66", "pct": 47}]]}
```

`pct` 不印在投影片上、不進數字溯源；但 `v` 形如 `a/b` 時會被回頭驗
`pct ≈ 100a/b`（差 >1 個百分點擋下）。為什麼一定要 `colw`、為什麼要驗 `pct`
→ `slide_types.md`「表格內的比例 bar」。

## 語言

`deck.json` 與 `figures/*.svg` **一律寫英文**（實驗室有外籍生，pptx 用英文版）。
`point`／`from`／`to`／`notes`／`why_text` 是我們自己的敘事與講稿，可用中文。

### ⭐ 例外一：**使用者原話豁免英文規則**（N24／N33）

**逐字抄使用者原話的欄位不受「一律英文」約束**，中文原話原樣保留：

| 哪裡 | 為什麼 |
|---|---|
| `threads[].user_points` | 關卡① 的原話，逐字，⛔ 不得由 agent 代擬 |
| 各線 outline（`agenda`）的 `items[].t` | 它**就是**把 `user_points` 列出來（見 `SKILL.md`「outline 頁」） |
| `plan.answers[].a` | 使用者的原話 |

> **為什麼要寫成例外**：舊版「`deck.json` 一律英文」與「outline 逐字抄
> `user_points`（中文原話）」**直接衝突，而且每一份中文日誌都必然發生**
> （FINDINGS N24；與 F10「中文數字」是同一型，F10 只修了數字那一半）。
> 兩條規則都對，缺的是這張豁免表。

**英文版怎麼處理**：這幾欄的中文原話**照樣進 `deck.json`**，由
`strings.zh.json` 的**反向條目**供英文版使用 —— 即 `--dump-strings` 收到的
是中文原句，`en` 版落回原文。⚠️ 需要英文 outline 時，把英譯寫進
`plan.quotes`（見下），⛔ **不要回頭改 `user_points` 本身**。

### ⭐ 例外二：`plan.quotes` —— 原話在翻譯路徑上的保護（N33）

凡是版面上的英文句子**其實是使用者中文原話的英譯**，一律登記：

```jsonc
"quotes": [
  { "en": "Just show the file tree",
    "zh": "不如把檔案結構直接顯示",       // ⭐ 他真正說的那一句，逐字
    "source": "2026-08-30#2" }
]
```

**規則**：`strings.zh.json` 裡凡是 key 命中 `quotes[].en` 的，值**必須逐字填
`quotes[].zh`**，⛔ **不得回譯**。

> **為什麼**：`delegation.md` 有「原話的位階高於解讀」，但在
> `deck.json 一律英文` → `strings.zh.json` 這條路徑上**沒有任何機制保護原話**：
> 上一次盲測的 `"Just show the file tree"` 已經是中文原話被英譯過一手的產物，
> 回譯出來的中文**不保證等於他說的那句**（FINDINGS N33）。
> 登記一次，中文版就會**還原**成原話而不是再翻一次。

中文版由**同目錄的 `strings.zh.json`** 產生，格式 `{英文原句: 中文譯文}`：

```bash
render_deck.py deck.json --dump-strings zh   # 收集待翻字串（值留空）
render_deck.py deck.json --lang zh           # → deck.zh.html
```

值可以是譯文、`"="`（刻意不翻：樣本名、工具名、純數字）、或 `""`（未翻，落回原文）。
替換範圍含**內嵌 SVG 的文字節點**。⛔ 不要產第二份 `deck.json`——結構共用一份，
否則兩版的數字會分岔。

## 結構頁（豁免 point / from / to / source）

### `body` 的形狀（⭐ 唯一定義在這裡）

| type | `body` 必填 | 選填 |
|---|---|---|
| `cover` | `kicker`、`title`、`range` | — |
| `thread-intro` | `label`、`title` | `sub` |
| `agenda` | `items[]`，且**每一項的 `t`** | 每項的 `n`、`d` |

**必填的判準**：`render_deck.py` 的 builder（`b_cover`／`b_agenda`／`b_thread_intro`）
**對它沒有 `if` 保護**的欄位就是必填 —— 缺了不是版面難看，是**當場崩**。

> ⚠️ 這三個形狀以前**只寫在 `render_deck.py` 與 `check_deck.py` 兩支 .py 裡**，
> 本檔與 `slide_types.md` 都沒有。實測後果：一張沒有 `body` 的 `thread-intro`
> **通過了 `check_deck.py` 的全部檢查**，卻讓 render 直接崩：
> `AttributeError: 'NoneType' object has no attribute 'replace'`
> （`render_deck.py:80 b_thread_intro → :52 inl → html.escape`）——
> 錯誤訊息完全看不出是哪一頁哪一欄（FINDINGS N30）。
> 現在 `check_deck.py` 的 `check_struct_body()` 會擋，本節是它的規格側。

`cover`、`agenda`、`thread-intro` 三種是結構頁，不進承接—拋出的鏈。
（`cover` 預設不使用 —— 簡報從 `agenda` 這張 outline 直接開始。）
`thread-intro` 同時擔任**轉場**：它的 `to` 會被下一頁承接。

## 數字的規矩

`body`、`title`、`sub` 裡的每個數字，**必須逐字出現在 `source` 指到那幾天的日誌 JSON**。
不得計算、不得換算、不得四捨五入。需要哪張表就回去讀來源 JSON 複製，不要憑記憶重打。

- 看起來像資料的數字（含小數點／百分比／三位數以上）對不上 → **ERROR，擋下**
- 小整數（列舉、頁碼之類）對不上 → WARN

外部 `.svg` 圖檔的 `<text>` / `<tspan>` 文字內容**也會被檢查**（座標與尺寸不算）——圖不是免檢區。

`notes`、`from`、`to`、`point`、`why_text` 不受此檢查（它們不上投影片，或是我們自己的敘事語言）。


## `depth`：這頁要講多深

| 值 | 意思 | 驗收 |
|---|---|---|
| `overview` | 講「有這件事」 | 一句話即可 |
| `mechanism` | 講**規則本身**：判準、公式、門檻、分數怎麼算 | ① 這頁必須看得到**一條具體規則**（算式／門檻／判準表）② 過「**聽眾照這頁講的，能不能說出這一步在做什麼判斷、依據是什麼？**」⚠️ ⛔ 不是「能不能自己重做一次」——那會把深度推到實作規格，上限見 `subagent-slide-planner.md §3a`（唯一定義在那裡） |
| `detail` | 講到參數與實作選擇 | 通常只在 backup |

`method` 格的頁**預設 `mechanism`**；要降成 `overview` 必須寫理由。

⛔ 只寫「我們整理了／篩選了／驗證了」= 空洞。空洞的頁面共同特徵就是
**只有動詞沒有規則**——`check_deck.py` 用「有沒有表格 ∨ 文字裡有沒有比較／門檻／算式符號」
當機械代理擋它；那只擋得到一半，另一半由 `layout_reviewer` 用上面那句提問審。

## 頁數預算

主線 **≤15 頁**、單一主線 **≤7 頁**（`backup` 不計）。`check_deck.py` 會擋。

⛔ **鋪陳頁與 `depth: mechanism` 的頁不得為了湊頁數被砍。**
要砍先砍 backup 與「決策的依據」類的頁（抽掉它結論不會變的那些）。

> 這條與 `editorial_policy §6`「頁數是加總出來的結果，不是配額」看似衝突，其實不同情境：
> 那條防的是**做完才砍**（貴）；這條擋在關卡②，使用者看到頁數時改一列表格的成本是零。
