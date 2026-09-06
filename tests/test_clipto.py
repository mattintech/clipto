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


if __name__ == "__main__":
    unittest.main()

