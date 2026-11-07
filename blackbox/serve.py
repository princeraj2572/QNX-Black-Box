"""Live preview: serve the dashboard for a trace, rebuilt on every request."""

from http.server import BaseHTTPRequestHandler, HTTPServer

from .analysis import analyze
from .config import ConfigError, load_config
from .dashboard import render_html
from .parser import ParseError, parse_file
from .report import build_report

REFRESH_SECONDS = 2


def build_page(trace_path: str, config_path: str) -> str:
    """Re-read the files and render the dashboard; raises on bad input."""
    config = load_config(config_path)
    events = parse_file(trace_path)
    page = render_html(build_report(events, analyze(events, config), config))
    refresh = f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">\n'
    return page.replace("<title>", refresh + "<title>", 1)


def make_server(trace_path: str, config_path: str, port: int = 8000) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/":
                self.send_error(404)
                return
            try:
                body, status, ctype = build_page(trace_path, config_path), 200, "text/html"
            except (OSError, ParseError, ConfigError) as exc:
                body, status, ctype = f"error: {exc}\n", 500, "text/plain"
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # keep the terminal quiet
            pass

    # Loopback only: the page shows the trace contents.
    return HTTPServer(("127.0.0.1", port), Handler)
