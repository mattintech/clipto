import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from clipto.server import CliptoHTTPServer, CliptoRequestHandler
from clipto.utils import find_available_port, get_unique_path, sanitize_filename


class TestCliptoUtils(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("valid_image.png"), "valid_image.png")
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("bad*char?.jpg"), "bad_char_.jpg")
        self.assertEqual(sanitize_filename(""), "upload")

    def test_get_unique_path(self):
        f1 = get_unique_path(self.temp_dir, "test.txt")
        self.assertEqual(f1.name, "test.txt")
        f1.write_text("first")

        f2 = get_unique_path(self.temp_dir, "test.txt")
        self.assertEqual(f2.name, "test (1).txt")
        f2.write_text("second")

        f3 = get_unique_path(self.temp_dir, "test.txt")
        self.assertEqual(f3.name, "test (2).txt")

    def test_find_available_port(self):
        port = find_available_port(0)
        self.assertGreater(port, 0)


class TestCliptoServer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.port = find_available_port(0)
        self.server = CliptoHTTPServer(
            ("127.0.0.1", self.port),
            CliptoRequestHandler,
            upload_dir=self.temp_dir,
            title="Test Session",
            once=False,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_info(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/info") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["title"], "Test Session")
            self.assertEqual(data["dir"], str(self.temp_dir.resolve()))

    def test_index_html(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode()
            self.assertIn("Clipto", html)

    def test_file_upload(self):
        boundary = "----TestBoundary123456"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="files"; filename="screenshot.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
            "FAKEDATA_IMAGE_CONTENT\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode())
            self.assertEqual(res_data["status"], "ok")
            self.assertEqual(len(res_data["saved_files"]), 1)
            self.assertEqual(res_data["saved_files"][0]["name"], "screenshot.png")

        saved_file = self.temp_dir / "screenshot.png"
        self.assertTrue(saved_file.exists())
        self.assertEqual(saved_file.read_text(), "FAKEDATA_IMAGE_CONTENT")

    def test_note_upload(self):
        boundary = "----TestBoundary789012"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="note"\r\n\r\n'
            "Some important error log trace\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode())
            self.assertEqual(res_data["status"], "ok")
            self.assertEqual(len(res_data["saved_files"]), 1)
            self.assertEqual(res_data["saved_files"][0]["name"], "note.txt")

        saved_note = self.temp_dir / "note.txt"
        self.assertTrue(saved_note.exists())
        self.assertEqual(saved_note.read_text(), "Some important error log trace")


if __name__ == "__main__":
    unittest.main()

    def test_file_download_and_traversal_prevention(self):
        # Create a test file
        test_file = self.temp_dir / "preview.png"
        test_file.write_bytes(b"PNG_BYTES")

        # Test valid download
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/file?name=preview.png") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read(), b"PNG_BYTES")

        # Test traversal attack prevention
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/file?name=../../etc/passwd")
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, [400, 403, 404])

    def test_visible_width_and_ansi(self):
        from clipto.utils import strip_ansi, visible_width

        plain = "Hello world"
        self.assertEqual(visible_width(plain), 11)

        hyperlink = "\033]8;;http://localhost:8765\033\\http://localhost:8765\033]8;;\033\\"
        self.assertEqual(strip_ansi(hyperlink), "http://localhost:8765")
        self.assertEqual(visible_width(hyperlink), len("http://localhost:8765"))

        emoji_str = "📎 Clipto v0.1.0"
        # Emoji 📎 has width 2
        self.assertEqual(visible_width(emoji_str), 16)

    def test_qr_generation(self):
        from clipto.utils import render_qr_svg, render_qr_terminal

        url = "http://192.168.1.100:8765"
        qr_terminal = render_qr_terminal(url)
        self.assertTrue(len(qr_terminal) > 0)
        self.assertIn("\033[47", qr_terminal)

        qr_svg = render_qr_svg(url)
        self.assertTrue(qr_svg.startswith("<svg"))
        self.assertIn("</svg>", qr_svg)

    def test_api_qr_endpoint(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/qr") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Type"), "image/svg+xml; charset=utf-8")
            content = resp.read().decode("utf-8")
            self.assertTrue(content.startswith("<svg"))

    def test_pin_and_auth_protection(self):
        # Create server with PIN
        pin_dir = Path(tempfile.mkdtemp())
        pin_port = find_available_port(0)
        pin_server = CliptoHTTPServer(
            ("127.0.0.1", pin_port),
            CliptoRequestHandler,
            upload_dir=pin_dir,
            title="Protected Session",
            once=False,
            auth_token="1234",
        )
        pin_thread = threading.Thread(target=pin_server.serve_forever, daemon=True)
        pin_thread.start()
        time.sleep(0.1)

        try:
            # 1. Unauthenticated request to /api/info should fail with 401
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{pin_port}/api/info")
                self.fail("Expected HTTPError 401")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401)

            # 2. Authenticate with wrong PIN should return 401
            auth_req = urllib.request.Request(
                f"http://127.0.0.1:{pin_port}/api/auth",
                data=json.dumps({"key": "wrong"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(auth_req)
                self.fail("Expected HTTPError 401")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401)

            # 3. Authenticate with correct PIN
            auth_req_good = urllib.request.Request(
                f"http://127.0.0.1:{pin_port}/api/auth",
                data=json.dumps({"key": "1234"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(auth_req_good) as resp:
                self.assertEqual(resp.status, 200)
                cookie = resp.headers.get("Set-Cookie")
                self.assertIn("clipto_auth=1234", cookie)

            # 4. Request with query param ?k=1234 should succeed directly
            with urllib.request.urlopen(f"http://127.0.0.1:{pin_port}/api/info?k=1234") as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertEqual(data["title"], "Protected Session")

        finally:
            pin_server.shutdown()
            pin_server.server_close()
            shutil.rmtree(pin_dir, ignore_errors=True)
