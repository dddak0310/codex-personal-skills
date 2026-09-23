#!/usr/bin/env python3
"""量一次實跑到底花了多少 token —— 協調者與每個 subagent 分開算。

## 為什麼要這支

`SKILL.md` 的「成本結構」那一節是靠這支量出來的。沒有它，關於成本的討論
全部只能靠猜，而實測顯示**猜的方向會反**（第一版打包把成本推高 33~92%，
當時估的是 −60%）。

## ⚠️ 兩個一定要知道的坑

**① 任務通知裡的 `subagent_tokens` 欄位不能用。**
實測：某個 builder 的通知寫 284,790，實際帳單 12,010,757 —— **差 42 倍**。
那個欄位大概只計非快取的部分。⛔ 不要拿它做任何比較。

**② 同一個 API 回應會被記成好幾行 JSONL，每行都帶同一份 usage。**
（一行 `thinking`、一行 `text`、一行 `tool_use`，usage 相同。）
直接加總會多算 2~3 倍。**一定要用 `requestId` 去重** —— 這支就是這樣做的。

**③ subagent 的帳要按 session 目錄取，不能用 `proj/*/subagents/` 全掃。**
2026-09-06 實測：那個 glob 把**專案下所有 session** 的 74 個 agent 檔全部加總，
於是一次 100.5M 的實跑被印成 703.8M（差 7 倍）。協調者那邊也錯——原本挑
「呼叫數最多的 JSONL」，挑到的是三天前另一場 session。**兩邊都要綁同一個 session id。**

## 怎麼讀結果

`成本 = Σ(每一回合當下的 context)`，而 context 只增不減。所以：
- **cache 讀**佔 95% 是正常的，那就是「把已經看過的東西重送一次」
- **output** 通常不到 1% —— 真正產出的內容很少，錢都花在重讀
- 一個 agent 的帳 ≈ 開場包大小 × 回合數 + 它自己累積的紀錄，
  所以**同樣的總回合數，分散在多個短 agent 比塞進一個長 agent 便宜**

用法：
  measure_tokens.py                 # 最近一次有活動的 session
  measure_tokens.py --list          # 列出這個專案的所有 session（挑 id 用）
  measure_tokens.py --session <id>  # 指定某一次實跑
  measure_tokens.py --project <專案 JSONL 目錄>
  measure_tokens.py --phases        # 另外按時段拆帳（看哪個階段最貴）
"""
import argparse, collections, glob, json, os, sys


def dedup_usage(path, with_tools=False):
    """回傳 [(timestamp, usage), ...]，已用 requestId 去重。

    `with_tools=True` 時回 [(timestamp, usage, [這一回合呼叫的工具名…])]：同一個 requestId
    的幾行（thinking／text／tool_use）合成一筆，tool_use 的 name 全收 —— `--growth` 要拿它
    解釋「下一回合 context 為什麼跳了這麼多」（工具的結果就是下一回合多出來的那一段）。
    """
    seen, out, tools, seen_tools = {}, [], {}, set()
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for ln in fh:
            try:
                j = json.loads(ln)
            except Exception:
                continue
            if j.get("type") != "assistant":
                continue
            msg = j.get("message") or {}
            u = msg.get("usage") or {}
            rid = j.get("requestId") or msg.get("id")
            if not rid:
                continue
            for blk in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
                if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name"):
                    tid = blk.get("id") or (rid + blk["name"])
                    if tid not in seen_tools:              # 同一個 tool_use 出現在幾行就只算一次
                        seen_tools.add(tid)
                        tools.setdefault(rid, []).append(blk["name"])
            if not u or rid in seen:
                continue
            seen[rid] = len(out)
            out.append((j.get("timestamp", ""), u))
    if with_tools:
        # 工具名依 requestId 回填（同一 requestId 的 tool_use 行可能在 usage 行之後）
        rid_of = {v: k for k, v in seen.items()}
        return [(ts, u, tools.get(rid_of[i], [])) for i, (ts, u) in enumerate(out)]
    return out


def ctx_of(u):
    """這一回合送出去的 context 大小 ＝ 新 input ＋ cache 讀 ＋ cache 寫。"""
    return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0))


def stats(rows):
    """(回合數, 平均 context, 最大 context, 開場 context) —— 帳單 ＝ 回合數 × 平均 context。

    ⭐ 為什麼要這四欄（PR 3）：2026-09-06 那次只有總量，於是「開場包佔 21%」是事後
    手算的。有了每回合的平均與最大，一眼看得出是「派遣包太大」（開場高、平均接近開場）
    還是「一路膨脹」（開場小、最大是開場的好幾倍）—— 兩種病的藥不同。
    """
    if not rows:
        return 0, 0, 0, 0
    cs = [ctx_of(u) for _, u in rows]
    return len(rows), sum(cs) // len(cs), max(cs), cs[0]


def total(rows):
    g = lambda k: sum(u.get(k, 0) for _, u in rows)
    inp, cr, cw, o = (g("input_tokens"), g("cache_read_input_tokens"),
                      g("cache_creation_input_tokens"), g("output_tokens"))
    return len(rows), inp, cr, cw, o, inp + cr + cw + o


def fmt(name, t, st=None):
    n, inp, cr, cw, o, s = t
    line = f"{name:<30}{n:>5}{inp:>8,}{cr:>13,}{cw:>11,}{o:>9,}{s:>13,}"
    if st:
        _n, avg, mx, first = st
        line += f"{avg:>10,}{mx:>10,}{first:>9,}"
    return line


def timespan(path):
    """回傳 (最早, 最晚) 的 timestamp 字串；空檔回 (None, None)。"""
    lo = hi = None
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    with fh:
        for ln in fh:
            i = ln.find('"timestamp":"')
            if i < 0:
                continue
            t = ln[i + 13:ln.find('"', i + 13)]
            if lo is None or t < lo:
                lo = t
            if hi is None or t > hi:
                hi = t
    return lo, hi


def elapsed(lo, hi):
    """兩個 ISO timestamp 的間隔，回 '2:59:17' 這種字串。"""
    if not lo or not hi:
        return "?"
    import datetime
    f = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))
    return str(f(hi) - f(lo)).split(".")[0]


def sessions(proj):
    """[(最早, 最晚, session_id, 主檔路徑, rows), ...]，依最晚活動排序。"""
    out = []
    for f in glob.glob(proj + "/*.jsonl"):
        rows = dedup_usage(f)
        if not rows:
            continue
        lo, hi = timespan(f)
        out.append((lo or "", hi or "", os.path.basename(f)[:-6], f, rows))
    out.sort(key=lambda x: x[1])
    return out


def subagents_of(proj, sid):
    """⚠️ 只取這個 session 目錄底下的 agent 檔。
    ⛔ 不要改回 `proj/*/subagents/` —— 那會把所有 session 的 subagent 加進來（坑 ③）。"""
    out = []
    for f in sorted(glob.glob(f"{proj}/{sid}/subagents/agent-*.jsonl")):
        rows = dedup_usage(f)
        if not rows:
            continue
        label = ""
        meta = f[:-6] + ".meta.json"
        if os.path.exists(meta):
            try:
                label = (json.load(open(meta, encoding="utf-8"))
                         .get("description") or "")
            except Exception:
                pass
        out.append((total(rows), os.path.basename(f)[6:18], label, f))
    out.sort(reverse=True, key=lambda x: x[0][5])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="~/.claude/projects/<專案> 目錄")
    ap.add_argument("--session", help="要算哪一次實跑（session id，見 --list）")
    ap.add_argument("--list", action="store_true", help="列出這個專案的所有 session")
    ap.add_argument("--phases", action="store_true", help="按小時拆帳")
    ap.add_argument("--growth", action="store_true",
                    help="⭐ 印協調者 context 跳最多的前 10 個回合，以及那一回合前面呼叫了哪些工具 —— "
                         "「是哪幾次 Read／Bash 把 context 撐大的」直接看得到")
    ap.add_argument("--agent", metavar="ID前綴", help="--growth 改看某個 subagent（agent id 前綴）")
    a = ap.parse_args()

    proj = a.project
    if not proj:
        root = os.path.expanduser("~/.claude/projects")
        cands = [d for d in glob.glob(root + "/*") if os.path.isdir(d)]
        if not cands:
            sys.exit(f"[tokens] 找不到任何專案目錄（{root}）")
        proj = max(cands, key=os.path.getmtime)
    print(f"[tokens] 專案：{proj}\n")

    sess = sessions(proj)
    if not sess:
        sys.exit("[tokens] 這個專案裡沒有任何帶 usage 的 session")

    # ── --list：挑 session 用 ────────────────────────────────
    if a.list:
        print(f"{'session':<10}{'開始':<20}{'時長':>10}{'主呼叫':>7}"
              f"{'subs':>5}{'總 token':>14}")
        for lo, hi, sid, f, rows in reversed(sess):
            subs = subagents_of(proj, sid)
            tot = total(rows)[5] + sum(t[5] for t, *_ in subs)
            print(f"{sid[:8]:<10}{lo[:19]:<20}{elapsed(lo, hi):>10}"
                  f"{len(rows):>7}{len(subs):>5}{tot:>14,}")
        return

    # ── 選定 session：預設取「最後有活動」的那一個 ──────────
    if a.session:
        hit = [x for x in sess if x[2].startswith(a.session)]
        if not hit:
            sys.exit(f"[tokens] 找不到 session {a.session}（用 --list 看有哪些）")
        if len(hit) > 1:
            sys.exit(f"[tokens] {a.session} 對到 {len(hit)} 個 session，請給更長的 id")
        lo, hi, sid, mainf, rows = hit[0]
    else:
        lo, hi, sid, mainf, rows = sess[-1]

    print(f"session {sid}")
    print(f"  時間 {lo[:19]} → {hi[:19]}　時長 {elapsed(lo, hi)}\n")

    print(f"{'':<30}{'呼叫':>5}{'新in':>8}{'cache讀':>13}"
          f"{'cache寫':>11}{'out':>9}{'小計':>13}{'平均ctx':>10}{'最大ctx':>10}{'開場':>9}")
    mt = total(rows)
    print(fmt("協調者（主 session）", mt, stats(rows)))
    grand = list(mt)

    sub = subagents_of(proj, sid)
    if sub:
        print()
        for t, aid, label, f in sub:
            print(fmt(f"  sub {aid} {label[:14]}", t, stats(dedup_usage(f))))
            grand = [grand[i] + t[i] for i in range(6)]
    print("-" * 118)
    print(fmt("合計", tuple(grand)))
    print("  ⭐ 帳單 ≈ 回合數 × 平均 ctx。開場 ≈ 派遣包；最大 ≫ 開場 ＝ 一路膨脹（工具全文、讀回的檔）。")
    if grand[5]:
        print(f"\n  cache 讀佔 {grand[2]*100//grand[5]}%（＝把已看過的東西重送）"
              f"　output 佔 {grand[4]*100/grand[5]:.2f}%（＝真正產出的內容）")
    if sub:
        s_sum = sum(t[5] for t, *_ in sub)
        print(f"  協調者 {mt[5]:,}（{mt[5]*100//grand[5]}%）"
              f"　vs　{len(sub)} 個 subagent 合計 {s_sum:,}")

    # ── 每回合的成長：哪幾次呼叫把 context 撐大的 ────────────
    if a.growth:
        target, name = mainf, "協調者"
        if a.agent:
            hit = [f for _, aid, _, f in sub if aid.startswith(a.agent)]
            if not hit:
                sys.exit(f"[tokens] 找不到 agent {a.agent}（有的是 {[x[1] for x in sub]}）")
            target, name = hit[0], f"agent {a.agent}"
        rows_t = dedup_usage(target, with_tools=True)
        print(f"\n[growth] {name}：context 增量最大的前 10 個回合（增量歸因給**前一回合**呼叫的工具）")
        jumps = []
        for i in range(1, len(rows_t)):
            d = ctx_of(rows_t[i][1]) - ctx_of(rows_t[i - 1][1])
            jumps.append((d, i, rows_t[i][0][11:19], rows_t[i - 1][2]))
        for d, i, ts, tools in sorted(jumps, reverse=True)[:10]:
            print(f"  第 {i:>3} 回合 {ts}  +{d:>8,}  ← {', '.join(tools) or '（沒有工具呼叫：純文字／thinking）'}")
        if rows_t:
            print(f"  開場 {ctx_of(rows_t[0][1]):,} → 收尾 {ctx_of(rows_t[-1][1]):,}"
                  f"（{len(rows_t)} 回合）。⚠️ 增量大的多半是 Read 大檔、Bash 大輸出、Write 整份 JSON。")

    # ── 按時段拆帳 ──────────────────────────────────────────
    if a.phases:
        print("\n[phases] 協調者按小時拆帳（看哪個階段最貴）")
        buckets = collections.defaultdict(list)
        for ts, u in rows:
            buckets[ts[11:13]].append((ts, u))
        for h in sorted(buckets):
            t = total(buckets[h])
            print(f"  {h}:00  呼叫 {t[0]:>3}　小計 {t[5]:>12,}　"
                  f"平均每次 {t[5]//max(t[0],1):>8,}")
        print("  ⚠️ 平均每次會隨時間單調上升 —— 那就是 context 累積。"
              "同一個動作在 session 後期可能貴上數倍。")


if __name__ == "__main__":
    main()
