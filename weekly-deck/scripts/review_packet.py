#!/usr/bin/env python3
"""把 layout_reviewer 要看的東西**先用腳本抽好**，合成一份檔：`_work/4_slides/review_packet.md`。

## 為什麼有這支（2026-09-06，PR 2）

2026-09-06 的實跑，layout_reviewer（Sonnet）審 7 頁花了 15.6M tokens。它的規格要它
逐張 SVG 列 `label`／`value`、數 hl class、加總手繪張數、讀兩版 shoot_check、對每頁的
honesty 六問 —— 每一項都是「打開一個檔、讀、記下」的回合，而且讀進去的東西留在
context 裡到收尾。這些**抽取**沒有判斷成分，腳本做；reviewer 只做需要眼睛與語意的那幾項。

三項純機械的判準已經搬進 `check_deck.py`（手繪配額、金字組合、樣板佔位符），
這裡只把它們的**數字**印一次給 reviewer 覆核，⛔ 不重驗。

用法：
    review_packet.py <日期目錄>            # → _work/4_slides/review_packet.md
"""
import argparse, glob, json, os, re, sys

import paths

TEXT = re.compile(r'<text[^>]*?(?:class="([^"]*)")?[^>]*>(.*?)</text>', re.S)
TSPAN = re.compile(r"<[^>]+>")


def load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def svg_texts(fp):
    """[(class 字串, 純文字), …]，依出現順序。"""
    try:
        txt = open(fp, encoding="utf-8").read()
    except OSError:
        return []
    out = []
    for m in re.finditer(r"<text\b([^>]*)>(.*?)</text>", txt, re.S):
        attrs, inner = m.group(1), m.group(2)
        cls = re.search(r'class="([^"]*)"', attrs)
        s = TSPAN.sub("", inner).strip()
        if s:
            out.append((cls.group(1) if cls else "", s))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="日期目錄")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    deck = load(os.path.join(out, "deck.json"))
    if not deck:
        sys.exit(f"[packet] 找不到或讀不了 {out}/deck.json")
    sd = paths.work_dir(out, "slides", create=True)
    plan = deck.get("plan") or {}
    slides = deck.get("slides") or []
    by_id = {s.get("id"): s for s in slides}

    L = ["# layout_reviewer 審查包（腳本抽取，⛔ 不含判斷）", "",
         f"deck：`{os.path.join(out, 'deck.json')}`　主線：{[t.get('id') for t in deck.get('threads') or []]}"
         f"　mode：{plan.get('mode')}　內容頁 {sum(1 for s in slides if s.get('type') not in ('agenda', 'cover', 'thread-intro') and not s.get('backup'))} 頁", "",
         "> 你要做的是規格裡**需要眼睛或語意**的那幾項（1 全域一致性、2 面積、3a 逐標籤盤問、3b、3c 第 3 問、4 深度、6 放大看圖、7 誠實性覆核）。",
         "> 純機械的三項（手繪配額、金字組合、樣板佔位符）`check_deck.py` 已經驗過，下面只印數字給你覆核。", ""]

    # ---- 名詞與物件 ----
    terms = (plan.get("terms") or {}).get("objects") or []
    L += ["## plan.terms.objects（同名物件全場一個名字）", "", "、".join(f"`{t}`" for t in terms) or "（空）", ""]

    # ---- manifests ----
    found = []
    for mp in sorted(glob.glob(os.path.join(sd, "compositions.*.json"))) + \
              sorted(glob.glob(os.path.join(out, "compositions.*.json"))):
        j = load(mp)
        if j:
            found.append((mp, j))
    hw_total = 0
    L += ["## 圖（compositions.*.json ＋ figures/*.svg）", ""]
    for mp, j in found:
        L += [f"### {os.path.basename(mp)}（線 {j.get('thread')}）", ""]
        st = j.get("shared_terms") or {}
        if st:
            L += ["shared_terms（身分宣告 —— 你要看 aka 有沒有漏登記、豁免理由站不站得住）：", ""]
            for k, v in st.items():
                L.append(f"- `{k}`：{json.dumps(v, ensure_ascii=False)[:200]}")
            L.append("")
        for e in (j.get("figures") or j.get("compositions") or []):
            if not isinstance(e, dict):
                continue
            rel = e.get("file") or e.get("figure") or "?"
            hw = bool(e.get("handwritten"))
            hw_total += hw
            fp = os.path.join(out, rel)
            texts = svg_texts(fp)
            roles = {}
            hl_combos = set()
            for cls, s in texts:
                toks = cls.split()
                role = next((t for t in ("label", "value", "annot", "def") if t in toks), "?")
                roles[role] = roles.get(role, 0) + 1
                if "hl" in toks:
                    hl_combos.add(" ".join(sorted(toks)))
            L += [f"#### {e.get('slide')} → `{rel}`　comp={e.get('comp')}　handwritten={hw}　"
                  f"<text> {len(texts)} 則（{', '.join(f'{k} {v}' for k, v in sorted(roles.items()))}）　"
                  f"金字組合 {len(hl_combos)} 種", ""]
            if e.get("objects"):
                L.append("objects：" + "；".join(f"`{k}`＝{v}" for k, v in e["objects"].items()))
                L.append("")
            L.append("逐則文字（3a：每一則 label／value 各寫一句「聽眾拿它做什麼」）：")
            L.append("")
            L.append("| # | class | 文字 |")
            L.append("|---|---|---|")
            for i, (cls, s) in enumerate(texts, 1):
                cell = s.replace("|", "／")[:80]
                L.append(f"| {i} | {cls or '—'} | {cell} |")
            L.append("")
            sl = by_id.get(e.get("slide")) or {}
            hon = sl.get("honesty")
            L.append(f"honesty（7：覆核，缺答案本身就是 BLOCKING）：" +
                     (json.dumps(hon, ensure_ascii=False) if hon else "**沒有填**"))
            L.append("")
    L += [f"**手繪合計 {hw_total} 張**（配額 2–3；check_deck 已驗，超過時逐張問「拿掉會少講什麼」）", ""]

    # ---- 每頁摘要 ----
    L += ["## 每頁（4 深度／2 面積 用）", "", "| id | 線 | type | depth | point | sub | caption |", "|---|---|---|---|---|---|---|"]
    for s in slides:
        if s.get("type") in ("agenda", "cover", "thread-intro"):
            continue
        b = s.get("body") or {}
        cap = b.get("caption") or ("；".join(t.get("caption", "") for t in (b.get("tables") or []) if t.get("caption")))
        L.append(f"| {s.get('id')} | {s.get('thread', '')} | {s.get('type')} | {s.get('depth', '')} | "
                 f"{str(s.get('point', '')).replace('|', '/')[:60]} | {str(s.get('sub') or '').replace('|', '/')[:40]} | "
                 f"{str(cap or '').replace('|', '/')[:40]} |")
    L.append("")

    # ---- shoot_check ----
    for lang in ("en", "zh"):
        p = paths.work_file(out, f"shoot_check.{lang}.txt", create=False)
        L += [f"## shoot_check.{lang}.txt（實測；⛔ 沒有這一份就不要用眼睛猜溢位）", ""]
        if os.path.isfile(p):
            body = open(p, encoding="utf-8").read().strip().splitlines()
            L += ["```"] + body[:120] + (["…（截斷，全文見檔案）"] if len(body) > 120 else []) + ["```", ""]
        else:
            L += [f"**不存在**（{p}）—— 請協調者先跑 verify.py；沒有實測輸出你就 BLOCKED", ""]

    # ---- 截圖 ----
    shots = sorted(glob.glob(os.path.join(paths.export_dir(out), "slides", "*.png")))
    L += ["## 截圖（6：放大看箭頭／壓字，只有眼睛驗得到）", "",
          (f"{len(shots)} 張在 `{os.path.dirname(shots[0])}`" if shots else
           f"還沒截。要看就跑 `python3 $S/shoot.py {out}/deck.en.html`（⚠️ 只看手繪與有連線的那幾張，"
           "⛔ 不要每張都讀進 context）"), ""]

    dest = paths.work_file(out, "review_packet.md", create=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[packet] → {dest}（{len(found)} 份 manifest、手繪 {hw_total} 張、{len(slides)} 頁）")


if __name__ == "__main__":
    main()
