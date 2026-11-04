"""Single-process hosted entry point: built React files and the existing API.

Run behind a managed HTTPS proxy. The local API/Vite workflow stays unchanged.
No repository files outside the frontend build directory are served.
"""
from __future__ import annotations

import mimetypes
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def make_handler(static_root: Path):
    import api_server

    root = static_root.resolve(strict=True)
    if not (root / "index.html").is_file():
        raise ValueError("Build the frontend first: npm run build --prefix frontend")

    class HostedHandler(api_server.ApiHandler):
        def _cross_site(self) -> bool:
            # Public clients must not be able to approve their own Origin by
            # supplying X-Forwarded-Host. The public Host is preserved by Render.
            origin = self.headers.get("Origin")
            if not origin:
                return False
            if origin in api_server.ALLOWED_ORIGINS:
                return False
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return True
            return (parsed.scheme not in ("http", "https")
                    or parsed.netloc.casefold() != self.headers.get("Host", "").casefold())

        def _static(self, head_only: bool = False) -> None:
            path = unquote(urlsplit(self.path).path)
            parts = path.split("/")
            if any(p.startswith(".") for p in parts if p) or "\\" in path or "\0" in path:
                self.send_error(404)
                return
            target = (root / (path.lstrip("/") or "index.html")).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self.send_error(404)
                return
            # Source maps are not part of the public application surface.
            if target.suffix.casefold() == ".map":
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix in (".js", ".mjs"):
                content_type = "text/javascript"
            try:
                with target.open("rb") as source:
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(os.fstat(source.fileno()).st_size))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("X-Frame-Options", "DENY")
                    self.send_header("Referrer-Policy", "same-origin")
                    self.end_headers()
                    if not head_only:
                        while chunk := source.read(64 * 1024):
                            self.wfile.write(chunk)
            except OSError:
                # Do not expose filesystem paths in HTTP error messages.
                self.close_connection = True

        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/api" or path.startswith("/api/"):
                super().do_GET()
            else:
                self._static()

        def do_HEAD(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/api" or path.startswith("/api/"):
                self.send_response(405)
                self.send_header("Allow", "GET, POST, OPTIONS")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._static(head_only=True)

    return HostedHandler


class HostedServer(ThreadingHTTPServer):
    """Bound idle connections; the managed edge supplies public TLS."""

    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(20)
        return connection, address


def main() -> None:
    # Set before importing api_server, which constructs the database and auth.
    # Explicit overrides keep local HTTP verification possible.
    os.environ.setdefault("PPT_COOKIE_SECURE", "1")
    if storage := os.environ.get("PPT_STORAGE_DIR"):
        storage_root = Path(storage)
        (storage_root / "data").mkdir(parents=True, exist_ok=True)
        (storage_root / "cache").mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("PPT_DB_PATH", str(storage_root / "data" / "app.db"))
    root = Path(__file__).resolve().parent
    handler = make_handler(root / "frontend" / "dist")
    host = os.environ.get("PPT_API_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT") or os.environ.get("PPT_API_PORT", "8000"))
    with HostedServer((host, port), handler) as server:
        print(f"Microstone web + API listening on {host}:{port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
