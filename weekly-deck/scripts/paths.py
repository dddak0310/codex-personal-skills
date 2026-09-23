#!/usr/bin/env python3
"""weekly-deck 的路徑解析：讓這個 skill 在任何人的機器上跑得起來。

## 為什麼有這支

`weekly-deck` 是 `daily-log` 的後處理（讀它的 `.data/*.json`，產出週報投影片）。
路徑寫死的後果**不是報錯，是無聲失效**：別人 clone 下來跑 `--since-last-deck`，
寫死的 `weekly_reports` 目錄在他機器上不存在 → 找不到上一份週報 → 區間推導失效 →
退回手填日期。而「區間一直是手填的」正是 不久前才剛修好的毛病。

## 兩件事，分得很開

1. **日誌 repo 在哪** —— 這是 `daily-log` 的事，**一律轉發**給它的 `paths.py`。
   ⛔ 不在這裡重寫一份慣例。同一事實寫在兩個地方，必定分岔。
   找不到 `daily-log` 就**直接報錯**（見 `_daily_log_paths`）——這兩個 skill 是配套的，
   靜默退回一個寫死的預設等於換個地方再寫死一次。

2. **週報輸出根目錄在哪** —— 這是 weekly-deck 自己的設定，沿用同一套三段式解析。

## 解析順序（三段，與 daily-log 一致）

1. **環境變數** —— 一次性覆寫
2. **個人設定檔** `~/.config/weekly-deck/<name>` —— 長期固定的個人設定
3. **慣例／預設** —— 什麼都沒設定時的行為

## 設定項一覽

| 設定 | 環境變數 | 設定檔 | 預設 |
|---|---|---|---|
| daily-log skill 位置 | `WEEKLY_DECK_DAILY_LOG` | `daily-log` | 同一個 skills 目錄下的 `daily-log/`，再退 `$CODEX_HOME/skills`、`~/.claude/skills/daily-log`、`~/.codex/skills/daily-log` |
| 日誌 `.data` 目錄 | `WEEKLY_DECK_DATA` | `data` | `<daily-log 的 log_repo>/.data` |
| 週報輸出根 | `WEEKLY_DECK_REPORTS` | `reports-root` | `<日誌 repo>/weekly`（與 `.data/`、`daily/` 並排）|
| 逐字稿 session 目錄 | `WEEKLY_DECK_TRANSCRIPT_DIRS`（`:` 分隔） | `transcript-dirs` | Claude Code：由專案路徑推導 `~/.claude/projects/<編碼>`；Codex：`~/.codex/sessions`（整個根） |

⚠️ **明確設定過的路徑若不存在，一律報錯，不退回預設。**
「我設了但它沒生效」是最難查的失效——寧可停下來。

## 用法

Python：
    import paths
    paths.data_dir(); paths.reports_root()

命令列（給 bash 腳本用，避免同一套邏輯寫兩份）：
    python3 paths.py data-dir
    python3 paths.py reports-root
    python3 paths.py transcript-dirs
"""

import importlib.util
import os
import sys

CONFIG_DIR = os.path.expanduser("~/.config/weekly-deck")
SKILL_NAME = "weekly-deck"


# --------------------------------------------------------------------------
# 設定檔讀取（形狀與 daily-log 的 paths.py 一致：跳過註解與空行）
# --------------------------------------------------------------------------

def _from_config(name):
    """讀設定檔的第一個**有效值**。`#` 開頭與空行忽略。

    跳過註解的理由同 daily-log：`config.example/` 是空白表單，
    忘了編輯要等同於「沒設定」（→ 報錯並告訴你怎麼設），
    而不是解析出一個看起來像路徑、其實不存在的值然後靜默用下去。
    """
    p = os.path.join(CONFIG_DIR, name)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                v = line.strip()
                if v and not v.startswith("#"):
                    return os.path.expanduser(v)
    return None


def _lines_from_config(name):
    """讀設定檔的每一行（清單型設定用）。"""
    p = os.path.join(CONFIG_DIR, name)
    if not os.path.isfile(p):
        return None
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(os.path.expanduser(line))
    return out or None


def _skill_root():
    """這支腳本所在的 skill 目錄（.../skills/weekly-deck）。

    ⚠️ **一定要用 `realpath` 而不是 `abspath`**（實測抓到的 bug）：
    skill 常以 symlink 安裝（`~/.codex/skills/weekly-deck -> /somewhere/clone`），
    而 Python 對兩條路徑的解法不一致 ——
      · 直接跑 `python3 <symlink>/scripts/paths.py`：`__file__` **保留 symlink 路徑**
      · 由別支腳本 `import paths`：走 `sys.path[0]`，那是**已解開的 realpath**
    用 `abspath` 的話兩者會解出**不同的 skill 目錄**，後果是
    **README 叫人跑的那道驗證指令，印出來的答案跟腳本實際用的不一樣** ——
    「驗證指令會說謊」，而且錯誤提示會叫人把 daily-log 放到他根本沒在用的目錄。
    `realpath` 讓兩條路徑一致。
    """
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _explicit(env, cfg):
    """回傳 (值, 來源說明)；沒有明確設定就 (None, None)。"""
    v = os.environ.get(env)
    if v:
        return os.path.expanduser(v), f"環境變數 {env}"
    v = _from_config(cfg)
    if v:
        return v, f"設定檔 {CONFIG_DIR}/{cfg}"
    return None, None


def _require_dir(path, source, what):
    """明確設定過的目錄必須存在，否則停下來。

    ⚠️ 這條刻意比 daily-log 嚴格。weekly-deck 的失效形態是**無聲**的
    （找不到上一份 deck → 區間推導默默失效），所以設錯路徑不能只是「沒效果」。
    """
    if not os.path.isdir(path):
        sys.exit(f"[錯誤] {what}不存在：{path}\n"
                 f"        來源：{source}\n"
                 f"        設錯了就改掉；沒有這個目錄就先建立。"
                 f"（不會退回預設值——那會讓錯誤靜默消失）")
    return path


# --------------------------------------------------------------------------
# 轉發給 daily-log
# --------------------------------------------------------------------------

_dl_cache = {}


def _daily_log_dir():
    """daily-log skill 的根目錄。"""
    v, src = _explicit("WEEKLY_DECK_DAILY_LOG", "daily-log")
    if v:
        return _require_dir(v, src, "daily-log skill 目錄")
    # 慣例：跟 weekly-deck 放在同一個 skills 目錄底下
    sibling = os.path.join(os.path.dirname(_skill_root()), "daily-log")
    if os.path.isdir(sibling):
        return sibling
    # 全域安裝的兩個落點。⚠️ 兩個都要找：Claude Code 用 ~/.claude/skills，
    # Codex 用 ~/.codex/skills（實測，codex 0.152.1 的
    # skill-installer 明文寫「Installs into $CODEX_HOME/skills/<skill-name>」）。
    # 只寫 ~/.claude/skills 的話，只用 Codex 的人會在這裡拿到 None →
    # 直接 sys.exit，訊息還叫他去放 ~/.claude ——那個目錄他根本沒有。
    for env_home in ("CODEX_HOME",):
        root = os.environ.get(env_home)
        if root:
            cand = os.path.join(os.path.expanduser(root), "skills", "daily-log")
            if os.path.isdir(cand):
                return cand
    for glob_install in ("~/.claude/skills/daily-log", "~/.codex/skills/daily-log"):
        d = os.path.expanduser(glob_install)
        if os.path.isdir(d):
            return d
    return None


def _daily_log_paths():
    """載入 daily-log 的 `paths.py` 模組。載不到就**直接報錯**。

    ⛔ 不做「靜默退回寫死的預設」。這兩個 skill 必須成對安裝：
    weekly-deck 讀的是 daily-log 產出的 `.data/*.json`，
    沒有 daily-log 就沒有輸入，猜一個路徑只會產出一份空週報。
    """
    if "mod" in _dl_cache:
        return _dl_cache["mod"]
    d = _daily_log_dir()
    scripts = os.path.join(d, "scripts") if d else None
    if not (scripts and os.path.isfile(os.path.join(scripts, "paths.py"))):
        sys.exit(
            "[錯誤] 找不到 daily-log 的 scripts/paths.py。\n"
            "        weekly-deck 是 daily-log 的後處理（讀它產出的 .data/*.json），\n"
            "        兩個 skill 必須成對安裝。請擇一：\n"
            f"          · 把 daily-log 放進同一個 skills 目錄："
            f"{os.path.dirname(_skill_root())}/daily-log\n"
            "            （Claude Code：~/.claude/skills/；Codex：~/.codex/skills/）\n"
            "          · export WEEKLY_DECK_DAILY_LOG=<daily-log skill 路徑>\n"
            f"          · mkdir -p {CONFIG_DIR} && "
            f"echo '<daily-log skill 路徑>' > {CONFIG_DIR}/daily-log\n"
            f"        （目前找到的位置：{d or '無'}；"
            f"環境變數／設定檔一旦設了就以它為準，慣例不再生效）")
    # ⚠️ 兩邊的檔名都叫 paths.py，不能用 `import paths`——
    # sys.path 上先命中的會是 weekly-deck 自己這一支（或已在 sys.modules 裡），
    # 於是「轉發」變成自己呼叫自己，無限遞迴。所以按檔案路徑掛成別的模組名。
    src = os.path.join(scripts, "paths.py")
    spec = importlib.util.spec_from_file_location("daily_log_paths", src)
    _dl = importlib.util.module_from_spec(spec)
    sys.modules["daily_log_paths"] = _dl
    spec.loader.exec_module(_dl)
    _dl_cache["mod"] = _dl
    return _dl


# --------------------------------------------------------------------------
# 對外的設定項
# --------------------------------------------------------------------------

def log_repo():
    """日誌 repo（daily-log 的輸出根）。轉發，不自己推導。"""
    return _daily_log_paths().log_repo()


def project_root():
    """被記錄的專案根。轉發，不自己推導。"""
    return _daily_log_paths().project_root()


def data_dir():
    """每日日誌的事實來源 `.data/`（weekly-deck 的唯一輸入）。"""
    v, src = _explicit("WEEKLY_DECK_DATA", "data")
    if v:
        return _require_dir(v, src, "日誌 .data 目錄")
    guess = os.path.join(log_repo(), ".data")
    if os.path.isdir(guess):
        return guess
    sys.exit(f"[錯誤] 找不到日誌的 .data 目錄：{guess}\n"
             f"        它由 daily-log 產生（日誌 repo = {log_repo()}）。\n"
             f"        路徑不對就設定：\n"
             f"          export WEEKLY_DECK_DATA=<路徑>\n"
             f"          mkdir -p {CONFIG_DIR} && echo '<路徑>' > {CONFIG_DIR}/data\n"
             f"        或先設好 daily-log 的 repo（~/.config/daily-log/repo）。")


def reports_root():
    """週報的輸出根目錄（`<root>/YYYY-MM-DD/`，目錄形狀見本檔尾的 WORK_STAGES）。

    **預設是日誌 repo 底下的 `weekly/`**（後改），與日誌並排：

        <日誌 repo>/
          .data/YYYY-MM-DD.json    ← 輸入：每日日誌（daily-log 產）
          daily/YYYY-MM-DD.html    ← 每日日誌的人類版
          weekly/YYYY-MM-DD/       ← 輸出：週報（本 skill 產）

    **為什麼放日誌 repo 而不是專案目錄**：週報是日誌的彙整產物，兩者同源；
    放在一起才能一起備份、一起被讀。⚠️ 舊版預設是 `<專案>/weekly_reports`，
    換版之後 `--since-last-deck` 會找不到舊的 deck —— 要沿用舊位置就明確設定
    `WEEKLY_DECK_REPORTS`（或 `~/.config/weekly-deck/reports-root`）。

    這也是 `--since-last-deck` 找上一份 deck 的地方 ——
    指錯了不會報錯，只會靜默推不出區間，所以明確設定過就驗存在。

    ⚠️ 預設值**不驗存在也不自動建立**：第一次跑的人那個目錄本來就還沒有，
    由 `--out` 的 `os.makedirs` 建。明確設定過的才驗（設錯要當場知道）。
    """
    v, src = _explicit("WEEKLY_DECK_REPORTS", "reports-root")
    if v:
        return _require_dir(v, src, "週報輸出根目錄")
    return os.path.join(log_repo(), "weekly")


def _encode_project(path):
    """Claude Code 的 session 目錄命名：路徑的 `/` 與 `_` 都換成 `-`。

    例：`/srv/work/alice/My_Proj` → `-srv-work-alice-My-Proj`
    """
    return path.rstrip("/").replace("/", "-").replace("_", "-")


def transcript_dirs():
    """逐字稿的 session 目錄（只有 `measure_effort.py` 用）。**兩種工具都回。**

    ⚠️ 後修：原本這裡寫 `if tool == "claude"`，把 Codex 濾掉了。
    後果不是報錯，是**靜默回空清單** —— 只用 Codex 的人跑 `measure_effort.py` 會得到
    「0 則對話」「區間內沒有任何對話」，跟「這週真的沒做事」長得一模一樣
    （見Codex 相容性驗證）。那正是本專案明令要避免的失效形態
    （`docs/STATE.md §4` 坑 #10：錯誤被吞掉 → 假的「0 個命中」）。
    現在兩種工具都回，由 `_transcripts.py` 依目錄形狀分派到對應的 adapter。

    兩種工具的目錄形狀不同：

    - **Claude Code**：一個專案一個目錄（路徑的 `/` 與 `_` 都換成 `-`）。
      預設回專案本身與它的上一層 —— 同一個帳號在上層目錄開過的 session 也算數。
    - **Codex**：沒有 project 目錄的概念，檔案按 `YYYY/MM/DD` 分。
      所以回**整個 sessions 根**，由 adapter 自己按日期與 cwd 過濾。

    只回存在的目錄；一個都沒有就**報錯**，不回空清單。
    """
    v = os.environ.get("WEEKLY_DECK_TRANSCRIPT_DIRS")
    if v:
        cands = [os.path.expanduser(p) for p in v.split(":") if p.strip()]
    else:
        cands = _lines_from_config("transcript-dirs")
    if cands:
        missing = [p for p in cands if not os.path.isdir(p)]
        if missing:
            sys.exit(f"[錯誤] 設定的逐字稿目錄不存在：{', '.join(missing)}\n"
                     f"        來源：WEEKLY_DECK_TRANSCRIPT_DIRS 或 "
                     f"{CONFIG_DIR}/transcript-dirs")
        return cands

    proj = project_root()
    out = []
    for tool, root in _daily_log_paths().transcript_roots():
        if tool == "claude":
            # 一個專案一個目錄，回專案本身與上一層。
            for cand in (proj, os.path.dirname(proj)):
                d = os.path.join(root, _encode_project(cand))
                if os.path.isdir(d) and d not in out:
                    out.append(d)
        else:
            # Codex：整個根丟給 adapter，它按 YYYY/MM/DD 自己找。
            if os.path.isdir(root) and root not in out:
                out.append(root)
    if not out:
        sys.exit(
            "[錯誤] 找不到任何逐字稿 session 目錄。\n"
            f"        專案根：{proj}\n"
            "        Claude Code 的目錄名由專案路徑推導（`/` 與 `_` 都換成 `-`），\n"
            "        Codex 則用 ~/.codex/sessions 整個根。兩邊都沒有找到。\n"
            "        這通常代表：這台機器上沒有用過這兩個工具，或專案根推錯了。\n"
            "        要指定就設定：\n"
            f"          export WEEKLY_DECK_TRANSCRIPT_DIRS=<目錄1>:<目錄2>\n"
            f"          （或一行一個寫進 {CONFIG_DIR}/transcript-dirs）\n"
            "        ⛔ 不回空清單 —— 那會讓 measure_effort.py 印出「0 則對話」，"
            "跟「這週真的沒做事」分不出來。")
    return out


def effort_log():
    """`measure_effort.py --log` 附加的那份紀錄檔。"""
    return os.path.join(reports_root(), "_effort_log.md")


def explanations():
    """`_explanations.md` 的絕對路徑（跨週的解釋資產；⛔ 不保證存在）。

    ⚠️ 它跟 `effort_log()` 一樣住在**輸出根**，不是某一週的日期目錄裡 ——
    上一次盲測踩過 `weekly_reports/_explanations.md` 這個舊版面的相對路徑，
    subagent 找不到、而規格寫「若存在」→ **靜默略過**，
    「未答的教授提問排最前」那條規則整個沒有生效（`delegation.md` ②）。
    """
    return os.path.join(reports_root(), "_explanations.md")


def last_deck():
    """上一份週報的 `deck.json` 絕對路徑；沒有就回 None。

    ⛔ **這是 Step 0「上一份 deck.json」那一項的唯一入口**，協調者不要自己
    `glob` 也不要自己判新舊結構 —— 新結構是 `<日期>/deck.json`、舊結構多一層
    `deck/`，同一週兩種都在時**新的贏**，底線開頭的目錄一律排除。
    ⭐ 那套判斷 `_range.py` 的 `find_last_deck()` 早就有一份了，本函式**轉發**過去，
    ⛔ 不在這裡重寫（同一事實寫在兩個地方，必定分岔）。
    """
    import importlib
    _r = importlib.import_module("_range")
    hit = _r.find_last_deck()
    return hit[1] if hit else None

# ---------------------------------------------------------------------------
# 週報目錄的形狀（定案）—— 只有這一份定義，⛔ 不要在各腳本裡另寫路徑
#
#   <週報輸出根>/<日期>/
#     deck.en.html / deck.zh.html   ★ 交付物：一眼看得出是哪一版語言
#     deck.json / strings.zh.json   單一事實來源與字串對照表
#     figures/*.svg                 兩份 HTML 都引用它（相對於 deck.json 所在目錄）
#     _work/1_..4_                  過程產物，按流程階段分類（哪個檔屬於哪一階段
#                                   見下面的 WORK_FILE_RULES，⛔ 只有那一份）
#       1_materials/  materials.md、deck.draft.json、plan.todo.json、merge_groups.*、threads.*
#       2_layer1/     layer1.md/json、layer1_confirmed.json
#       3_layer2/     layer2.T*.md/json
#       3b_specs/     逐頁構圖 spec 暫存檔（<slide id>.json）
#       4_slides/     slides.T*.json、compositions.T*.md/json、shoot_check.<lang>.txt
#       _briefs/      brief.<role>[.<thread>].md（派遣包；跨階段，所以不編號）
#     _export/                      截圖與 pptx（不跑就不該存在）
#
# 為什麼過程產物的資料夾用 `_` 開頭：排序時沉到底，
# 打開日期目錄第一眼看到的是兩份 HTML，而不是 30 個中間檔。
#
# ⚠️ `deck.json` **仍然放在日期目錄本身**，不進 `_work/`：
#    render_deck.py / check_deck.py / to_pptx.py / shoot.py 全都是
#    「從 deck.json 所在目錄推算」figures、strings、輸出位置的。
#    把它挪進子目錄會讓那些推算整組錯位。

WORK_STAGES = {
    "materials": "1_materials",   # merge_groups / threads / materials / deck.draft / plan.todo
    "layer1":    "2_layer1",      # layer1.md、layer1_confirmed.json
    "layer2":    "3_layer2",      # layer2.md、layer2.T*.md/json
    "specs":     "3b_specs",      # 逐頁構圖 spec 暫存檔（<slide id>.json）
    "slides":    "4_slides",      # slides.T*.json、compositions.T*.md/json
    # ⚠️ **不帶編號是刻意的**：brief 是「派遣前的打包」，而派遣發生在**每一個**
    #    階段之前（finder 在 layer1 前、planner 在 layer2 前、builder 在 slides 前），
    #    它不屬於流程上的某一格。給它一個 `0_` 或 `1b_` 都會撒謊 ——
    #    數字前綴在這套命名裡的意思就是「流程順序」。
    #    `_` 前綴沿用 `_work`／`_export` 的慣例：非流程產物，排序沉到底，
    #    打開 `_work/` 第一眼看到的仍是 1→4 的流程。
    "briefs":    "_briefs",       # brief.<role>[.<thread>].md（派遣包）
}

# 檔名 → 階段。⚠️ **後補（N14）**：`WORK_STAGES` 原本只說了「有哪幾個階段」，
# 沒說「哪個檔屬於哪一階段」—— 那條事實只寫在 SKILL.md 的目錄圖（散文）裡，
# 於是兩個 builder 都把 `compositions.A/B.json` 寫在**日期目錄最上層**，
# 其中一個還自行開了 `_work/_specs/`。三個地方各寫各的，正是「同一事實寫在
# 兩個地方必定分岔」。現在把對應關係放進**同一份定義**，並提供 `work_file()`，
# 讓寫檔的人只說檔名、不必自己記路徑。
#
# ⛔ 既有階段的目錄名不動（`1_materials`～`4_slides` 已經有產物在用），
#    這裡只是把「檔名歸屬」補上，外加一個新的 `specs` 階段。
WORK_FILE_RULES = (
    (r"^(materials\.md|deck\.draft\.json|plan\.todo\.json|merge_groups\.|threads\.)", "materials"),
    (r"^layer1", "layer1"),
    (r"^layer2", "layer2"),
    # 關卡的確認稿與答案檔（gate_view.py 產、check_gate.py --confirm 讀）
    (r"^gate1_", "layer1"),
    (r"^gate2_", "layer2"),
    (r"^(slides\.|compositions\.)", "slides"),
    # `shoot.py --check-only` 的實測輸出（shoot_check.<lang>.txt）——
    # layout_reviewer 的必要輸入，跟它量的那批投影片同一階段，所以歸 slides。
    # ⚠️ 分成獨立一條而不是併進上面那個 group：它不是 `slides.`／`compositions.`
    #    那種「內容產物」，是**量測紀錄**；分開寫，下一個人看規則就知道有這個檔。
    (r"^shoot_check\.", "slides"),
    # 逐線的中文對照片段（builder 交件時附；merge_slides 併進 strings.zh.json）、
    # 退回 builder 的合成 findings、layout_reviewer 的審查包。
    (r"^strings\..+\.zh\.json$", "slides"),
    (r"^findings\.", "slides"),
    (r"^review_packet\.md$", "slides"),
    # B17-14：`layout_review.md` 是審查紀錄（過程產物），跟它審的那批投影片同一階段。
    #    舊版角色規格寫在日期目錄最上層，與「交付物在最上層、過程產物進 _work/」牴觸。
    (r"^layout_review\.md$", "slides"),
    # `verify.py --quiet` 的完整輸出（verify.<線|all>.log）—— 摘要印在終端，全文落地，
    #    builder 不必把七支腳本的全文讀進 context。
    (r"^verify\..*\.log$", "slides"),
    (r"(^spec\.|\.spec\.json$|^[A-Za-z]+\d+\.json$)", "specs"),
    (r"^brief\.", "briefs"),
)


def stage_of(name):
    """這個檔名屬於哪一個階段？認不出來回 None（呼叫端自己決定要不要停）。

    ⚠️ 只看**檔名**，不看內容 —— 這份對應表是要給人與 subagent 讀的，
    看得懂才不會又各寫各的。
    """
    import re as _re
    base = os.path.basename(name)
    for pat, stage in WORK_FILE_RULES:
        if _re.search(pat, base):
            return stage
    return None


def work_file(out, name, create=True):
    """過程產物的**完整路徑**：只給檔名，由這裡決定它該落在哪個階段目錄。

        paths.work_file(out, "compositions.A.json")
            → <日期目錄>/_work/4_slides/compositions.A.json

    ⛔ 不要在各腳本／各 subagent 說明裡自己拼 `_work/...` —— N14 就是那樣來的：
    SKILL.md 說 `compositions.T*.json` 在 `4_slides/`，實際卻寫在日期目錄最上層，
    而且**沒有任何機制會發現**（沒人檢查，兩邊就這樣分岔了一整輪）。

    認不出來的檔名直接報錯，不猜一個位置放下去 —— 猜錯只會再生出一個
    「產物散在不該在的地方」的下一輪。
    """
    stage = stage_of(name)
    if stage is None:
        raise ValueError(
            f"不知道 {os.path.basename(name)!r} 屬於哪個階段。"
            f"請在 paths.py 的 WORK_FILE_RULES 補一條（現有階段：{sorted(WORK_STAGES)}），"
            f"⛔ 不要繞過去自己拼路徑。")
    return os.path.join(work_dir(out, stage, create=create), os.path.basename(name))


def work_dir(out, stage, create=False):
    """過程產物的子目錄：`<日期目錄>/_work/<階段>`。

    `stage` 取 `WORK_STAGES` 的鍵。`create=True` 時順手建好 ——
    **使用者只會傳一個 `--out <日期目錄>`**，子資料夾由腳本自己開，
    ⛔ 不要逼人記四個子路徑。
    """
    if stage not in WORK_STAGES:
        raise ValueError(f"未知的階段 {stage!r}，可用：{sorted(WORK_STAGES)}")
    d = os.path.join(out, "_work", WORK_STAGES[stage])
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def export_dir(out, create=False):
    """截圖與 pptx 的去處：`<日期目錄>/_export`。

    ⚠️ **不跑截圖／pptx 就不該存在** —— 所以預設 `create=False`，
    只有真的要寫檔的那一刻才建。
    """
    d = os.path.join(out, "_export")
    if create:
        os.makedirs(d, exist_ok=True)
    return d




if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "data-dir":
        print(data_dir())
    elif cmd == "reports-root":
        print(reports_root())
    elif cmd == "project-root":
        print(project_root())
    elif cmd == "log-repo":
        print(log_repo())
    elif cmd == "daily-log-dir":
        print(_daily_log_dir() or "")
    elif cmd == "transcript-dirs":
        for p in transcript_dirs():
            print(p)
    elif cmd == "effort-log":
        print(effort_log())
    elif cmd == "explanations":
        # ⚠️ 不存在時 **exit 1 並印到 stderr** —— 協調者才分得出「沒有這個檔」
        #    與「有但今天沒有待答提問」。⛔ 不要靜默印一個不存在的路徑。
        p = explanations()
        if not os.path.isfile(p):
            sys.exit("找不到 %s（本週無跨週解釋資產；⛔ 不等於教授沒有提問）" % p)
        print(p)
    elif cmd == "last-deck":
        # 上一份週報的 deck.json；沒有任何一份時 exit 1（第一份週報的正常情況）
        p = last_deck()
        if not p:
            sys.exit("%s 底下找不到任何一份 deck.json（第一份週報？改用 --last N）"
                     % reports_root())
        print(p)
    else:
        sys.exit("用法：paths.py data-dir|reports-root|project-root|log-repo|"
                 "daily-log-dir|transcript-dirs|effort-log|explanations|last-deck|"
                 "last-report-json")
