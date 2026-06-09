"""Loopback HTTP server for the attendance heatmap.

Serves the interactive dashboard and the print report as HTML pages, bound to
127.0.0.1 only (never exposed to the network) on an OS-assigned ephemeral port.
Started on demand from the Heatmap sidebar screen; runs in a daemon thread that
dies when the app process exits. Each request queries SQLite live and renders a
Jinja2 template (reusing the reports stack, so template paths resolve in both
dev and the PyInstaller bundle).
"""
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context
from src.reports.html_renderer import _build_env

_server = None
_port = None
_lock = threading.Lock()


def _render(path, qs):
    month = (qs.get("month", [""])[0] or "").strip()
    with get_connection(DB_PATH) as conn:
        if not month:
            month = get_setting(conn, "current_month", default="") or ""
        if not month:
            month = date.today().strftime("%Y-%m")
        env = _build_env()
        if path == "/heatmap":
            ctx = build_heatmap_context(conn, month, exclude_outliers=False)
            return env.get_template("heatmap.html.j2").render(**ctx)
        # /heatmap/print
        scope = qs.get("scope", ["full"])[0]
        outlier = qs.get("outlier", ["inc"])[0]
        ctx = build_heatmap_context(conn, month, exclude_outliers=(outlier == "exc"))
        return env.get_template("heatmap_print.html.j2").render(scope=scope, **ctx)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default stderr access logging
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path not in ("/heatmap", "/heatmap/print"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        try:
            body = _render(u.path, parse_qs(u.query)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # never let a request crash the app
            msg = ("Heatmap render error: %r" % (e,)).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg)


def ensure_started() -> str:
    """Start the loopback server if not already running; return its base URL.
    Idempotent — repeated calls return the same URL."""
    global _server, _port
    with _lock:
        if _server is not None:
            return f"http://127.0.0.1:{_port}"
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        _port = srv.server_address[1]
        _server = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{_port}"
