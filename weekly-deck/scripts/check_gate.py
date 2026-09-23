#!/usr/bin/env python3
"""關卡檢查 —— 在**每一層結束時**跑，不要等到 Step 4。

## 為什麼有這支

`check_deck.py` 是唯一會擋的檢查，但它跑在 **Step 4**，也就是三個關卡全部之後。
它驗的正是關卡①② 的產物（`plan.answers`、`slide_plan_confirmed`、`user_points`），
於是流程上可以一路做到 layer3 再回頭補填 —— **關卡①② 在機械上並不存在，
它們只是散文**。首次實跑那次三個關卡都有跑（`layer1.md` 14:03、
`layer2.T1.md` 也都在），但使用者的感覺是關卡好像都沒有跳出來，
因為沒有任何東西在它們該發生的時候擋住。

這支把關卡變成機械的：**沒過就不准進下一層。**

⚠️ 它驗得了「有沒有這個檔、欄位齊不齊、順序對不對」，
**驗不了「答案是不是真的出自使用者」** —— 那沒有辦法用程式驗。
所以 `answers` 一律要求逐字抄原話並標日期，讓造假至少留下痕跡。

用法：
  check_gate.py layer1 <out>     # <out> ＝ 週報的**日期目錄**（不是 _work 子目錄）
  check_gate.py layer2 <out>     # layer2 結束、進 layer3 之前
  check_gate.py layer3 <out>     # layer3 結束、進 pptx 之前

⚠️ 關卡產物住在 `<out>/_work/2_layer1`、`_work/3_layer2`。
   **舊結構的週報（`<日期>/deck/` 扁平放）會報「缺 layer1.md」—— 那是預期的**：
   關卡只服務**進行中**的那一份，已經報告過的週不會再跑它。
"""
import argparse, json, os, sys

import paths

# `point` 的字數上限 —— ⛔ **不要在這裡另外訂一個數字**。
# 唯一的定義在 check_deck.py 的 `LIMITS["point"]`，這裡直接 import 過來：
# 同一事實寫兩個地方必定分岔（本 repo 已知坑 #13）。改上限請改 check_deck.py 那一處。
# 下面的 fallback 只是為了讓 check_gate 在 check_deck 匯入失敗時仍跑得動，
# 走到它會印一行提醒 —— ⛔ 它不是第二份定義。
try:
    from check_deck import (LIMITS as _DECK_LIMITS, MAX_MAIN as _DECK_MAX_MAIN,
                            MAX_PER_THREAD as _DECK_MAX_PER_THREAD,
                            SLOT_EXEMPT as _DECK_SLOT_EXEMPT)
    MAX_POINT = _DECK_LIMITS["point"]
    _POINT_SRC = "check_deck.LIMITS['point']"
    # N64：頁數上限同理 —— 這裡數的是關卡① 的**預估**頁數（那時還沒有頁），
    # check_deck 數的是 Step 4 的**真實**頁數。量的東西不同是刻意的，
    # 但**數字只有一份**，⛔ 不要在這裡再寫一次 15。
    MAX_MAIN_EST = _DECK_MAX_MAIN
    # B17-3：單線的週要用**單線**上限（`MAX_PER_THREAD`），不是多線的 15 ——
    # 否則一份已經超過單線上限的規劃在關卡① 完全不會被警告。
    MAX_PER_THREAD_EST = _DECK_MAX_PER_THREAD
    SLOT_EXEMPT = _DECK_SLOT_EXEMPT
except Exception as _ex:                                   # pragma: no cover
    MAX_POINT, _POINT_SRC = 90, f"fallback（讀不到 check_deck：{_ex}）"
    MAX_MAIN_EST = 15
    MAX_PER_THREAD_EST = 7
    SLOT_EXEMPT = {"buildup", "problem", "intro", "result"}   # N99 的 fallback

# N117 ①：layer3 的 `must_numbers` 對帳要問「這個數字畫在頁上了嗎」——
# ⛔ 那個判斷只有 check_deck 一份（`number_on_page`），這裡**借用**、不重寫。
# 借不到就讓那條檢查整條退場並出聲（⛔ 不要退回自己寫一個近似的：兩份必定分岔）。
try:
    from check_deck import (texts as _texts, svg_text_only as _svg_text,
                            number_on_page as _on_page, dropped_map as _dropped_map)
    _CAN_READ_PAGE, _PAGE_ERR = True, None
except Exception as _ex2:                                  # pragma: no cover
    _CAN_READ_PAGE, _PAGE_ERR = False, _ex2

# 結構頁（cover／agenda／thread-intro）不對應 layer2 的任何一頁 ——
# ⛔ 這份名單只有 merge_slides.STRUCT 一份定義，借用不重抄。
try:
    from merge_slides import STRUCT as _STRUCT
except Exception:                                          # pragma: no cover
    _STRUCT = {"cover", "agenda", "thread-intro"}

# 三個關卡的產物分別住在哪 —— ⛔ 不要在這裡寫死字串路徑，
# 目錄形狀只有 paths.WORK_STAGES 一份定義（同一事實寫兩個地方，必定分岔）。

E, W = [], []
def err(m): E.append(f"  [ERROR] {m}")
def warn(m): W.append(f"  [WARN ] {m}")


def load(path):
    if not os.path.isfile(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        err(f"{os.path.basename(path)} 讀不了：{ex}")
        return None


def as_list(val, tid, field, hint):
    """欄位一律要是 list —— 型別不對就給**一則清楚的**錯誤，回傳 (list, ok)。

    ⚠️ 後補（N1）：`user_points` 曾經在草稿階段被填成字串 `"PENDING_USER"`，
    而下游直接 `len()` 它 → 報「線「A」有 **12** 個 user_points」（那是字串的
    **字元數**），再對那 12 個字元各噴一次「members_without_point 有一筆沒有 sid」。
    12 個一模一樣、完全誤導的 ERROR，真正的問題（值根本還沒填）反而看不見。
    ⛔ 不要用 `or []` 把型別錯誤吞掉：吞掉之後它會在別的地方以錯誤的面貌爆出來。
    """
    if val is None:
        return None, True
    if isinstance(val, list):
        return val, True
    err(f"線「{tid}」的 {field} 是 {type(val).__name__} 不是 list（值：{str(val)[:60]!r}）"
        f"—— {hint}")
    return [], False


def _threads(out):
    """關卡① 定案的主線清單（id → 該線的 user_points）。

    ⚠️ 型別不對的線一律當成空清單（錯誤由 gate1 報一次就好，
    這裡不能讓字串流進去被 `len()` 當成字元數數）。
    """
    j = load(os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json")) or {}
    out_ = {}
    for t in (j.get("threads") or []):
        if not t.get("id"):
            continue
        ups = t.get("user_points")
        out_[t["id"]] = ups if isinstance(ups, list) else []
    return out_


SPEC_OF = {"layer2": "subagent-slide-planner.md",
           "slides": "subagent-slide-builder.md"}


def _spec_path(stage):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", SPEC_OF.get(stage, ""))


# 圖表誠實性 6 問（N71）—— ⭐ 唯一的定義在 `presentation_rules.md §8`，
# 這裡只是那六問的**欄位名**，⛔ 不是第二份判準。
HONESTY_6 = {
    "filter":      "篩選條件（⛔「沒有篩選」也要寫出來）",
    "averaging":   "有沒有把異質的東西平均掉",
    "axis_label":  "軸標籤講的是「什麼」還是「哪裡」",
    "multiplicity": "多重比對的深度",
    "truncation":  "邊界有沒有被截斷的資料",
    "control":     "對照組在不在同一張圖",
}

# check_must_numbers() 的逐線判決 —— check_spec_fresh 的義務① 讀它，
# ⛔ 不要重算一次（同一件事算兩次必定分岔）。gate3 保證前者先跑。
_MN_VERDICT = {}


def _spec_obligations(out, stage, tid, j):
    """`slide_builder` 的交件義務，**逐條看檔案上有沒有證據**（N117 ②）。

    回傳 `(unmet, met)` 兩串人話。⛔ 只列**這一關看得見**的義務：
    第三件（代價欄逐列可數，§2b）由 `check_deck.py` 驗，⛔ 這裡不重複也不假裝驗過。

    ⚠️ `stage` 不是 slides 時回 `([], [])` —— layer2 沒有對應的義務清單，
    那一層維持原本的行為（⛔ 不要順手把 planner 也綁進來，那是另一件事）。
    """
    if stage != "slides" or not isinstance(j, dict):
        return [], []
    unmet, met = [], []

    # ── 義務①：must_numbers 逐字帶過來、砍掉要留痕 ──────────────
    v = _MN_VERDICT.get(tid)
    if v is None:
        unmet.append("① must_numbers 對帳沒跑到（⛔ 這不是通過）")
    elif v:
        unmet.append(f"① must_numbers 對帳有 {v} 條紅字 —— ⛔ 上面那幾條才是實話")
    else:
        met.append("① must_numbers 帳目閉合")

    # ── 義務②：圖表誠實性 6 問 ────────────────────────────────
    # ⭐ 病根就在這件：規格只要求「答案寫進 DONE 回報」——那是**對話**，
    #   檔案上零痕跡。於是 mtime 一舊，根本沒有東西可以逐條對帳
    #   （回填一個欄位就把時間戳帶新，這條檢查對那兩份產物直接失效）。
    #   ⛔ 修法不是放寬，是讓它**落地成檔案欄位**。
    slides = (j.get("slides") if isinstance(j, dict) else None) or []
    figs = [s for s in slides if isinstance(s, dict)
            and str(((s.get("body") or {}) if isinstance(s.get("body"), dict)
                     else {}).get("src") or "").lower().endswith(".svg")]
    missing, holes = [], []
    for s in figs:
        h = s.get("honesty")
        if not isinstance(h, dict):
            missing.append(str(s.get("id")))
            continue
        gaps = [k for k in HONESTY_6 if not str(h.get(k) or "").strip()]
        if gaps:
            holes.append(f"{s.get('id')}（缺 {'、'.join(gaps)}）")
    if not figs:
        pass                      # 這條線沒有主圖，⛔ 不是義務沒做
    elif missing or holes:
        unmet.append("② 圖表誠實性 6 問（§5b）"
                     + (f"：{len(missing)} 張主圖完全沒有 `honesty`"
                        f"（{'、'.join(missing)}）" if missing else "")
                     + (f"；{len(holes)} 張答不齊（{'；'.join(holes)}）" if holes else "")
                     + "。\n             ⛔ 寫進 `DONE` 回報**不算證據** —— 那是對話，"
                       "檔案上留不下東西，\n"
                       "             而這條檢查要問的正是「檔案上有沒有」"
                       "（⭐ 這就是 N117 ② 的病根）")
    else:
        met.append(f"② 誠實性 6 問（{len(figs)} 張主圖逐問有答）")
    return unmet, met


def check_spec_fresh(out, stage, prefix, role):
    """產物是不是照**現在這一版**規格產的（後補）。

    ⚠️ 擋的是這個形狀：規格改版之後，上一輪留下的中間產物**看起來完全正常**
    （欄位在、關卡過），但它是照舊規格產的。實測撞過一次：
    `slide_plan` 被改名成 `pages`、新增 `gate1`／`gate2`／`buildup_note`，
    而舊的 `layer2.T*.json` 三份都還在，`check_gate` 只報「缺 .md」，
    看不出「json 是舊規格產的」——md 若剛好也寫完了，關卡就會**通過**。

    ⛔ 刻意**不**要求 subagent 自己填 `spec_version`：那是它會忘記的欄位，
    而忘記的後果又是靜默的。改用時間戳，不需要任何人配合。

    ## ⚠️ N117 ②：時間戳是**代理指標**，不是義務清單

    實測撞過反方向：協調者把 `must_numbers` 逐字回填進 `slides.A/B.json`，
    mtime 一新，這條的 2 個 ERROR **當場消失、關卡轉綠** —— 但 5e 給 builder 的
    三件交件義務只做了第一件。⭐ **這條分不出「補了一個欄位」與「照新規格重做過」。**

    ⛔ 解法不是換成 subagent 自填 `spec_version`（上一段已經否決過），
    而是 **mtime 只留作觸發器**：時間一舊就**逐條對帳那三件義務**
    （`_spec_obligations()`）。⭐ 差別在於它問的是**檔案上有沒有證據**，
    ⛔ 不是問「你有沒有確認過」—— 後者就是 `spec_reviewed` 變成橡皮章的原因。

    ⚠️ 於是 `spec_reviewed` 的權力被**縮小**（⛔ 不是拿掉）：它仍然放行得了
    「規格只是把話講清楚」這種改動，但 ⛔ **它消不掉義務層的紅字** ——
    義務沒有證據就是沒有證據，那跟規格改了幾個字無關。
    """
    spec = _spec_path(stage)
    if not os.path.isfile(spec):
        return
    sm = os.path.getmtime(spec)
    d = paths.work_dir(out, stage)
    for tid in sorted(_threads(out)):
        f = os.path.join(d, f"{prefix}.{tid}.json")
        if os.path.isfile(f) and sm > os.path.getmtime(f):
            # ⚠️ 這條分不出「規格實質改變」與「規格只是把話講清楚」——
            #    實跑當場誤判過：規格的兩處改動一個是**放寬**（中文數字例外）、
            #    一個是**描述既有行為**（輸出形狀二選一），都不影響已產出的內容。
            #    ⛔ 解法不是偷偷 touch 時間戳（那會讓這條檢查變成裝飾），
            #    而是要求協調者**具名放行並寫下理由** —— 造假至少留下痕跡。
            j = load(f) or {}
            ack = j.get("spec_reviewed") if isinstance(j, dict) else None
            # ── N117 ②：先逐條對帳義務，⛔ 再看有沒有具名放行。
            #    順序是刻意的：具名放行 ⛔ **消不掉**義務層的紅字。
            unmet, met = _spec_obligations(out, stage, tid, j)
            if unmet:
                err(f"{prefix}.{tid}.json 比角色規格 {os.path.basename(spec)} 舊，"
                    f"而 **{role} 的交件義務有 {len(unmet)} 件在檔案上找不到證據**：\n"
                    + "".join(f"           ✗ {u}\n" for u in unmet)
                    + "".join(f"           ✓ {m}\n" for m in met)
                    + "           ⭐ 時間戳只是**觸發器**：它分不出「補了一個欄位」與"
                    "「照新規格重做過」（N117 ②，實測撞過）。\n"
                    + ("           ⚠️ 這份有 `spec_reviewed` 具名放行，"
                       "⛔ 但那放行的是**規格改動**，消不掉上面那幾條 —— \n"
                       "           義務沒有證據就是沒有證據，跟規格改了幾個字無關。\n"
                       if ack else "")
                    + f"           修法：重派 {role} 補齊上面打 ✗ 的那幾件"
                    "（⛔ 不要只 touch 時間戳，那會讓這條變裝飾）。")
                continue
            if met:
                warn(f"{prefix}.{tid}.json 比角色規格 {os.path.basename(spec)} 舊，"
                     f"但 {role} 的 {len(met)} 件交件義務**逐條對帳過、檔案上有證據**："
                     f"{'；'.join(met)}\n"
                     f"        ⭐ 這一條是**證據**換來的，⛔ 不是具名放行換來的。")
                continue
            if ack:
                warn(f"{prefix}.{tid}.json 比角色規格 {os.path.basename(spec)} 舊，"
                     f"但已具名放行：{str(ack)[:90]}")
                continue
            err(f"{prefix}.{tid}.json 比角色規格 {os.path.basename(spec)} **舊** ——\n"
                f"           規格在這份產物寫出來之後改過，它是照**舊版**產的。\n"
                f"           ⛔ 不要直接沿用（欄位可能被改名，關卡驗得過但內容對不上）：\n"
                f"           重派 {role} 重產一次；\n"
                f"           若你**逐項確認過那次規格改動不影響這份產物**，"
                f"在該 json 加 `spec_reviewed: \"<理由>\"` 具名放行。")


def check_per_thread(out, stage, prefix, layer_name, role):
    """**逐線產物必須存在，且互不越界** —— 派遣紀律的機械化。

    ## 為什麼不是「記一筆就好」

    規格（`delegation.md`）一直寫著「每條主線派一個 subagent，平行跑」，
    但**沒有任何東西在驗**。而這個 skill 已經量過同一個形狀的失效：
    `check_deck.py` 的註解記著「規格早就寫著每頁都要對得上一個 user_point，
    首次實跑實測——**規格寫了、planner 沒照做**，七頁裡只有兩頁對得上」。
    **散文擋不住事情，只有會 exit 1 的東西擋得住。**

    ## 這支驗得了什麼、驗不了什麼

    ✅ **驗得了**（你在意的兩種失效）：
      · 某條線**被整條漏掉** —— 少一個 `<prefix>.<線id>.json` 就 exit 1
      · **一個 agent 全包** —— 若某條線的檔裡出現**別條線的** user_point，
        代表寫它的人手上有全部主線的素材，那不是隔離的 subagent

    ⛔ **驗不了**：orchestrator 到底有沒有真的呼叫 Agent 工具、是不是在同一則訊息
       裡發出去（＝真平行）。**沒有任何腳本看得到那件事** —— 腳本只看得到檔案。
       所以這裡不驗「有沒有派」，改驗**派了才生得出來的形狀**。
       ⚠️ 不要在文件裡把它寫成「保證平行」，那是過度宣稱。
    """
    ids = _threads(out)
    if not ids:
        return                                   # 關卡① 自己會報缺
    d = paths.work_dir(out, stage)
    ls = os.listdir(d) if os.path.isdir(d) else []
    for tid, own in sorted(ids.items()):
        fn = f"{prefix}.{tid}.json"
        if fn not in ls:
            err(f"線「{tid}」沒有 {fn} —— {layer_name} 規定**每條主線派一個 "
                f"{role}**（`delegation.md`）。\n"
                f"           少一條線的產物 = 那條線沒有被單獨處理。"
                f"⛔ 不要把兩條線寫進同一個檔。")
            continue
        j = load(os.path.join(d, fn)) or {}
        # 越界檢查：這個檔裡不該出現別條線的 user_point
        others = {u for k, v in ids.items() if k != tid for u in v}
        if not others:
            continue
        pages = j.get("slide_plan") or j.get("pages") or j.get("slides") or []
        for i, pg in enumerate(pages, 1):
            up = pg.get("user_point")
            if up and up in others and up not in own:
                err(f"{fn} 第 {i} 頁的 user_point 屬於**別條線**："
                    f"「{str(up)[:40]}」\n"
                    f"           一個 {role} 只看自己那條線。出現別條線的內容，"
                    f"代表這幾條線是同一個 agent 一起做的。")


def gate1(out):
    """關卡① —— 主線與 user_points 由使用者定案。"""
    d1 = paths.work_dir(out, "layer1")
    dm = paths.work_dir(out, "materials")
    md = os.path.join(d1, "layer1.md")
    if not os.path.isfile(md):
        err("缺 layer1.md —— 關卡① 交給使用者看的就是這一份，沒有它等於沒有關卡")
    j = load(os.path.join(d1, "layer1_confirmed.json"))
    if j is None:
        err("缺 layer1_confirmed.json —— 關卡① 尚未定案。"
            "⛔ 不要往 layer2 走，先把主線清單交給使用者確認")
        return
    if not j.get("confirmed_by"):
        err("layer1_confirmed.json 缺 confirmed_by —— 誰確認的？沒人確認就不是關卡")
    if not j.get("narrative"):
        err("缺 narrative（本週敘事一句話）—— 這句由**使用者**組出來，不是 agent 擬")
    threads = j.get("threads") or []
    if not threads:
        err("threads 是空的")
    ids = {}                    # 只收型別正確的線：id → user_points（list）
    for t in threads:
        tid = t.get("id") or "?"
        ups, ok = as_list(t.get("user_points"), tid, "user_points",
                          "它是**使用者親口列出的重點清單**（一個 list）。"
                          "草稿階段的佔位字串（例如 \"PENDING_USER\"）代表這一題還沒問到答案，"
                          "⛔ 定案前要換成真正的清單，不要留佔位值。")
        if not ok:
            continue            # 型別已經報過一次，⛔ 不要再拿它去 len()
        ids[tid] = ups = ups or []
        if not ups:
            err(f"線「{tid}」沒有 user_points —— 關卡① 漏問了那一題"
                "（「這條線如果只講 3~4 個重點，是哪幾個」）。"
                "⛔ 這一題不得由 agent 代擬，它直接決定有哪幾頁")
        elif len(ups) > 5:
            warn(f"線「{tid}」有 {len(ups)} 個 user_points —— 超過 4~5 個通常代表"
                 "這條線該拆兩條，回頭問使用者")
    # ── 頁數預估：在關卡① 就先算出來（後補）──────────────────
    # ⚠️ 這是**提醒不是擋關**。頁數 = Σ(每條線的 user_points 數 + result 頁)，
    #    而 user_points 是使用者親口指定的 —— 機械沒有資格判它太多。
    # 為什麼要在這裡算：以前要到 layer2 規劃完才看得到總頁數，那時圖都想過了，
    #    回頭砍是最貴的一刀。在關卡① 減一個重點只是改一行字。
    #    ⑦ 削減回合（slide_planner §7）是「規劃完再收」，這個是「規劃前先攔」，兩者互補。
    est = [(tid, len(ups) + 1) for tid, ups in sorted(ids.items())]
    if est:
        total = sum(n for _, n in est)
        detail = "、".join(f"{t} {n-1} 點+1 = {n}" for t, n in est)
        # B17-3：上限跟著 mode 走。單線的週（或只有一條線）用單線上限，
        # 多線的週用全場上限；兩個數字都只有 check_deck 一份，這裡只是借用。
        single = (j.get("mode") == "single") or len(est) == 1
        limit = MAX_PER_THREAD_EST if single else MAX_MAIN_EST
        kind = "單線上限" if single else "主線上限"
        if total > limit:
            warn(f"頁數預估 {total} 頁（{detail}）—— 超過{kind} {limit}"
                 f"（mode={j.get('mode')!r}）。\n"
                 "        ⛔ 這裡不擋（user_points 是使用者指定的），但**現在減最便宜**：\n"
                 "        少給一個重點 = −1 頁；一條線降 backup = −(該線點數+1) 頁；"
                 "說某條線不要 result = −1 頁。\n"
                 "        ⚠️ B17-2：「Σ user_points ＋ result」只是**預估**，result 頁要在"
                 "上限的額度內擇一 —— 給滿上限個重點就沒有 result 頁的位置。\n"
                 "        等到 layer2 規劃完才砍，圖都已經想過了。")
        else:
            print(f"[gate] 頁數預估 {total} 頁（{detail}）　{kind} {limit}")
        # 多線的週也要逐線看：某一條線自己就撞單線上限，全場沒超也擋不住它。
        if not single:
            for t, n in est:
                if n > MAX_PER_THREAD_EST:
                    warn(f"線「{t}」預估 {n} 頁，超過單線上限 {MAX_PER_THREAD_EST} —— "
                         f"先問這條線是不是該拆成兩條，或少給一個重點")

    # ── 線內落單成員：members 有、user_points 沒有的那幾個 sid（後補）──
    # ⚠️ 這是兩套帳在同一條線上對不起來：members 涵蓋每個 sid，
    #    user_points 是使用者只選的那幾個重點，頁數等於 user_points 數。
    #    使用者少選一個重點，就會有成員「上了主線卻沒有頁」——
    #    而 check_deck.py 的對帳只認「上投影片 or plan.dropped」，
    #    slide_planner 又禁止把它們塞進 notes 復活 → 那幾個 sid 會無處可去。
    #    規格見 subagent-thread-finder.md §5a。⛔ 去處由使用者填，這裡只驗有沒有填。
    OK_WHERE = {"口頭", "backup", "不講"}
    for t in threads:
        tid = t.get("id") or "?"
        mem, ok_m = as_list(t.get("members"), tid, "members",
                            "它是這條線涵蓋的 sid 清單（一個 list）")
        if not ok_m or tid not in ids:
            continue            # user_points／members 型別錯：已經各報過一次
        mem, ups = mem or [], ids[tid]
        if not mem or not ups or len(mem) <= len(ups):
            continue
        mwp = t.get("members_without_point")
        if mwp is None:
            warn(f"線「{tid}」有 {len(mem)} 個 members 但只有 {len(ups)} 個 user_points ——"
                 f"至少 {len(mem)-len(ups)} 項會**上了主線卻沒有頁**。\n"
                 "        要嘛它們真的被某一頁的 source 涵蓋，要嘛就要在 "
                 "members_without_point 逐個寫去處（口頭／backup／不講）。\n"
                 "        ⛔ 去處由使用者決定，不得由 agent 代填"
                 "（thread-finder §5a）")
            continue
        mwp, ok_w = as_list(mwp, tid, "members_without_point",
                            "它是**逐個**落單 sid 的去處清單，每筆是 "
                            "{sid, where, why} 物件")
        if not ok_w:
            continue
        listed = set()
        for e in mwp:
            if not isinstance(e, dict) or not e.get("sid"):
                err(f"線「{tid}」的 members_without_point 有一筆不是 "
                    f"{{sid, where, why}} 物件、或缺 sid：{str(e)[:60]!r}")
                continue
            sid = e.get("sid")
            listed.add(sid)
            if sid not in mem:
                err(f"線「{tid}」的落單成員「{sid}」不在這條線的 members 裡 ——"
                    "落單成員只能是**本線**的 sid")
            elif e.get("where") not in OK_WHERE:
                err(f"線「{tid}」的落單成員「{sid}」where="
                    f"{e.get('where')!r} —— 只能是 口頭／backup／不講")
            elif not e.get("why"):
                err(f"線「{tid}」的落單成員「{sid}」沒有寫 why")
        # ── 完整性：落單的**每一個** sid 都要有著落（後補，N2）──────────
        # ⚠️ 原本只在 members_without_point **整個沒填**時發 WARN，
        #    於是「填了一筆」就等於把這道檢查關掉：實測 A 線 14 members／
        #    4 user_points（10 項落單）只填 2 筆，警告完全消失、另外 8 項無聲通過。
        #    ⛔ 有沒有填 ≠ 填完了。這裡改成對**數量**：至少 len(members)−len(user_points)
        #    個 sid 要被點名。
        # ⚠️ 這裡只能是 WARN 不是 ERROR：關卡① 還沒有頁，
        #    剩下那幾個 sid 有可能真的被某一頁的 source 涵蓋（那不是錯）。
        #    但它**不得再是靜默的** —— 缺幾個、缺哪幾個都要印出來給使用者看。
        need = len(mem) - len(ups)
        if len(listed) < need:
            rest = [s for s in mem if s not in listed]
            err_sample = "、".join(rest[:12]) + ("…" if len(rest) > 12 else "")
            warn(f"線「{tid}」有 {len(mem)} 個 members、{len(ups)} 個 user_points ——"
                 f"至少 {need} 項落單，但 members_without_point 只寫了 "
                 f"{len(listed)} 筆，**還有 {need - len(listed)} 個 sid 沒有著落**。\n"
                 f"        沒被點名的 sid（{len(rest)} 個）：{err_sample}\n"
                 "        要嘛逐個寫進 members_without_point（口頭／backup／不講），"
                 "要嘛在關卡② 確認它們真的被某一頁的 source 涵蓋。\n"
                 "        ⛔ 去處由使用者決定，不得由 agent 代填（thread-finder §5a）")

    if len(threads) > 4:
        err(f"threads 有 {len(threads)} 條（上限 4）——"
            "第 5 條以後要放 overflow_threads 並問使用者")
    # 合併提名要被裁決過（後補，見 SKILL.md「選材之前先合併」）
    # ⚠️ 後修：這裡原本寫成條件式「**如果**跑過 merge_items.py 但沒裁決 → 擋」，
    #    於是「**根本沒跑**」那條路徑整個漏掉 —— 實測 exit=0 靜默通過，
    #    合併整步被跳過而沒有人發現。那正是本專案一直在打的失效形狀。
    #    合併是 Step 1 的必經步驟，所以它的產物**無條件必須存在**。
    if not os.path.isfile(os.path.join(dm, "merge_groups.json")):
        err(f"缺 merge_groups.json（找的是 {dm}）—— Step 1 的 merge_items.py 沒有跑。\n"
            "           ⛔ **合併要在選材之前**：daily-log 的合併判準只在單日內生效，"
            "同一件事做三天就會變成三個看起來平行的候選\n"
            "           （實測：4 天 16 個 item，一件事佔 7 項，"
            "使用者回「太多東西要講，不知道重點該放哪」）")
    elif not j.get("merged_groups"):
        err("merge_items.py 跑了，但 layer1_confirmed.json 沒有 merged_groups ——\n"
            "           合併提名**沒有被裁決過**。機械只提名（同模組＋改同一批檔），"
            "語意的四條判準要 LLM 逐組確認、使用者拍板（editorial_policy §5a）")


def gate2(out):
    """關卡② —— 逐頁表由使用者確認。"""
    d2 = paths.work_dir(out, "layer2")
    ls = os.listdir(d2) if os.path.isdir(d2) else []
    mds = [f for f in ls if f.startswith("layer2") and f.endswith(".md")]
    if not mds:
        err(f"缺 layer2*.md（找的是 {d2}）—— 關卡② 交給使用者看的逐頁表不存在")
    j1 = load(os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json"))
    ups = {u for t in ((j1 or {}).get("threads") or [])
           for u in (t.get("user_points") or [])}
    n_plan = 0
    for f in sorted(ls):
        if not (f.startswith("layer2") and f.endswith(".json")):
            continue
        j = load(os.path.join(d2, f))
        if not j:
            continue
        pages = j.get("slide_plan") or j.get("pages") or []
        n_plan += len(pages)
        # ── 頂層 slide_plan_confirmed：關卡② 的定案標記（後補）────────────
        # slide_builder 的 Preflight 現在讀**這一欄**（不再去 deck.json 找），
        # 沒有它，layer2→layer3 又會退回「靠協調者口頭說已經確認過」。
        # B17-5：規格要求 planner 交件時填 `false`（`true` 是關卡② 之後協調者才設的），
        # 舊版用 falsy 判斷 → 照規格填 false 的人 100% 被 WARN，訊息還說成「舊檔沒這欄」。
        # 現在分兩種：**缺欄位**是 ERROR（新產的 layer2 一定要有）；`false` 只是
        # 「還沒確認」，印一行提醒 —— planner 自跑 gate2 時看到它是正常的。
        if "slide_plan_confirmed" not in j:
            err(f"{f} 沒有頂層 slide_plan_confirmed —— 那是 slide_builder "
                "Preflight 的擋關依據（這份逐頁表誰、什麼時候確認的）。\n"
                "           planner 交件時填 false，關卡② 過了由協調者改成 true；"
                "⛔ 缺欄位不是「還沒確認」，是規格沒照做。")
        elif not j.get("slide_plan_confirmed"):
            print(f"[gate] {f} 的 slide_plan_confirmed 仍是 false —— "
                  f"關卡② 過了才設 true；進 layer3 之前這一格一定要是 true")
        # ⚠️ 介紹頁與 result 頁**豁免**「一個 user_point 一頁」——
        #    它們不是使用者指定要講的重點，是支撐結構（slide_planner 規格
        #    「兩個必填欄位」那節）。但必須填 slot_reason 寫出哪個觸發成立。
        #    ⚠️ 這條以前沒實作：規格寫了豁免、這裡照擋，於是這道檢查實際上在
        #    **強迫「不要有 result 頁」** —— 實跑當場發生（三條線裡兩條乾脆不做 result）。
        # ⛔ 唯一定義在 check_deck.SLOT_EXEMPT（N99）——⛔ 不要在這裡另訂一份。
        #    以前這裡少了 `problem`，於是 problem 頁在關卡② 被 depth 預設成
        #    mechanism、被要求交 example，而 Step 4 反而豁免它（半修的 N11）。
        EXEMPT = SLOT_EXEMPT
        for i, p in enumerate(pages, 1):
            up = p.get("user_point")
            slot = (p.get("slot") or "").strip()
            # ── point 字數：在**關卡②** 就擋（後補，N18／F17）──────────
            # ⚠️ 這條以前完全不驗，要到 Step 4 的 check_deck.py 才爆
            #    （實測 9 頁的 point 84~161 字，7 個 ERROR）——
            #    那時圖都畫完了，兩個 builder 各多返工一輪。
            #    上限與 check_deck.py 同源（見檔頭 MAX_POINT），⛔ 不要在這裡另訂數字。
            pt = p.get("point")
            if pt is not None and not isinstance(pt, str):
                err(f"{f} 第 {i} 頁的 point 是 {type(pt).__name__} 不是字串："
                    f"{str(pt)[:60]!r}")
            elif pt and len(pt) > MAX_POINT:
                err(f"{f} 第 {i} 頁的 point 超過上限（{len(pt)} > {MAX_POINT} 字，"
                    f"上限來自 {_POINT_SRC}）：「{pt[:40]}…」\n"
                    "           ⛔ 現在改最便宜：一句話講不完通常代表這頁塞了兩個重點，"
                    "拆頁或把細節挪到 notes。\n"
                    "           拖到 Step 4 才爆的話，圖已經畫完了。")
            if not up and slot in EXEMPT:
                if not p.get("slot_reason"):
                    err(f"{f} 第 {i} 頁是 {slot} 頁（豁免 user_point），"
                        "但沒有 slot_reason —— ⛔ 不填就擋：要寫出是哪個觸發成立")
                continue
            if not up:
                err(f"{f} 第 {i} 頁沒有 user_point —— 每一頁都要對得上使用者說的"
                    "某一條重點（逐字）。\n"
                    f"           （只有 slot 是 {'／'.join(sorted(EXEMPT))} 的頁豁免，"
                    f"這一頁的 slot 是 {slot!r}）")
            elif ups and up not in ups:
                err(f"{f} 第 {i} 頁的 user_point 不在關卡① 定案的清單裡（逐字比對失敗）："
                    f"「{str(up)[:40]}」")
            # 例子優先：mechanism 頁若沒有讓規則跑過一個具體案例，layer3 只能畫摘要。
            # 機械驗欄位與來源；案例是否真的說明規則仍交給關卡②與 layout reviewer。
            # ⚠️ result／intro／buildup 頁**不套 mechanism 的預設**（後補，N11）：
            #    它們是支撐結構、本來就豁免 user_point，卻被 depth 的預設反過來
            #    要求交 example → planner 只能明寫 depth: overview ＋ depth_note 繞開。
            depth = p.get("depth") or ("mechanism" if slot not in EXEMPT else "overview")
            if depth == "mechanism" and not p.get("example_exception"):
                ex = p.get("example") or {}
                missing = [k for k in ("kind", "before", "operation", "after", "sources")
                           if not ex.get(k)]
                if missing:
                    err(f"{f} 第 {i} 頁缺 example.{','.join(missing)} —— mechanism 頁要先讓"
                        "一個真實案例或明示為示意的案例跑過規則，不能只交摘要。")
                elif ex.get("kind") not in ("observed", "constructed"):
                    err(f"{f} 第 {i} 頁 example.kind 要是 observed 或 constructed")
                elif ex.get("kind") == "constructed" and not ex.get("disclosure"):
                    err(f"{f} 第 {i} 頁是 constructed example，缺 disclosure —— "
                        "示意例子不得偽裝成實測結果。")
        check_chain(f, pages)
    if not n_plan:
        err("layer2*.json 裡沒有任何頁 —— 關卡② 還沒產出逐頁表")
    # 每一條 user_point 都要有頁
    used = set()
    for f in ls:
        if f.startswith("layer2") and f.endswith(".json"):
            j = load(os.path.join(d2, f)) or {}
            used |= {p.get("user_point") for p in
                     (j.get("slide_plan") or j.get("pages") or [])}
    for u in sorted(ups - used):
        err(f"user_point 沒有對應的頁：「{u[:50]}」——"
            "使用者說要講的東西不能沒有頁")
    # 每條主線都要有自己的 layer2.<id>.json（＝各派一個 slide_planner）
    check_per_thread(out, "layer2", "layer2", "layer2", "slide_planner")
    check_spec_fresh(out, "layer2", "layer2", "slide_planner")
    check_trim_pass(out)
    check_deck_skeleton(out)


def check_deck_skeleton(out):
    """關卡② 過了就要有 `deck.json` 骨架 —— ⭐ 派 `slide_builder` 之前（N61）。

    **為什麼是機械檢查而不是一句話**：`slide_builder` 的交件條件是
    「自己跑 `verify.py --thread <線>` 拿到綠燈」，而 `verify.py` 沒有日期目錄
    最上層的 `deck.json` 就 `sys.exit` —— 骨架晚一步寫，**首次交件那一輪的自驗
    就整輪跑不了**，而那一輪正是它要消滅的東西（上一場 builder A 被 resume 4 次，
    前 2 次就是「交件 → 協調者跑 check_deck → 退回」）。
    ⚠️ 這條規則如果只寫在 `SKILL.md` 而沒有人驗，它就是 FINDINGS 裡
    「規則寫了、沒有任何角色執行」那一類（本場出現 6 次）。
    """
    deck = os.path.join(out, "deck.json")   # ⚠️ 刻意在最上層，見 paths.py 的目錄圖
    if not os.path.isfile(deck):
        err(f"缺 deck.json 骨架（找的是 {deck}）—— 關卡② 過了就要先寫，"
            "⛔ 不要拖到 Step 4。\n"
            "        沒有它，slide_builder 首次交件時的自驗（verify.py --thread）"
            "整輪跑不了（N61）。\n"
            "        內容：meta／arc／plan／threads ＋ slides: []，"
            "由 `build_deck.py --skeleton --out <日期目錄>` 產（PR 2 起不手寫）。")
        return
    d = load(deck)
    if d is None:
        err(f"deck.json 讀不起來（不是合法 JSON）：{deck}")
        return
    for k in ("meta", "arc", "plan", "threads"):
        if not d.get(k):
            err(f"deck.json 骨架缺 `{k}` —— 四欄都要有才叫骨架"
                f"（來源見 build_deck.py 的 skeleton() 說明）")
    if "slides" not in d:
        err("deck.json 骨架缺 `slides` 欄 —— 要有這個鍵、值是 `[]`，"
            "留給 merge_slides.py 填")
    elif not isinstance(d.get("slides"), list):
        err(f"deck.json 的 `slides` 不是陣列（是 {type(d['slides']).__name__}）")
    elif d["slides"]:
        # ⛔ 不是「有頁就好」：候選頁抄進去會讓 merge_slides 的第一次合併
        #    誤以為已經併過（它靠 `slides` 是不是空的來決定要不要整批加入）。
        warn(f"deck.json 骨架的 `slides` 已經有 {len(d['slides'])} 頁 —— "
             "關卡② 這時應該是 `[]`。\n"
             "        ⛔ 特別不要把 deck.draft.json 的候選頁留在裡面（那是篩選前的），"
             "頁是 slide_builder 產、merge_slides.py 併進來的。\n"
             "        （若這是**重跑**已經做完的一週，忽略這條。）")
    # 骨架宣告的主線要跟 layer1 定案的對得上 —— `verify.py --thread` 認的就是 threads[]
    ids = {t.get("id") for t in (d.get("threads") or []) if t.get("id")}
    want = set(_threads(out))          # ⚠️ _threads() 回的是 dict（id → user_points）
    if want and ids != want:
        err(f"deck.json 的 threads id {sorted(ids)} 對不上關卡① 定案的 {sorted(want)} "
            "—— slide_builder 自驗時 `--thread <線id>` 認的就是 deck.json 這一份")


def check_chain(f, pages):
    """承接—拋出：第 i 頁的 `from` **逐字**等於第 i-1 頁的 `to`（後補，N16）。

    `deck_schema.md`：「`from` 必須逐字等於前一頁的 `to`（換線時重置）」。
    ⚠️ 這條以前只有 `check_deck.py` 在 Step 4 驗 —— 而 layer2 寫的 `from`
    是前一頁 `to` 的**縮寫版**，於是兩個 slide_builder 都只能自己改寫，
    改寫又是無紀錄的（誰也不知道使用者確認的是哪一句）。
    在關卡② 擋，改的成本是一行字。

    豁免：**每個檔就是一條線**，所以「換線」＝ 檔案的第一頁（不驗 from）；
    `backup` 頁不進承接鏈（`deck_schema.md`「豁免承接／拋出」）。
    """
    main = [(i, p) for i, p in enumerate(pages, 1) if not p.get("backup")]
    prev_to, prev_n = None, None
    for k, (i, p) in enumerate(main):
        frm, to = p.get("from"), p.get("to")
        frm = frm.strip() if isinstance(frm, str) else ""
        to = to.strip() if isinstance(to, str) else ""
        if k > 0:                          # 第一頁＝換線，不驗 from
            if not frm:
                err(f"{f} 第 {i} 頁缺 from —— 同一條線裡，除了開場頁，"
                    f"每一頁都要逐字承接前一頁（第 {prev_n} 頁）的 to：\n"
                    f"           「{(prev_to or '')[:60]}」")
            elif prev_to and frm != prev_to:
                err(f"{f} 第 {i} 頁的 from **不等於**前一頁（第 {prev_n} 頁）的 to ——"
                    "`deck_schema.md` 要求**逐字相同**，縮寫、改寫、換標點都不行：\n"
                    f"           第 {prev_n} 頁 to  ：「{prev_to}」\n"
                    f"           第 {i} 頁 from：「{frm}」\n"
                    "           ⛔ 現在對齊最便宜：拖到 layer3 就變成 builder 自己改寫，"
                    "而那句話使用者在關卡② 沒看過。")
        if not to and k < len(main) - 1:
            err(f"{f} 第 {i} 頁缺 to（這頁講完，聽眾帶走的那句結論）—— "
                f"下一頁的 from 要逐字等於它，沒有它就沒有東西可以承接")
        prev_to, prev_n = to, i


def check_trim_pass(out):
    """⑦ 削減回合有沒有跑過（後補）。

    ⚠️ 不驗「刪得對不對」—— 那是使用者在關卡② 的判斷。
    只驗**這一步真的發生過**，跟 `merged_groups`、`slot_reason` 同一個模式。

    ## 為什麼需要它

    ①~⑥ 是生成程序（一個 user_point 一頁），本身沒有任何往下收的力量。
    使用者的話：「只要有講到重點，基本上是不會需要那麼多投影片的」——
    但 planner 沒有被要求回頭問「這頁真的需要嗎」，於是頁數只會等於重點數。

    ⛔ 注意界線：planner **不得**自己砍頁（那等於砍掉使用者要講的東西），
    它只能**提議**；`kept` 也必填，否則使用者分不出「檢查過並保留」與「根本沒想過」。
    """
    d2 = paths.work_dir(out, "layer2")
    if not os.path.isdir(d2):
        return
    for f in sorted(os.listdir(d2)):
        if not (f.startswith("layer2") and f.endswith(".json")):
            continue
        j = load(os.path.join(d2, f)) or {}
        pages = j.get("slide_plan") or j.get("pages") or []
        tp = (j.get("plan") or {}).get("trim_pass") or j.get("trim_pass")
        if not tp:
            err(f"{f} 沒有 trim_pass —— ⑦ 削減回合沒跑過。\n"
                "           ①~⑥ 只會讓頁數等於 user_points 數，**沒有任何往下收的力量**。\n"
                "           逐頁問「抽掉這頁，聽眾會漏掉什麼」，"
                "答不出具體的就提議降口頭或併頁（規格見 slide_planner §7）")
            continue
        n = tp.get("reviewed")
        if n != len(pages):
            err(f"{f} 的 trim_pass.reviewed={n}，但這條線有 {len(pages)} 頁 —— "
                "⑦ 要**逐頁**問過，不是抽查")
        if not tp.get("proposals") and not tp.get("kept"):
            err(f"{f} 的 trim_pass 既沒有 proposals 也沒有 kept —— "
                "零項提議是合法的，但那時 `kept` 要列滿所有頁，"
                "⛔ 兩個都空等於沒做")


def _pair_pages(l2, sl):
    """把 `layer2.<線>.json` 的逐頁表與 `slides.<線>.json` 的頁配對。

    ⚠️ 兩邊**沒有共用的鍵**：layer2 的頁只有 `n`（1、2、3…），slides 的頁只有
    `id`（A1、A2…），實測兩邊都沒有對方那一欄。所以主線頁**照順序配**，
    backup 頁照 `id` 配（layer2 的 `backup[]` 有 id）。
    ⛔ 結構頁（cover／agenda／thread-intro）不進配對：它們不對應 layer2 的任何一頁。

    回傳 `(pairs, ok)`；頁數對不上時 `ok=False`，**主線頁一頁都不配**
    （⛔ 錯位的配對會噴出一整排張冠李戴的 ERROR，比不報還糟）。
    """
    pages = l2.get("slide_plan") or l2.get("pages") or []
    backup = [b for b in (l2.get("backup") or []) if isinstance(b, dict)]
    bk_ids = {str(b.get("id")) for b in backup if b.get("id")}
    slides = (sl.get("slides") if isinstance(sl, dict) else sl) or []
    slides = [s for s in slides if isinstance(s, dict)]
    by_id = {str(s.get("id")): s for s in slides if s.get("id")}
    main = [s for s in slides
            if s.get("type") not in _STRUCT and str(s.get("id")) not in bk_ids]
    pairs, ok = [], (len(main) == len(pages))
    if ok:
        for p, s in zip(pages, main):
            pairs.append((f"第 {p.get('n')} 頁（{s.get('id')}）", p, s))
    for b in backup:
        s = by_id.get(str(b.get("id")))
        if s is not None:
            pairs.append((f"backup {b.get('id')}", b, s))
    return pairs, ok, len(main), len(pages)


def check_must_numbers(out):
    """`must_numbers` 兩邊對帳 —— **砍掉可以，⛔ 靜默砍掉不行**（N117 ①）。

    ## 為什麼在這裡

    ⭐ 只有 layer3 這一關同時看得到 `layer2.<線>.json`（使用者在關卡② 確認的清單）
    與 `slides.<線>.json`（builder 實際做出來的頁）。`check_deck.py` 只看得到
    合併後的 `deck.json` —— 清單被 builder 整條刪掉時，它**結構上看不出來**。

    ## 病

    `must_numbers` 的鏈接回 builder（N101）之後，實測照出 6 個「指名要出現、
    版面上找不到」的數字，而**那 6 個 builder 砍得對**（`presentation_rules §2c-2`：
    佐證性的規格數字與旁支統計是版面複雜度最大的來源）。`123ed2f` 已經把那道篩
    補進 planner 挑清單的那一端；但**下游仍然是靜默的** —— builder 到了版面才
    發現放不下時，砍掉不留任何痕跡，於是使用者真的指名的數字（「這頁一定要有
    96%」）沒有人守。

    ## ⛔ 這個欄位憑什麼不會退化成第二個 `spec_reviewed`

    同一份檔案上面那個 `check_spec_fresh()` 的 `spec_reviewed` 是**任何字串都放行**，
    而且**填了會賺到**（ERROR → WARN，關卡由紅轉綠）—— 那是它變成橡皮章的原因。
    這裡刻意兩件事都反過來（比照 `plan.layout_reviewed.nits[]` 那套已經沒有退化的）：

      1. **填了不會賺到**：每則具名紀錄印一條 WARN（`check_deck` 那邊也印一條）——
         ⭐ 砍越多 WARN 越多，⛔ 關卡不會因為填了它而轉綠。
      2. **有獨立事實可以打臉**：它宣稱的是一件**驗得到**的事（這個數字不在版面上）。
         宣稱砍了卻畫著 → ERROR；清單本身被動過 → ERROR。
         ⛔ `spec_reviewed` 宣稱的「我逐項確認過」在世界上沒有對應物，無從反駁。

    ⚠️ 誠實講清楚承重的是哪幾道：`why` 仍然是自由字串，**沒有機器評得了一段理由**。
    擋門的是「帳目閉合 ＋ 版面打臉 ＋ 填了只會變吵」，⛔ 不是理由寫得好不好。

    ## ⛔ 誰有權砍

    builder 砍，**但砍不掉清單**。`subagent-slide-builder.md` 那句「不得改
    `must_numbers`」⛔ 一個字都沒動 —— `must_numbers_dropped` 是**另一個欄位**，
    是加法。builder 拿到的是「宣告我沒畫、並說明為什麼」的權力，清單原封不動
    留在那裡**正是本函式對帳的左邊**。⭐ 一旦允許改清單，帳就沒有左邊了。
    而「**版面放不下**」不是這個欄位的理由 —— 那是頁面預算，照舊寫
    `open_questions` 交協調者裁決（理由印在 WARN 裡讓人看得到）。
    """
    if not _CAN_READ_PAGE:                                 # pragma: no cover
        warn(f"must_numbers 對帳整條沒跑（借不到 check_deck 的 `number_on_page`："
             f"{_PAGE_ERR}）—— ⛔ 這不是「通過」")
        return
    deck_path = os.path.join(out, "deck.json")
    l2d = paths.work_dir(out, "layer2")
    sld = paths.work_dir(out, "slides")
    for tid in sorted(_threads(out)):
        l2 = load(os.path.join(l2d, f"layer2.{tid}.json"))
        sl = load(os.path.join(sld, f"slides.{tid}.json"))
        if not isinstance(l2, dict) or sl is None:
            continue                     # 缺檔由 check_per_thread 報，⛔ 不重複
        _e0 = len(E)                     # 這條線的判決留給 `_spec_obligations` 義務①
        pairs, ok, n_sl, n_l2 = _pair_pages(l2, sl)
        if not ok:
            warn(f"線「{tid}」的主線頁數對不上（layer2 {n_l2} 頁、slides {n_sl} 頁）"
                 f"—— must_numbers 對帳**跳過主線頁**。\n"
                 f"        ⛔ 這不是通過：頁數本身就該先對齊（check_deck 會擋），"
                 f"對齊之後這條才驗得了")
        whys = []
        for label, p, s in pairs:
            want = [str(x).strip() for x in (p.get("must_numbers") or [])]
            got = [str(x).strip() for x in (s.get("must_numbers") or [])]
            if set(want) != set(got):
                miss = sorted(set(want) - set(got))
                extra = sorted(set(got) - set(want))
                err(f"線「{tid}」{label} 的 must_numbers **跟關卡② 確認的那份不一樣**：\n"
                    + (f"           少了：{'、'.join(miss)}\n" if miss else "")
                    + (f"           多了：{'、'.join(extra)}\n" if extra else "")
                    + "           ⛔ 清單是使用者在關卡② 確認的，builder 不得增刪改"
                    "（`subagent-slide-builder.md` Role 那一句）。\n"
                    "           ⭐ 放不下不是刪清單的理由 —— 逐字帶過來，"
                    "再依 §2c-2 寫進 `must_numbers_dropped` 具名留痕。")
            dropped = _dropped_map(s)
            for num, d in sorted(dropped.items()):
                if num not in got:
                    err(f"線「{tid}」{label} 的 must_numbers_dropped 宣告砍掉「{num}」，"
                        f"但它**不在這頁的 must_numbers 裡** —— ⛔ 砍不掉沒有列進去的東西")
                    continue
                for k, what in (("why", "為什麼聽眾用不到它（§2c-2 那一問）"),
                                ("where", "搬去哪（notes／口頭／哪一頁）")):
                    if not str(d.get(k) or "").strip():
                        err(f"線「{tid}」{label} 砍掉「{num}」但沒寫 `{k}` —— {what}。\n"
                            f"           ⛔ 沒有理由的砍掉就是靜默砍掉，"
                            f"這個欄位存在的意義正是不要那樣")
                if str(d.get("why") or "").strip():
                    whys.append(str(d["why"]).strip())
            blob = " ".join(list(_texts(s))) + " " + _svg_text(deck_path, s)
            for num in got:
                on = _on_page(blob, num)
                if on and num in dropped:
                    err(f"線「{tid}」{label} 宣告砍掉「{num}」，**但它畫在頁上** ——\n"
                        f"           ⛔ 兩者只能有一個為真。真的畫了就把那則 "
                        f"must_numbers_dropped 拿掉。")
                elif not on and num not in dropped:
                    err(f"線「{tid}」{label} 的 must_numbers 指名「{num}」，"
                        f"**頁上找不到、也沒有留下任何紀錄** ——\n"
                        f"           那是使用者在關卡② 指名要出現的數字，"
                        f"⛔ 靜默砍掉正是這條要治的病。\n"
                        f"           兩條路（⛔ 沒有第三條）：\n"
                        f"           ① 畫上去；\n"
                        f"           ② 依 `presentation_rules §2c-2` 判它聽眾用不到 →\n"
                        f"              寫進該頁的 `must_numbers_dropped`："
                        f"`{{\"number\": \"{num}\", \"why\": \"…\", \"where\": \"…\"}}`\n"
                        f"           ⚠️ **版面放不下不是 ② 的理由**（那是頁面預算）——"
                        f"那要寫 `open_questions` 交協調者裁決。")
                elif not on:
                    d = dropped[num]
                    warn(f"線「{tid}」{label} 的「{num}」**沒畫，具名記錄中** —— "
                         f"{str(d.get('why'))[:70]}\n"
                         f"        搬到：{str(d.get('where'))[:50]}\n"
                         f"        ⛔ 砍掉不是畫上去了，它只是把判斷寫在看得見的地方")
        if len(whys) > 1 and len(set(whys)) == 1:
            err(f"線「{tid}」每一則 must_numbers_dropped 的 why 都是同一句話"
                f"（「{whys[0][:40]}…」）——\n"
                "           ⛔ 整批同一個理由是「把清單掃掉」的指紋"
                "（`plan.layout_reviewed.nits` 那條擋的是同一個形狀）。\n"
                "           ⭐ 逐個寫這個數字為什麼聽眾用不到。")
        _MN_VERDICT[tid] = len(E) - _e0


def gate3(out):
    """關卡③ —— 中英兩版 HTML 都產好、都量過溢位，才交給使用者看。"""
    for f in ("deck.en.html", "deck.zh.html"):
        if not os.path.isfile(os.path.join(out, f)):
            err(f"缺 {f} —— 關卡③ **兩版一起交**（deck.en.html ＋ deck.zh.html）。"
                "⛔ 兩版平等，不要替使用者選哪一版")
    if not os.path.isfile(os.path.join(out, "deck.json")):
        err("缺 deck.json")
    # 每條主線都要有自己的 slides.<id>.json（＝各派一個 slide_builder）
    check_per_thread(out, "slides", "slides", "layer3", "slide_builder")
    # ⛔ 順序是刻意的：`check_must_numbers` 的逐線判決是 `check_spec_fresh`
    #    義務① 的輸入（`_MN_VERDICT`），⛔ 不要對調（N117 ①＋②）。
    check_must_numbers(out)          # N117 ①：砍掉可以，⛔ 靜默砍掉不行
    check_spec_fresh(out, "slides", "slides", "slide_builder")


def order_check(out, stage):
    """時間戳順序：關卡的定案檔必須早於它下游的產物。

    ⚠️ 這條擋的是「先做完再回頭補填」—— 那正是首次實跑之前
    關卡形同虛設的具體形狀。
    """
    def mt(p):
        return os.path.getmtime(p) if os.path.isfile(p) else None
    if stage in ("layer2", "layer3"):
        a = mt(os.path.join(paths.work_dir(out, "layer1"), "layer1_confirmed.json"))
        b = mt(os.path.join(out, "deck.json"))
        if a and b and a > b:
            warn("layer1_confirmed.json 比 deck.json 還新 —— 關卡① 的定案是"
                 "**事後補填**的嗎？關卡要在產出之前發生才有意義")


def _now():
    import datetime as _dt
    return _dt.date.today().isoformat()


def confirm_layer1(out, answers_path):
    """關卡① 的定案由**腳本**寫：`layer1.json` ＋ 使用者的答案檔 → `layer1_confirmed.json`。

    ⭐ 為什麼（PR 2）：以前這個檔是協調者親手寫的 —— 一個回合外加一份大 JSON 的 output，
    寫錯再修又是回合（B17-2 那次就是協調者自己推錯規則）。答案檔的形狀由
    `gate_view.py layer1` 產（空白模板），這裡只做機械的合成，⛔ 不做任何判斷：
    decision／user_points／members_without_point／narrative 全部逐字來自答案檔。
    """
    d1 = paths.work_dir(out, "layer1")
    j = load(os.path.join(d1, "layer1.json"))
    if j is None:
        sys.exit(f"[gate] 找不到 {d1}/layer1.json —— thread_finder 還沒交件")
    ans = load(answers_path)
    if ans is None:
        sys.exit(f"[gate] 讀不到答案檔 {answers_path}")
    for k in ("confirmed_by", "narrative", "mode"):
        if not str(ans.get(k) or "").strip():
            sys.exit(f"[gate] 答案檔缺 {k} —— 那是使用者在關卡① 給的，⛔ 不得由 agent 代填")
    if ans.get("mode") not in ("single", "multi"):
        sys.exit(f"[gate] 答案檔的 mode 要是 single 或 multi（現在是 {ans.get('mode')!r}）")
    real_answers = [a for a in (ans.get("answers") or []) if str(a.get("a") or "").strip()]
    if len(real_answers) < 3:
        sys.exit(f"[gate] 答案檔只有 {len(real_answers)} 題有答案 —— check_deck 要求至少 3 題，"
                 "而且每一則要是使用者的原話")

    decisions = ans.get("threads") or {}
    kept, dropped = [], list(j.get("dropped") or [])
    all_threads = list(j.get("threads") or []) + list(j.get("overflow_threads") or [])
    by_id = {t.get("id"): t for t in all_threads}
    ov_dec = ans.get("overflow") or {}
    # 先處理 overflow 的合併（成員併進另一條線）
    for oid, od in ov_dec.items():
        t = by_id.get(oid)
        if not t:
            continue
        dec = (od.get("decision") or "").strip()
        if dec.startswith("合併") and od.get("into") in by_id:
            tgt = by_id[od["into"]]
            tgt["members"] = list(dict.fromkeys((tgt.get("members") or []) + (t.get("members") or [])))
            tgt["evidence"] = (tgt.get("evidence") or "") + f"　＋（關卡① 併入 {oid}：{od.get('why', '使用者裁決')}）"
            t["_merged_into"] = od["into"]
        elif dec in ("backup", "不講", "口頭"):
            for sid in t.get("members") or []:
                dropped.append({"source": sid, "where": dec, "why": od.get("why") or f"關卡①：overflow 線 {oid} 判 {dec}"})
            t["_merged_into"] = "dropped"
        elif dec == "入選":
            decisions.setdefault(oid, {"decision": "入選", "order": 99})
        else:
            sys.exit(f"[gate] overflow 線「{oid}」沒有裁決（decision 要是 入選／合併進 X／backup／不講）")
    for t in all_threads:
        tid = t.get("id")
        if t.get("_merged_into"):
            continue
        dec = decisions.get(tid) or {}
        d = (dec.get("decision") or "入選").strip()
        if d in ("backup", "不講", "口頭"):
            for sid in t.get("members") or []:
                dropped.append({"source": sid, "where": d, "why": dec.get("why") or f"關卡①：線 {tid} 判 {d}"})
            continue
        if d != "入選":
            sys.exit(f"[gate] 線「{tid}」的 decision「{d}」不認得（入選／backup／不講／口頭）")
        ups = dec.get("user_points")
        if not isinstance(ups, list) or not ups:
            sys.exit(f"[gate] 線「{tid}」沒有 user_points —— 這一題（這條線只講 3~4 個重點是哪幾個）"
                     "只有使用者答得出來，⛔ 不得代擬")
        nt = dict(t)
        nt.pop("_merged_into", None)
        nt["decision"] = "入選"
        nt["user_points"] = [str(u).strip() for u in ups]
        nt["members_without_point"] = dec.get("members_without_point") or []
        if dec.get("title"):
            nt["title"] = dec["title"]
        if dec.get("summary"):
            nt["summary"] = dec["summary"]
        nt["order"] = dec.get("order", len(kept) + 1)
        kept.append(nt)
    kept.sort(key=lambda t: (t.get("order", 99), t.get("id")))
    # dropped 覆寫：同一個 sid 以答案檔為準
    ov = {x.get("source"): x for x in (ans.get("dropped_overrides") or []) if x.get("source")}
    merged = {}
    for x in dropped:
        merged[x.get("source")] = x
    merged.update(ov)
    outj = {
        "confirmed_by": ans["confirmed_by"],
        "confirmed_at": ans.get("confirmed_at") or _now(),
        "narrative": ans["narrative"],
        "narrative_source": ans.get("narrative_source", ""),
        "mode": ans["mode"],
        "threads": kept,
        "merged_groups": j.get("merged_groups") or [],
        "dropped": list(merged.values()),
        "coverage_note": j.get("coverage_note", ""),
        "merge_note": j.get("merge_note", ""),
    }
    dest = os.path.join(d1, "layer1_confirmed.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(outj, fh, ensure_ascii=False, indent=2)
    print(f"[gate] layer1_confirmed.json ← {os.path.basename(answers_path)}：{len(kept)} 條線入選、"
          f"{len(merged)} 項有去處 → {dest}")
    if len(kept) > 4:
        warn(f"入選 {len(kept)} 條線，超過 4 條 —— 這是使用者的裁決，但頁數預估會反映它")


def confirm_layer2(out, answers_path):
    """關卡② 的定案由腳本翻旗標：每一份 `layer2.<線>.json` 的 `slide_plan_confirmed` → true，
    並把確認人／時間記進去。⚠️ 內容（每一頁講什麼）若使用者要改，由 planner 角色
    **先改 json 再 confirm** —— 這裡不動內容，只認「使用者說可以了」這一件事。
    """
    d2 = paths.work_dir(out, "layer2")
    ans = load(answers_path) if answers_path else {}
    if ans is None:
        sys.exit(f"[gate] 讀不到答案檔 {answers_path}")
    by = str((ans or {}).get("confirmed_by") or "").strip()
    if not by:
        sys.exit("[gate] 答案檔缺 confirmed_by —— 沒人確認就不是關卡")
    n = 0
    for f in sorted(os.listdir(d2)):
        if not (f.startswith("layer2") and f.endswith(".json")):
            continue
        p = os.path.join(d2, f)
        j = load(p)
        if not isinstance(j, dict):
            continue
        j["slide_plan_confirmed"] = True
        j["confirmed_by"] = by
        j["confirmed_at"] = (ans or {}).get("confirmed_at") or _now()
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(j, fh, ensure_ascii=False, indent=2)
        n += 1
    print(f"[gate] {n} 份 layer2.*.json 的 slide_plan_confirmed → true（{by}）")


GATES = {"layer1": gate1, "layer2": gate2, "layer3": gate3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=sorted(GATES))
    ap.add_argument("out")
    ap.add_argument("--confirm", metavar="ANSWERS_JSON",
                    help="⭐ 先依答案檔寫定案，再跑關卡檢查。layer1：layer1.json ＋ 答案檔 → "
                         "layer1_confirmed.json；layer2：把每份 layer2.*.json 的 "
                         "slide_plan_confirmed 翻成 true。答案檔的空白模板由 gate_view.py 產")
    a = ap.parse_args()
    if not os.path.isdir(a.out):
        sys.exit(f"[gate] 找不到目錄 {a.out}")
    if a.confirm:
        if a.stage == "layer1":
            confirm_layer1(a.out, a.confirm)          # 寫完接著跑 gate1，當場驗
        elif a.stage == "layer2":
            confirm_layer2(a.out, a.confirm)
            # ⛔ 這裡不跑 gate2：它會驗 deck.json 骨架，而骨架要在 confirm **之後**才由
            #    build_deck.py --skeleton 寫。順序：confirm → skeleton → check_gate layer2。
            print(f"[gate] 接著：python3 scripts/build_deck.py --skeleton --out {a.out}"
                  f"　→　python3 scripts/check_gate.py layer2 {a.out}")
            return
        else:
            sys.exit("[gate] --confirm 只給 layer1／layer2（layer3 的定案是 verify.py 全綠）")

    GATES[a.stage](a.out)
    order_check(a.out, a.stage)

    for x in W:
        print(x)
    for x in E:
        print(x)
    if E:
        print(f"\n[gate] ✗ 關卡 {a.stage} 未通過（{len(E)} 個 ERROR）。"
              "⛔ 不要往下一層走 —— 先把關卡補完。")
        sys.exit(1)
    print(f"[gate] ✓ 關卡 {a.stage} 通過"
          + (f"（{len(W)} 個 WARN）" if W else ""))


if __name__ == "__main__":
    main()
