"""Every control name the tester presses or looks for must exist in the app (NAMES.md is generated from the app's source). A typo or a
renamed control would otherwise only show up as a failed step in a live run."""
import glob
import importlib.util
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_names():
    text = open(os.path.join(ROOT, "NAMES.md")).read()
    return {n.split("\\(")[0] for n in re.findall(r"^\| `([^`]+)` \|", text, re.M)}      # a name built at run time counts as its fixed start


def names_used_by_the_tester():
    first_parts = {n.split(".")[0] for n in app_names()}
    used = {}
    for path in glob.glob(os.path.join(ROOT, "suites", "*.py")) + glob.glob(os.path.join(ROOT, "tester", "*.py")):
        if os.path.basename(path) in ("page.py", "server.py"):          # the page's own JavaScript is not an app control
            continue
        for match in re.finditer(r'["\']([a-z][A-Za-z]*(?:\.[A-Za-z]+)+\.?)["\']', open(path).read()):
            name = match.group(1)
            if name.startswith("alert.button."):
                continue          # worked out by the tester from the words on a pop-up's buttons (SwiftUI names every part alert.dialog)
            if name.split(".")[0] in first_parts:
                used.setdefault(name, set()).add(os.path.basename(path))
    return used


class NamesExist(unittest.TestCase):
    def test_every_name_the_tester_uses_is_a_name_in_the_app(self):
        app = app_names()
        missing = []
        for name, files in sorted(names_used_by_the_tester().items()):
            found = any(a.startswith(name) for a in app) if name.endswith(".") else name in app
            if not found:
                missing.append(f"{name} (used in {', '.join(sorted(files))})")
        self.assertEqual(missing, [], "the tester uses control names that are not in NAMES.md (typo, or the app renamed them, or "
                                      "NAMES.md is stale: run scripts/gen_test_names.py): " + "; ".join(missing))

    def test_the_names_the_support_check_requires_are_real_names(self):
        from tester import support
        app = app_names()
        for name in support.CORE:
            found = any(a.startswith(name) for a in app) if name.endswith(".") else name in app
            self.assertTrue(found, f"support.CORE lists {name} but the app has no such control name")

    def test_the_check_really_finds_a_wrong_name(self):
        self.assertNotIn("capture.finalise", app_names())             # a British-spelling typo would not pass
        self.assertIn("capture.finalize", app_names())


class NamesGenerator(unittest.TestCase):
    """The generator lives in the Studio repository's scripts/ folder (not in the QA copy of the tester): skipped when it is not there."""
    PATH = os.path.join(os.path.dirname(ROOT), "scripts", "gen_test_names.py")

    @unittest.skipUnless(os.path.exists(PATH), "scripts/gen_test_names.py is not in this copy")
    def test_it_reads_plain_conditional_and_run_time_names(self):
        spec = importlib.util.spec_from_file_location("gen_test_names", self.PATH)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        read = lambda text: gen.literals_in_call(text, text.index("(") + 1)
        self.assertEqual(read('.testID("login.signIn")'), ["login.signIn"])
        self.assertEqual(read('.testID(type == .yesNo ? "alert.rightButton" : "alert.okButton")'), ["alert.rightButton", "alert.okButton"])
        self.assertEqual(read('.testID("sessions.row.name.\\((session?.id ?? ""))")'), ["sessions.row.name.\\(...)"])   # nested quotes
        self.assertEqual(read('.testID("capture.take.card.\\(index)").other("x.y")'), ["capture.take.card.\\(...)"])
        self.assertEqual(read('.testID(someVariable)'), [])


if __name__ == "__main__":
    unittest.main()
