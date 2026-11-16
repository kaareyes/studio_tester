import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_release_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        for name in ("tester", "suites", "tests", "docs"):
            for base, dirs, files in os.walk(os.path.join(ROOT, name)):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    full = os.path.join(base, f)
                    z.write(full, "studio_tester-release/" + os.path.relpath(full, ROOT))
        for name in ("NAMES.md", "README.md", "requirements.txt", "VERSION", "install.sh", "Studio Tester.command"):
            z.write(os.path.join(ROOT, name), "studio_tester-release/" + name)


@unittest.skipUnless(shutil.which("curl") and shutil.which("unzip"), "needs curl and unzip")
class InstallScript(unittest.TestCase):
    def run_install(self, home, zip_url):
        env = dict(os.environ, STUDIO_TESTER_HOME=home, STUDIO_TESTER_ZIP_URL=zip_url, STUDIO_TESTER_NO_START="1")
        return subprocess.run(["/bin/bash", os.path.join(ROOT, "install.sh")], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_install_then_update_keeps_the_data(self):
        work = tempfile.mkdtemp()
        archive = os.path.join(work, "release.zip")
        make_release_zip(archive)
        home = os.path.join(work, "Studio Tester")
        first = self.run_install(home, "file://" + archive)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(sorted(os.listdir(home)), [".studio_tester", "Studio Tester.command"][::-1] if False else sorted([".studio_tester", "Studio Tester.command"]))
        inner = os.path.join(home, ".studio_tester")
        self.assertTrue(os.path.exists(os.path.join(inner, "tester", "launcher.py")))
        self.assertTrue(os.access(os.path.join(home, "Studio Tester.command"), os.X_OK))
        self.assertTrue(os.access(os.path.join(inner, "Studio Tester.command"), os.X_OK))
        # the person has collected data and installed the tools; running the line again must keep all of it
        open(os.path.join(inner, "catalog.json"), "w").write('{"mine": 1}')
        os.makedirs(os.path.join(inner, "reports", "run1"))
        os.makedirs(os.path.join(inner, ".venv"))
        open(os.path.join(inner, "tester", "old_file.py"), "w").write("stale")
        second = self.run_install(home, "file://" + archive)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(open(os.path.join(inner, "catalog.json")).read(), '{"mine": 1}')
        self.assertTrue(os.path.isdir(os.path.join(inner, "reports", "run1")))
        self.assertTrue(os.path.isdir(os.path.join(inner, ".venv")))
        self.assertFalse(os.path.exists(os.path.join(inner, "tester", "old_file.py")))      # code replaced, not merged

    def test_refuses_while_a_test_is_running(self):
        import http.server, json, threading
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                body = json.dumps({"suite": "chaos", "finished": None} if self.path == "/api/state" else {"running": False}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        work = tempfile.mkdtemp()
        archive = os.path.join(work, "release.zip")
        make_release_zip(archive)
        home = os.path.join(work, "Studio Tester")
        env = dict(os.environ, STUDIO_TESTER_HOME=home, STUDIO_TESTER_ZIP_URL="file://" + archive, STUDIO_TESTER_NO_START="1",
                   STUDIO_TESTER_PORT=str(httpd.server_address[1]))
        try:
            result = subprocess.run(["/bin/bash", os.path.join(ROOT, "install.sh")], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        finally:
            httpd.shutdown()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("A test is running", result.stdout)
        self.assertFalse(os.path.exists(home))                      # nothing was installed over it

    def test_a_cut_off_download_runs_nothing(self):
        """The whole script is one function called on the last line: a truncated copy never reaches the call."""
        text = open(os.path.join(ROOT, "install.sh")).read()
        cut = text[: text.index("  mkdir -p \"$INNER\"")]           # the download stops half way through main()
        work = tempfile.mkdtemp()
        home = os.path.join(work, "Studio Tester")
        env = dict(os.environ, STUDIO_TESTER_HOME=home, STUDIO_TESTER_NO_START="1")
        result = subprocess.run(["/bin/bash"], input=cut, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)                    # syntax error: the function never closed
        self.assertFalse(os.path.exists(home))

    def test_bad_download_changes_nothing(self):
        work = tempfile.mkdtemp()
        home = os.path.join(work, "Studio Tester")
        result = self.run_install(home, "file://" + os.path.join(work, "missing.zip"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not download", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(home, ".studio_tester", "tester")))

    def test_wrong_zip_is_refused(self):
        work = tempfile.mkdtemp()
        archive = os.path.join(work, "x.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("something/readme.txt", "not the tester")
        result = self.run_install(os.path.join(work, "Studio Tester"), "file://" + archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not look like Studio Tester", result.stdout)


if __name__ == "__main__":
    unittest.main()
