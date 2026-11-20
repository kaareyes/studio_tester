import shutil
import tempfile
import json
import os
import subprocess
import unittest
from unittest import mock

from tester import awake, catalog
import suites
from suites import realistic


class Awake(unittest.TestCase):
    def test_caffeinate_is_tied_to_the_tester_and_stopped(self):
        calls = []
        class Proc:
            def poll(self): return None
            def terminate(self): calls.append("terminate")
        with mock.patch("subprocess.Popen", lambda cmd, **k: calls.append(cmd) or Proc()):
            process = awake.start()
        self.assertEqual(calls[0][:2], ["/usr/bin/caffeinate", "-dimsu"])
        self.assertEqual(calls[0][2:], ["-w", str(os.getpid())])               # ends by itself if the tester ends
        awake.stop(process)
        self.assertEqual(calls[1], "terminate")
        awake.stop(None)                                                        # nothing to stop: fine

    def test_no_caffeinate_is_not_fatal(self):
        with mock.patch("subprocess.Popen", side_effect=OSError("missing")):
            self.assertIsNone(awake.start())

    def test_the_mac_really_stays_awake_while_it_runs(self):
        process = awake.start()
        try:
            import time
            time.sleep(1.0)
            out = subprocess.run(["/usr/bin/pmset", "-g", "assertions"], capture_output=True, text=True).stdout
            self.assertIn("caffeinate", out)                                    # macOS lists the sleep assertion we hold
        finally:
            awake.stop(process)
        import time
        time.sleep(1.0)
        out = subprocess.run(["/usr/bin/pmset", "-g", "assertions"], capture_output=True, text=True).stdout
        self.assertNotIn(f"pid {process.pid}(caffeinate)", out)                  # and lets go afterwards


class RealisticAfterACrash(unittest.TestCase):
    def test_every_audition_starts_by_making_sure_studio_is_ready(self):
        folder = tempfile.mkdtemp()                       # never the real catalog.json of the user
        patcher = mock.patch.object(catalog, "PATH", os.path.join(folder, "catalog.json"))
        patcher.start()
        catalog.save({"projects": [{"id": "p", "name": "QA", "sessions": [{"id": "s" * 32, "name": "S", "talents": [{"id": "t", "name": "A"}], "talents_read": True}]}]})
        try:
            tests = suites.SUITES["realistic"][2]({"picked": json.dumps(["s" * 32]), "auditions": "2"})
        finally:
            patcher.stop()
            shutil.rmtree(folder, ignore_errors=True)
        audition_tests = [f for n, f in tests if "audition" in n and "Wait" not in n]
        self.assertEqual(len(audition_tests), 2)
        seen = []
        class Context:
            def log(self, t): pass
        done = {"talents": 1, "takes": 1, "photos": 0, "slates": 0, "labels": [], "seconds_finalize": 1, "extras": []}
        with mock.patch.object(realistic.recover, "ensure_ready", lambda c, session=None: seen.append(session) or object()), \
             mock.patch.object(realistic.driver, "random_audition", lambda *a, **k: done), \
             mock.patch.object(realistic.faults, "offline", lambda on: None), mock.patch.object(realistic.oracle, "last_media_pk", lambda: 0), \
             mock.patch.object(realistic.oracle, "check", lambda *a, **k: []), mock.patch.object(realistic, "verify_upload_started", lambda *a, **k: "ok"), mock.patch("time.sleep", lambda s: None):
            for function in audition_tests:
                function(Context())
        self.assertEqual(len(seen), 2)                                          # once per audition, not only the first
        self.assertEqual(seen[0], ("s" * 32, "S"))


if __name__ == "__main__":
    unittest.main()
