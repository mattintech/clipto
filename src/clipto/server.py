import collections
import hmac
import http.cookies
import json
import mimetypes
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.parse
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional, Set

from clipto.totp import calculate_totp, verify_totp
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


TEXT_EXTENSIONS = {
    ".txt", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss",
    ".json", ".yaml", ".yml", ".md", ".sh", ".bash", ".zsh", ".c", ".cpp", ".h",
    ".hpp", ".rs", ".go", ".java", ".rb", ".php", ".sql", ".xml", ".csv", ".tsv",
    ".log", ".conf", ".ini", ".toml", ".dockerfile", ".r", ".swift", ".kt", ".lua",
    ".env.example", ".lock"
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}

def is_text_file(path: Path) -> bool:
    name_lower = path.name.lower()
    suffix_lower = path.suffix.lower()
    if suffix_lower in TEXT_EXTENSIONS or name_lower in {"dockerfile", "makefile", "license", "gemfile", "pipfile"}:
        return True
    if suffix_lower in IMAGE_EXTENSIONS:
        return False
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            if b"\x00" in chunk:
                return False
            chunk.decode("utf-8")
            return True
    except Exception:
        return False


class CliptoHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        upload_dir: Path,
        title: Optional[str] = None,
        once: bool = False,
        auth_token: Optional[str] = None,
        totp_secret: Optional[str] = None,
        tunnel_url: Optional[str] = None,
        share_mode: bool = False,
        share_file: Optional[Path] = None,
        ssl_cert: Optional[Path] = None,
        ssl_key: Optional[Path] = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.title = title
        self.once = once
        self.auth_token = auth_token
        self.totp_secret = totp_secret
        self.tunnel_url = tunnel_url
        self.share_mode = share_mode
        self.share_file = Path(share_file).resolve() if share_file else None
        self.ssl_cert = Path(ssl_cert).resolve() if ssl_cert else None
        self.ssl_key = Path(ssl_key).resolve() if ssl_key else None
        self.is_ssl = bool(self.ssl_cert and self.ssl_key)
        if self.is_ssl:
            import ssl
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=self.ssl_cert, keyfile=self.ssl_key)
            self.socket = context.wrap_socket(self.socket, server_side=True)
        self.uploaded_files: List[Path] = []
        self.shutdown_event = threading.Event()
        self.failed_auth_attempts = collections.defaultdict(list)
        self.authenticated_sessions: Set[str] = set()
        self.auth_lock = threading.Lock()

    def get_current_auth_key(self) -> Optional[str]:
        """Return the active auth key (dynamic TOTP code or static PIN)."""
        if self.totp_secret:
            return calculate_totp(self.totp_secret)
        return self.auth_token

    def get_mobile_url(self) -> str:
        scheme = "https" if self.is_ssl else "http"
        if self.tunnel_url:
            base = self.tunnel_url
        else:
            port = self.server_port
            tailscale_ip = get_tailscale_ip()
            if tailscale_ip:
                base = f"{scheme}://{tailscale_ip}:{port}"
            else:
                lan_ip = get_local_ip()
                if lan_ip and lan_ip != "127.0.0.1":
                    base = f"{scheme}://{lan_ip}:{port}"
                else:
                    base = f"{scheme}://localhost:{port}"

        key = self.get_current_auth_key()
        if key:
            sep = "&" if "?" in base else "/?"
            return f"{base}{sep}k={key}"
        return base

    def load_gists(self) -> List[str]:
        """Return list of filenames explicitly created or shared as gists."""
        gists: List[str] = []
        if self.share_file and self.share_file.is_file():
            gists.append(self.share_file.name)
        gists_file = self.upload_dir / ".clipto_gists.json"
        if gists_file.is_file():
            try:
                data = json.loads(gists_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and (self.upload_dir / item).is_file() and item not in gists:
                            gists.append(item)
            except Exception:
                pass
        return gists

    def record_gist(self, filename: str) -> None:
        """Persist a filename into the local gists registry."""
        gists_file = self.upload_dir / ".clipto_gists.json"
        existing: List[str] = []
        if gists_file.is_file():
            try:
                data = json.loads(gists_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    existing = [x for x in data if isinstance(x, str)]
            except Exception:
                existing = []
        if filename not in existing:
            existing.append(filename)
        try:
            gists_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass


class CliptoRequestHandler(BaseHTTPRequestHandler):
    server: CliptoHTTPServer

    def log_message(self, format, *args):
        # Suppress verbose standard logging to keep terminal clean
        pass

    def is_authenticated(self) -> bool:
        if not self.server.auth_token and not self.server.totp_secret:
            return True

        # 1. Check Cookie: clipto_auth
        cookie_header = self.headers.get("Cookie", "")
        cookies = http.cookies.SimpleCookie(cookie_header)
        if "clipto_auth" in cookies:
            cookie_val = cookies["clipto_auth"].value
            with self.server.auth_lock:
                if cookie_val in self.server.authenticated_sessions:
                    return True
            if self.server.auth_token and hmac.compare_digest(cookie_val, self.server.auth_token):
                return True

        # 2. Check Query parameter: ?k=...
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if "k" in query:
            k = query["k"][0].strip()
            if self.server.totp_secret and verify_totp(self.server.totp_secret, k):
                return True
            if self.server.auth_token and hmac.compare_digest(k, self.server.auth_token):
                return True

        # 3. Check Authorization header: Bearer <token>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            with self.server.auth_lock:
                if token in self.server.authenticated_sessions:
                    return True
            if self.server.totp_secret and verify_totp(self.server.totp_secret, token):
                return True
            if self.server.auth_token and hmac.compare_digest(token, self.server.auth_token):
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
            auth_type = "totp" if self.server.totp_secret else ("pin" if self.server.auth_token else "none")
            self.send_json(200, {
                "required": bool(self.server.auth_token or self.server.totp_secret),
                "authenticated": is_authed,
                "auth_type": auth_type,
            })
            return

        # Protected API endpoints
        if not self.is_authenticated():
            self.send_json(401, {"error": "Authentication required", "auth_required": True})
            return

        if path == "/api/info":
            auth_type = "totp" if self.server.totp_secret else ("pin" if self.server.auth_token else "none")
            self.send_json(200, {
                "hostname": socket.gethostname(),
                "dir": str(self.server.upload_dir),
                "title": self.server.title,
                "once": self.server.once,
                "tunnel_url": self.server.tunnel_url,
                "mobile_url": self.server.get_mobile_url(),
                "auth_required": bool(self.server.auth_token or self.server.totp_secret),
                "auth_type": auth_type,
                "share_mode": self.server.share_mode,
                "share_file": self.server.share_file.name if self.server.share_file else None,
                "is_ssl": self.server.is_ssl,
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
        elif path == "/api/files":
            gist_names = self.server.load_gists()
            gist_set = set(gist_names)
            files_list = []
            if self.server.share_file and self.server.share_file.is_file():
                f = self.server.share_file
                stat = f.stat()
                files_list.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                    "is_text": is_text_file(f),
                    "is_image": f.suffix.lower() in IMAGE_EXTENSIONS,
                    "is_gist": f.name in gist_set,
                    "extension": f.suffix.lower().lstrip("."),
                    "raw_url": f"/raw/{urllib.parse.quote(f.name)}",
                })
            else:
                try:
                    for entry in sorted(self.server.upload_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                        if entry.name.startswith("."):
                            continue
                        if entry.is_file():
                            stat = entry.stat()
                            files_list.append({
                                "name": entry.name,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime,
                                "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                                "is_text": is_text_file(entry),
                                "is_image": entry.suffix.lower() in IMAGE_EXTENSIONS,
                                "is_gist": entry.name in gist_set,
                                "extension": entry.suffix.lower().lstrip("."),
                                "raw_url": f"/raw/{urllib.parse.quote(entry.name)}",
                            })
                except Exception as e:
                    self.send_json(500, {"error": f"Failed to list directory: {e}"})
                    return

            self.send_json(200, {
                "files": files_list,
                "count": len(files_list),
                "share_mode": self.server.share_mode,
                "gists": gist_names,
            })
        elif path == "/api/gists":
            gist_names = self.server.load_gists()
            gists_list = []
            for name in gist_names:
                target = (self.server.upload_dir / name).resolve()
                if target.is_file():
                    stat = target.stat()
                    gists_list.append({
                        "name": target.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                        "is_text": True,
                        "is_gist": True,
                        "extension": target.suffix.lower().lstrip("."),
                        "raw_url": f"/raw/{urllib.parse.quote(target.name)}",
                    })
            self.send_json(200, {
                "gists": gists_list,
                "count": len(gists_list),
            })
        elif path == "/api/content":
            query = urllib.parse.parse_qs(parsed_url.query)
            filename = query.get("name", [None])[0]
            if not filename:
                self.send_error(400, "Missing file name")
                return

            safe_name = sanitize_filename(filename)
            target = (self.server.upload_dir / safe_name).resolve()

            try:
                target.relative_to(self.server.upload_dir)
            except ValueError:
                self.send_error(403, "Forbidden")
                return

            if not target.is_file():
                self.send_error(404, "File Not Found")
                return

            stat = target.stat()
            if stat.st_size > 2 * 1024 * 1024:
                self.send_json(400, {"error": "File exceeds 2MB preview limit. Please download directly."})
                return

            try:
                text_content = target.read_text(encoding="utf-8", errors="replace")
                lines_count = len(text_content.splitlines())
                self.send_json(200, {
                    "name": target.name,
                    "size": stat.st_size,
                    "lines": lines_count,
                    "content": text_content,
                    "raw_url": f"/raw/{urllib.parse.quote(target.name)}",
                })
            except Exception as e:
                self.send_json(500, {"error": f"Failed to read file: {e}"})
        elif path.startswith("/raw/") or path == "/raw":
            query = urllib.parse.parse_qs(parsed_url.query)
            if path.startswith("/raw/"):
                raw_target_name = urllib.parse.unquote(path[5:].strip())
            else:
                raw_target_name = query.get("name", [None])[0]

            if not raw_target_name and self.server.share_file:
                raw_target_name = self.server.share_file.name

            if not raw_target_name:
                self.send_error(400, "Missing file name for raw download")
                return

            safe_name = sanitize_filename(raw_target_name)
            target = (self.server.upload_dir / safe_name).resolve()

            try:
                target.relative_to(self.server.upload_dir)
            except ValueError:
                self.send_error(403, "Forbidden")
                return

            if not target.is_file():
                self.send_error(404, "File Not Found")
                return

            stat = target.stat()
            is_text = is_text_file(target)
            content_type = "text/plain; charset=utf-8" if is_text else (mimetypes.guess_type(str(target))[0] or "application/octet-stream")

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(stat.st_size))
            disposition = "inline" if is_text else f'attachment; filename="{target.name}"'
            self.send_header("Content-Disposition", disposition)
            self.end_headers()

            with open(target, "rb") as f:
                shutil.copyfileobj(f, self.wfile)

            if self.server.once and self.server.share_mode:
                print(f"\n✓ Delivered {target.name} to {self.client_address[0]} (one-shot transfer complete).", file=sys.stderr)
                self.server.shutdown_event.set()
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

                is_valid = False
                if self.server.totp_secret:
                    is_valid = verify_totp(self.server.totp_secret, provided_key)
                elif self.server.auth_token:
                    is_valid = hmac.compare_digest(provided_key, self.server.auth_token)
                else:
                    is_valid = True

                if is_valid:
                    # Generate session token and store
                    session_token = secrets.token_hex(20)
                    with self.server.auth_lock:
                        self.server.authenticated_sessions.add(session_token)

                    cookie_val = f"clipto_auth={session_token}; Path=/; SameSite=Strict; HttpOnly"
                    self.send_json(200, {"status": "ok", "authenticated": True}, cookie=cookie_val)
                else:
                    with self.server.auth_lock:
                        self.server.failed_auth_attempts[client_ip].append(now)
                    err_msg = "Invalid 6-digit authenticator code" if self.server.totp_secret else "Incorrect PIN or password"
                    self.send_json(401, {"error": err_msg, "authenticated": False})
            except Exception as e:
                self.send_json(400, {"error": f"Invalid request: {e}"})
            return

        # Gist creation endpoint requires authentication
        if self.path == "/api/gist":
            if not self.is_authenticated():
                self.send_json(401, {"error": "Authentication required", "auth_required": True})
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                raw_filename = (data.get("filename") or data.get("name") or "").strip()
                filename = sanitize_filename(raw_filename, default_name="gist.txt")
                content = str(data.get("content", ""))
                target_path = get_unique_path(self.server.upload_dir, filename)
                target_path.write_text(content, encoding="utf-8")
                self.server.record_gist(target_path.name)
                self.server.uploaded_files.append(target_path)
                lines_count = len(content.splitlines())
                self.send_json(200, {
                    "status": "ok",
                    "name": target_path.name,
                    "path": str(target_path.resolve()),
                    "size": target_path.stat().st_size,
                    "lines": lines_count,
                    "raw_url": f"/raw/{urllib.parse.quote(target_path.name)}",
                })
                if self.server.once and self.server.uploaded_files:
                    threading.Timer(0.3, self.server.shutdown_event.set).start()
            except Exception as e:
                self.send_json(500, {"error": f"Failed to save gist: {e}"})
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

            is_gist_upload = False
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "is_gist":
                    val = part.get_payload(decode=True).decode("utf-8", errors="ignore").strip().lower()
                    if val in ("1", "true", "yes"):
                        is_gist_upload = True

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
                            if is_gist_upload:
                                self.server.record_gist(target_path.name)
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
                    if is_gist_upload:
                        self.server.record_gist(target_path.name)
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
