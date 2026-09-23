#!/usr/bin/env python3
"""彙整 builder：把一個資料夾裡的每頁 HTML 合成一份可投影/可匯出 PPTX 的 deck.html。

用法:
    python build.py <folder> [--name SLUG] [--presenter "Hung-Lin, Chen"]
                             [--title "標題"] [--date YYYYMMDD] [--titlecover]

行為:
    - 收集 <folder>/*.html（排除 deck.html、底線開頭檔），依檔名排序。
    - 每頁只取 <!-- SLIDE:START --> 與 <!-- SLIDE:END --> 之間的內容。
    - 預設**不**加標題封面；加 --titlecover 才會在最前面插入一張進度報告封面。
    - 報告者未指定時自動解析：$DECK_PRESENTER > presenters.json（依 OS 使用者）> 使用者名。
    - 把共用 slides.css / deck.js 內嵌進 deck.html，產出單一可攜檔。
"""
import argparse
import datetime as dt
import getpass
import json
import os
import re
import sys
from pathlib import Path
from scripts.validate_report import validate_report

SKILL_DIR = Path(__file__).resolve().parent
ASSETS = SKILL_DIR / "assets"
PRESENTERS = SKILL_DIR / "presenters.json"
MARKER = re.compile(r"<!--\s*SLIDE:START.*?-->(.*?)<!--\s*SLIDE:END\s*-->", re.S)


def resolve_presenter(override: str | None) -> str:
    """依序解析報告者名字：--presenter > $DECK_PRESENTER > presenters.json（依 OS 使用者）> 使用者名。

    這是團隊共用 skill，presenter 不能寫死成某個人；改用當前使用者自動對應。
    要加入自己：在 presenters.json 補一筆 "<OS使用者名>": "<正式英文名>"。
    """
    if override:
        return override
    env = os.environ.get("DECK_PRESENTER")
    if env:
        return env
    user = getpass.getuser()
    if PRESENTERS.is_file():
        try:
            mapping = json.loads(PRESENTERS.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            mapping = {}
        if user in mapping:
            return mapping[user]
    return user


def extract_slide(html: str, fname: str) -> str:
    m = MARKER.search(html)
    if not m:
        sys.exit(f"[錯誤] {fname} 找不到 <!-- SLIDE:START --> / <!-- SLIDE:END --> 標記")
    return m.group(1).strip()


def derive_date(folder: Path, override: str | None) -> str:
    if override:
        return override
    named_date = re.search(r"(?<!\d)(\d{8})(?!\d)", folder.name)
    if named_date:
        return named_date.group(1)
    return dt.date.today().strftime("%Y%m%d")


def derive_name(folder: Path, override: str | None) -> str:
    """匯出檔名（PPTX / 單頁 PNG / 可攜版 HTML）。

    資料夾後綴只區分日／週／月；匯出名稱仍使用原有報告名稱。
    `YYYYMMDD-w` → `進度報告YYYYMMDD-<OS使用者名>`，`YYYYMMDD-m` → `月會報告YYYYMM`。
    舊有純日期資料夾維持 `進度報告YYYYMMDD`；其他歷史命名原樣沿用。
    --name 一律優先。
    """
    if override:
        return override
    weekly = re.fullmatch(r"(\d{8})-w", folder.name)
    if weekly:
        return f"進度報告{weekly.group(1)}-{getpass.getuser()}"
    monthly = re.fullmatch(r"(\d{8})-m", folder.name)
    if monthly:
        return f"月會報告{monthly.group(1)[:6]}"
    if re.fullmatch(r"\d{8}", folder.name):
        return f"進度報告{folder.name}"
    return folder.name


ORDER_FILE = "order.txt"


def discover_pages(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.glob("*.html")
        if p.name != "deck.html" and not p.name.startswith("_")
    )


def order_pages(folder: Path) -> list[Path]:
    """Page order: order.txt if present, otherwise filename sort.

    Filename prefixes are a poor ordering key — decks get reordered while they are being
    written, and two people adding a page on the same day collide on the same number.
    order.txt decouples the two: reorder by moving a line, never by renaming a file.

    Files listed but missing are a hard error (something was renamed). Files present but
    unlisted are appended in filename order with a warning, so a page can never silently
    vanish from the deck.
    """
    found = discover_pages(folder)
    manifest = folder / ORDER_FILE
    if not manifest.is_file():
        return found

    by_name = {p.name: p for p in found}
    listed: list[Path] = []
    missing: list[str] = []
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line in by_name:
            listed.append(by_name.pop(line))
        else:
            missing.append(line)
    if missing:
        sys.exit(f"[錯誤] {ORDER_FILE} 列出的頁面不存在：{', '.join(missing)}\n"
                 f"       檔案被改名或刪除了，請更新 {manifest}")
    if by_name:
        extra = sorted(by_name)
        print(f"[提醒] 這些頁面不在 {ORDER_FILE} 裡，已附在最後：{', '.join(extra)}")
        listed.extend(by_name[n] for n in extra)
    return listed


def write_order(folder: Path) -> Path:
    """Write order.txt reflecting the current filename order, for hand-editing after."""
    pages = discover_pages(folder)
    if not pages:
        sys.exit(f"[錯誤] {folder} 底下沒有可用的頁面 HTML")
    manifest = folder / ORDER_FILE
    manifest.write_text(
        "# 投影片順序：一行一個檔名，改順序＝搬動行，不需要改檔名。\n"
        "# 以 # 開頭或空白行會被忽略；沒列到的頁面會被附在最後並提醒。\n"
        + "".join(f"{p.name}\n" for p in pages),
        encoding="utf-8")
    return manifest


def build(folder: Path, name: str, presenter: str, title: str,
          date: str, titlecover: bool, pages: list[Path] | None = None) -> Path:
    pages = order_pages(folder) if pages is None else pages
    if not pages:
        sys.exit(f"[錯誤] {folder} 底下沒有可用的頁面 HTML")

    blocks: list[str] = []
    if titlecover:
        blocks.append(
            '<div class="slide-outer" data-titlecover="1">\n'
            '  <div class="slide" style="display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;">\n'
            f'    <div style="font-size:52px;font-weight:800;letter-spacing:4px;margin-bottom:22px;">進度報告</div>\n'
            f'    <div style="font-size:22px;color:#6b7280;letter-spacing:3px;margin-bottom:10px;">{date}</div>\n'
            f'    <div style="font-size:24px;font-weight:600;color:#344054;">{presenter}</div>\n'
            '  </div>\n'
            '</div>'
        )
    for p in pages:
        blocks.append(extract_slide(p.read_text(encoding="utf-8"), p.name))

    css = (ASSETS / "slides.css").read_text(encoding="utf-8")
    js = (ASSETS / "deck.js").read_text(encoding="utf-8")
    body = "\n\n".join(blocks)

    deck = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js"></script>
<style>
{css}
</style>
</head>
<body>
<button class="modetoggle" id="copyImgBtn" style="right:490px;" title="複製當前頁成圖片（快捷鍵 c）；非安全連線則改下載 PNG">⧉ 複製本頁</button>
<button class="modetoggle" id="exportPortableBtn" style="right:330px;">⇓ 匯出可攜版 HTML</button>
<button class="modetoggle" id="exportBtn" style="right:170px;">↓ 匯出 PPTX</button>
<button class="modetoggle" id="modeBtn">▶ 投影片模式</button>
<div class="wrap">
  <h1>{title}</h1>
  <div class="sub">{folder.name}</div>

{body}

</div>

<div class="nav" id="nav">
  <button id="prev">← 上一頁</button>
  <div class="dots" id="dots"></div>
  <span class="count" id="count"></span>
  <button id="next">下一頁 →</button>
</div>
<button class="nav-toggle" id="navToggle" title="收合導覽列">▼</button>

<script>window.DECK_NAME = {name!r}; window.DECK_DATE = {date!r}; window.DECK_PRESENTER = {presenter!r};</script>
<script>
{js}
</script>
</body>
</html>
"""
    out = folder / "deck.html"
    out.write_text(deck, encoding="utf-8")
    errors = validate_report(folder, out, date, titlecover, presenter)
    if errors:
        details = "\n".join(f"[錯誤] {error}" for error in errors)
        raise SystemExit(details)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="放各頁 HTML 的資料夾，如 REPORT_ROOT/YYYYMMDD-w 或 YYYYMMDD-m")
    ap.add_argument("--name", default=None,
                    help="PPTX 檔名（slug）；-w 匯出進度報告YYYYMMDD-使用者名，-m 匯出月會報告YYYYMM")
    ap.add_argument("--presenter", default=None,
                    help="報告者名字；未指定時自動用 $DECK_PRESENTER / presenters.json（依 OS 使用者）")
    ap.add_argument("--title", default="進度報告")
    ap.add_argument("--date", default=None, help="標題封面日期 YYYYMMDD，預設取資料夾名")
    ap.add_argument("--titlecover", action="store_true", help="在最前面加進度報告標題封面")
    ap.add_argument("--init-order", action="store_true",
                    help=f"依目前檔名順序產生 {ORDER_FILE} 後結束；之後改順序只要搬動裡面的行")
    a = ap.parse_args()

    folder = a.folder.resolve()
    if not folder.is_dir():
        sys.exit(f"[錯誤] 找不到資料夾 {folder}")
    if a.init_order:
        manifest = write_order(folder)
        print(f"✅ 已寫出 {manifest}")
        print("   改頁面順序＝搬動裡面的行，不用改檔名。")
        return
    name = derive_name(folder, a.name)
    presenter = resolve_presenter(a.presenter)
    pages = order_pages(folder)
    out = build(folder, name, presenter, a.title,
                derive_date(folder, a.date), a.titlecover, pages)
    src = ORDER_FILE if (folder / ORDER_FILE).is_file() else "檔名排序"
    print(f"✅ 已彙整 {len(pages)} 頁 → {out}（順序來源：{src}）")
    print("   頁面順序：" + " → ".join(p.name for p in pages))


if __name__ == "__main__":
    main()
