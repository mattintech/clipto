import collections
import hmac
import http.cookies
import json
import mimetypes
import socket
import threading
import time
import urllib.parse
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

from clipto.utils import (
    get_local_ip,
    get_tailscale_ip,
    get_unique_path,
    render_qr_svg,
    sanitize_filename,
)


def get_web_dir() -> Path:
    """Locate the web assets directory."""
    try:
        import importlib.resources as pkg_resources
        return Path(str(pkg_resources.files("clipto").joinpath("web")))
    except Exception:
        return Path(__file__).parent / "web"


class CliptoHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        upload_dir: Path,
        title: Optional[str] = None,
        once: bool = False,
        auth_token: Optional[str] = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.title = title
        self.once = once
        self.auth_token = auth_token
        self.uploaded_files: List[Path] = []
        self.shutdown_event = threading.Event()
        self.failed_auth_attempts = collections.defaultdict(list)  # ip -> timestamps
        self.auth_lock = threading.Lock()

    def get_mobile_url(self) -> str:
        port = self.server_port
        tailscale_ip = get_tailscale_ip()
        if tailscale_ip:
            base = f"http://{tailscale_ip}:{port}"
        else:
            lan_ip = get_local_ip()
            if lan_ip and lan_ip != "127.0.0.1":
                base = f"http://{lan_ip}:{port}"
            else:
                base = f"http://localhost:{port}"

        if self.auth_token:
            return f"{base}/?k={self.auth_token}"
        return base


class CliptoRequestHandler(BaseHTTPRequestHandler):
    server: CliptoHTTPServer

    def log_message(self, format, *args):
        # Suppress verbose standard logging to keep terminal clean
        pass

    def is_authenticated(self) -> bool:
        if not self.server.auth_token:
            return True

        # 1. Check Query parameter: ?k=...
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if "k" in query:
            if hmac.compare_digest(query["k"][0], self.server.auth_token):
                return True

        # 2. Check Cookie: clipto_auth=...
        cookie_header = self.headers.get("Cookie", "")
        cookies = http.cookies.SimpleCookie(cookie_header)
        if "clipto_auth" in cookies:
            if hmac.compare_digest(cookies["clipto_auth"].value, self.server.auth_token):
                return True

        # 3. Check Authorization header: Bearer <token>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if hmac.compare_digest(token, self.server.auth_token):
                return True

        # 4. Check X-Clipto-Key header
        key_header = self.headers.get("X-Clipto-Key", "")
        if key_header and hmac.compare_digest(key_header, self.server.auth_token):
            return True

        return False

    def send_json(self, status: int, data: dict, cookie: Optional[str] = None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, file_path: Path):
        if not file_path.is_file():
            self.send_error(404, "File Not Found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".js":
            content_type = "application/javascript"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        web_dir = get_web_dir()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Public web assets (always serve so lock screen UI can load)
        if path in ("/", "/index.html"):
            self.serve_file(web_dir / "index.html")
            return
        elif path == "/static/style.css":
            self.serve_file(web_dir / "style.css")
            return
        elif path == "/static/app.js":
            self.serve_file(web_dir / "app.js")
            return
        elif path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return

        # Auth status check
        if path == "/api/auth":
            is_authed = self.is_authenticated()
            self.send_json(200, {
                "required": bool(self.server.auth_token),
                "authenticated": is_authed,
            })
            return

        # Protected API endpoints
        if not self.is_authenticated():
            self.send_json(401, {"error": "Authentication required", "auth_required": True})
            return

        if path == "/api/info":
            self.send_json(200, {
                "hostname": socket.gethostname(),
                "dir": str(self.server.upload_dir),
                "title": self.server.title,
                "once": self.server.once,
                "mobile_url": self.server.get_mobile_url(),
                "auth_required": bool(self.server.auth_token),
            })
        elif path == "/api/qr":
            mobile_url = self.server.get_mobile_url()
            svg = render_qr_svg(mobile_url)
            body = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/file":
            query = urllib.parse.parse_qs(parsed_url.query)
            filename = query.get("name", [None])[0]
            if not filename:
                self.send_error(400, "Missing file name")
                return

            safe_name = sanitize_filename(filename)
            target = (self.server.upload_dir / safe_name).resolve()

            # Prevent directory traversal attacks
            try:
                target.relative_to(self.server.upload_dir)
            except ValueError:
                self.send_error(403, "Forbidden")
                return

            if not target.is_file():
                self.send_error(404, "File Not Found")
                return

            self.serve_file(target)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        # Auth verification endpoint
        if self.path == "/api/auth":
            client_ip = self.client_address[0]
            now = time.time()

            # Rate-limiting brute force check
            with self.server.auth_lock:
                self.server.failed_auth_attempts[client_ip] = [
                    t for t in self.server.failed_auth_attempts[client_ip] if now - t < 60
                ]
                recent_failures = len(self.server.failed_auth_attempts[client_ip])

            if recent_failures >= 5:
                self.send_json(429, {"error": "Too many failed attempts. Please wait 1 minute."})
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                provided_key = str(data.get("key", "")).strip()

                if not self.server.auth_token or hmac.compare_digest(provided_key, self.server.auth_token):
                    # Success
                    cookie_val = f"clipto_auth={self.server.auth_token or ''}; Path=/; SameSite=Strict; HttpOnly"
                    self.send_json(200, {"status": "ok", "authenticated": True}, cookie=cookie_val)
                else:
                    # Failed attempt
                    with self.server.auth_lock:
                        self.server.failed_auth_attempts[client_ip].append(now)
                    self.send_json(401, {"error": "Incorrect PIN or password", "authenticated": False})
            except Exception as e:
                self.send_json(400, {"error": f"Invalid request: {e}"})
            return

        # Upload endpoint requires authentication
        if not self.is_authenticated():
            self.send_json(401, {"error": "Authentication required", "auth_required": True})
            return

        if self.path != "/api/upload":
            self.send_error(404, "Not Found")
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_error(400, "Content-Type must be multipart/form-data")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_error(400, "Invalid Content-Length")
                return

            body = self.rfile.read(content_length)
            raw_data = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8") + body
            msg = BytesParser(policy=default).parsebytes(raw_data)

            saved_results = []
            for part in msg.iter_parts():
                filename = part.get_filename()
                if not filename:
                    # Check for note or text parameter
                    name = part.get_param("name", header="content-disposition")
                    if name == "note":
                        text = part.get_payload(decode=True).decode("utf-8", errors="replace").strip()
                        if text:
                            target_path = get_unique_path(self.server.upload_dir, "note.txt")
                            target_path.write_text(text, encoding="utf-8")
                            saved_results.append({
                                "name": target_path.name,
                                "path": str(target_path.resolve()),
                                "size": target_path.stat().st_size,
                                "is_image": False,
                            })
                            self.server.uploaded_files.append(target_path)
                    continue

                clean_name = sanitize_filename(filename, default_name="upload.bin")
                target_path = get_unique_path(self.server.upload_dir, clean_name)
                payload = part.get_payload(decode=True)

                if payload is not None:
                    target_path.write_bytes(payload)
                    is_img = target_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
                    saved_results.append({
                        "name": target_path.name,
                        "path": str(target_path.resolve()),
                        "size": target_path.stat().st_size,
                        "is_image": is_img,
                    })
                    self.server.uploaded_files.append(target_path)

            self.send_json(200, {
                "status": "ok",
                "saved_files": saved_results,
            })

            if self.server.once and self.server.uploaded_files:
                # Trigger shutdown cleanly in a short delay so the response finishes sending
                threading.Timer(0.3, self.server.shutdown_event.set).start()

        except Exception as e:
            self.send_json(500, {"error": str(e)})
