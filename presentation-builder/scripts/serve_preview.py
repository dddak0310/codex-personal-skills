#!/usr/bin/env python3
"""Serve weekly deck previews on a reusable port and return a browser-safe URL."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import os
from pathlib import Path

PORT_MIN = 44550
PORT_MAX = 44599
STATE_DIR = Path.home() / ".cache" / "presentation-builder"
STATE_FILE = STATE_DIR / "preview-port.json"
LOG_FILE = STATE_DIR / "preview-server.log"
DEFAULT_PUBLIC_HOST = os.environ.get("WEEKLY_DECK_PREVIEW_HOST", "192.168.2.57")
LOCAL_CHECK_HOST = "127.0.0.1"


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((LOCAL_CHECK_HOST, port)) != 0


def url_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def load_cached_port() -> int | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    port = data.get("port")
    return port if isinstance(port, int) else None


def save_cached_port(port: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"port": port}, indent=2), encoding="utf-8")


def candidate_ports(preferred: int | None) -> list[tuple[int, bool]]:
    """Return (port, trusted) pairs. `trusted` ports are ones this user's own
    state previously started, so a healthy response there is safe to reuse.
    Ports found only by scanning the shared range are NOT trusted for reuse —
    on a shared multi-user server, another user's server may already be
    listening there and happen to answer the same <date>/deck.html relative
    path (everyone uses the same naming convention), which would silently
    hand back someone else's deck."""
    seen: set[int] = set()
    ordered: list[tuple[int, bool]] = []
    for port in (preferred, load_cached_port()):
        if port is None or port in seen:
            continue
        seen.add(port)
        ordered.append((port, True))
    for port in range(PORT_MIN, PORT_MAX + 1):
        if port in seen:
            continue
        seen.add(port)
        ordered.append((port, False))
    return ordered


# Plain `http.server` sends no cache headers, so browsers keep serving a stale
# deck.html / figure after a rebuild — the page looks unchanged and the edit
# appears to have been lost. Serve everything no-store instead.
NOCACHE_SERVER = """
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


port, root = int(sys.argv[1]), sys.argv[2]
ThreadingHTTPServer(("0.0.0.0", port), partial(NoCacheHandler, directory=root)).serve_forever()
"""


def start_server(root_dir: Path, port: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("ab") as log:
        subprocess.Popen(
            [sys.executable, "-c", NOCACHE_SERVER, str(port), str(root_dir)],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )


def ensure_assets_link(folder: Path) -> None:
    """Make the shared stylesheet reachable from inside the report folder.

    Single-page HTML links the stylesheet relatively, but the server root is the
    report folder's parent, so a path climbing out to ``~/.claude`` lands outside
    the root and 404s. A symlink named ``assets`` keeps the URL inside the root
    while still resolving to the skill's real assets, and serving the whole home
    directory instead would expose far more than a stylesheet on a shared host.
    """
    link = folder / "assets"
    target = Path(os.path.relpath(
        Path.home() / ".codex/skills/presentation-builder/assets",
        start=folder,
    ))
    if link.is_symlink():
        if Path(os.readlink(link)) == target:
            return
        link.unlink()
    elif link.exists():
        # A real directory of that name — leave it alone rather than clobber it.
        return
    link.symlink_to(target, target_is_directory=True)


def ensure_preview(
    folder: Path, preferred_port: int | None, public_host: str
) -> str:
    folder = folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"[錯誤] 找不到資料夾 {folder}")

    ensure_assets_link(folder)
    root_dir = folder.parent
    # 資料夾名稱可能是中文（進度報告YYYYMMDD），必須先 percent-encode，
    # 否則 http.client 在送出 request line 時會 UnicodeEncodeError。
    rel_path = urllib.parse.quote(f"{folder.name}/deck.html")

    for port, trusted in candidate_ports(preferred_port):
        healthcheck_url = f"http://{LOCAL_CHECK_HOST}:{port}/{rel_path}"
        public_url = f"http://{public_host}:{port}/{rel_path}"
        if trusted and url_ok(healthcheck_url):
            save_cached_port(port)
            return public_url
        if not is_port_free(port):
            # Occupied by something else (possibly another user's server on
            # this shared host) — never reuse an untrusted, already-bound
            # port just because it happens to answer 200.
            continue

        start_server(root_dir, port)
        for _ in range(20):
            time.sleep(0.25)
            if url_ok(healthcheck_url):
                save_cached_port(port)
                return public_url

    raise SystemExit(
        f"[錯誤] 無法在 {PORT_MIN}-{PORT_MAX} 之間建立 preview server"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, help="報告資料夾，例如 REPORT_ROOT/YYYYMMDD")
    parser.add_argument("--port", type=int, default=None, help="優先重用的 preview port")
    parser.add_argument(
        "--public-host",
        default=DEFAULT_PUBLIC_HOST,
        help=(
            "回傳給瀏覽器的主機名稱或 IP。"
            " 遠端 server 預設使用 192.168.2.57，可用環境變數"
            " WEEKLY_DECK_PREVIEW_HOST 覆寫。"
        ),
    )
    args = parser.parse_args()

    url = ensure_preview(args.folder, args.port, args.public_host)
    print(url)


if __name__ == "__main__":
    main()
