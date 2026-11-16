import os
import plistlib
import tempfile
import threading
import time
import unittest
from unittest import mock

from tester import support

MACHO = b"\xcf\xfa\xed\xfe"


def bundle(main_names=(), dylib_names=None, version=("1.0", "775"), name="Studio (macOS) - Test"):
    """A fake .app: Info.plist and a program file (and, for a Debug build, a .debug.dylib holding the code)."""
    app = os.path.join(tempfile.mkdtemp(), name + ".app")
    os.makedirs(os.path.join(app, "Contents", "MacOS"))
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as handle:
        plistlib.dump({"CFBundleExecutable": name, "CFBundleShortVersionString": version[0], "CFBundleVersion": version[1]}, handle)

    def write(file_name, names):
        with open(os.path.join(app, "Contents", "MacOS", file_name), "wb") as handle:
            handle.write(MACHO + b"\x00" * 64 + b"\x00".join(n.encode() for n in names) + b"\x00" * 64 + os.urandom(2000))
    write(name, main_names)
    if dylib_names is not None:
        write(name + ".debug.dylib", dylib_names)
    return app


class Support(unittest.TestCase):
    def test_the_decision_only_uses_names_that_are_always_stored_as_text(self):
        for name in list(support.CORE) + list(support.OPTIONAL.values()):
            self.assertGreaterEqual(len(name.encode()), 16, name)       # Swift keeps shorter literals inside the code: they can look missing

    def test_a_good_build_whose_short_names_are_not_readable_is_still_supported(self):
        # an optimized build: the long names are text, the 12-15 byte names are not findable (login.signIn, nav.projects...)
        result = support.check(bundle(main_names=support.CORE))
        self.assertEqual(result["state"], "ok")

    def test_a_build_with_the_names_can_be_tested(self):
        result = support.check(bundle(main_names=support.CORE + list(support.OPTIONAL.values())))
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["version"], "1.0 (775)")
        self.assertEqual(result["notes"], [])

    def test_an_old_build_without_the_names_is_not_supported(self):
        result = support.check(bundle(main_names=["some.other.string", "Hello"], version=("0.9", "412")))
        self.assertEqual(result["state"], "unsupported")
        self.assertEqual(set(result["missing"]), set(support.CORE))
        self.assertIn("App version not supported for testing", result["message"])
        self.assertIn(support.SUPPORTED_BRANCH, result["message"])                         # says which branch is supported
        self.assertIn("0.9 (412)", result["message"])

    def test_a_build_with_only_some_names_is_not_supported(self):
        result = support.check(bundle(main_names=support.CORE[:-3]))                      # an in-between build
        self.assertEqual(result["state"], "unsupported")
        self.assertEqual(result["missing"], support.CORE[-3:])

    def test_a_debug_build_keeps_its_code_in_a_dylib(self):
        result = support.check(bundle(main_names=[], dylib_names=support.CORE))             # the main file is a stub
        self.assertEqual(result["state"], "ok")

    def test_newer_features_missing_is_a_note_not_a_block(self):
        result = support.check(bundle(main_names=support.CORE))
        self.assertEqual(result["state"], "ok")
        self.assertTrue(any("Link to talent" in n for n in result["notes"]))

    def test_unreadable_app_is_unknown_not_blocked(self):
        folder = os.path.join(tempfile.mkdtemp(), "Nothing.app")
        os.makedirs(folder)
        result = support.check(folder)
        self.assertEqual(result["state"], "unknown")
        self.assertIsNone(support.scan(folder))

    def test_names_must_be_inside_a_program_file_not_just_anywhere(self):
        app = bundle(main_names=[])
        with open(os.path.join(app, "Contents", "readme.txt"), "w") as handle:              # a text file with the names does not count
            handle.write("\n".join(support.CORE))
        self.assertEqual(support.check(app)["state"], "unsupported")

    def test_scan_is_remembered_and_repeated_after_a_rebuild(self):
        app = bundle(main_names=support.CORE)
        calls = []
        def scanner(path):
            calls.append(path)
            return support.check(path)
        support._cache.clear()
        first = support.cached(app, scanner=scanner)
        self.assertEqual(first["state"], "checking")                                        # the page is not made to wait
        for _ in range(50):
            time.sleep(0.05)
            second = support.cached(app, scanner=scanner)
            if second["state"] != "checking":
                break
        self.assertEqual(second["state"], "ok")
        support.cached(app, scanner=scanner)
        self.assertEqual(len(calls), 1)                                                     # asked again, scanned once
        time.sleep(1.1)
        with open(os.path.join(app, "Contents", "MacOS", "Studio (macOS) - Test"), "wb") as handle:   # rebuilt: an older build now
            handle.write(MACHO + b"\x00" * 3000)
        support.cached(app, scanner=scanner)
        for _ in range(50):
            time.sleep(0.05)
            third = support.cached(app, scanner=scanner)
            if third["state"] != "checking":
                break
        self.assertEqual(third["state"], "unsupported")
        self.assertEqual(len(calls), 2)


class SupportInTheServer(unittest.TestCase):
    def test_start_and_collect_refuse_an_unsupported_app_with_the_plain_sentence(self):
        from tester import server
        old = bundle(main_names=["nothing here"])
        support._cache.clear()
        support.cached(old)
        for _ in range(60):
            time.sleep(0.05)
            if support.cached(old)["state"] != "checking":
                break
        server.chosen["path"] = old
        try:
            for suite in ("smoke", "explore", "realistic", "chaos"):
                problem = server.suite_problem(suite)
                self.assertIn("App version not supported for testing", problem)
                self.assertIn(support.SUPPORTED_BRANCH, problem)
            self.assertIsNone(server.suite_problem("checks") if "Test.app" in old else None)         # the code checks do not need the app
            text, problem, blocking = server.estimate_text("smoke", {})
            self.assertTrue(blocking)
        finally:
            server.chosen["path"] = None

    def test_a_supported_app_is_not_blocked(self):
        from tester import server
        good = bundle(main_names=support.CORE)
        support._cache.clear()
        support.cached(good)
        for _ in range(60):
            time.sleep(0.05)
            if support.cached(good)["state"] != "checking":
                break
        server.chosen["path"] = good
        try:
            self.assertIsNone(server.suite_problem("smoke"))
            self.assertIsNone(server.suite_problem("chaos"))
        finally:
            server.chosen["path"] = None

    def test_the_page_shows_the_badge_and_blocks_the_rest(self):
        from tester import server
        for text in ("not supported", "can be tested", "unsup", "App version not supported for testing"):
            self.assertIn(text, server.PAGE)


if __name__ == "__main__":
    unittest.main()
