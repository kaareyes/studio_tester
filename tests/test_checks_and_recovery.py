import shutil
import json
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import suites
from suites import checks, recovery
from tester import catalog, control
from tester.runner import Skip


class Context:
    def __init__(self):
        self.lines = []

    def log(self, text):
        self.lines.append(text)


class Checks(unittest.TestCase):
    def test_skipped_without_the_repository(self):
        with mock.patch.object(checks, "repo_root", lambda: None):
            for _, function in checks.TESTS:
                with self.assertRaises(Skip) as raised:
                    function(Context())
                self.assertIn("repository", str(raised.exception))

    def test_repo_is_found_through_the_environment(self):
        folder = tempfile.mkdtemp()
        open(os.path.join(folder, "Studio.xcodeproj"), "w").close()
        with mock.patch.dict(os.environ, {"STUDIO_REPO": folder}):
            self.assertEqual(checks.repo_root(), folder)
        with mock.patch.dict(os.environ, {"STUDIO_REPO": "/no/such/folder"}), mock.patch.object(catalog, "load_settings", lambda: {}), \
             mock.patch.object(checks.runner, "ROOT", "/also/missing/studio_tester"):
            self.assertIsNone(checks.repo_root())

    @staticmethod
    def spawner(code, text, delay=0.0):
        """A fake child process that writes `text` to the output file and exits with `code` after `delay` seconds."""
        def spawn(command, cwd, out):
            out.write(text)
            out.flush()
            began = time.time()
            return SimpleNamespace(poll=lambda: code if time.time() - began >= delay else None, kill=lambda: None, returncode=code)
        return spawn

    def test_schema_drift_result_handling(self):
        with mock.patch.object(checks, "repo_root", lambda: "/repo"):
            with mock.patch.object(checks, "_spawn", self.spawner(0, "no drift")):
                checks.schema_drift(Context())                                   # passes
            with mock.patch.object(checks, "_spawn", self.spawner(1, "REMOVED field Talent.stageName")):
                with self.assertRaises(AssertionError) as raised:
                    checks.schema_drift(Context())
                self.assertIn("drifted", str(raised.exception))
                self.assertIn("REMOVED", str(raised.exception))                  # the reason is in the failure sentence
            with mock.patch.object(checks, "_spawn", self.spawner(2, "network error")):
                with self.assertRaises(AssertionError):
                    checks.schema_drift(Context())                               # could not run: a failure, never a silent pass

    def test_swift_tests_need_swift_and_fail_loudly(self):
        with mock.patch.object(checks, "repo_root", lambda: "/repo"), mock.patch("shutil.which", lambda n: None):
            with self.assertRaises(Skip):
                checks.offline_package_tests(Context())
        with mock.patch.object(checks, "repo_root", lambda: "/repo"), mock.patch("shutil.which", lambda n: "/usr/bin/swift"), \
             mock.patch.object(checks, "_spawn", self.spawner(1, "Test Case failed")):
            with self.assertRaises(AssertionError) as raised:
                checks.offline_package_tests(Context())
            self.assertIn("failed", str(raised.exception))

    def test_a_long_check_can_be_cancelled_and_the_child_is_stopped(self):
        killed = []
        def spawn(command, cwd, out):
            return SimpleNamespace(poll=lambda: None, kill=lambda: killed.append(1), returncode=None)      # never ends by itself
        box = {}
        def work():
            control.begin(threading.current_thread())
            try:
                with mock.patch.object(checks, "repo_root", lambda: "/repo"), mock.patch.object(checks, "_spawn", spawn):
                    checks.schema_drift(Context())
            except control.StopRun:
                box["cancelled"] = True
            finally:
                control.end()
        t = threading.Thread(target=work)
        t.start()
        time.sleep(1.0)
        began = time.time()
        control.cancel()
        t.join(5)
        self.assertTrue(box.get("cancelled"))
        self.assertLess(time.time() - began, 3)
        self.assertEqual(killed, [1])                                            # the running check was stopped, not left behind

    def test_timeout_stops_the_child(self):
        killed = []
        spawn = lambda command, cwd, out: SimpleNamespace(poll=lambda: None, kill=lambda: killed.append(1), returncode=None)
        with mock.patch.object(checks, "_spawn", spawn):
            with self.assertRaises(AssertionError) as raised:
                checks._run(Context(), ["x"], "/", timeout=0)
        self.assertIn("timed out", str(raised.exception))
        self.assertEqual(killed, [1])

    def test_the_suite_is_registered(self):
        self.assertIn("checks", suites.SUITES)
        self.assertEqual(len(suites.SUITES["checks"][2]), 2)


class RecoveryList(unittest.TestCase):
    def test_every_scenario_of_scenarios_md_is_listed_by_name(self):
        folder = tempfile.mkdtemp()                       # never the real catalog.json of the user
        patcher = mock.patch.object(catalog, "PATH", os.path.join(folder, "catalog.json"))
        patcher.start()
        catalog.save({"projects": [{"id": "p", "name": "QA", "sessions": [{"id": "s" * 32, "name": "S", "talents": [{"id": "t", "name": "A"}], "talents_read": True}]}]})
        try:
            names = " | ".join(n for n, _ in suites.SUITES["recovery"][2]({"picked": json.dumps(["s" * 32])}))
        finally:
            patcher.stop()
            shutil.rmtree(folder, ignore_errors=True)
        for ident in ("PT-01", "PT-02", "PT-03", "PT-04", "PT-05", "PT-06", "PT-07", "PT-08", "PT-09", "PT-10", "PT-11", "PT-12", "PT-13",
                      "PT-14", "PT-15", "PT-16", "PT-17", "RF-01"):
            self.assertIn(ident, names)                      # driven or listed as manual/planned: never silently missing

    def test_manual_ones_skip_with_a_reason(self):
        for ident, _, reason in recovery.MANUAL:
            self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
