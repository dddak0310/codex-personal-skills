#!/usr/bin/env python3
"""Write and validate daily-report page-to-session provenance without touching HTML."""

import argparse
import json
import sys
from pathlib import Path


def parse_page_spec(value: str) -> tuple[str, list[str]]:
    try:
        page, session_list = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected PAGE=source:session_id[,source:session_id]"
        ) from exc
    page = page.strip()
    sessions = [item.strip() for item in session_list.split(",") if item.strip()]
    if not page.endswith(".html") or page == "deck.html":
        raise argparse.ArgumentTypeError(
            "page must name one source slide HTML file, not deck.html"
        )
    if not sessions:
        raise argparse.ArgumentTypeError(
            "each page must cite at least one source:session_id"
        )
    return page, sessions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True,
                        help="daily report folder containing the source slide HTML files")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page", action="append", type=parse_page_spec, required=True,
                        help="PAGE=source:session_id[,source:session_id]")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("report_kind") != "daily":
        print("[ERROR] --manifest is not a daily session-manifest.json schema v1", file=sys.stderr)
        return 2

    known = {
        f"{item['source']}:{item['session_id']}"
        for item in manifest.get("sessions", [])
    }
    pages = []
    seen_pages = set()
    for page, refs in args.page:
        if page in seen_pages:
            print(f"[ERROR] page is supplied more than once: {page}", file=sys.stderr)
            return 2
        seen_pages.add(page)
        missing = sorted(set(refs) - known)
        if missing:
            print(f"[ERROR] {page} cites sessions absent from manifest: {', '.join(missing)}", file=sys.stderr)
            return 2
        pages.append({
            "page": page,
            "sessions": [
                {"source": ref.split(":", 1)[0], "session_id": ref.split(":", 1)[1]}
                for ref in dict.fromkeys(refs)
            ],
        })

    expected_pages = {
        item.name
        for item in args.report_dir.glob("*.html")
        if item.name != "deck.html" and not item.name.startswith("_")
    }
    cited_pages = set(seen_pages)
    missing_pages = sorted(expected_pages - cited_pages)
    unknown_pages = sorted(cited_pages - expected_pages)
    if missing_pages or unknown_pages:
        details = []
        if missing_pages:
            details.append(f"missing page source records: {', '.join(missing_pages)}")
        if unknown_pages:
            details.append(f"page records without source slide files: {', '.join(unknown_pages)}")
        print(f"[ERROR] {'; '.join(details)}", file=sys.stderr)
        return 2

    payload = {
        "schema_version": 1,
        "report_kind": "daily",
        "report_date": manifest["report_date"],
        "manifest": args.manifest.name,
        "pages": pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] wrote {len(pages)} page source record(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
