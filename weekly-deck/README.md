# weekly-deck

一個 skill：把一週的**每日工作日誌**做成一份可以拿去報告的投影片（HTML → 截圖 → pptx）。
**[Claude Code](https://claude.com/claude-code) 與 [Codex](https://developers.openai.com/codex/) 都可以用**
（同一份檔案、同一個格式，只是安裝目錄不同 —— 見下方「安裝」）。

> 語言：本 skill 的指示與產出都是繁體中文（`deck.json` 內文寫英文，中文版由字串對照表產生）。

---

> ⚠️ **skill 目錄必須可寫** —— Python 匯入同目錄模組會產生 `__pycache__/`
> （已在 `.gitignore` 裡）。裝在唯讀位置會失敗。

## 它是 `daily-log` 的後處理

輸入不是研究現場，是**已經編輯過的每日日誌**：
[`daily-log`](../daily-log) 每天把 git、檔案變動、對話紀錄整理成
「問題→做法→結果→解讀」，寫進日誌 repo 的 `.data/<日期>.json`。
weekly-deck 只做兩件事：**跨日合併成敘事**，以及**排成投影片**。

```
daily-log ──> <日誌 repo>/.data/*.json ──> weekly-deck ──> <週報根>/<日期>/deck.{en,zh}.html
```

⛔ **兩個 skill 必須成對安裝。** 沒有 `daily-log` 就沒有輸入，
所以找不到它時 weekly-deck 會**直接報錯並告訴你怎麼設**，不會猜一個路徑跑下去
（猜出來的結果是一份空週報，而那不會報錯）。

---

## 安裝

兩個工具的 skill 格式**是同一個**：一個資料夾、進入點是 `SKILL.md`、
frontmatter 要 `name` 與 `description`。差別只有兩件事：

| | Claude Code | Codex |
|---|---|---|
| 全域安裝目錄 | `~/.claude/skills/<name>/` | `~/.codex/skills/<name>/`（＝ `$CODEX_HOME/skills/`） |
| 明確觸發 | `/weekly-deck` | `$weekly-deck` |

> ℹ️ Codex 另外吃一個**選填**的 `agents/openai.yaml`（顯示名稱、預設提示語）。
> 本 skill 已附一份；Claude Code 會忽略它。沒有它 skill 照樣能被觸發。
> ⛔ 不要把觸發條件寫進那個檔 —— 觸發一律以 `SKILL.md` 的 frontmatter 為準，寫兩份會分岔。

```bash
# 兩個 skill 放進同一個 skills 目錄（全域或某個專案的 .claude/skills/ 都可以）
git clone <daily-log repo>   ~/.claude/skills/daily-log
git clone <weekly-deck repo> ~/.claude/skills/weekly-deck

# 同時要給 Codex 用：symlink 過去就好，不要複製第二份（會分岔）
mkdir -p ~/.codex/skills
ln -sfn ~/.claude/skills/daily-log   ~/.codex/skills/daily-log
ln -sfn ~/.claude/skills/weekly-deck ~/.codex/skills/weekly-deck
# ✅ 實測（codex-cli 0.152.1）：symlink 可以，Codex 讀得到、也載得進來。

# daily-log 的設定（weekly-deck 靠它解析日誌 repo 與專案根）
mkdir -p ~/.config/daily-log
cp ~/.claude/skills/daily-log/config.example/* ~/.config/daily-log/
rm ~/.config/daily-log/README.md
$EDITOR ~/.config/daily-log/*

# weekly-deck 自己的設定（全部選填，慣例通常就對）
mkdir -p ~/.config/weekly-deck
cp ~/.claude/skills/weekly-deck/config.example/* ~/.config/weekly-deck/
rm ~/.config/weekly-deck/README.md
$EDITOR ~/.config/weekly-deck/*
```

需要 Python 3.8+、`git`、`bash`。截圖與 pptx 那兩步另外需要
Playwright（`shoot.py`）與 `python-pptx`（`to_pptx.py`）。

**裝完跑這個確認**（三個值都要是你自己的，而且真的存在）：

```bash
S=~/.claude/skills/weekly-deck/scripts     # 只用 Codex 的人：S=~/.codex/skills/weekly-deck/scripts
cd <你的專案>
for k in daily-log-dir log-repo project-root data-dir reports-root; do
  printf "%-14s %s\n" "$k" "$(python3 $S/paths.py $k 2>&1)"
done
```

對不上就照它印的錯誤訊息設定。

---

## 設定

四項，全部選填，放在 `~/.config/weekly-deck/`。詳見
[`config.example/`](config.example/)。解析順序與 `daily-log` 一致：
**環境變數 → `~/.config/weekly-deck/<檔名>` → 慣例**。

| 設定 | 環境變數 | 慣例（不設定時） | 不設定的後果 |
|---|---|---|---|
| `daily-log` | `WEEKLY_DECK_DAILY_LOG` | 同一個 skills 目錄下的 `daily-log/`，再退 `$CODEX_HOME/skills/daily-log`、`~/.claude/skills/daily-log`、`~/.codex/skills/daily-log` | 兩個 skill 沒放在一起就**報錯**（刻意） |
| `data` | `WEEKLY_DECK_DATA` | `<daily-log 的 repo>/.data` | 通常不必設 |
| `reports-root` | `WEEKLY_DECK_REPORTS` | `<日誌 repo>/weekly` | 通常不必設 |
| `transcript-dirs` | `WEEKLY_DECK_TRANSCRIPT_DIRS`（`:` 分隔） | 由專案路徑推導 session 目錄（Claude Code 與 Codex 兩種都回） | 只影響 `scripts/measure_effort.py` |
| —（只有環境變數） | `WEEKLY_DECK_CHROMIUM`（chromium 執行檔路徑） | Playwright 自己管理的 Chromium | 只影響 `scripts/shoot.py`；機器上已有 Chromium 但 Playwright 叫你 `playwright install` 時才要設 |

日誌 repo 與專案根**不是 weekly-deck 的設定項** —— 它們一律轉發給
`daily-log/scripts/paths.py`（`~/.config/daily-log/repo`、`project`）。
同一事實只有一份，不會分岔。

> ⚠️ **明確設定過的路徑若不存在，一律報錯，不退回預設。**
> 這比 `daily-log` 嚴格，理由是 weekly-deck 的失效形態是**無聲**的：
> `--since-last-deck` 的起日是從**上一份 deck** 的 `meta.range` 推來的，
> 週報根指錯了只會「找不到上一份」→ 區間推導默默失效 → 退回手填日期。
> 那正是這個 skill 剛修好的毛病，不能讓它從設定那邊繞回來。

---

## 換一台機器要做什麼

1. clone 兩個 skill 到同一個 skills 目錄（Claude Code `~/.claude/skills/`、
   Codex `~/.codex/skills/`；兩邊都要用就 clone 一份、另一邊 symlink）。
2. 設好 `~/.config/daily-log/repo`（日誌 repo 在哪）。
3. 其餘通常不必設 —— 跑一次上面那段確認指令，全部對得上就可以用。
4. `scripts/measure_effort.py` 要吃 session 目錄（Claude Code 與 Codex 皆可）；
   目錄名由專案路徑推導（`/` 與 `_` 都換成 `-`），換機器不必改。
5. **本機的參考素材不會跟著走**：`references/BACKLOG.md` 與
   `scripts/render_figure.py` 提到的口試簡報截圖是別人的實驗圖，
   不屬於這個 skill，公版沒有附。要做那幾條 backlog 的人自己備一份。

⛔ **不要在任何腳本裡寫死路徑。** 規則只寫一次，在 `scripts/paths.py`；
bash 腳本也走同一份（`python3 paths.py reports-root`），不要在 shell 裡再實作一遍。

---

## 用法

| 打什麼 | 做到哪裡 |
|---|---|
| `/weekly-deck layer1`（Codex：`$weekly-deck layer1`） | Step 1 抽素材 → 找主線 → **關卡①**（停下來問你） |
| `/weekly-deck layer2` | 逐頁規劃 → **關卡②** → `deck.json` 骨架 |
| `/weekly-deck layer3` | 產頁 → 渲染 → 機械檢查 → **關卡③** →（選用）截圖、pptx |
| `/weekly-deck all` | 三層連跑在同一個 session（⚠️ 貴 3~4 倍，只給很短的週） |
| `/weekly-deck plan` | ＝ layer1 ＋ layer2（舊入口） |

⭐ **一層一個 session** 是 2026-09-06 起的預設：帳單是「每一回合當下的 context」的總和，
同一個 session 從頭跑到尾時後期每回合是前期的 4.5 倍。三個關卡本來就是停下來等人的地方，
狀態全在磁碟（`_work/`），新 session 從 `check_gate.py` 接手。單線的週**不派任何 subagent**，
同一個 agent 依序扮演角色；兩條線以上才平行派。

⚠️ **「跑完」不等於「不問人」。** 這個流程有**三個人工關卡**（layer1／layer2／layer3 各一個），
`scripts/check_gate.py` 會擋。尤其 `layer1` 的 `user_points`
**明令不得由 agent 代擬** —— 所以正確行為是**停在關卡① 向你提問**，
而不是自己把一份完整週報產完。看到它停下來問你，那是對的。

掃描區間有三種來源，優先序由高到低（見 `scripts/_range.py`）：

| 參數 | 起日怎麼來 |
|---|---|
| `--days <起> <迄>` | 你明講（會與推導值比對，有落差就警告） |
| `--since-last-deck` | **上一份 deck 的 `meta.range[1]` + 1 天**（建議） |
| `--last N` | 最近 N 天。⚠️ 實際週報間隔很不規則（5~13 天），固定 7 天會漏，只給第一份週報用 |

---

## 這份 repo 有什麼

| 路徑 | 是什麼 |
|---|---|
| `SKILL.md` | 主流程（16 KB）：三層 ＋ 三個關卡，一層一個 session。理由與歷史在 `references/rule-provenance.md` |
| `references/` | 選材與寫作判準、投影片規則、`deck.json` 規格、subagent 角色規格 |
| `references/` 的**情境檔** | 走到特定情況才讀：`output-layout.md`（目錄形狀與舊結構）、`gate-facilitation.md`（關卡怎麼問、卡住怎麼辦）、`delivery.md`（怎麼播／pptx／改頁／backup 頁）。⭐ 每一份開頭都寫著「什麼情況才讀這一份」 |
| `references/` 的**開發用檔** | ⛔ 出週報用不到，只有要改這個 skill 時才讀：`BACKLOG.md`（已決定延後的事）、`orchestrator-cost.md`（成本量測與論證）、`rule-provenance.md`（每條規則在防哪一次實測失效） |
| `scripts/paths.py` | **路徑解析的唯一來源**（三段式；日誌 repo 轉發給 daily-log）＋ 輸出目錄形狀 `WORK_STAGES` |
| `scripts/merge_items.py` | 跨日合併提名 ＋ 週層級排序信號（只提名，不裁決） |
| `scripts/cluster_threads.py` | 用 artifacts 路徑把一週的項目分群成主線 |
| `scripts/build_deck.py` | 產 `materials.md` 與候選頁骨架 `deck.draft.json`（都在 `_work/1_materials/`）|
| `scripts/check_gate.py` / `check_deck.py` | 關卡與機械檢查（會擋）。`check_gate.py --confirm` 寫關卡①② 的定案檔；`check_deck.py --limits` 印全部門檻 |
| `scripts/gate_view.py` | 關卡①② 的確認稿（固定模板）＋ 空白答案檔 |
| `scripts/review_packet.py` | layout_reviewer 的審查包（逐圖文字、手繪數、shoot 實測），reviewer 只讀這一份 |
| `scripts/verify.py` | Step 4 的七步一個回合；`--quiet` 全文落地、終端只剩摘要 |
| `scripts/render_*.py`、`shoot.py`、`to_pptx.py` | 渲染、截圖、匯出 |
| `scripts/glyphs.py` | 盒子裡的小圖（點陣、分段條、read、探針、深度…19 種）由數字畫出來；字彙在 `references/glyphs.md`，`render_figure.py --demo` 有範例 |
| `scripts/measure_effort.py` | 量一份週報實際花了多久（選用） |
| `config.example/` | 設定範例（空白表單，值都被註解掉） |
| `agents/openai.yaml` | Codex 的顯示用中繼資料（選填；Claude Code 忽略） |

> ℹ️ **本 skill 內含兩個定序領域的構圖 renderer**（`scripts/render_figure.py` 的
> `read_pileup`／`haplotype_split`，以及配套的語意色盤 somatic／germline／error）。
> 它們只在畫 read 層的圖時用得到，**非該領域的專案忽略即可** —— 其餘流程不依賴它們。
> 對應的判準寫在 `references/composition-vocabulary.md`「領域構圖」那一段。
