import os
import sqlite3
import tempfile
import unittest
from tester import oracle


def make_db(rows):
    path = os.path.join(tempfile.mkdtemp(), "StudioApp.sqlite")
    c = sqlite3.connect(path)
    c.execute("create table ZDBMEDIA (Z_PK integer primary key, ZAUDITIOID text, ZFOLDERPATH text, ZISUPLOADED integer, ZISDELETED integer)")
    for r in rows:
        c.execute("insert into ZDBMEDIA (ZAUDITIOID, ZFOLDERPATH, ZISUPLOADED, ZISDELETED) values (?,?,?,?)", r)
    c.commit(); c.close()
    return path


def f(project, session, kind, name, tmp=None):
    folder = {"take": "Audition", "slate": "ImageAndSlate", "photo": "Images"}[kind]
    return f"/Users/x/Movies/STUDIO APP/{project}/{session}/{folder}/{name}"


class Oracle(unittest.TestCase):
    def test_clean(self):
        db = make_db([("a1", f("P", "S", "take", "t1.mp4"), 1, 0), ("a1", f("P", "S", "slate", "s1.mp4"), 1, 0), ("a1", f("P", "S", "photo", "p1.jpg"), 1, 0)])
        self.assertEqual(oracle.check(0, {"takes": 1, "slates": 1, "photos": 1}, uploaded=True, path=db, check_files=False), [])

    def test_duplicate(self):
        row = ("a1", f("P", "S", "take", "t1.mp4"), 1, 0)
        problems = oracle.check(0, path=make_db([row, row]), check_files=False)
        self.assertTrue(any("duplicate" in p for p in problems))

    def test_wrong_session(self):
        db = make_db([("a1", f("P", "S1", "take", "t1.mp4"), 1, 0), ("a1", f("P", "S2", "take", "t2.mp4"), 1, 0)])
        self.assertTrue(any("wrong session" in p for p in oracle.check(0, path=db, check_files=False)))

    def test_not_uploaded_and_missing(self):
        db = make_db([("a1", f("P", "S", "take", "t1.mp4"), 0, 0)])
        self.assertTrue(any("not uploaded" in p for p in oracle.check(0, uploaded=True, path=db, check_files=False)))
        self.assertEqual(oracle.check(0, uploaded=None, path=db, check_files=False), [])
        self.assertTrue(any("lost file" in p for p in oracle.check(0, path=db, check_files=True)))
        problems = oracle.check(0, {"takes": 2}, path=db, check_files=False)
        self.assertTrue(any("missing takes" in p for p in problems))

    def test_offline_must_not_be_uploaded(self):
        db = make_db([("a1", f("P", "S", "take", "t1.mp4"), 1, 0)])
        self.assertTrue(any("while offline" in p for p in oracle.check(0, uploaded=False, path=db, check_files=False)))

    def test_deleted_rows_and_snap_ignored(self):
        db = make_db([("a1", f("P", "S", "take", "gone.mp4"), 0, 1), ("a1", "/x/STUDIO APP/P/S/Snap.jpg", 0, 0)])
        self.assertEqual(oracle.check(0, uploaded=True, path=db, check_files=True), [])

    def test_since_pk_and_no_audition(self):
        db = make_db([("a1", f("P", "S", "take", "old.mp4"), 0, 0), ("", f("P", "S", "take", "new.mp4"), 1, 0)])
        self.assertEqual(oracle.last_media_pk(db), 2)
        problems = oracle.check(1, path=db, check_files=False)
        self.assertTrue(any("no audition" in p for p in problems))
        self.assertFalse(any("old.mp4" in p for p in problems))

    def test_no_database(self):
        self.assertEqual(oracle.media_since(0, path=None) if oracle.database_path() is None else [], [])


if __name__ == "__main__":
    unittest.main()
