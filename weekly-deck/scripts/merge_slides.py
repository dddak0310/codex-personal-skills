#!/usr/bin/env python3
"""把各主線的 slides.<thread>.json 合併進 deck.json。

⚠️ 首次實跑之後新增。為什麼要有這支：
layer3 的 builder 從 `layer2.<thread>.json` 重生成 `slides[]`，於是**每一輪都會把
協調者在 deck.json 上做過的整形帶回舊值**——最常見的是被縮短過的 `point`
（`check_deck.py` 有 90 字上限與「一頁一重點」檢查）與被改成 null 的 `output`。
首次實跑那天手動重套了 6 次，每次都要記得，漏一次就會被檢查擋下來。

**保留 deck.json 既有值的欄位**（builder 不得覆寫）：point / depth / output / user_point
**從 slides.<thread>.json 取的**：其餘全部（title / body / notes / composition / must_numbers…）

順帶做兩件每次都要做的事：
  1. `from` 逐字接上同主線前一頁的 `to`（換線與 agenda 頁重置）
  2. 印出被保留的欄位，讓人看得到協調者的整形沒有被吃掉

⛔ **不做**「把版面回填 `plan.slide_plan`」（舊檔頭寫的第 2 件，是死碼且模型錯了）——
理由寫在下面那段註解：`slide_plan` 是關卡② 的定案，差異要留給 `check_deck.py` 對帳。
"""
import argparse, fcntl, json, os, sys

KEEP = ("point", "depth", "output", "user_point")   # 以 deck.json 為準
STRUCT = {"cover", "agenda", "thread-intro"}


def _short(v, n=60):
    t = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return t if len(t) <= n else t[:n] + "…"


def reorder_by_slice(out, slice_order):
    """每條有 slice 的線：線內順序照 slice；線的位置不動。回 (新序列, 有重排的線)。"""
    moved = []
    for th, ids in slice_order.items():
        if th is None:
            continue                     # 不掛 thread 的頁（全場 outline）不歸任何 slice 管
        idx = [i for i, s in enumerate(out) if s.get("thread") == th]
        if not idx:
            continue
        block = [out[i] for i in idx]
        rank = {sid: k for k, sid in enumerate(ids)}
        new_block = (sorted([s for s in block if s["id"] in rank], key=lambda s: rank[s["id"]])
                     + [s for s in block if s["id"] not in rank])
        if [s["id"] for s in new_block] != [s["id"] for s in block]:
            moved.append(f"{th}（{' → '.join(s['id'] for s in new_block)}）")
        keep_idx = set(idx)
        out = [s for i, s in enumerate(out) if i not in keep_idx]
        out[idx[0]:idx[0]] = new_block
    return out, moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("slices", nargs="*", help="slides.T1.json slides.T2.json …（可省，只做 --outline 時）")
    ap.add_argument("--outline", action="store_true",
                    help="⭐ 補／更新全場 outline 頁（不掛 thread 的 agenda，放最前）。"
                         "multi：一條主線一列（title／summary 逐字取自 deck.threads）；"
                         "single：列該線的 user_points（B17-4：單線的週只有一張 outline）。"
                         "⛔ 這一頁沒有任何判斷成分，所以由腳本寫，不再派 deck_assembler")
    ap.add_argument("--no-strings", action="store_true",
                    help="不把 slice 旁邊的 strings.<線>.zh.json 併進 strings.zh.json")
    ap.add_argument("--no-keep", action="store_true",
                    help="不保留 deck.json 既有的 point/depth/output/user_point，改用 slice 的值。"
                         "什麼時候用：builder **修了** point（例如換掉分號讓「一頁一重點」過關）、"
                         "或關卡② 之後改了題目 —— 預設保留是為了護住協調者在 Step 4 的整形，"
                         "但它也會把 builder 的修正吃掉（B17-8），merge 會逐欄印出被保留的差異")
    a = ap.parse_args()

    # ⛔ 整段「讀 deck.json → 改 → 寫回」要在同一把鎖裡（N103）。
    #    為什麼：`SKILL.md` 明訂兩條主線的 slide_builder **平行跑**，而每個 builder 的
    #    交件自驗都是 `verify.py --thread <線>`，它的第一步無條件跑這支。
    #    實測（同一份 deck、兩個背景程序同時跑，8 輪撞到 4 輪）：後到的那個
    #    `json.load` 讀到**寫到一半的 deck.json** → `JSONDecodeError: Expecting value` →
    #    merge FAIL → 那條線的 builder 被判紅燈，而它自己那條線一個錯都沒有。
    #    ⚠️ 鎖檔另開（`deck.json.lock`），⛔ 不要鎖 deck.json 本身：
    #    以 "w" 開它就會先截斷，等於在拿鎖之前就把交付物清空。
    #    ⚠️ 呼叫端已經拿著同一把鎖時**不要再拿**（`verify.py --thread` 會把整段自驗
    #    包在鎖裡）——flock 是綁在「開檔」上的，父程序持有、子程序另外開一次去拿，
    #    會直接卡死。用環境變數交接，⛔ 不要靠猜。
    if os.environ.get("WD_DECK_LOCK_HELD") == a.deck:
        run(a)
        return
    lock = open(a.deck + ".lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        run(a)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def outline_page(deck, existing=None):
    """全場 outline 的內容**逐字**來自 deck.threads；single 時列 user_points。"""
    threads = deck.get("threads") or []
    single = (deck.get("plan") or {}).get("mode") == "single" or len(threads) == 1
    if single and threads:
        items = [{"n": str(i), "t": u} for i, u in enumerate(threads[0].get("user_points") or [], 1)]
    else:
        items = [{"n": str(i), "t": t.get("title", ""), "d": t.get("summary", "")}
                 for i, t in enumerate(threads, 1)]
    page = dict(existing or {"id": "OUT", "type": "agenda", "title": "Outline", "source": []})
    page["type"] = "agenda"
    page.pop("thread", None)
    page["body"] = {"items": items}
    return page, single


def merge_strings(deck_path, slices):
    """把 slice 旁邊的 `strings.<線>.zh.json`（builder 交的逐線譯文片段）併進 `strings.zh.json`。

    ⭐ PR 2 之後中文譯文由**寫英文的那個 builder** 一起寫（它手上有全部脈絡，多付的只是
    output token），每條線一份片段；這裡合成全場一份。片段的值非空就蓋掉既有值。
    """
    out_dir = os.path.dirname(os.path.abspath(deck_path))
    dest = os.path.join(out_dir, "strings.zh.json")
    cur = {}
    if os.path.isfile(dest):
        cur = json.load(open(dest, encoding="utf-8"))
    n_files = n_keys = 0
    dirs = {os.path.dirname(os.path.abspath(p)) for p in slices}
    for d in sorted(dirs):
        for f in sorted(os.listdir(d)):
            if not (f.startswith("strings.") and f.endswith(".zh.json")):
                continue
            try:
                part = json.load(open(os.path.join(d, f), encoding="utf-8"))
            except (OSError, ValueError) as ex:
                print(f"[merge] ⚠️ {f} 讀不了，跳過：{ex}")
                continue
            n_files += 1
            for k, v in (part or {}).items():
                if v not in (None, ""):
                    cur[k] = v
                    n_keys += 1
                else:
                    cur.setdefault(k, "")
    if n_files:
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(cur, fh, ensure_ascii=False, indent=2)
        print(f"[merge] 併入 {n_files} 份 strings.<線>.zh.json（{n_keys} 句）→ {dest}")


def run(a):
    deck = json.load(open(a.deck, encoding="utf-8"))
    old = {s["id"]: s for s in deck.get("slides", [])}

    new = {}
    slice_order = {}          # thread → [slide id …]（slice 內的順序，B17-12）
    for p in a.slices:
        if not os.path.isfile(p):
            sys.exit(f"[merge] 找不到 {p}")
        j = json.load(open(p, encoding="utf-8"))
        # ⚠️ 兩種形狀都收：裸陣列 `[...]`，或 `{"thread": "...", "slides": [...]}`。
        #    規格只寫「這條主線的 `slides[]` 陣列片段」，兩種讀法都講得通，
        #    而 `check_gate.py` 讀的是 `j.get("slides")`（**期待 dict**），
        #    這裡卻直接 `for s in json.load(...)`（**期待裸陣列**）——兩支腳本互相矛盾。
        #    實跑三個 builder 都選了 dict，於是這裡 TypeError 當場炸掉。
        #    ⛔ 不要只改一邊：兩種都收，規格那句也已經改寫清楚。
        if isinstance(j, dict):
            j = j.get("slides") or []
        if not isinstance(j, list):
            sys.exit(f"[merge] {p} 不是 slides 陣列，也不是 {{'slides': [...]}}：{type(j).__name__}")
        for s in j:
            if not isinstance(s, dict) or "id" not in s:
                sys.exit(f"[merge] {p} 裡有一筆不是投影片物件（缺 id）：{str(s)[:60]}")
            new[s["id"]] = s
            slice_order.setdefault(s.get("thread"), []).append(s["id"])

    kept, out = [], []
    for s in deck.get("slides", []):
        sid = s["id"]
        if sid not in new:
            out.append(s)
            continue
        n = dict(new[sid])
        if not a.no_keep:
            for k in KEEP:
                if k in s and s.get(k) != n.get(k):
                    # B17-8：⛔ 靜默吃掉 builder 的修正、還印 OK，是這支曾經有的病。
                    #    值不同就把**兩邊**印出來，並指路 --no-keep；判斷留給人，
                    #    但一定要看得見。
                    kept.append((sid, k, s.get(k), n.get(k)))
                    n[k] = s.get(k)
        out.append(n)

    # ⭐ **第一次合併**：deck.json 的 slides 還是空的，上面那個迴圈一頁都不會產出。
    #    舊版沒有這一段，於是首次跑必然得到 0 頁，而且 **exit 0、還印「N 頁併入」**——
    #    整份 deck 是空的，沒有任何東西報錯（實跑當場踩到）。
    #    ⛔ 不要靠「先手動把 deck.draft.json 抄成 deck.json」補救：
    #    那一步沒有寫在任何流程裡，而且抄過去的是候選頁、不是 builder 產的頁。
    seen = {s["id"] for s in out}
    order = {t.get("id"): t.get("order", i)
             for i, t in enumerate(deck.get("threads", []), 1)}
    added = [s for sid, s in new.items() if sid not in seen]
    added.sort(key=lambda s: (order.get(s.get("thread"), 99),
                              s.get("n", 0), s.get("id", "")))
    out += added

    # B17-12：**線內的頁序以 slice 為準**。舊版把後補的頁一律接在最後 ——
    #    builder 補一張 B0 outline 放在 slice 最前面，merge 之後它變成整份 deck 的
    #    最後一頁，而且沒有任何檢查會抓到（outline 存不存在有人驗、位置沒有）。
    #    線與線之間的先後不動（照 deck 既有位置／threads 順序），只重排線內。
    #    slice 裡沒有的頁（deck 獨有）接在該線之後、維持原相對順序。
    out, moved = reorder_by_slice(out, slice_order)

    # ⭐ --outline：全場 outline 由腳本產／更新，放最前（PR 2；B17-4）
    if a.outline:
        idx = [i for i, s in enumerate(out) if s.get("type") == "agenda" and not s.get("thread")]
        page, single = outline_page(deck, out[idx[0]] if idx else None)
        for i in reversed(idx):
            out.pop(i)
        out.insert(0, page)
        print(f"[merge] 全場 outline {'更新' if idx else '新增'}：{len(page['body']['items'])} 項"
              f"（{'single：列 user_points' if single else 'multi：一條線一列'}）")

    # from 逐字接前一頁的 to（換線／結構頁重置）
    prev, fixed = None, []
    for s in out:
        if s.get("type") in STRUCT:
            prev = None
            continue
        if prev is not None and prev.get("thread") == s.get("thread") and prev.get("to"):
            if s.get("from") != prev["to"]:
                fixed.append(s["id"])
            s["from"] = prev["to"]
        prev = s
    deck["slides"] = out

    # ⛔ **刻意不同步 `plan.slide_plan`**（N100，批次 5g）。
    #    這裡原本有一段迴圈想把 `must_numbers`／`point` 從版面回填 slide_plan，
    #    它是**死碼**：迴圈讀 `x.get("thread")` 與 `x.get("n")`，而 slide_plan 的
    #    項目 schema 是 `{point, pages, body}`（deck_schema.md）→ `i = -1` 恆成立，
    #    **迴圈體一次都沒有執行過**，不印任何東西、exit 0。
    #    ⭐ 但正解不是「修好它」——那段程式的**模型本身是錯的**：
    #    `slide_plan` 是**逐線一項**（這條線要講什麼、幾頁、主體用什麼），
    #    不是逐頁；把某一頁的 `point`／`must_numbers` 蓋上去等於張冠李戴。
    #    ⚠️ 而且**靜默同步會把差異抹掉**：`slide_plan` 是使用者在關卡② 拍板的
    #    那一份，「說好 3 頁、實際做出 5 頁」正是 `check_deck.py` 要當成 ERROR
    #    報出來的東西（它拿 slide_plan 對帳）。同步 = 把對帳的另一邊改成一樣，
    #    那道檢查就永遠通過。**要留下差異，不要消滅差異。**

    # ⛔ 先寫暫存檔再 `os.replace` —— 換名是原子的（N103）。
    #    鎖只擋得住同樣拿鎖的 merge；`check_deck.py`／`render_deck.py` 是**沒拿鎖的讀者**，
    #    直接寫回去的話它們一樣讀得到寫到一半的 deck.json。
    tmp = a.deck + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(deck, f, ensure_ascii=False, indent=2)
    os.replace(tmp, a.deck)
    print(f"[merge] {len(new)} 頁併入 {a.deck}（共 {len(out)} 頁）")
    if a.slices and not a.no_strings:
        merge_strings(a.deck, a.slices)
    if kept:
        print(f"[merge] ⚠️ {len(kept)} 個欄位 slice 與 deck.json **不一致**，保留 deck.json 的值"
              f"（KEEP = {'/'.join(KEEP)}）：")
        for sid, k, dv, nv in kept:
            print(f"        {sid}.{k}\n"
                  f"          deck.json（保留）：{_short(dv)}\n"
                  f"          slice   （丟棄）：{_short(nv)}")
        print("        ⭐ 若 slice 那邊才是對的（builder 修了 point／output），"
              "重跑一次加 --no-keep；⛔ 這一行不是 OK，是「有差異、我選了 deck」。")
    if moved:
        print(f"[merge] 線內頁序依 slice 重排：{'、'.join(moved)}")
    if fixed:
        print(f"[merge] from 接回前一頁的 to：{'、'.join(fixed)}")
    print("[merge] ⛔ 下一步一定要跑 check_deck.py，不要直接 render。")


if __name__ == "__main__":
    main()
