#!/usr/bin/env python3
"""Validate weekly-report structure and the canonical generated cover."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


SLIDE_MARKER = re.compile(
    r"<!--\s*SLIDE:START.*?-->(.*?)<!--\s*SLIDE:END\s*-->", re.S
)
DATE_IN_FOLDER = re.compile(r"(?<!\d)(\d{8})(?!\d)")
NATIVE_COVER_TITLE = re.compile(
    r'<div style="font-size:52px;font-weight:800;letter-spacing:4px;'
    r'margin-bottom:22px;">進度報告</div>'
)


def infer_date(folder: Path) -> str | None:
    """Extract the report date from either numeric or named folders."""

    match = DATE_IN_FOLDER.search(folder.name)
    return match.group(1) if match else None


def page_files(folder: Path) -> list[Path]:
    """Return report pages in builder order."""

    return sorted(
        path
        for path in folder.glob("*.html")
        if path.name != "deck.html" and not path.name.startswith("_")
    )


def validate_report(
    folder: Path,
    deck_path: Path,
    expected_date: str,
    titlecover: bool,
    presenter: str,
) -> list[str]:
    """Return structural errors for a built report."""

    errors: list[str] = []
    pages = page_files(folder)
    if not pages:
        errors.append("report folder has no HTML pages")

    folder_date = infer_date(folder)
    if folder_date and folder_date != expected_date:
        errors.append(
            f"folder date {folder_date} does not match build date {expected_date}"
        )

    for path in pages:
        text = path.read_text(encoding="utf-8")
        if len(SLIDE_MARKER.findall(text)) != 1:
            errors.append(
                f"{path.name} must contain exactly one SLIDE:START/END block"
            )

    if "01-cover.html" in {path.name for path in pages}:
        errors.append(
            "do not hand-create 01-cover.html; use build.py --titlecover"
        )

    if not deck_path.is_file():
        errors.append(f"missing built deck: {deck_path}")
        return errors

    deck = deck_path.read_text(encoding="utf-8")
    # build.py tags the generated cover as <div class="slide-outer" data-titlecover="1">,
    # so the opening tag must be matched with its optional attributes — a bare
    # '<div class="slide-outer">' match silently skips the cover.
    slide_open = re.compile(r'<div class="slide-outer"[^>]*>')
    slide_count = len(slide_open.findall(deck))
    expected_slides = len(pages) + (1 if titlecover else 0)
    if slide_count != expected_slides:
        errors.append(
            f"deck contains {slide_count} slides; expected {expected_slides}"
        )

    if titlecover:
        # The generated cover is not wrapped in page markers, so it is the
        # first slide-outer block in the assembled deck.
        slide_parts = slide_open.split(deck, 2)
        if len(slide_parts) < 2:
            errors.append("--titlecover deck has no first slide to validate")
        else:
            first_slide = slide_parts[1]
            if not NATIVE_COVER_TITLE.search(first_slide):
                errors.append("--titlecover did not produce the canonical native cover")
            if expected_date not in first_slide:
                errors.append(f"native cover date is not {expected_date}")
            if html.escape(presenter) not in first_slide:
                errors.append(f"native cover presenter is not {presenter}")
    return errors


def main() -> int:
    """Run the report validator from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--deck", type=Path, default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--titlecover", action="store_true")
    parser.add_argument("--presenter", default="")
    args = parser.parse_args()

    folder = args.folder.resolve()
    date = args.date or infer_date(folder)
    if not date:
        print("[ERROR] report date is not supplied and cannot be inferred", file=sys.stderr)
        return 2
    deck = (args.deck or folder / "deck.html").resolve()
    errors = validate_report(folder, deck, date, args.titlecover, args.presenter)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(f"[OK] report structure valid: {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
