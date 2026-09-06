import json
import mimetypes
import socket
import threading
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

from clipto.utils import get_unique_path, sanitize_filename


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
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.title = title
        self.once = once
        self.uploaded_files: List[Path] = []
        self.shutdown_event = threading.Event()


class CliptoRequestHandler(BaseHTTPRequestHandler):
    server: CliptoHTTPServer

    def log_message(self, format, *args):
        # Suppress verbose standard logging to keep terminal clean
        pass

    def send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
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
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            self.serve_file(web_dir / "index.html")
        elif path == "/static/style.css":
            self.serve_file(web_dir / "style.css")
        elif path == "/static/app.js":
            self.serve_file(web_dir / "app.js")
        elif path == "/api/info":
            self.send_json(200, {
                "hostname": socket.gethostname(),
                "dir": str(self.server.upload_dir),
                "title": self.server.title,
                "once": self.server.once,
            })
        elif path == "/api/health":
            self.send_json(200, {"status": "ok"})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
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
                            })
                            self.server.uploaded_files.append(target_path)
                    continue

                clean_name = sanitize_filename(filename, default_name="upload.bin")
                target_path = get_unique_path(self.server.upload_dir, clean_name)
                payload = part.get_payload(decode=True)

                if payload is not None:
                    target_path.write_bytes(payload)
                    saved_results.append({
                        "name": target_path.name,
                        "path": str(target_path.resolve()),
                        "size": target_path.stat().st_size,
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
