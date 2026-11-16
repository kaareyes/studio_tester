import os
import random
import tempfile
import unittest
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

    def test_selection_refuses_real_projects(self):
        pairs, problems = catalog.resolve_selection(DATA, [S[0], S[2], "missing"])
        self.assertEqual([s["id"] for _, s in pairs], [S[0]])
        self.assertEqual(len(problems), 2)
        pairs, problems = catalog.resolve_selection(DATA, [S[2], S[0]], allow_real=[PID2])
        self.assertEqual([s["id"] for _, s in pairs], [S[2], S[0]])          # order kept
        self.assertEqual(problems, [])

    def test_random_pick(self):
        ids = catalog.pick_random(DATA, 5, random.Random(1))
        self.assertEqual(ids, [S[0]])                      # only usable sessions of test projects
        self.assertEqual(catalog.pick_random(DATA, 5, random.Random(1)), ids)

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
