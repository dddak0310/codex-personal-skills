# Issue Report

呈現單一 Jira issue（bug fix、規則調整、任何 APGPAS/CoJudger 程式變更）時的簡報流程。
Jira issue ID 取自當前對話或使用者指示，不需另外詢問。

## 限制

- **最多 5 頁**——封面若需要才算一頁，通常不用。
- **不放「Next steps / 下週計畫」頁**，除非使用者明確要求。
- 頁數與安排彈性；下面的結構是常見樣式，不是硬規則。

---

## autojudge / cojudger 規則類 issue 的常見結構

### 第 1 頁 — 問題陳述
- 簡述哪條規則錯了、怎麼發現的
- 受影響檢體表（`chip_id` / `specimen_id` / `seq_id` 擇一或多）
- 有問題的 pathogen 資料表，常見欄位：`organism`、`sec.hit`、`sec.original_ani`、`G_order`、`S_order`、`blastn`
- **檢體基礎資訊必附**：`specimen_id`、檢體類型（tissue 寫成 `tissue ($organ_source)`）、
  醫院、部門、醫生——規則與「整批相同就提到表格上方」的做法見
  `references/weekly-report.md` →「檢體基礎資訊」
- 所有表格資料放 TSV/CSV，**不手打數字**

### 第 2 頁 — 解法與測試準則
- 規則變更說明（bullet）
- 測試資料篩選準則（bullet 或小表）
- 測試集檢體數

### 第 3–5 頁 — Before / After 結果
- 用 apgpas-testing 的比較輸出呈現修正影響
- RT / RK code 變化（before → after）
- 副作用檢查：是否影響到其他檢體
- 改善 vs 退步彙整

---

## 各頁版型建議

| 頁 | 建議版型 | 備註 |
|---|---|---|
| 問題陳述 | 左右欄（說明＋表格）或純表格 | 檢體清單用表格 |
| 解法 | bullet 或混合 | 精簡 |
| Before/After 結果 | 表格或混合 | 一頁一組比較 |

版型細節（版型 1–6、語意 class）見主 `SKILL.md`。

---

## 備註

- Issue 類型差異大——頁數與內容依實際調整。
- 若牽涉圖（plot / diagram），用圖片頁。
- 一頁多表：用左右欄或上下疊版型。
- 省略沒有資訊量的頁——少而清楚的資料勝過湊頁數。
