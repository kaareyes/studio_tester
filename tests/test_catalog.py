import os
import random
import tempfile
import unittest
from unittest import mock
from tester import catalog, collect

PID = "11111111-1111-1111-1111-111111111111"
PID2 = "22222222-2222-2222-2222-222222222222"
S = ["aaaaaaaa-0000-0000-0000-00000000000%d" % i for i in range(5)]

DATA = {"projects": [
    {"id": PID, "name": "QA Sim Project", "sessions": [
        {"id": S[0], "name": "Auditions on November 04", "talents": [{"id": "t1", "name": "Ann"}], "talents_read": True},
        {"id": S[1], "name": "Empty session", "talents": [], "talents_read": True}]},
    {"id": PID2, "name": "Real Customer Film", "sessions": [
        {"id": S[2], "name": "Callbacks", "talents": [{"id": "t2", "name": "Bob"}], "talents_read": True}]}]}


class Catalog(unittest.TestCase):
    def test_test_project_filter(self):
        self.assertTrue(catalog.is_test_project("QA Sim Project", ["qa"]))
        self.assertTrue(catalog.is_test_project("my TEST run", ["test"]))
        self.assertFalse(catalog.is_test_project("Real Customer Film", ["qa", "test"]))
        self.assertFalse(catalog.is_test_project("Contest Winners", ["test"]))         # whole words only

    def test_decorate_and_usable(self):
        d = catalog.decorate(DATA, ["qa"])
        self.assertTrue(d["projects"][0]["is_test"])
        self.assertFalse(d["projects"][1]["is_test"])
        self.assertTrue(d["projects"][0]["sessions"][0]["usable"])
        self.assertFalse(d["projects"][0]["sessions"][1]["usable"])

    def test_every_project_can_be_used_by_default(self):
        with mock.patch.object(catalog, "load_settings", lambda path=None: {}):
            self.assertFalse(catalog.protect_enabled())
            pairs, problems = catalog.resolve_selection(DATA, [S[0], S[2], "missing"])
            self.assertEqual([s["id"] for _, s in pairs], [S[0], S[2]])          # the Test build is a test environment: all projects are fine
            self.assertEqual(len(problems), 1)                                   # only the id that does not exist is reported
            decorated = catalog.decorate(DATA)
            self.assertTrue(all(p["is_test"] for p in decorated["projects"]))
            self.assertFalse(decorated["protected"])

    def test_protect_real_projects_is_an_optional_switch(self):
        with mock.patch.object(catalog, "load_settings", lambda path=None: {"protect_projects": True}):
            self.assertTrue(catalog.protect_enabled())
            pairs, problems = catalog.resolve_selection(DATA, [S[0], S[2], "missing"])
            self.assertEqual([s["id"] for _, s in pairs], [S[0]])
            self.assertEqual(len(problems), 2)
            pairs, problems = catalog.resolve_selection(DATA, [S[2], S[0]], allow_real=[PID2])
            self.assertEqual([s["id"] for _, s in pairs], [S[2], S[0]])          # order kept; 'use anyway' still works
            self.assertTrue(catalog.decorate(DATA)["protected"])

    def test_random_pick(self):
        with mock.patch.object(catalog, "load_settings", lambda path=None: {}):
            ids = catalog.pick_random(DATA, 5, random.Random(1))
            self.assertEqual(sorted(ids), sorted([S[0], S[2]]))                   # every usable session of every project
            self.assertEqual(catalog.pick_random(DATA, 5, random.Random(1)), ids)
        with mock.patch.object(catalog, "load_settings", lambda path=None: {"protect_projects": True}):
            self.assertEqual(catalog.pick_random(DATA, 5, random.Random(1)), [S[0]])   # only test projects when protection is on

    def test_fuzzy_session(self):
        r = catalog.find_session(DATA, "auditions nov 4")
        self.assertEqual(r["status"], "found")
        self.assertEqual(r["best"][1]["id"], S[0])
        r = catalog.find_session(DATA, "qa sim / empty sesion")
        self.assertEqual(r["best"][1]["id"], S[1])

    def test_save_load_roundtrip(self):
        path = os.path.join(tempfile.mkdtemp(), "catalog.json")
        self.assertEqual(catalog.load(path)["projects"], [])
        catalog.save(dict(DATA, complete=True), path)
        loaded = catalog.load(path)
        self.assertEqual(len(loaded["projects"]), 2)
        self.assertTrue(loaded["collected_at"])
        open(path, "w").write("{broken")
        self.assertEqual(catalog.load(path)["projects"], [])


class Assign(unittest.TestCase):
    def test_sessions_follow_the_project_above(self):
        out = collect.assign_sessions([
            {"kind": "session", "id": "s2", "name": "B", "y": 300},
            {"kind": "project", "id": "p1", "name": "One", "y": 100},
            {"kind": "session", "id": "s1", "name": "A", "y": 150},
            {"kind": "project", "id": "p2", "name": "Two", "y": 250},
        ])
        self.assertEqual(out["p1"]["sessions"], {"s1": "A"})
        self.assertEqual(out["p2"]["sessions"], {"s2": "B"})

    def test_session_before_any_project(self):
        out = collect.assign_sessions([{"kind": "session", "id": "s1", "name": "A", "y": 10}])
        self.assertEqual(out[None]["name"], "(project not shown)")


if __name__ == "__main__":
    unittest.main()


class Limit(unittest.TestCase):
    def test_stops_scrolling_only_when_the_next_project_is_seen(self):
        three = {"a": {}, "b": {}, "c": {}}
        self.assertFalse(collect.enough_projects(three, 3))            # the 3rd project's sessions may still continue below
        self.assertTrue(collect.enough_projects({"a": {}, "b": {}, "c": {}, "d": {}}, 3))
        self.assertFalse(collect.enough_projects(three, 0))            # 0 / None = all projects: never stop early
        self.assertFalse(collect.enough_projects(three, None))

    def test_keeps_the_first_projects_in_list_order(self):
        seen = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}
        self.assertEqual(list(collect.first_projects(seen, 2)), ["p1", "p2"])
        self.assertEqual(list(collect.first_projects(seen, 0)), ["p1", "p2", "p3", "p4"])
        self.assertEqual(list(collect.first_projects(seen, 10)), ["p1", "p2", "p3", "p4"])


class SmokeSessionChoiceTest(unittest.TestCase):
    def test_prefers_a_session_with_talents(self):
        from suites import smoke
        from unittest import mock
        data = {"projects": [{"sessions": [{"name": "Empty", "talents": []}, {"name": "Full", "talents": [{"id": "t"}]}]}]}
        with mock.patch("tester.catalog.load", return_value=data):
            self.assertEqual(smoke.session_with_talents(), "Full")
        with mock.patch("tester.catalog.load", return_value={"projects": []}):
            self.assertEqual(smoke.session_with_talents(), "November 04")


class CatalogPathTest(unittest.TestCase):
    def test_load_and_save_follow_a_patched_path_never_the_real_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(catalog, "PATH", os.path.join(folder, "c.json")):
                catalog.save({"projects": [{"id": "x"}]})
                self.assertEqual(catalog.load()["projects"][0]["id"], "x")
            self.assertTrue(os.path.exists(os.path.join(folder, "c.json")))
