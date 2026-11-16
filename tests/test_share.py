import os
import tempfile
import unittest
import zipfile

from tester import share


def make_run(base, name="2026-11-16_203000_realistic"):
    run = os.path.join(base, name)
    os.makedirs(os.path.join(run, "sub"))
    for f in ("report.html", "results.json", "run.log", "fail_01_x.png"):
        open(os.path.join(run, f), "w").write(f)
    open(os.path.join(run, "sub", "crash.ips"), "w").write("crash")
    return run


class Share(unittest.TestCase):
    def test_visible_folder_only_for_a_hidden_install(self):
        self.assertEqual(share.shared_dir("/Users/x/Desktop/Studio Tester/.studio_tester"), "/Users/x/Desktop/Studio Tester/Reports")
        self.assertIsNone(share.shared_dir("/Users/x/dev/studio_tester"))          # a working copy: reports/ is already visible

    def test_zip_holds_the_whole_run_and_is_not_half_written(self):
        base = tempfile.mkdtemp()
        run = make_run(base)
        dest = os.path.join(base, "Studio Tester", "Reports")
        path = share.make_copy(run, dest_dir=dest)
        self.assertEqual(os.path.basename(path), "2026-11-16_203000_realistic.zip")
        names = zipfile.ZipFile(path).namelist()
        for expected in ("report.html", "results.json", "run.log", "fail_01_x.png", "sub/crash.ips"):
            self.assertIn("2026-11-16_203000_realistic/" + expected, names)
        self.assertEqual([f for f in os.listdir(dest) if f.endswith(".part")], [])
        share.make_copy(run, dest_dir=dest)                                          # again: replaced, not duplicated
        self.assertEqual(len(os.listdir(dest)), 1)

    def test_nothing_to_do_without_a_visible_place_or_a_run(self):
        self.assertIsNone(share.make_copy("/no/such/run", dest_dir=tempfile.mkdtemp()))
        self.assertIsNone(share.make_copy(make_run(tempfile.mkdtemp()), dest_dir=None) if share.shared_dir() is None else None)

    def test_zip_for_refuses_paths_outside_the_folder(self):
        base = tempfile.mkdtemp()
        dest = os.path.join(base, "Reports")
        path = share.make_copy(make_run(base), dest_dir=dest)
        self.assertEqual(share.zip_for("2026-11-16_203000_realistic", dest), path)
        self.assertIsNone(share.zip_for("../../etc/passwd", dest))
        self.assertIsNone(share.zip_for("missing_run", dest))
        self.assertIsNone(share.zip_for("", dest))


if __name__ == "__main__":
    unittest.main()
