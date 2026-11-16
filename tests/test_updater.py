import io
import json
import os
import tempfile
import unittest
import zipfile

from tester import updater


def make_zip(files, top="studio_tester-release"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(f"{top}/{name}" if top else name, text)
    return buffer.getvalue()


def install(version="1.0.0"):
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "tester"))
    os.makedirs(os.path.join(root, "reports"))
    open(os.path.join(root, "VERSION"), "w").write(version)
    open(os.path.join(root, "tester", "old_only.py"), "w").write("old")
    open(os.path.join(root, "tester", "server.py"), "w").write("OLD")
    open(os.path.join(root, "catalog.json"), "w").write('{"mine": true}')
    open(os.path.join(root, "settings.json"), "w").write('{"test_words": ["x"]}')
    open(os.path.join(root, "reports", "run1.txt"), "w").write("report")
    open(os.path.join(root, "requirements.txt"), "w").write("a\n")
    return root


NEW = {"VERSION": "1.1.0", "tester/__init__.py": "", "tester/server.py": "NEW", "requirements.txt": "a\nb\n",
       "catalog.json": "{\"evil\": true}", "reports/x.txt": "no"}


class Updater(unittest.TestCase):
    def test_version_compare(self):
        self.assertTrue(updater.newer("1.10.0", "1.9.9"))
        self.assertTrue(updater.newer("v2", "1.9"))
        self.assertFalse(updater.newer("1.0.0", "1.0.0"))
        self.assertFalse(updater.newer("0.9", "1.0.0"))

    def test_check_available_and_offline(self):
        root = install("1.0.0")
        info = json.dumps({"version": "1.1.0", "notes": "faster", "min_build": "abc123"}).encode()
        r = updater.check(root=root, fetcher=lambda url, timeout=0: info)
        self.assertTrue(r["available"])
        self.assertEqual((r["current"], r["latest"], r["notes"], r["min_build"]), ("1.0.0", "1.1.0", "faster", "abc123"))
        r = updater.check(root=root, fetcher=lambda url, timeout=0: json.dumps({"version": "1.0.0"}).encode())
        self.assertFalse(r["available"])
        def boom(url, timeout=0):
            raise OSError("no network")
        r = updater.check(root=root, fetcher=boom)
        self.assertFalse(r["available"])
        self.assertIn("online", r["error"])

    def test_check_asks_the_api_first_and_falls_back_to_raw(self):
        asked = []
        def api_ok(url, timeout=0):
            asked.append(url)
            return b'{"version": "1.2.0"}'
        r = updater.check(root=install("1.0.0"), fetcher=api_ok)
        self.assertIn("api.github.com", asked[0])
        self.assertEqual(len(asked), 1)                                   # answered by the API: raw is not needed
        self.assertTrue(r["available"])
        asked.clear()
        def api_down(url, timeout=0):
            asked.append(url)
            if "api.github.com" in url:
                raise OSError("rate limited")
            return b'{"version": "1.3.0"}'
        r = updater.check(root=install("1.0.0"), fetcher=api_down)
        self.assertEqual(len(asked), 2)
        self.assertIn("raw.githubusercontent.com", asked[1])
        self.assertEqual(r["latest"], "1.3.0")

    def test_apply_replaces_code_and_keeps_data(self):
        root = install()
        result = updater.apply(root=root, fetcher=lambda url, timeout=0: make_zip(NEW), test=lambda r: (True, ""))
        self.assertTrue(result["ok"], result)
        self.assertEqual(updater.local_version(root), "1.1.0")
        self.assertEqual(open(os.path.join(root, "tester", "server.py")).read(), "NEW")
        self.assertFalse(os.path.exists(os.path.join(root, "tester", "old_only.py")))      # removed upstream, removed here
        self.assertEqual(open(os.path.join(root, "catalog.json")).read(), '{"mine": true}')  # data kept, never overwritten
        self.assertEqual(open(os.path.join(root, "settings.json")).read(), '{"test_words": ["x"]}')
        self.assertTrue(os.path.exists(os.path.join(root, "reports", "run1.txt")))
        self.assertFalse(os.path.exists(os.path.join(root, "reports", "x.txt")))
        self.assertTrue(result["packages_changed"])

    def test_rollback_when_new_code_does_not_start(self):
        root = install()
        result = updater.apply(root=root, fetcher=lambda url, timeout=0: make_zip(NEW), test=lambda r: (False, "ImportError"))
        self.assertFalse(result["ok"])
        self.assertEqual(updater.local_version(root), "1.0.0")
        self.assertEqual(open(os.path.join(root, "tester", "server.py")).read(), "OLD")
        self.assertTrue(os.path.exists(os.path.join(root, "tester", "old_only.py")))
        self.assertEqual(open(os.path.join(root, "catalog.json")).read(), '{"mine": true}')

    def test_refuses_unsafe_or_wrong_zip(self):
        root = install()
        evil = make_zip({"VERSION": "9", "tester/x.py": "x", "tester/../../escape.py": "boom"})
        r = updater.apply(root=root, fetcher=lambda url, timeout=0: evil, test=lambda r: (True, ""))
        self.assertFalse(r["ok"])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(root), "escape.py")))
        wrong = make_zip({"hello.txt": "hi"})
        r = updater.apply(root=root, fetcher=lambda url, timeout=0: wrong, test=lambda r: (True, ""))
        self.assertFalse(r["ok"])
        self.assertEqual(updater.local_version(root), "1.0.0")

    def test_refuses_while_a_test_runs_and_survives_download_failure(self):
        root = install()
        r = updater.apply(root=root, busy=lambda: True, fetcher=lambda *a, **k: make_zip(NEW), test=lambda r: (True, ""))
        self.assertFalse(r["ok"])
        self.assertIn("test is running", r["message"])
        def boom(url, timeout=0):
            raise OSError("down")
        r = updater.apply(root=root, fetcher=boom)
        self.assertFalse(r["ok"])
        self.assertEqual(updater.local_version(root), "1.0.0")

    def test_command_files_stay_executable(self):
        root = install()
        z = dict(NEW, **{"Start Studio Tester.command": "#!/bin/bash\n"})
        updater.apply(root=root, fetcher=lambda url, timeout=0: make_zip(z), test=lambda r: (True, ""))
        self.assertTrue(os.access(os.path.join(root, "Start Studio Tester.command"), os.X_OK))


if __name__ == "__main__":
    unittest.main()
