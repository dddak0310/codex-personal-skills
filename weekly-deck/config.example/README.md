# 設定範例

把這裡的檔案複製到 `~/.config/weekly-deck/`，改成你自己的值。
**每一項都是選填** —— 沒設定就走慣例（見 `scripts/paths.py` 的表）。

```bash
mkdir -p ~/.config/weekly-deck
cp config.example/* ~/.config/weekly-deck/
rm ~/.config/weekly-deck/README.md      # 那是說明，不是設定
$EDITOR ~/.config/weekly-deck/*
```

| 檔案 | 沒設定會怎樣 |
|---|---|
| `daily-log` | 依序找：同一個 skills 目錄下的 `daily-log/` → `$CODEX_HOME/skills/daily-log` → `~/.claude/skills/daily-log` → `~/.codex/skills/daily-log`；都沒有就**報錯** |
| `data` | 用 `<daily-log 的 repo>/.data` |
| `reports-root` | 用 `<日誌 repo>/weekly`（與 `.data/`、`daily/` 並排，⚠️ 不是專案目錄）|
| `transcript-dirs` | 由專案路徑推導 session 目錄，**Claude Code 與 Codex 兩種都回** |

也可以用環境變數一次性覆寫（優先於設定檔）：
`WEEKLY_DECK_DAILY_LOG`、`WEEKLY_DECK_DATA`、`WEEKLY_DECK_REPORTS`、
`WEEKLY_DECK_TRANSCRIPT_DIRS`。

⚠️ **設定過的路徑若不存在，腳本會直接報錯，不會退回預設。**
這是刻意的：weekly-deck 的失效形態是**無聲**的（找不到上一份 deck →
掃描區間默默推不出來 → 退回手填日期），所以「我設了但沒生效」不能被吞掉。
這也是為什麼每個範例檔的值都被註解掉——忘了編輯等同於沒設定，
而不是解析出一個看起來像路徑、其實不存在的值。
