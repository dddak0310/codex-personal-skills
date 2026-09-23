#!/usr/bin/env python3
"""把關卡①／關卡② 要給使用者看的東西**用腳本排成固定模板**，並留一份空白的答案檔。

## 為什麼有這支（2026-09-06，PR 2）

三個關卡裡，關卡① 與關卡② 以前是協調者**臨場**把 `layer1.json`／`layer2.*.json`
改寫成一段散文或一張表再問人。兩個後果：

1. 每一場的問法都不一樣，B17-6 就是這樣來的 —— 關卡② 沒有問「每一頁要講什麼」，
   使用者按了「可以開始畫」之後才一口氣給出七頁逐頁的內容指示，整輪 layer3 重畫。
2. 改寫本身是回合：讀 json、想措辭、寫 markdown，每一步都把當下整段 context 再送一次。

這支借了 asiapathogenomics `weekly-deck-builder` 的做法：**確認稿是固定的空白模板**，
腳本從 json 填進去，agent 只負責拿去問、把原話填回答案檔。⛔ 模板裡不預填任何判斷。

## 用法

    gate_view.py layer1 <日期目錄>     # → _work/2_layer1/gate1_view.md ＋ gate1_answers.json（空白）
    gate_view.py layer2 <日期目錄>     # → _work/3_layer2/gate2_view.md ＋ gate2_answers.json（空白）

答案檔填完之後：

    check_gate.py layer1 <日期目錄> --confirm _work/2_layer1/gate1_answers.json
    check_gate.py layer2 <日期目錄> --confirm _work/3_layer2/gate2_answers.json
    build_deck.py --skeleton --out <日期目錄>

⚠️ 答案檔**已存在就不覆寫**（裡面可能已經有使用者的原話）。要重來就自己刪。
"""
import argparse, glob, json, os, sys

import paths


def load(p):
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _write(p, txt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)


def _dump_if_absent(p, obj):
    if os.path.exists(p):
        print(f"[gate_view] 答案檔已存在，不覆寫：{p}")
        return
    _write(p, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    print(f"[gate_view] 空白答案檔 → {p}")


# ---------------------------------------------------------------------------
# 關卡①
# ---------------------------------------------------------------------------

def view_layer1(out):
    d1 = paths.work_dir(out, "layer1")
    dm = paths.work_dir(out, "materials")
    j = load(os.path.join(d1, "layer1.json"))
    if j is None:
        sys.exit(f"[gate_view] 找不到 {d1}/layer1.json —— thread_finder 還沒交件")
    todo = load(os.path.join(dm, "plan.todo.json")) or {}
    draft = load(os.path.join(dm, "deck.draft.json")) or {}
    rng = (draft.get("meta") or {}).get("range") or ["?", "?"]

    L = ["# 關卡① 主線組成確認", "",
         "> 這一份是腳本從 `layer1.json` 排出來的，⛔ 不含任何 agent 的判斷。",
         "> 每一條主線的「決定」欄現在都是**待使用者選擇** —— 由你拍板。", "",
         "## 範圍", "",
         f"- 日誌區間：{rng[0]} ~ {rng[1]}",
         f"- mode 提名：{j.get('mode', '?')}",
         f"- 聚類覆蓋：{j.get('coverage_note') or '（thread_finder 沒寫）'}",
         f"- 合併提名怎麼裁：{j.get('merge_note') or '（thread_finder 沒寫）'}", ""]

    hl = todo.get("headlines") or []
    if hl:
        L += ["## 每日 headline（敘事一句話的候選；⛔ agent 不先挑）", ""]
        L += [f"- {h.get('date')}：{h.get('headline')}" for h in hl]
        L += ["", f"> {todo.get('reminder', '')}", ""]

    L += ["## 候選主線", ""]
    for t in j.get("threads") or []:
        L += [f"### 主線 {t.get('id')}　{t.get('title', '')}", "",
              f"- 一句它在做什麼：{t.get('summary', '')}",
              f"- 成員（sid）：{'、'.join(t.get('members') or [])}",
              f"- 物證：{t.get('evidence', '')}",
              f"- 為什麼可能值得講：{t.get('why_maybe', '')}",
              f"- 還不確定的：{t.get('uncertain', '')}",
              f"- 教授交代：{'是' if t.get('advisor_assigned') else '（欄位空的 —— 只有你補得了）'}",
              f"- 決定：**{t.get('decision', '待使用者選擇')}**", ""]
    ov = j.get("overflow_threads") or []
    if ov:
        L += ["## 第 5 條以後（overflow，一定要裁）", ""]
        for t in ov:
            L += [f"### {t.get('id')}　{t.get('title', '')}", "",
                  f"- 成員：{'、'.join(t.get('members') or [])}",
                  f"- 物證：{t.get('evidence', '')}",
                  f"- 選項：{'／'.join(t.get('options') or [])}", ""]

    mg = j.get("merged_groups") or []
    if mg:
        L += ["## 合併提名的裁決（寫得出一個共同目標的標題嗎？寫不出來就拆）", "",
              "| 組 | 標題 | 成員 | 拆出 | 補掛 |", "|---|---|---|---|---|"]
        for g in mg:
            so = "、".join(f"{x.get('sid')}（{x.get('why', '')}）" for x in g.get("split_out") or []) or "—"
            ad = "、".join(f"{x.get('sid')}（{x.get('why', '')}）" for x in g.get("added") or []) or "—"
            L.append(f"| {g.get('gid')} | {g.get('title', '')} | {'、'.join(g.get('members') or [])} | {so} | {ad} |")
        L.append("")

    dr = j.get("dropped") or []
    if dr:
        L += ["## 判成不上主線的", "", "| sid | 去處 | 理由 |", "|---|---|---|"]
        L += [f"| {x.get('source')} | {x.get('where')} | {x.get('why', '')} |" for x in dr]
        L.append("")
    cu = j.get("causality_uncertain") or []
    if cu:
        L += ["## 因果接點（由你判定，⛔ agent 只看得到時間順序）", ""]
        L += [f"- {x}" for x in cu] + [""]
    qs = j.get("questions_for_user") or []
    if qs:
        L += ["## thread_finder 要問你的", ""] + [f"- {q}" for q in qs] + [""]

    L += ["## 固定七題（答案逐字進 `plan.answers`）", ""]
    tids = [t.get("id") for t in (j.get("threads") or [])]
    n = 0
    for q in todo.get("questions") or []:
        if q.get("_per_thread"):
            for tid in tids:
                n += 1
                L.append(f"{n}. 【主線 {tid}】{q['q'].replace('【每一條主線各問一次】', '')}")
        else:
            n += 1
            L.append(f"{n}. {q['q']}")
    L += ["", "> ⭐ 第 2 題（每條線 3~4 個重點）決定有哪幾頁；選項列候選重點，但**一定留「都不是，我自己說」**。",
          "> 🗣 選不出來／東西太多 → `references/gate-facilitation.md`。", "",
          "## 填答案", "",
          f"把原話逐字填進 `{os.path.relpath(os.path.join(d1, 'gate1_answers.json'), out)}`，然後：",
          "", "```bash",
          f"python3 $S/check_gate.py layer1 {out} --confirm {os.path.join(d1, 'gate1_answers.json')}",
          "```", ""]

    _write(os.path.join(d1, "gate1_view.md"), "\n".join(L))
    print("\n".join(L))
    print(f"[gate_view] → {os.path.join(d1, 'gate1_view.md')}")

    answers = {
        "_how": "全部填**原話**。threads 的 key 是主線 id；decision 三選一：入選／backup／不講。"
                "user_points 逐字、順序就是頁序。members_without_point：成員有、user_points 沒有的 sid，"
                "where 三選一（口頭／backup／不講），由使用者決定。overflow 的線填 decision 與（合併時）into。",
        "confirmed_by": "",
        "confirmed_at": "",
        "narrative": "",
        "narrative_source": "",
        "mode": j.get("mode", ""),
        "arc": {"problem": "", "motivation": "", "results": "", "conclusion": ""},
        "answers": [{"q": "", "a": "", "date": ""}],
        "threads": {t.get("id"): {"decision": "入選", "order": i,
                                  "title": t.get("title", ""), "summary": t.get("summary", ""),
                                  "user_points": [], "members_without_point": []}
                    for i, t in enumerate(j.get("threads") or [], 1)},
        "overflow": {t.get("id"): {"decision": "", "into": ""} for t in ov},
        "dropped_overrides": [],
        "rebuttals": [],
    }
    _dump_if_absent(os.path.join(d1, "gate1_answers.json"), answers)


# ---------------------------------------------------------------------------
# 關卡②
# ---------------------------------------------------------------------------

def view_layer2(out):
    d2 = paths.work_dir(out, "layer2")
    files = sorted(glob.glob(os.path.join(d2, "layer2.*.json")))
    if not files:
        sys.exit(f"[gate_view] {d2} 底下沒有 layer2.*.json —— planner 還沒交件")
    j1 = load(os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json")) or {}
    titles = {t.get("id"): t.get("title", "") for t in j1.get("threads") or []}

    L = ["# 關卡② 逐頁規劃確認", "",
         "> 腳本從 `layer2.<線>.json` 排出來的，⛔ 不含 agent 的判斷；**刻意不給任何長相**（視覺是 layer3 的事）。", ""]
    terms, terms_zh = [], {}
    all_pages = []
    for f in files:
        j = load(f) or {}
        tid = j.get("thread") or os.path.basename(f)[7:-5]
        pages = j.get("pages") or j.get("slide_plan") or []
        L += [f"## 主線 {tid}　{titles.get(tid, '')}", "",
              "| # | 對應的 user_point | 講什麼（point） | 形狀 | slot | depth | 主體 | 必須出現的數字 | 沒選的機制 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for p in pages:
            comp = (p.get("composition") or {}).get("comp")
            body = p.get("body") or ""
            body = f"{body}／{comp}" if comp else body
            alt = "；".join(p.get("alternatives") or []) or "—"
            L.append(f"| {tid}{p.get('n', '?')} | {p.get('user_point', '')} | {p.get('point', '')} | "
                     f"{p.get('gate2', '')} | {p.get('slot', '')} | {p.get('depth', '')} | {body} | "
                     f"{'、'.join(str(x) for x in (p.get('must_numbers') or []))} | {alt} |")
            all_pages.append((tid, p))
        L.append("")
        if j.get("buildup_note"):
            L += [f"- 非 method 格：{j['buildup_note']}", ""]
        tp = j.get("trim_pass") or {}
        if tp:
            L += [f"### ⑦ 削減提議（planner 檢查了 {tp.get('reviewed', '?')} 頁）", ""]
            for pr in tp.get("proposals") or []:
                L.append(f"- **{pr.get('action')}** {'、'.join(pr.get('pages') or [])}：{pr.get('why', '')}　→ 採納？")
            if not tp.get("proposals"):
                L.append("- （零項提議；下面是逐頁「檢查過但保留」的理由）")
            for k in tp.get("kept") or []:
                L.append(f"  - 保留 {k.get('page')}：{k.get('why', '')}")
            L.append("")
        oq = j.get("open_questions") or []
        if oq:
            L += ["### planner 要問你的", ""] + [f"- {q}" for q in oq] + [""]
        for t in j.get("terms_proposed") or []:
            if t not in terms:
                terms.append(t)
        for k, v in (j.get("terms_proposed_zh") or {}).items():
            terms_zh.setdefault(k, v)

    L += ["## 名詞凍結（全場只有一個名字；中譯在這裡一起定，layer3 照表翻）", "",
          "| 物品名（en，進 deck.json） | 中譯（zh，進 strings.zh.json） |", "|---|---|"]
    for t in terms:
        L.append(f"| {t} | {terms_zh.get(t, '')} |")
    L += ["", "## 固定三題（B17-6：這是唯一決定「每頁內容」的一關）", "",
          "1. 逐頁看「講什麼」那一欄，**哪一頁的重心不對**？（選項列頁號＋point；一定要有「都對」）",
          "2. 哪一頁該用圖、哪一頁口頭帶過就好？（選項列頁號）",
          "3. 頁序與上面的削減提議，採不採納？（逐則採納／不採納）", "",
          "> 使用者的每一句指示都逐字進 `gate2_answers.json` 的 `page_notes`；",
          "> 內容要改的頁由 planner 角色改 `layer2.<線>.json`，改完才 `--confirm`。", "",
          "## 填答案", "", "```bash",
          f"python3 $S/check_gate.py layer2 {out} --confirm {os.path.join(d2, 'gate2_answers.json')}",
          f"python3 $S/build_deck.py --skeleton --out {out}",
          "```", ""]
    _write(os.path.join(d2, "gate2_view.md"), "\n".join(L))
    print("\n".join(L))
    print(f"[gate_view] → {os.path.join(d2, 'gate2_view.md')}")

    answers = {
        "_how": "page_notes：使用者對每一頁的原話（key 是頁號如 B3）。adopted_proposals：採納了哪些削減提議。"
                "terms：core_metric 與物品名的中譯（zh），關卡② 凍結後 layer3 照表翻。",
        "confirmed_by": "", "confirmed_at": "",
        "page_notes": {f"{tid}{p.get('n', '?')}": "" for tid, p in all_pages},
        "adopted_proposals": [],
        "terms": {"core_metric": "", "objects": terms,
                  "zh": {t: terms_zh.get(t, "") for t in terms}},
    }
    _dump_if_absent(os.path.join(d2, "gate2_answers.json"), answers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["layer1", "layer2"])
    ap.add_argument("out", help="日期目錄")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if not os.path.isdir(out):
        sys.exit(f"[gate_view] 找不到目錄 {out}")
    (view_layer1 if a.stage == "layer1" else view_layer2)(out)


if __name__ == "__main__":
    main()
