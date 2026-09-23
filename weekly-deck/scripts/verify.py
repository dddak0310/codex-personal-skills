#!/usr/bin/env python3
"""Step 4 的整條驗證序列 —— **一支腳本、一個回合**。

## 為什麼有這支（實測，不是偏好）

`SKILL.md` Step 4 以前把這件事寫成六行分開的指令
（`merge_slides` → `check_deck` → `render` ×2 → `shoot --check-only` ×2）。
**規格的形狀決定了行為**：協調者一定會一行一行貼、一行一個 API 回合，
而每一個回合都會把當下整段 context 重送一次
（`成本 = Σ(每一回合當下的 context)`，context 只增不減）。

實測（`measure_tokens.py`，用 requestId 去重）：本場 175M tokens 裡 **96% 是 cache 讀**
＝重送已看過的東西，output 只佔 0.16%；而協調者每次呼叫的價格從 13:00 的
10.5 萬一路漲到 20:00 的 52 萬。這條序列本場跑了 6 次、每次 4~6 個回合 ≈ **30 個回合**，
其中 29 個回合買到的東西是 0 —— 它們只是「把同一段 context 再送一次」。
這支腳本把它壓成 **1 個回合**。

## 順序：跟著 `SKILL.md` layer3「機械檢查 → 一次退回」，⛔ 不要自己發明

Step 4 的順序是**刻意**讓「帶著 ERROR 繼續往下跑」的：
`layout_reviewer` 審的是**畫出來的 SVG 與實測版面**，所以它必須拿得到
render 過的 HTML 與 `shoot --check-only` 的實測輸出；
check_deck 的 ERROR 沒修完**不是**不 render 的理由 —— 那會讓 reviewer 白等一輪。

所以本腳本的停與不停是這樣分的（⛔ 不要改成「一有錯就停」）：

| 步驟 | 失敗了怎麼辦 | 為什麼 |
|---|---|---|
| `merge` | **停** | deck.json 沒併成，後面全部在驗一份舊的 |
| `check` | **記下來，照樣往下** | Step 4 明訂；reviewer 需要 render 過的產物 |
| `render_en` / `render_zh` | 只擋**該語言**的 shoot | 沒有 HTML 就沒得量；另一版不受影響 |
| `strings` 有待翻 | **擋中文版**（除非 `--allow-untranslated`） | ⛔ 不要靜默產出一份半英文的 HTML |
| `shoot_*` | 記下來，往下 | 兩版要各自量完，findings 要湊齊才一次退回 |

## pipe 與 exit code

舊 SKILL.md 有一條警告「跑檢查時不要接 pipe，exit code 會被吃掉」——
那條警告存在是因為它假設你**手動一行一行跑**。這支腳本用 `subprocess.run`
直接拿每一支的 returncode（**沒有 shell、沒有 pipe**，等價於 `set -o pipefail`
但更徹底），輸出照樣完整印出來。摘要表最後會逐步列出 exit code。

## 路徑

一律走 `paths.py` 的 `work_dir()`／`work_file()`。⛔ 不要自己拼 `_work/…` ——
那正是缺陷 N14 的成因（SKILL.md 說在 `4_slides/`、實際寫在最上層，兩邊分岔一整輪）。
`deck.json` 是唯一的例外，它**刻意**留在日期目錄最上層（見 `paths.py` 的目錄圖）。

## 用法

    python3 scripts/verify.py --out <日期目錄>
    python3 scripts/verify.py --out <日期目錄> --stop-after check   # 只跑到機械檢查
    python3 scripts/verify.py --out <日期目錄> --no-merge           # deck.json 已手動整形過
    python3 scripts/verify.py --out <日期目錄> --allow-untranslated # 明知半英文仍要出中文版
    python3 scripts/verify.py --out <日期目錄> --thread B           # slide_builder 自驗自己那條線

⚠️ **骨架階段也跑得動**（N61）：`deck.json` 只有 `meta`／`arc`／`plan`／`threads` ＋
`slides: []` 時，本腳本照樣跑完七步並印摘要表（多數步驟會紅，因為還沒有頁）——
⛔ 它**不** `sys.exit`。`--thread` 認的是 `threads[]` 宣告的主線，不是合併後的頁。

exit code：0 ＝ 跑過的步驟全綠；1 ＝ 至少一步紅（摘要表指名是哪一步）。
"""

import argparse
import fcntl
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import paths  # noqa: E402

S = os.path.dirname(os.path.realpath(__file__))
PY = sys.executable or "python3"

# 機械序列的步驟順序 —— **唯一定義，就是這一行**（N70）。
# ⛔ 不要在任何 `.md` 裡再抄一份：原本 `SKILL.md` Step 4 抄的那份**漏了 `strings`**，
#    於是「中文版整份沒翻」在文件上看起來是合法流程。要引用就指路到這裡。
STEPS = ["merge", "check", "render_en", "strings", "render_zh", "shoot_en", "shoot_zh"]

# `--quiet`：七支腳本的全文**不印到終端**，落地成 `_work/4_slides/verify.<線|all>.log`，
# 終端只剩摘要表 ＋ 本線 ERROR 抬頭。⭐ 為什麼：builder 每次自驗都把全文灌進自己的
# context（實測一個 builder 收尾時 context 55 萬 token，其中大半是這種輸出）；
# 自驗越勤越貴，等於懲罰照規矩做事的人。全文還在檔案裡，要細看用 grep 抽那一段。
QUIET = {"on": False, "log": None, "fh": None}


class Step:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.code = None          # None＝沒跑
        self.skip = None          # 沒跑的理由
        self.summary = "—"
        self.out = ""

    @property
    def state(self):
        if self.code is None:
            return "SKIP"
        return "OK" if self.code == 0 else "FAIL"


def run(step, argv, cwd=None):
    """跑一支腳本，原樣印出它的輸出，回傳 (exit code, 合併後的輸出)。

    ⛔ 不接 pipe、不經 shell：exit code 就是那支腳本自己的，不會被吃掉。
    """
    head = f"\n{'=' * 72}\n▶ [{step.name}] {step.title}\n  $ {' '.join(argv)}\n{'-' * 72}"
    p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    body = p.stdout if p.stdout.endswith("\n") else p.stdout + "\n"
    tail = f"{'-' * 72}\n◀ [{step.name}] exit code = {p.returncode}"
    sink = QUIET["fh"] if QUIET["on"] else sys.stdout
    sink.write(head + "\n" + body + tail + "\n")
    if QUIET["on"]:
        sink.flush()
        print(f"▶ [{step.name}] exit {p.returncode}　（全文在 {QUIET['log']}）")
    step.code, step.out = p.returncode, p.stdout
    return p.returncode, p.stdout


# ---------------------------------------------------------------------------
# 各步驟輸出的解讀（只認腳本自己印的字串；⛔ 不要另外重算一份）
# ---------------------------------------------------------------------------

def read_check(out):
    """check_deck.py → (ERROR 數, WARN 數, 每條 ERROR 的抬頭)。

    ⚠️ 抬頭要一起帶回來 —— 摘要表的用處是「一眼看得出是哪一步、**哪一頁**」，
    只給一個數字等於逼人再捲回去讀一次全文（又是一個回合）。
    """
    w = re.search(r"^警告 (\d+) 項", out, re.M)
    e = re.search(r"^錯誤 (\d+) 項", out, re.M)
    heads = [x.strip() for x in re.findall(r"^\s*\[ERROR\] (.*)$", out, re.M)]
    return (int(e.group(1)) if e else 0), (int(w.group(1)) if w else 0), heads


def read_render(out):
    """render_deck.py 失敗時第一行就指名頁與欄位，原樣拿來當摘要。"""
    m = re.search(r"^\[render\] 第 .*", out, re.M)
    return m.group(0).strip() if m else ""


def read_shoot(out):
    """shoot.py --check-only → (溢位頁, 版面過空頁, 文字互壓頁, 可改善項數)。

    三種擋法都要抓：溢位（`[溢位] 第 N 頁`）、主線內容過空與文字互壓（`第 N 頁 [type] …`
    出現在「主線內容過空」那一段底下，依 `[type]` 分桶；B17-13 之後多了文字互壓）。
    """
    over = [int(m) for m in re.findall(r"^\[溢位\] 第 (\d+) 頁", out, re.M)]
    sparse, overlap, in_block = [], [], False
    for ln in out.splitlines():
        if "主線內容過空" in ln and "會擋" in ln or ln.strip().startswith("[版面]") and "主線內容過空" in ln:
            in_block = True
            continue
        if in_block:
            m = re.match(r"\s*第 (\d+) 頁 \[([^\]]+)\]", ln)
            if m:
                (overlap if m.group(2) == "文字互壓" else sparse).append(int(m.group(1)))
            elif ln.strip() and not ln.startswith(" "):
                in_block = False
    soft = re.search(r"^\[版面\] (\d+) 項可改善", out, re.M)
    return over, sorted(set(sparse)), sorted(set(overlap)), (int(soft.group(1)) if soft else 0)


def read_strings(out):
    """render_deck.py --dump-strings → (總句數, 待翻句數)。"""
    m = re.search(r"\[render\] (\d+) 句 .*?（其中 (\d+) 句待翻）", out)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ---------------------------------------------------------------------------
# `--thread`：讓 slide_builder 在交件前自驗**自己那條線**
#
# ⭐ 為什麼要有這個：本場 `slide_builder` A 被 resume 6 次，其中第 1、2 次
# 純粹是「builder 交出來 → 協調者跑 check_deck → 退回」—— 而那些檢查
# **builder 自己也跑得動**。把它挪進 builder 的交件條件，那兩次 resume 就不存在了
# （代價見 `delegation.md`「resume 還是派新的」：被 resume 的 agent 每次呼叫貴 2.4 倍）。
#
# ⛔ 但**不要要求 builder 去修別條線的錯**：`verify.py` 跑的是合併後的整份 deck，
# 別條線的 ERROR 照樣會印出來，只是標成「非本線」、不算進你的紅燈。
# 被別條線擋住（例如它的頁讓 render 崩了）→ 回報協調者，⛔ 不要自己動手。
#
# ⛔ 同理，**中文那條鏈整段不算 builder 的紅燈**（strings／render_zh／shoot_zh 一律 SKIP）：
# builder 交的是自己那條線的 strings.<線>.zh.json 片段，全場的對照表要等各線都併進來才完整 ——
# 在它交件的時點恆有別條線的句子待翻，恆紅的關卡等於沒有關卡，
# 而 builder 的規格裡沒有「這一步跑不了」這個出口，只會逼它違規交件或無限自我修正（N98）。
# ⚠️ `render_en` 例外，照樣算紅燈：沒有英文 HTML 就量不到你自己的版面（shoot_en 會停），
# 所以那一步只標明該找誰（blame_render），不降級。
# ---------------------------------------------------------------------------

def load_owner(owner, deck_path):
    """建 slide id → thread 與 頁碼 → (id, thread) 的對照。

    ⭐ 也記下 `threads[]` **宣告**的主線 id。為什麼要分成兩種來源（N61）：
    協調者在派 builder 之前先寫 `deck.json` 骨架，那時 `slides` 是 `[]`，
    「有哪些主線」只有 `threads[]` 知道。舊版只認合併後的頁，於是骨架階段
    `--thread B` 會被判成「沒有這條線」直接 `sys.exit` —— 而那正是
    builder 首次交件自驗的時間點。
    """
    try:
        d = json.load(open(deck_path, encoding="utf-8"))
    except Exception:
        return
    owner["declared"] = {t.get("id") for t in (d.get("threads") or []) if t.get("id")}
    for i, sl in enumerate(d.get("slides", []), 1):
        sid, th = sl.get("id"), sl.get("thread")
        owner["by_id"][sid] = th
        owner["by_page"][i] = (sid, th)


def head_thread(owner, head):
    """check_deck 的 ERROR 抬頭形如 `A2: point 超過上限…` → 回它屬於哪條線。

    認不出 id 的（例如 `plan`、`i18n` 這種全域檢查項）回 None ——
    ⚠️ 全域的錯**不歸任何一條線**，所以 `--thread` 一律把它算成「非本線」，
    ⛔ 不要讓 builder 去扛整份 deck 的規劃問題。
    """
    m = re.match(r"([A-Za-z0-9_]+)[:：]", head)
    sid = m.group(1) if m else None
    return owner["by_id"].get(sid, None) if sid in owner["by_id"] else False


def blame_render(owner, msg):
    """render 失敗訊息裡有 `id=XXX` —— 用 `--thread` 時標明是不是別條線擋的。

    ⚠️ 這一步照樣算紅燈（沒有 HTML 就沒得量你的版面），但要講清楚**該找誰**。
    """
    if not owner["thread"]:
        return msg
    m = re.search(r"id=([A-Za-z0-9_]+)", msg)
    th = owner["by_id"].get(m.group(1)) if m else None
    if m and th != owner["thread"]:
        return (msg + f"\n{'':<27}⚠️ 擋住的是**非本線**的頁（id={m.group(1)}、"
                      f"線={th or '無'}）→ 回報協調者，⛔ 不要自己去修別條線")
    return msg


def split_mine(owner, items, key):
    """把 items 分成 (本線, 非本線)。`--thread` 沒給就全部算本線。"""
    if not owner["thread"]:
        return list(items), []
    mine, theirs = [], []
    for x in items:
        (mine if key(x) == owner["thread"] else theirs).append(x)
    return mine, theirs


# ---------------------------------------------------------------------------

def dump_strings_readonly(out_dir, deck, lang):
    """在**沙盒副本**上跑 `--dump-strings`，數待翻句數。

    ⚠️ 為什麼不直接在日期目錄上跑：`--dump-strings` 會**改寫**
    `strings.<lang>.json`（保留既有譯文，補上新句、丟掉已不存在的句）。
    那是 builder（逐線片段）與協調者（補漏）的工作，不是「驗證」該做的事 ——
    驗證腳本不應該動交付物。所以把 deck.json 與 figures 連進暫存目錄，
    把現有的 strings 表複製一份進去，在那份上跑。

    回傳 (Step, 沙盒裡的 strings 路徑)。
    """
    step = Step("strings", f"待翻句數（strings.{lang}.json，在副本上量，不動交付物）")
    tmp = tempfile.mkdtemp(prefix="wd-verify-strings-")
    try:
        os.symlink(deck, os.path.join(tmp, "deck.json"))
        figs = os.path.join(out_dir, "figures")
        if os.path.isdir(figs):
            os.symlink(figs, os.path.join(tmp, "figures"))
        real = os.path.join(out_dir, f"strings.{lang}.json")
        if os.path.isfile(real):
            shutil.copy2(real, os.path.join(tmp, f"strings.{lang}.json"))
        code, o = run(step, [PY, os.path.join(S, "render_deck.py"),
                             os.path.join(tmp, "deck.json"), "--dump-strings", lang])
        total, pending = read_strings(o)
        if code != 0:
            step.summary = "dump 失敗，見上方輸出"
            return step, None, None
        if total is None:
            step.summary = "讀不出句數（render_deck.py 的輸出格式變了？）"
            step.code = 1
            return step, None, None
        if pending:
            step.code = 1          # ⛔ 待翻不為 0 就是紅的，不許靜默過關
            step.summary = (f"{total} 句中 **{pending} 句待翻** → 中文版會落回英文原文，"
                            f"⛔ 不產出半英文的 HTML")
        else:
            step.summary = f"{total} 句、0 句待翻"
        return step, total, pending
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    """`--thread` 時把整段自驗包在 `deck.json.lock` 裡（N103）。

    ⭐ 為什麼是整段、不只 merge：兩條主線的 builder 平行跑，而這支不只改
    `deck.json`，還會覆寫共用的 `deck.en.html` 與 `_work/4_slides/shoot_check.en.txt`
    ——`shoot.py` 讀 HTML 的時候另一條線可能正在重寫它。實測（8 輪撞到 4 輪）
    是 merge 讀到寫到一半的 deck.json 直接 `JSONDecodeError`，那只是最先撞到的一處。
    ⛔ 序列化是這裡代價最小的解：builder 的自驗只有幾十秒，而**它本來就是**
    `SKILL.md:539` 那個「平行」唯一會互相踩到的地方。

    ⚠️ 協調者的完整驗證（不給 `--thread`）**不拿鎖**：那時沒有平行的第二個跑者。
    """
    a = _parse()
    if not a.thread:
        return _run(a)
    out_abs = os.path.abspath(os.path.expanduser(a.out))
    if not os.path.isdir(out_abs):
        return _run(a)      # 讓 _run 去印「日期目錄不存在」那句，⛔ 不要在這裡炸開檔錯誤
    lock = open(os.path.join(out_abs, "deck.json.lock"), "w")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[verify] 另一條主線正在自驗，等它跑完 —— "
                  "⛔ 這不是錯誤，兩條線共用同一份 deck.json（N103）", file=sys.stderr)
            fcntl.flock(lock, fcntl.LOCK_EX)
        # 子程序（merge_slides.py）不要再去拿同一把鎖，會卡死自己
        os.environ["WD_DECK_LOCK_HELD"] = os.path.join(out_abs, "deck.json")
        return _run(a)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _parse():
    ap = argparse.ArgumentParser(
        description="Step 4 的整條驗證序列，一次跑完並印一張摘要表。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="日期目錄（<週報輸出根>/YYYY-MM-DD）")
    ap.add_argument("--stop-after", choices=STEPS,
                    help="只跑到這一步（含）。例：--stop-after check")
    ap.add_argument("--no-merge", action="store_true",
                    help="跳過 merge_slides（deck.json 已是最新、沒有新的 slides.*.json 要併）")
    ap.add_argument("--allow-untranslated", action="store_true",
                    help="明知有待翻句仍要產中文版（⛔ 預設不允許：會出一份半英文的 HTML）")
    ap.add_argument("--lang", default="zh", help="第二語言（預設 zh）")
    ap.add_argument("--quiet", action="store_true",
                    help="⭐ 七支腳本的全文不印到終端，落地成 _work/4_slides/verify.<線|all>.log；"
                         "終端只剩摘要表與本線的 ERROR 抬頭。builder 自驗一律加這個 —— "
                         "全文進 context 是一整場的錢；要細看用 grep 抽 log 的那一段")
    ap.add_argument("--thread", metavar="ID",
                    help="⭐ 給 slide_builder 自驗用：只把**這條主線**的頁算成你的紅燈，"
                         "別條線的照樣印出來但標成「非本線」。⛔ 不要去修別條線的錯，"
                         "被別條線擋住就回報協調者。"
                         "中文版（strings／render_zh／shoot_zh）一律 SKIP —— 全場的中文版由協調者的"
                         "完整 verify 跑；你交的是 strings.<線>.zh.json 片段（merge 會併）。")
    return ap.parse_args()


def _warn_wrong_repo(out):
    """⚠️ `--out` 落在**別的 repo** 時出聲（N86）。

    擋的形狀：subagent **不繼承協調者 `source env.sh` 的環境**，於是它在自己的 shell 裡
    跑 `paths.py reports-root` 拿到的是**別的 repo 的路徑，而且不會報錯**。上一次盲測
    builder 在 subagent 內拿到 `<平時那個日誌 repo>/weekly/`，只因為協調者剛好給了絕對路徑
    才沒有把週報寫進別人的 repo（`delegation.md` 的「環境設定」那一欄）。
    在那之前**沒有任何腳本**比對過 `--out` 與 `paths.reports_root()`。

    ⚠️ 這是 **WARN 不是 ERROR**（N56 的反方向）：拿輸出目錄的**複本**跑回歸
    （前幾批的增量量測就是這樣做的，⛔ 正本一個 byte 都不能動）是**正當用法**，
    升成 ERROR 會把它擋死。所以這裡只負責**讓人看見**，不負責攔。
    """
    try:
        root = os.path.abspath(paths.reports_root())
    except Exception as e:                      # paths.py 自己不成立時不要連累主流程
        print(f"[verify] ⚠️ 取不到 reports-root（{e}）—— 略過 repo 比對", file=sys.stderr)
        return
    if os.path.dirname(out.rstrip(os.sep)) == root:
        return
    print(f"[verify] ⚠️ --out 不在本 repo 的週報輸出根底下（N86）：\n"
          f"         --out         = {out}\n"
          f"         reports-root  = {root}\n"
          f"         ⛔ 若你是 subagent：先照派遣訊息的「環境設定」設好環境再跑一次；\n"
          f"            仍然不一致就回報 BLOCKED，不要自己挑一個。\n"
          f"         （拿複本跑回歸時這一行是預期的，忽略即可。）", file=sys.stderr)


def _run(a):
    out = os.path.abspath(os.path.expanduser(a.out))
    if not os.path.isdir(out):
        sys.exit(f"[verify] 日期目錄不存在：{out}")
    deck = os.path.join(out, "deck.json")   # ⚠️ 刻意留在最上層，見 paths.py 的目錄圖
    if not os.path.isfile(deck):
        sys.exit(f"[verify] 找不到 deck.json：{deck}")
    _warn_wrong_repo(out)
    if a.quiet:
        QUIET["on"] = True
        QUIET["log"] = paths.work_file(out, f"verify.{a.thread or 'all'}.log", create=True)
        QUIET["fh"] = open(QUIET["log"], "w", encoding="utf-8")
        print(f"[verify] --quiet：逐步全文 → {QUIET['log']}")

    # 頁 → 主線的對照（`--thread` 用）。⚠️ 在 merge 之後才建才是最新的，
    # 所以這裡先留空，merge 跑完再填。
    owner = {"thread": a.thread, "by_id": {}, "by_page": {}, "declared": set()}

    limit = STEPS.index(a.stop_after) + 1 if a.stop_after else len(STEPS)
    wanted = set(STEPS[:limit])
    done = {}

    def want(name):
        return name in wanted

    # ---- 1. merge_slides：把各主線的 slides.<線>.json 併進 deck.json ----
    #    ⚠️ 必經的一步。builder 每輪都會把你縮短過的 point 與改成 null 的 output
    #    帶回舊值，手動合併會漏（首次實跑手動重套了 6 次）。
    st = Step("merge", "併各主線的 slides.*.json 進 deck.json（保留你在 deck.json 上的整形）")
    slices = sorted(glob.glob(os.path.join(paths.work_dir(out, "slides"), "slides.*.json")))
    if not want("merge"):
        st.skip = "--stop-after 排除"
    elif a.no_merge:
        st.skip = "--no-merge"
    elif not slices:
        st.skip = f"{paths.work_dir(out, 'slides')} 底下沒有 slides.*.json"
    else:
        run(st, [PY, os.path.join(S, "merge_slides.py"), deck] + slices)
        if st.code == 0:
            st.summary = f"併入 {len(slices)} 份：" + "、".join(
                os.path.basename(x) for x in slices)
    done["merge"] = st
    if st.state == "FAIL":
        return report(done, out, a.lang, hard_stop="merge")
    load_owner(owner, deck)
    # ⚠️ 兩種來源都算數：合併後的頁（`slides[]`）**與** `threads[]` 宣告的主線。
    #    ⛔ 不要只認前者 —— 骨架階段（`slides: []`）沒有任何頁，但主線早就定案了（N61）。
    known = {v for v in owner["by_id"].values() if v} | owner["declared"]
    if a.thread and a.thread not in known:
        sys.exit(f"[verify] deck.json 裡沒有主線 {a.thread!r}（有的是：{sorted(known)}）"
                 f"\n         —— `threads[]` 與已合併的頁都沒有它。")

    # ---- 2. check_deck：機械檢查。⭐ 有 ERROR **照樣往下跑**（Step 4 明訂）----
    st = Step("check", "機械檢查 deck.json（有 ERROR 也照樣往下，findings 最後一次合成退回）")
    if want("check"):
        _, o = run(st, [PY, os.path.join(S, "check_deck.py"), deck])
        e, w, heads = read_check(o)
        done["check_counts"] = (e, w)
        mine, theirs = split_mine(owner, heads, lambda h: head_thread(owner, h))
        st.summary = f"{e} ERROR / {w} WARN"
        # ⚠️ `check_deck.py` 有「還沒有頁可檢查」這類提早收工的出口（骨架階段就會走到），
        #    它不印「錯誤 N 項」→ 上面那行會變成沒有意義的 `0 ERROR / 0 WARN`。
        #    ⛔ 摘要表的用處是一眼看得出**卡在哪**，所以改印它自己那句話。
        if st.code and not heads and "錯誤 " not in o:
            tail = [x.strip() for x in o.splitlines() if x.strip()]
            if tail:
                st.summary = tail[-1]
        if owner["thread"]:
            st.summary += f"（本線 {len(mine)} 條、非本線 {len(theirs)} 條）"
            st.code = 1 if mine else 0      # ⛔ 別條線的錯不算你的紅燈
        for h in mine[:5]:
            st.summary += f"\n{'':<27}· {h}"
        if len(mine) > 5:
            st.summary += f"\n{'':<27}· …另外 {len(mine) - 5} 條，見上方 [check] 段"
        if theirs:
            st.summary += (f"\n{'':<27}（非本線 {len(theirs)} 條已略去，"
                           f"⛔ 不要去修別條線 —— 回報協調者）")
        if mine and not owner["thread"]:
            st.summary += (f"\n{'':<27}⛔ 先不要退回 builder，"
                           f"等 shoot 與 layout_reviewer 的 findings 湊齊再一次退")
    else:
        st.skip = "--stop-after 排除"
    done["check"] = st

    # ---- 3. render 英文版 ----
    st = Step("render_en", "產 deck.en.html")
    if want("render_en"):
        _, o = run(st, [PY, os.path.join(S, "render_deck.py"), deck])
        if st.code == 0:
            st.summary = "deck.en.html"
        else:
            st.summary = blame_render(owner, read_render(o) or "render 失敗，見上方輸出")
    else:
        st.skip = "--stop-after 排除"
    done["render_en"] = st

    # ---- 4. 待翻句數（在副本上量）----
    #    ⛔ `--thread` 模式一律 SKIP：全場對照表要等各線的 strings.<線>.zh.json 都併進來，
    #    這條線交件的時點別條線必然還沒填 → 恆有待翻 → 恆紅。
    #    判斷與 `check` 那步逐字相同：**那不是這條線產生的**（別條線的錯不算你的紅燈），
    #    而 builder 的規格裡「⛔ 沒有『這一步跑不了』這個出口」，
    #    恆紅就等於逼它違規交件或無限自我修正（N98）。
    pending = None
    if owner["thread"]:
        st = Step("strings", "待翻句數")
        st.skip = ("`--thread`：全場的待翻句數由協調者的完整 verify 算 —— "
                   "你交 strings.<線>.zh.json 片段就好（merge 會併），⛔ 不是這條線的紅燈")
    elif want("strings"):
        st, _total, pending = dump_strings_readonly(out, deck, a.lang)
    else:
        st = Step("strings", "待翻句數")
        st.skip = "--stop-after 排除"
    done["strings"] = st

    # ---- 5. render 中文版 ----
    st = Step("render_zh", f"產 deck.{a.lang}.html")
    if not want("render_zh"):
        st.skip = "--stop-after 排除"
    elif owner["thread"]:
        # ⛔ 同上：沒有對照表就只會產出一份半英文的 HTML，
        #    而且那是交付物 —— 驗證不該讓 builder 去覆寫它（N98）。
        st.skip = "`--thread`：中文版由協調者的完整 verify 產，不算你的紅燈"
    elif pending and not a.allow_untranslated:
        st.skip = (f"strings.{a.lang}.json 還有 {pending} 句待翻 —— "
                   f"⛔ 不產半英文的 HTML。翻完再跑，或加 --allow-untranslated")
    else:
        _, o = run(st, [PY, os.path.join(S, "render_deck.py"), deck, "--lang", a.lang])
        st.summary = (f"deck.{a.lang}.html" if st.code == 0
                      else blame_render(owner, read_render(o) or "render 失敗，見上方輸出"))
    done["render_zh"] = st

    # ---- 6/7. shoot --check-only 兩版：量溢位與版面（中英行高不同，兩版都要量）----
    for name, lang in (("shoot_en", "en"), ("shoot_zh", a.lang)):
        html = os.path.join(out, f"deck.{lang}.html")
        st = Step(name, f"量 deck.{lang}.html 的溢位與版面（--check-only）")
        rstep = done.get("render_en" if lang == "en" else "render_zh")
        if not want(name):
            st.skip = "--stop-after 排除"
        elif owner["thread"] and lang != "en":
            st.skip = "`--thread`：中文版不歸 builder 驗（見 render_zh 那列）"
        elif rstep is None or rstep.state != "OK":
            st.skip = f"上游 render 沒有成功產出 deck.{lang}.html"
        elif not os.path.isfile(html):
            st.skip = f"找不到 {html}"
        else:
            _, o = run(st, [PY, os.path.join(S, "shoot.py"), html, "--check-only"])
            over, sparse, overlap, soft = read_shoot(o)
            pth = lambda n: owner["by_page"].get(n, (None, None))[1]
            over_m, over_t = split_mine(owner, over, pth)
            sparse_m, sparse_t = split_mine(owner, sparse, pth)
            olap_m, olap_t = split_mine(owner, overlap, pth)
            bits = []
            if over_m:
                bits.append("溢位擋住第 " + "、".join(map(str, over_m)) + " 頁")
            if sparse_m:
                bits.append("版面過空擋住第 " + "、".join(map(str, sparse_m)) + " 頁")
            if olap_m:
                bits.append("文字互壓擋住第 " + "、".join(map(str, olap_m)) + " 頁（B17-13：中文譯文太長）")
            if soft:
                bits.append(f"{soft} 項可改善（不擋）")
            if over_t or sparse_t or olap_t:
                bits.append("非本線被擋第 " + "、".join(
                    map(str, sorted(set(over_t + sparse_t + olap_t)))) + " 頁（⛔ 不歸你修）")
            st.summary = "；".join(bits) or "零過空、零溢位、零互壓"
            if st.code and not (over_m or sparse_m or olap_m or soft or over_t or sparse_t or olap_t):
                # shoot.py 自己炸了（playwright 沒裝、瀏覽器對不上版本…）—— ⛔ 不要印成「零溢位」
                tail = [x.strip() for x in o.splitlines() if x.strip()]
                st.summary = "shoot.py 沒跑成：" + (tail[-1][:100] if tail else "（沒有輸出）")
            if owner["thread"]:
                st.code = 1 if (over_m or sparse_m or olap_m) else 0
            # 實測輸出由 shoot.py 自己落地，layout_reviewer 要讀它（N37）
            st.summary += "　→ " + os.path.relpath(
                paths.work_file(out, f"shoot_check.{lang}.txt", create=False), out)
        done[name] = st

    return report(done, out, a.lang)


def report(done, out, lang, hard_stop=None):
    """摘要表：任何一步紅了，這張表要一眼指得出是哪一步、哪一頁。"""
    print("\n" + "=" * 72)
    print(f"摘要　{out}")
    print("=" * 72)
    print(f"{'步驟':<12}{'狀態':<8}{'exit':<7}說明")
    print("-" * 72)
    bad = []
    for name in STEPS:
        st = done.get(name)
        if st is None:
            continue
        code = "-" if st.code is None else str(st.code)
        note = st.skip if st.code is None else st.summary
        print(f"{name:<12}{st.state:<8}{code:<7}{note}")
        if st.state == "FAIL":
            bad.append(name)
    print("-" * 72)
    if QUIET["on"]:
        print(f"（--quiet：七步的完整輸出在 {QUIET['log']}，"
              f"要看某一步就 grep '▶ \\[<步驟>\\]' 之後那一段，⛔ 不要 cat 整份）")
        if QUIET["fh"]:
            QUIET["fh"].close()
    e, w = done.get("check_counts", (0, 0))
    if hard_stop:
        print(f"⛔ [{hard_stop}] 失敗，後面的步驟全部沒跑 —— "
              f"它的產出是後面每一步的輸入，繼續跑只會在驗一份過期的 deck.json。")
    if bad:
        print(f"⛔ 紅燈：{'、'.join(bad)}　（逐步輸出在上面，找 `▶ [<步驟>]` 那一行）")
        if e and set(bad) <= {"check", "shoot_en", "shoot_zh", "strings"}:
            print("⚠️ 這些是**要合成一次退回**的 findings（check_deck ERROR ＋ shoot 版面 ＋ "
                  "layout_reviewer 的 BLOCKING），⛔ 不要分幾輪退 —— 見 delegation.md「試錯上限」。")
        return 1
    print("✅ 跑過的步驟全綠。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
