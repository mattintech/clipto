import io
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from clipto.server import CliptoHTTPServer, CliptoRequestHandler
from clipto.utils import (
    find_available_port,
    get_config_file,
    get_unique_path,
    load_global_config,
    sanitize_filename,
    save_global_config,
)


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
        self.assertEqual(sanitize_filename(".."), "upload")
        self.assertEqual(sanitize_filename("."), "upload")
        self.assertEqual(sanitize_filename("..."), "upload")
        self.assertEqual(sanitize_filename(".env"), "env")
        self.assertEqual(sanitize_filename(".bashrc"), "bashrc")
        self.assertEqual(sanitize_filename("photo.png."), "photo.png")

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

    def test_global_config_load_and_save(self):
        fake_config_file = self.temp_dir / "config.json"
        with patch("clipto.utils.get_config_file", return_value=fake_config_file):
            # 1. Defaults when no file exists
            cfg = load_global_config()
            self.assertEqual(cfg["tab_order"], ["dropzone", "files", "gist"])
            self.assertEqual(cfg["default_tab"], "first")
            self.assertEqual(cfg["view_mode"], "grid")
            self.assertEqual(cfg["files_view_mode"], "list")
            self.assertEqual(cfg["config_path"], str(fake_config_file))

            # 2. Save custom config with reordered tabs
            saved = save_global_config({
                "tab_order": ["gist", "files"],
                "default_tab": "gist",
                "view_mode": "list",
                "files_view_mode": "grid",
            })
            # Missing tab ('dropzone') is automatically appended
            self.assertEqual(saved["tab_order"], ["gist", "files", "dropzone"])
            self.assertEqual(saved["default_tab"], "gist")
            self.assertEqual(saved["view_mode"], "list")
            self.assertEqual(saved["files_view_mode"], "grid")
            self.assertTrue(fake_config_file.is_file())

            # 3. Reload config from file
            reloaded = load_global_config()
            self.assertEqual(reloaded["tab_order"], ["gist", "files", "dropzone"])
            self.assertEqual(reloaded["default_tab"], "gist")
            self.assertEqual(reloaded["view_mode"], "list")
            self.assertEqual(reloaded["files_view_mode"], "grid")

            # 4. Invalid tab entries filtered out
            save_global_config({
                "tab_order": ["unknown_tab", "files", "dropzone"],
            })
            reloaded2 = load_global_config()
            self.assertNotIn("unknown_tab", reloaded2["tab_order"])
            self.assertIn("gist", reloaded2["tab_order"])


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
            self.assertIn("config", data)
            self.assertIn("tab_order", data["config"])

    def test_api_config_endpoints(self):
        fake_config_file = self.temp_dir / "test_api_config.json"
        with patch("clipto.utils.get_config_file", return_value=fake_config_file):
            # 1. GET /api/config
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/config") as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertIn("tab_order", data)
                self.assertIn("default_tab", data)
                self.assertIn("files_view_mode", data)

            # 2. POST /api/config
            payload = json.dumps({
                "tab_order": ["files", "gist", "dropzone"],
                "default_tab": "files",
                "files_view_mode": "grid"
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/config",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                res_data = json.loads(resp.read().decode())
                self.assertEqual(res_data["status"], "ok")
                self.assertEqual(res_data["config"]["tab_order"], ["files", "gist", "dropzone"])
                self.assertEqual(res_data["config"]["default_tab"], "files")
                self.assertEqual(res_data["config"]["files_view_mode"], "grid")

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
                self.assertIn("clipto_auth=", cookie)

            # 4. Request with query param ?k=1234 should succeed directly
            with urllib.request.urlopen(f"http://127.0.0.1:{pin_port}/api/info?k=1234") as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertEqual(data["title"], "Protected Session")

        finally:
            pin_server.shutdown()
            pin_server.server_close()
            shutil.rmtree(pin_dir, ignore_errors=True)

    def test_api_config_requires_auth(self):
        auth_dir = Path(tempfile.mkdtemp())
        auth_port = find_available_port(0)
        auth_server = CliptoHTTPServer(
            ("127.0.0.1", auth_port),
            CliptoRequestHandler,
            upload_dir=auth_dir,
            title="Auth Config Session",
            once=False,
            auth_token="secure123",
        )
        auth_thread = threading.Thread(target=auth_server.serve_forever, daemon=True)
        auth_thread.start()
        time.sleep(0.1)

        try:
            payload = json.dumps({"tab_order": ["gist", "files", "dropzone"]}).encode("utf-8")
            # Unauthenticated POST /api/config should fail with 401
            req_unauth = urllib.request.Request(
                f"http://127.0.0.1:{auth_port}/api/config",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req_unauth)
                self.fail("Expected 401 for unauthenticated POST /api/config")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401)

            # Authenticate
            auth_req = urllib.request.Request(
                f"http://127.0.0.1:{auth_port}/api/auth",
                data=json.dumps({"key": "secure123"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(auth_req) as resp:
                cookie = resp.headers.get("Set-Cookie")

            # Authenticated POST /api/config with cookie should succeed
            fake_config_file = auth_dir / "auth_test_config.json"
            with patch("clipto.utils.get_config_file", return_value=fake_config_file):
                req_auth = urllib.request.Request(
                    f"http://127.0.0.1:{auth_port}/api/config",
                    data=payload,
                    headers={"Content-Type": "application/json", "Cookie": cookie},
                    method="POST",
                )
                with urllib.request.urlopen(req_auth) as resp:
                    self.assertEqual(resp.status, 200)
                    res_data = json.loads(resp.read().decode())
                    self.assertEqual(res_data["status"], "ok")
        finally:
            auth_server.shutdown()
            auth_server.server_close()
            shutil.rmtree(auth_dir, ignore_errors=True)

    def test_tunnel_helpers(self):
        from clipto.tunnel import is_cloudflared_available, print_tunnel_guide

        # Should be a boolean
        self.assertIsInstance(is_cloudflared_available(), bool)

        # print_tunnel_guide should execute without error
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            print_tunnel_guide()
            output = sys.stderr.getvalue()
            self.assertIn("Clipto Remote Access", output)
        finally:
            sys.stderr = old_stderr

    def test_start_cloudflare_tunnel_registration(self):
        from unittest.mock import MagicMock, patch
        from clipto.tunnel import start_cloudflare_tunnel

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stderr.readline.side_effect = [
            "INF Requesting new quick Tunnel on trycloudflare.com...\n",
            "INF | https://test-tunnel-unit.trycloudflare.com |\n",
            "INF Registered tunnel connection connIndex=0 connection=12345 protocol=quic\n",
        ]

        with patch("shutil.which", return_value="/usr/local/bin/cloudflared"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("time.sleep", return_value=None):
            url, proc = start_cloudflare_tunnel(8765, timeout=5.0)
            self.assertEqual(url, "https://test-tunnel-unit.trycloudflare.com")
            self.assertEqual(proc, mock_proc)

    def test_totp_rfc6238_and_verification(self):
        from clipto.totp import (
            calculate_totp,
            generate_totp_secret,
            get_totp_uri,
            verify_totp,
        )

        secret = generate_totp_secret()
        self.assertTrue(len(secret) >= 16)

        # RFC test vector
        rfc_secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        code_59 = calculate_totp(rfc_secret, timestamp=59)
        self.assertEqual(code_59, "287082")

        # Verify matching
        now = time.time()
        curr_code = calculate_totp(secret, timestamp=now)
        self.assertTrue(verify_totp(secret, curr_code, timestamp=now))
        self.assertFalse(verify_totp(secret, "000000", timestamp=now))

        # Test URI
        uri = get_totp_uri(secret, issuer="Clipto", account="test@box")
        self.assertTrue(uri.startswith("otpauth://totp/Clipto%3Atest%40box?"))
        self.assertIn("secret=", uri)

    def test_server_with_totp(self):
        from clipto.totp import calculate_totp, generate_totp_secret

        totp_dir = Path(tempfile.mkdtemp())
        totp_port = find_available_port(0)
        secret = generate_totp_secret()

        totp_server = CliptoHTTPServer(
            ("127.0.0.1", totp_port),
            CliptoRequestHandler,
            upload_dir=totp_dir,
            title="TOTP Session",
            once=False,
            totp_secret=secret,
        )
        totp_thread = threading.Thread(target=totp_server.serve_forever, daemon=True)
        totp_thread.start()
        time.sleep(0.1)

        try:
            # 1. Unauthenticated request to /api/info fails with 401
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{totp_port}/api/info")
                self.fail("Expected 401")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401)

            # 2. Authenticate with valid TOTP code
            code = calculate_totp(secret)
            auth_req = urllib.request.Request(
                f"http://127.0.0.1:{totp_port}/api/auth",
                data=json.dumps({"key": code}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(auth_req) as resp:
                self.assertEqual(resp.status, 200)
                cookie = resp.headers.get("Set-Cookie")
                self.assertIn("clipto_auth=", cookie)

        finally:
            totp_server.shutdown()
            totp_server.server_close()
            shutil.rmtree(totp_dir, ignore_errors=True)

    def test_api_files_and_content(self):
        # Create test files
        code_file = self.temp_dir / "test_script.py"
        code_file.write_text("print('hello world')\nprint('line 2')\n")

        image_file = self.temp_dir / "sample.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        hidden_file = self.temp_dir / ".secret_env"
        hidden_file.write_text("SECRET=12345\n")

        # 1. GET /api/files
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/files") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            file_names = [f["name"] for f in data["files"]]
            self.assertIn("test_script.py", file_names)
            self.assertIn("sample.png", file_names)
            self.assertNotIn(".secret_env", file_names)

            code_entry = next(f for f in data["files"] if f["name"] == "test_script.py")
            self.assertTrue(code_entry["is_text"])
            self.assertFalse(code_entry["is_image"])

            img_entry = next(f for f in data["files"] if f["name"] == "sample.png")
            self.assertFalse(img_entry["is_text"])
            self.assertTrue(img_entry["is_image"])

        # 2. GET /api/content?name=test_script.py
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/content?name=test_script.py") as resp:
            self.assertEqual(resp.status, 200)
            content_data = json.loads(resp.read().decode())
            self.assertEqual(content_data["name"], "test_script.py")
            self.assertEqual(content_data["lines"], 2)
            self.assertIn("hello world", content_data["content"])

        # 3. Path traversal protection on /api/content
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/content?name=../../etc/passwd")
            # sanitize_filename will turn ../../etc/passwd into passwd, which doesn't exist in temp_dir -> 404
            self.fail("Expected HTTP error for non-existent traversed file")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, [400, 403, 404])

        # 4. GET /raw/<filename>
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/raw/test_script.py") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/plain", resp.headers.get("Content-Type", ""))
            self.assertEqual(resp.read().decode(), "print('hello world')\nprint('line 2')\n")

    def test_share_mode_and_once_download(self):
        share_dir = Path(tempfile.mkdtemp())
        share_port = find_available_port(0)
        target_file = share_dir / "archive.tar.gz"
        target_file.write_bytes(b"FAKE_TAR_GZ_DATA_BYTES")

        server = CliptoHTTPServer(
            ("127.0.0.1", share_port),
            CliptoRequestHandler,
            upload_dir=share_dir,
            title="Share Session",
            once=True,
            share_mode=True,
            share_file=target_file,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        try:
            # Check /api/info
            with urllib.request.urlopen(f"http://127.0.0.1:{share_port}/api/info") as resp:
                data = json.loads(resp.read().decode())
                self.assertTrue(data["share_mode"])
                self.assertEqual(data["share_file"], "archive.tar.gz")

            # Check /api/files returns only the shared file
            with urllib.request.urlopen(f"http://127.0.0.1:{share_port}/api/files") as resp:
                data = json.loads(resp.read().decode())
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["files"][0]["name"], "archive.tar.gz")

            # Download via /raw/archive.tar.gz
            with urllib.request.urlopen(f"http://127.0.0.1:{share_port}/raw/archive.tar.gz") as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read(), b"FAKE_TAR_GZ_DATA_BYTES")

            # Server shutdown_event should have been triggered by --once download
            time.sleep(0.1)
            self.assertTrue(server.shutdown_event.is_set())

        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(share_dir, ignore_errors=True)

    def test_cli_share_parser(self):
        from clipto.cli import build_parser
        parser = build_parser()

        args1 = parser.parse_args(["share", "my_script.py"])
        self.assertEqual(args1.share_args, ["share", "my_script.py"])

        args2 = parser.parse_args(["share"])
        self.assertEqual(args2.share_args, ["share"])

        args3 = parser.parse_args(["my_archive.zip"])
        self.assertEqual(args3.share_args, ["my_archive.zip"])

    def test_print_banner_share_mode(self):
        from clipto.cli import print_banner
        test_file = self.temp_dir / "test_file.txt"
        test_file.write_text("sample content")

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            print_banner(
                port=8765,
                target_dir=self.temp_dir,
                share_mode=True,
                share_file=test_file,
            )
            output = sys.stderr.getvalue()
            self.assertIn("SHARING FILE", output)
            self.assertIn("test_file.txt", output)
            self.assertIn("Config:", output)
            self.assertIn("curl -sSL", output)
        finally:
            sys.stderr = old_stderr

    def test_gist_creation_and_listing(self):
        # 1. Existing text file in directory should NOT be a gist
        normal_file = self.temp_dir / "regular_file.py"
        normal_file.write_text("print('not a gist')")

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/files") as resp:
            data = json.loads(resp.read().decode())
            file_entry = next(f for f in data["files"] if f["name"] == "regular_file.py")
            self.assertTrue(file_entry["is_text"])
            self.assertFalse(file_entry["is_gist"])
            self.assertEqual(data["gists"], [])

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/gists") as resp:
            gists_data = json.loads(resp.read().decode())
            self.assertEqual(gists_data["count"], 0)

        # 2. Create a Gist via /api/gist
        gist_payload = json.dumps({"filename": "my_gist.py", "content": "print('hello gist')\n"}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/gist",
            data=gist_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode())
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["name"], "my_gist.py")
            self.assertEqual(res["lines"], 1)

        # 3. Verify /api/gists and /api/files now reflect the created gist
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/gists") as resp:
            gists_data = json.loads(resp.read().decode())
            self.assertEqual(gists_data["count"], 1)
            self.assertEqual(gists_data["gists"][0]["name"], "my_gist.py")
            self.assertTrue(gists_data["gists"][0]["is_gist"])

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/files") as resp:
            data = json.loads(resp.read().decode())
            gist_entry = next(f for f in data["files"] if f["name"] == "my_gist.py")
            reg_entry = next(f for f in data["files"] if f["name"] == "regular_file.py")
            self.assertTrue(gist_entry["is_gist"])
            self.assertFalse(reg_entry["is_gist"])

    def test_ensure_self_signed_cert(self):
        from clipto.utils import ensure_self_signed_cert
        with tempfile.TemporaryDirectory() as tmp_home:
            old_home = Path.home
            try:
                Path.home = lambda: Path(tmp_home)
                cert_path, key_path = ensure_self_signed_cert()
                self.assertTrue(cert_path.is_file())
                self.assertTrue(key_path.is_file())
                # Calling it again returns the cached cert
                cert_path2, key_path2 = ensure_self_signed_cert()
                self.assertEqual(cert_path, cert_path2)
                self.assertEqual(key_path, key_path2)
            finally:
                Path.home = old_home

    def test_ssl_server_and_info(self):
        import ssl
        from clipto.utils import ensure_self_signed_cert
        cert_path, key_path = ensure_self_signed_cert()

        ssl_port = find_available_port(0)
        ssl_server = CliptoHTTPServer(
            ("127.0.0.1", ssl_port),
            CliptoRequestHandler,
            upload_dir=self.temp_dir,
            title="SSL Test Session",
            ssl_cert=cert_path,
            ssl_key=key_path,
        )
        self.assertTrue(ssl_server.is_ssl)
        ssl_thread = threading.Thread(target=ssl_server.serve_forever, daemon=True)
        ssl_thread.start()
        time.sleep(0.1)

        ctx = ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(f"https://127.0.0.1:{ssl_port}/api/info", context=ctx) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data["is_ssl"])
        finally:
            ssl_server.shutdown()
            ssl_server.server_close()

    def test_ssl_server_http_redirect(self):
        import ssl
        from clipto.utils import ensure_self_signed_cert
        cert_path, key_path = ensure_self_signed_cert()

        ssl_port = find_available_port(0)
        ssl_server = CliptoHTTPServer(
            ("127.0.0.1", ssl_port),
            CliptoRequestHandler,
            upload_dir=self.temp_dir,
            title="SSL Redirect Session",
            ssl_cert=cert_path,
            ssl_key=key_path,
        )
        ssl_thread = threading.Thread(target=ssl_server.serve_forever, daemon=True)
        ssl_thread.start()
        time.sleep(0.1)

        ctx = ssl._create_unverified_context()
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            try:
                opener.open(f"http://127.0.0.1:{ssl_port}/api/info")
                self.fail("Expected HTTP 307 redirect")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 307)
                self.assertTrue(e.headers.get("Location").startswith(f"https://127.0.0.1:{ssl_port}"))

            opener_follow = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            with opener_follow.open(f"http://127.0.0.1:{ssl_port}/api/info") as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data["is_ssl"])
        finally:
            ssl_server.shutdown()
            ssl_server.server_close()

    def test_dotfile_access_protection(self):
        env_file = self.temp_dir / ".env"
        env_file.write_text("SECRET_KEY=123456")

        hidden_file = self.temp_dir / ".hidden_notes.txt"
        hidden_file.write_text("classified notes")

        # 1. /api/content?name=.env -> 403 Forbidden
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/content?name=.env")
            self.fail("Expected 403 for .env in /api/content")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)

        # 2. /raw/.env -> 403 Forbidden
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/raw/.env")
            self.fail("Expected 403 for .env in /raw/")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)

        # 3. /api/file?name=.hidden_notes.txt -> 403 Forbidden
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/file?name=.hidden_notes.txt")
            self.fail("Expected 403 for .hidden_notes.txt in /api/file")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)

    def test_single_file_share_isolation(self):
        share_dir = Path(tempfile.mkdtemp())
        share_port = find_available_port(0)
        target_file = share_dir / "allowed.txt"
        target_file.write_text("ALLOWED_CONTENT")
        secret_file = share_dir / "secret.txt"
        secret_file.write_text("TOP_SECRET_CONTENT")

        server = CliptoHTTPServer(
            ("127.0.0.1", share_port),
            CliptoRequestHandler,
            upload_dir=share_dir,
            title="Single File Share",
            once=False,
            share_mode=True,
            share_file=target_file,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        try:
            # 1. Allowed file should be accessible via /raw and /api/content
            with urllib.request.urlopen(f"http://127.0.0.1:{share_port}/raw/{target_file.name}") as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read().decode(), "ALLOWED_CONTENT")

            with urllib.request.urlopen(f"http://127.0.0.1:{share_port}/api/content?name={target_file.name}") as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertEqual(data["content"], "ALLOWED_CONTENT")

            # 2. Secret sibling file should be forbidden via /raw, /api/content, /api/file
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{share_port}/raw/{secret_file.name}")
                self.fail("Expected 403 for sibling file in /raw/")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

            try:
                urllib.request.urlopen(f"http://127.0.0.1:{share_port}/api/content?name={secret_file.name}")
                self.fail("Expected 403 for sibling file in /api/content")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

            try:
                urllib.request.urlopen(f"http://127.0.0.1:{share_port}/api/file?name={secret_file.name}")
                self.fail("Expected 403 for sibling file in /api/file")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

            # 3. POST /api/upload should be rejected with 403
            req_upload = urllib.request.Request(
                f"http://127.0.0.1:{share_port}/api/upload",
                data=b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"upload.txt\"\r\n\r\ntest\r\n--boundary--\r\n",
                headers={"Content-Type": "multipart/form-data; boundary=boundary"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req_upload)
                self.fail("Expected 403 for upload in single-file share mode")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

            # 4. POST /api/gist should be rejected with 403
            req_gist = urllib.request.Request(
                f"http://127.0.0.1:{share_port}/api/gist",
                data=json.dumps({"filename": "new.txt", "content": "hello"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req_gist)
                self.fail("Expected 403 for gist creation in single-file share mode")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(share_dir, ignore_errors=True)

    def test_auth_rate_limiting_across_vectors(self):
        auth_dir = Path(tempfile.mkdtemp())
        auth_port = find_available_port(0)
        auth_server = CliptoHTTPServer(
            ("127.0.0.1", auth_port),
            CliptoRequestHandler,
            upload_dir=auth_dir,
            title="Rate Limit Test",
            once=False,
            auth_token="secret_pin",
        )
        thread = threading.Thread(target=auth_server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        try:
            # 5 consecutive failed attempts via GET ?k=wrong
            for i in range(5):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{auth_port}/api/info?k=wrong_{i}")
                    self.fail(f"Expected 401 on attempt {i+1}")
                except urllib.error.HTTPError as e:
                    self.assertEqual(e.code, 401)

            # 6th attempt should be blocked with 429 Too Many Requests (even with correct PIN!)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{auth_port}/api/info?k=secret_pin")
                self.fail("Expected 429 Too Many Requests on 6th attempt")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 429)

            # POST /api/auth should also return 429
            auth_req = urllib.request.Request(
                f"http://127.0.0.1:{auth_port}/api/auth",
                data=json.dumps({"key": "secret_pin"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(auth_req)
                self.fail("Expected 429 for POST /api/auth while rate limited")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 429)

        finally:
            auth_server.shutdown()
            auth_server.server_close()
            shutil.rmtree(auth_dir, ignore_errors=True)

    def test_chunked_upload_assembly(self):
        upload_id = "test_upload_12345678"
        chunk_data = [
            b"PART1_DATA_" * 100,
            b"PART2_DATA_" * 100,
            b"PART3_DATA_" * 50,
        ]
        total_data = b"".join(chunk_data)
        chunk_size = len(chunk_data[0])

        for i, chunk in enumerate(chunk_data):
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/upload-chunk",
                data=chunk,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Upload-Id": upload_id,
                    "X-Chunk-Index": str(i),
                    "X-Total-Chunks": "3",
                    "X-Chunk-Size": str(chunk_size),
                    "X-Filename": urllib.parse.quote("my_large_video.mp4"),
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                res_json = json.loads(resp.read().decode())
                if i < 2:
                    self.assertFalse(res_json["completed"])
                    self.assertEqual(res_json["chunk"], i)
                else:
                    self.assertTrue(res_json["completed"])
                    self.assertEqual(len(res_json["saved_files"]), 1)
                    self.assertEqual(res_json["saved_files"][0]["name"], "my_large_video.mp4")

        # Verify file exists on disk and content matches
        saved_file = self.temp_dir / "my_large_video.mp4"
        self.assertTrue(saved_file.is_file())
        self.assertEqual(saved_file.read_bytes(), total_data)

        # Temporary part file should have been cleaned up
        self.assertFalse((self.temp_dir / f".clipto_part_{upload_id}").exists())

    def test_chunked_upload_security_guards(self):
        # 1. Invalid upload_id (path traversal attempt)
        req_bad_id = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/upload-chunk",
            data=b"test",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Upload-Id": "../../../etc/passwd",
                "X-Chunk-Index": "0",
                "X-Total-Chunks": "1",
                "X-Chunk-Size": "4",
                "X-Filename": "test.bin",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req_bad_id)
            self.fail("Expected 400 for path traversal upload_id")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

        # 2. Rejection in single-file share mode
        share_dir = Path(tempfile.mkdtemp())
        share_port = find_available_port(0)
        target_file = share_dir / "only_this.txt"
        target_file.write_text("ONLY")

        server = CliptoHTTPServer(
            ("127.0.0.1", share_port),
            CliptoRequestHandler,
            upload_dir=share_dir,
            title="Share Guard",
            once=False,
            share_mode=True,
            share_file=target_file,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        try:
            req_chunk = urllib.request.Request(
                f"http://127.0.0.1:{share_port}/api/upload-chunk",
                data=b"test",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Upload-Id": "valid_id_123456",
                    "X-Chunk-Index": "0",
                    "X-Total-Chunks": "1",
                    "X-Chunk-Size": "4",
                    "X-Filename": "test.bin",
                },
                method="POST",
            )
            try:
                urllib.request.urlopen(req_chunk)
                self.fail("Expected 403 for upload-chunk in share_file mode")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(share_dir, ignore_errors=True)

    def test_cli_ssl_options(self):
        from clipto.cli import build_parser
        parser = build_parser()

        args = parser.parse_args(["--self-signed"])
        self.assertTrue(args.self_signed)
        self.assertIsNone(args.cert)
        self.assertIsNone(args.key)

        args2 = parser.parse_args(["--cert", "cert.pem", "--key", "key.pem"])
        self.assertFalse(args2.self_signed)
        self.assertEqual(args2.cert, Path("cert.pem"))
        self.assertEqual(args2.key, Path("key.pem"))

    def test_upload_status_and_cancel(self):
        chunk_dir = Path(tempfile.mkdtemp())
        port = find_available_port(0)
        server = CliptoHTTPServer(
            ("127.0.0.1", port),
            CliptoRequestHandler,
            upload_dir=chunk_dir,
            title="Resume Test",
            once=False,
            debug=True,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        upload_id = "test_resume_upload_12345"

        try:
            # Check status before upload -> exists: False
            req_status_pre = urllib.request.Request(f"http://127.0.0.1:{port}/api/upload-status?upload_id={upload_id}")
            with urllib.request.urlopen(req_status_pre) as resp:
                data = json.loads(resp.read().decode())
                self.assertFalse(data["exists"])

            # Upload chunk 0 of 2
            req_chunk0 = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/upload-chunk",
                data=b"CHUNK_0_BYTES",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Upload-Id": upload_id,
                    "X-Chunk-Index": "0",
                    "X-Total-Chunks": "2",
                    "X-Chunk-Size": "14",
                    "X-Filename": "resume_file.bin",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_chunk0) as resp:
                data = json.loads(resp.read().decode())
                self.assertFalse(data["completed"])

            # Check status -> exists: True, chunks_received: [0]
            req_status_post = urllib.request.Request(f"http://127.0.0.1:{port}/api/upload-status?upload_id={upload_id}")
            with urllib.request.urlopen(req_status_post) as resp:
                data = json.loads(resp.read().decode())
                self.assertTrue(data["exists"])
                self.assertEqual(data["chunks_received"], [0])
                self.assertEqual(data["total_chunks"], 2)

            # Cancel upload
            req_cancel = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/upload-cancel",
                data=json.dumps({"upload_id": upload_id}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_cancel) as resp:
                data = json.loads(resp.read().decode())
                self.assertTrue(data["cancelled"])

            # Part file should be unlinked
            part_file = chunk_dir / f".clipto_part_{upload_id}"
            self.assertFalse(part_file.exists())

            # Status should now report exists: False
            with urllib.request.urlopen(req_status_pre) as resp:
                data = json.loads(resp.read().decode())
                self.assertFalse(data["exists"])

        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(chunk_dir, ignore_errors=True)

    def test_cli_debug_option(self):
        from clipto.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--debug"])
        self.assertTrue(args.debug)

    def test_cli_single_dash_long_options_rejected(self):
        from clipto.cli import build_parser
        parser = build_parser()

        # -debug should fail with SystemExit(2)
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["-debug"])
        self.assertEqual(ctx.exception.code, 2)

        # -dir should fail with SystemExit(2)
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["-dir"])
        self.assertEqual(ctx.exception.code, 2)

        # Legitimate clustered flags should still work
        args_cluster = parser.parse_args(["-1o"])
        self.assertTrue(args_cluster.once)
        self.assertTrue(args_cluster.open)

        # Separate -d <path> should still work
        args_dir = parser.parse_args(["-d", "/tmp"])
        self.assertEqual(str(args_dir.dir), "/tmp")


if __name__ == "__main__":
    unittest.main()

