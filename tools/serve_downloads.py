#!/usr/bin/env python3
"""Small static server for media/ with downloads that work on Android Chrome.

Routes:
    /                         -> media/index.html
    /<name>                   -> static file, with HTTP Range support (inline video)
    /download/<name>          -> same file, forced as an attachment
    /download/video           -> alias for the final rendered MP4
    /download                 -> alias for the final rendered MP4
    /<name>?dl=1              -> forced attachment without changing the path
    /api/video                -> JSON describing the exact final MP4 on disk

Why a custom server instead of ``python3 -m http.server``:

* Android Chrome frequently *plays* a video/mp4 inline when the response has no
  ``Content-Disposition: attachment``.  The download routes always send it.
* Android's download manager and the browser's media element both need
  ``Accept-Ranges: bytes`` / 206 Partial Content plus an exact Content-Length.
  http.server supports neither.
* Only real media files inside media/ are served, and MP4 responses are checked
  for the ISO-BMFF ``ftyp`` box, so a Python source file can never be returned
  in place of the video.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent / "media"

# The one file the "Download Video" button points at.  Change here if you ever
# re-render under a different name; /download/video always resolves to this.
FINAL_VIDEO = "rock_singer_live_concert.mp4"
VIDEO_ALIASES = {"", "video", "final", "latest", "render", "video.mp4"}

TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def is_real_mp4(path: Path) -> bool:
    """Cheap sanity check: an MP4 must start with a 'ftyp' box."""
    try:
        with path.open("rb") as fh:
            head = fh.read(12)
        return len(head) >= 12 and head[4:8] == b"ftyp"
    except OSError:
        return False


class MediaHandler(BaseHTTPRequestHandler):
    server_version = "JewelMedia/1.1"
    protocol_version = "HTTP/1.1"  # keep-alive requires exact Content-Length

    # ------------------------------------------------------------------ helpers
    def _send_bytes(self, status: int, body: bytes, ctype: str,
                    extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _fail(self, status: int, message: str) -> None:
        self._send_bytes(status, (message + "\n").encode(), "text/plain; charset=utf-8")

    def _json(self, obj: dict) -> None:
        self._send_bytes(200, json.dumps(obj, indent=2).encode(), TYPES[".json"])

    # ------------------------------------------------------------------- routes
    def do_HEAD(self) -> None:  # noqa: N802
        self._serve()

    def do_GET(self) -> None:  # noqa: N802
        self._serve()

    def _serve(self) -> None:
        parts = urlsplit(self.path)
        raw_path = unquote(parts.path)
        query = parse_qs(parts.query)

        if raw_path == "/api/video":
            f = ROOT / FINAL_VIDEO
            self._json({
                "file": FINAL_VIDEO,
                "path": str(f.resolve()),
                "exists": f.is_file(),
                "size_bytes": f.stat().st_size if f.is_file() else 0,
                "mime": TYPES[".mp4"],
                "verified_mp4": is_real_mp4(f) if f.is_file() else False,
                "download_url": f"/download/{FINAL_VIDEO}",
            })
            return

        force_download = "dl" in query or query.get("download") == ["1"]
        if raw_path.startswith("/download"):
            force_download = True
            name = raw_path[len("/download"):].lstrip("/")
            if name in VIDEO_ALIASES:
                name = FINAL_VIDEO
        else:
            name = raw_path.lstrip("/") or "index.html"

        # Never escape media/ and never serve source code.  A request for
        # /download/make_concert_video.py is refused rather than silently
        # returning the script as "the video".
        name = Path(name).name
        suffix = Path(name).suffix.lower()
        if name.startswith(".") or suffix not in TYPES:
            if suffix in {".py", ".sh", ""}:
                self._fail(403, "Only rendered media files are downloadable "
                               "(Python/source files are not served).")
            else:
                self._fail(404, "Unsupported file type.")
            return

        path = ROOT / name
        if not path.is_file():
            self._fail(404, f"Not found: {name}")
            return
        if suffix in {".mp4", ".m4v"} and not is_real_mp4(path):
            self._fail(409, f"{name} is not a valid MP4 file.")
            return

        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        byte_range = self.headers.get("Range")
        if byte_range:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range.strip())
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):                       # suffix range: bytes=-500
                    start = max(0, size - int(m.group(2)))
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return
                status = 206
            else:
                self._fail(416, "Malformed Range header.")
                return

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", TYPES[suffix])
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if force_download:
            # RFC 5987 name as well, for non-ASCII filenames on Android.
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{name}"; filename*=UTF-8\'\'{quote(name, safe="")}',
            )
            self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()

        if self.command == "HEAD":
            return
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # user cancelled the download on mobile

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} "
              f"{fmt % args}", file=sys.stderr, flush=True)


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=ROOT)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = ap.parse_args()
    ROOT = args.dir.resolve()

    final = ROOT / FINAL_VIDEO
    print(f"[server] media dir   : {ROOT}", flush=True)
    print(f"[server] final video : {final} "
          f"({final.stat().st_size:,} bytes, mp4={is_real_mp4(final)})", flush=True)
    print(f"[server] download    : /download/video -> {final.name}", flush=True)
    print(f"[server] listening   : http://{args.host}:{args.port}/", flush=True)

    httpd = ThreadingHTTPServer((args.host, args.port), MediaHandler)
    httpd.daemon_threads = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
