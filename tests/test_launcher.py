import os
import tempfile
import unittest
from types import SimpleNamespace

from tester import launcher


class Launcher(unittest.TestCase):
    def test_ask_defaults_and_answers(self):
        self.assertTrue(launcher.ask("q", True, answer=""))
        self.assertFalse(launcher.ask("q", False, answer=""))
        self.assertTrue(launcher.ask("q", False, answer="Yes"))
        self.assertFalse(launcher.ask("q", True, answer="n"))

    def test_requirements_stamp(self):
        folder = tempfile.mkdtemp()
        req, stamp = os.path.join(folder, "r.txt"), os.path.join(folder, "stamp")
        open(req, "w").write("a\n")
        self.assertFalse(launcher.packages_current(stamp, req))          # nothing installed yet
        open(stamp, "w").write(launcher.requirements_hash(req))
        self.assertTrue(launcher.packages_current(stamp, req))
        open(req, "w").write("a\nb\n")                                     # requirements changed by an update
        self.assertFalse(launcher.packages_current(stamp, req))
        self.assertFalse(launcher.packages_current(stamp, os.path.join(folder, "missing.txt")))

    def test_venv_works(self):
        python = os.path.join(tempfile.mkdtemp(), "python")
        self.assertFalse(launcher.venv_works(python, runner=None))        # no file
        open(python, "w").write("x")
        self.assertTrue(launcher.venv_works(python, runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="True\n")))
        self.assertFalse(launcher.venv_works(python, runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="False\n")))
        self.assertFalse(launcher.venv_works(python, runner=lambda *a, **k: SimpleNamespace(returncode=1, stdout="")))

        def boom(*a, **k):
            raise OSError("broken")
        self.assertFalse(launcher.venv_works(python, runner=boom))

    def test_internet(self):
        class Page:
            def close(self):
                pass
        self.assertTrue(launcher.internet(opener=lambda url, timeout: Page()))

        def down(url, timeout):
            raise OSError("offline")
        self.assertFalse(launcher.internet(opener=down))

    def test_wait_until(self):
        calls = {"n": 0, "t": 0}
        def check():
            calls["n"] += 1
            return calls["n"] >= 3
        self.assertTrue(launcher.wait_until(check, 100, every=1, clock=lambda: calls["t"], sleep=lambda s: calls.__setitem__("t", calls["t"] + s)))
        calls.update(n=0, t=0)
        self.assertFalse(launcher.wait_until(lambda: False, 5, every=1, clock=lambda: calls["t"], sleep=lambda s: calls.__setitem__("t", calls["t"] + s)))

    def test_install_writes_stamp_only_on_success(self):
        old_stamp, old_venv = launcher.STAMP, launcher.VENV_PYTHON
        folder = tempfile.mkdtemp()
        launcher.STAMP = os.path.join(folder, "stamp")
        try:
            launcher.install_packages(runner=lambda *a, **k: SimpleNamespace(returncode=1))
            self.assertFalse(os.path.exists(launcher.STAMP))
            launcher.install_packages(runner=lambda *a, **k: SimpleNamespace(returncode=0))
            self.assertTrue(os.path.exists(launcher.STAMP))
        finally:
            launcher.STAMP, launcher.VENV_PYTHON = old_stamp, old_venv


if __name__ == "__main__":
    unittest.main()
