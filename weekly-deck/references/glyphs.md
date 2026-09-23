# glyph 字彙：盒子裡的小圖（由數字畫，不由人排座標）

<!-- @for: builder -->

> **什麼時候讀這一份**：你在寫構圖 spec（`_work/3b_specs/<頁id>.json`），而這一頁的框裡有
> **數量、比例、座標、取捨**要講。⭐ 一個框裡只有字（`pairs`／`lines`）就是「表格塞進框裡」——
> 2026-09-06 那份 deck 九頁全是這樣，而同一批事實 APG 的手繪 SVG 看起來「有圖」。
> 差別只在每一步有沒有**那件東西本身的一張小圖**。這一份給你那些小圖的名字與參數。

## 一、規矩（先讀）

1. **glyph 是 `blocks[]` 的第四種內容**，與 `lines`／`pairs`／`numbered` 擇一：
   ```jsonc
   {"head": "genomes", "glyph": "dots", "n": 469, "of": 1286, "tone": "good",
    "label": "on-target", "value": 469}
   ```
   `head`（小標）、`label`（左下的名字）、`value`（右下的數字）三個都可選；`h` 可覆寫高度（48～320，吸 8pt）。
2. **數字進 glyph，不進 `pairs`**。「被 4 項提到」「120,830 → 18,500」「1,566 / 9,587」這種東西
   一律有 glyph 可畫（`bars`／`hero`／`segbar`／`dots`）；寫成 `["masked bp", "166,526"]` 的定義列
   等於放棄視覺。⛔ 同一個數字不要 glyph 與 pairs 各寫一次。
3. **顏色只有三種角色**（presentation_rules §5）：分類 `tone: good／bad／null／ctl`、
   區別（並列的群自動拿 `mk-c1`~`c12`，同名同色，⛔ 不必填）、淡 `dim`（被捨棄／不算）。
   ⛔ 沒有強調色：要說「看這個數字」用 `hero`（放大），不是塗金。
4. **每個 glyph 最多一列說明**（左 `label`、右 `value`），都是 22px 的正常字。⛔ 不在圖裡塞旁白
   （旁白是 `annot`，一頁 ≤2，寫在 deck.json 的 `sub`／`caption`）。
5. **高度只由參數決定**（表裡有寫），與盒寬無關 —— 所以你在寫 spec 時就算得出這一格會多高，
   照 diagram-craft §6 的預算加總；超了 renderer 會出聲，正解是減項或拆頁，⛔ 不是縮字。
6. **基因組座標一律 bp**：帶 `total`；放進 `genome_tracks` 時 `total` 由上層統一給，⛔ 不要自己填。
7. 一頁 **一個 `hero`** 就夠。兩個 hero 就沒有 hero。

## 二、目錄

### 計數／比例

| glyph | 畫什麼 | 參數（粗體必填） | 高 |
|---|---|---|---|
| `dots` | 點陣：一點＝`unit` 個東西，自動選 unit（1/2/5/10…）讓點放得下 | **`n`** 或 **`groups[{n,tone,label}]`**；`of`（分母，補成淡點）；`unit`；`tone` | 64 (+32 有說明列) |
| `tiles` | 一排 tile（k-mer、read、探針、樣本） | **`n`**（≤40）；`marks{索引:tone}` 或 `tones[]`；`gradient:true` 不透明度漸增 | 40 (+32) |
| `segbar` | 分段橫條，多列時列間畫向下箭頭（before → after） | **`rows[{segs[{len,tone}], label, value}]`**；`total`；`tone:"gap"` 空白、`"dim"` 捨棄 | 每列 32 (+32 有 label／value；列間 +24) |
| `bars` | 橫向長條，長 ∝ 值，值印條尾（`compare` 關係的小圖版） | **`items[{k,v,tone,text}]`**；`max`；`thr{v,label}` 虛線門檻 | 32 × 項數 (+32 有 thr label) |
| `hero` | 這一頁最重要的那個數字，44px | **`v`**；`label`（同列接在後）；`sub`（下一列） | 64 (+32 有 sub) |
| `hist` | 直方圖，門檻右邊可換色 | **`bins[]`**；`thr`（第幾個 bin 之前，或 0～1 比例）；`above` tone；`x:[左標,右標]` | 72 (+32) |
| `heat` | 熱度條，逐格 0～1 以不透明度表示 | **`cells[]`**；`x:[左標,右標]`；`tone` | 40 (+32) |
| `venn` | 兩個集合的重疊（兩圓等大，只講有沒有重疊） | **`a`、`b`、`both`**；`la`、`lb` 兩邊的名字 | 128 (+32 有名字) |

### 流程／判斷

| glyph | 畫什麼 | 參數 | 高 |
|---|---|---|---|
| `funnel` | 小漏斗：由多到少、置中的橫條 | **`stages[{n,label}]`**（2～5 段） | 32 × 段數 |
| `tree` | 合併樹：葉 → 中間 → 根，每層印個數 | **`leaves`**（≤12）；`mid`；`root` 根的名字 | 112 (+32) |
| `checklist` | 取捨清單：✓ 留、✕ 捨（捨的畫刪除線） | **`items[{t,ok}]`** | 32 × 項數 |
| `gate` | 人工確認閘：紅虛線框 ＋ 人形（結構標記，不是強調） | `label`；`value` | 64 |
| `pills` | 小流程：藥丸串＋箭頭 | **`items[]`**；`flow:"row"`（預設；放不下會登記紅帶）或 `"col"` | 48；col 時 40 × 項數 + 8 |

### NGS（座標 bp；吃 `total`）

| glyph | 畫什麼 | 參數 | 高 |
|---|---|---|---|
| `feat` | 參考軸上的區段（signature、基因、mask 窗），放得下就寫名字 | **`features[{s,e,label,tone}]`**；`total`；`axis:false` 不印兩端座標 | 64 (+32) |
| `reads` | read 堆疊：有方向的箭形、mismatch 紅刻、配對細線相連；列由程式排 | **`reads[{s,e,dir,mm[],mate[s,e],tone}]`**；`total` | 24 + 16 × 列數 (+32) |
| `probes` | 探針鋪瓦（兩列交錯），誤抓的探針紅並虛線落到 off-target 軌 | **`total`、`probe`、`stride`**；`hits[]` 索引；`n` | 96 (+32) |
| `kmers` | k-mer 滑窗：一條序列 tile ＋ 底下幾個錯一格的窗 | **`n`、`k`**；`show`（幾個窗，≤6） | 40 + 16 × show + 8 (+32) |
| `lollipop` | 變異位點／斷點：一根桿一顆珠，`n` 寫在珠上 | **`marks[{pos,tone,n}]`**；`total` | 80 (+32) |
| `coverage` | 深度／GC／identity 沿座標的面積圖 ＋ 門檻虛線 | **`values[]`**；`thr`；`max` | 80 (+32) |
| `align` | 多序列對齊示意：`M` 同、`X` 錯配、`-` 缺口、`N` 未知（⛔ 不畫字母） | **`rows[{name,cells}]`** | 24 × 列數 + 8 |

> ⚠️ 要畫**鹼基字母**（哪一個位點是 A 還是 G）用領域構圖 `read_pileup`／`haplotype_split`，
> 那一族有自己的座標系。glyph 的 `align`／`reads` 只講形狀，不講字母。

## 三、兩個新構圖（整張圖就是 glyph）

### `bars` —— `compare` 關係（一個指標 × 多個對象）

```jsonc
{"comp": "bars", "title": "probes that also hit off-target genomes", "unit": "probes",
 "items": [{"k": "designed", "v": 9587, "tone": "ctl"},
           {"k": "clean", "v": 8021, "tone": "good"},
           {"k": "off-target hit", "v": 1566, "tone": "bad", "text": "1,566 · 16.3%"}],
 "max": 9587, "thr": {"v": 959, "label": "10% cap"}}
```
2～8 個對象；超過 8 個是表格。`text` 覆寫條尾印的字（想印「1,566 · 16.3%」就填這裡，`v` 仍是數字）。

### `genome_tracks` —— 領域構圖：一條參考軸、幾條共用座標的軌

```jsonc
{"comp": "genome_tracks", "budget": 680, "title": "sig-2 · 120 kb window", "length": 120000,
 "lanes": [
   {"type": "feat",     "label": "signatures", "features": [{"s": 4000, "e": 26000, "label": "sig-1"}]},
   {"type": "probes",   "label": "probes 120 bp", "probe": 6000, "stride": 3000, "hits": [3, 4], "value": "2 / 39 hit"},
   {"type": "coverage", "label": "depth", "thr": 30, "values": [12, 28, 41, 55, 62, 58, 47]},
   {"type": "reads",    "label": "reads", "reads": [{"s": 5000, "e": 19000, "mm": [11000]}]},
   {"type": "lollipop", "label": "variants", "marks": [{"pos": 11000, "tone": "bad", "n": 3}]},
   {"type": "segbar",   "label": "masked", "rows": [{"segs": [{"len": 40000, "tone": "good"}, {"len": 12000, "tone": "bad"}]}]}]}
```
軌只能是 `feat`／`reads`／`probes`／`lollipop`／`coverage`／`heat`／`segbar`（有座標的那幾個）；
`total` 由 `length` 統一給。這就是 genome browser 的排法，⛔ 不要拿它畫沒有座標的東西。

## 四、選哪一個（守門提問）

| 你要講的是… | 用 | ⛔ 不要 |
|---|---|---|
| 「有多少個」（基因組、樣本、session） | `dots`（兩群用 `groups`） | 一列 `pairs` |
| 「A 比 B 多多少」「改前→改後」 | `bars`；只有一個數字要記住 → `hero` | 兩個 `value` 並排同大小 |
| 「整體裡哪一段被拿掉／留下」 | `segbar`（多列＝多個狀態） | 文字「26.6%」 |
| 「多 → 少，每一跳的個數」 | `funnel`（小）／comp `funnel`（全頁） | `numbered` |
| 「哪些留、哪些濾掉」 | `checklist` | 兩個 `lines` 區塊 |
| 「這裡有人要點頭」 | `gate` | `tone:"bad"` 的框 |
| 「沿基因組座標發生什麼」 | comp `genome_tracks`，一軌一件事 | 幾個沒對齊的 glyph 疊在不同框 |
| 「這個量沿座標怎麼變」 | `coverage`（有門檻就填 `thr`） | 表格列出每個窗的值 |
| 「兩個集合重疊多少」 | `venn` | 三個數字排一列 |

守門提問（每一張 glyph 都要答得出來）：**這張小圖上有哪一個數字，是觀眾看形狀就能比字更快讀到的？**
答不出來 → 這裡不該有 glyph，一列 `pairs` 就好。

## 五、範例圖

```bash
python3 scripts/render_figure.py --demo /tmp/_demo
# glyphs_counts.svg · glyphs_flow.svg · glyphs_ngs.svg · bars.svg · genome_tracks.svg
```
每個 glyph 至少出現在其中一張。DEMO 的數字是虛構的 TB 專一性區域探勘情境，只為了看形狀。

## 六、為什麼不是手繪 SVG（2026-09-06 的對照）

APG `weekly-deck-builder` 的兩頁：一頁 3,600～4,100 個輸出 token、60～93 個形狀、字級 5～9px、
比例憑感覺（一處 mask 比例畫 23% 標 26.6%）、每改一次整頁重寫。同一批事實用 glyph 寫成 spec
約 200～400 token，比例由程式算、字級一律 22px、同一個 glyph 全 deck 一個長相、
`<text>` 走 `T()` 所以 zh 版照樣翻得到。⭐ 小圖的價值在「畫的是那件東西本身」，
⛔ 不在「由人一筆一筆畫」。
