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
