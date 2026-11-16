import unittest
from tester import matcher as m

SESSIONS = ["Auditions on November 04, 2026", "Auditions on November 05, 2026", "Audition 10", "Audition 100", "Not Me", "Not me v2", "Not me v3",
            "Fifty Talents for Today", "The CED", "QA Sim Project", "Café Müller"]


class Matcher(unittest.TestCase):
    def pick(self, query):
        return m.find(query, SESSIONS)

    def test_capitalization_and_spacing(self):
        for q in ["fifty talents for today", "FIFTY  TALENTS FOR   TODAY", "fifty-talents for today!"]:
            self.assertEqual(self.pick(q)["best"], "Fifty Talents for Today")

    def test_accents(self):
        self.assertEqual(self.pick("cafe muller")["best"], "Café Müller")

    def test_typos(self):
        self.assertEqual(self.pick("Fiftey Talants for Todya")["best"], "Fifty Talents for Today")
        self.assertEqual(self.pick("QA Sim Projcet")["best"], "QA Sim Project")

    def test_month_short_and_number_padding(self):
        r = self.pick("nov 4")
        self.assertEqual(r["status"], "found")
        self.assertEqual(r["best"], "Auditions on November 04, 2026")
        self.assertEqual(self.pick("november 05")["best"], "Auditions on November 05, 2026")

    def test_numbers_never_blur(self):
        self.assertEqual(self.pick("Audition 10")["best"], "Audition 10")
        self.assertEqual(self.pick("audition 100")["best"], "Audition 100")
        self.assertEqual(m.find("Audition 11", SESSIONS)["status"], "none")
        self.assertEqual(m.find("november 06", SESSIONS)["status"], "none")

    def test_similar_names_are_not_guessed(self):
        self.assertEqual(self.pick("not me")["best"], "Not Me")             # exact wins
        r = self.pick("not me v")
        self.assertIn(r["status"], ("ambiguous", "found"))
        if r["status"] == "found":
            self.assertIn(r["best"], ("Not me v2", "Not me v3"))
        r = m.find("Notme v", ["Not me v2", "Not me v3"])
        self.assertEqual(r["status"], "ambiguous")
        self.assertEqual(len(r["candidates"]), 2)

    def test_words_run_together(self):
        self.assertEqual(self.pick("thecedd")["best"] if self.pick("thecedd")["best"] else None, "The CED")

    def test_missing_word(self):
        self.assertEqual(self.pick("fifty talents")["best"], "Fifty Talents for Today")

    def test_nothing_close(self):
        r = self.pick("completely different thing")
        self.assertEqual(r["status"], "none")
        self.assertEqual(len(r["candidates"]), 3)
        self.assertEqual(m.find("x", [])["status"], "none")

    def test_empty_and_odd_input(self):
        self.assertEqual(m.find("", SESSIONS)["status"], "none")
        self.assertEqual(m.find("   ", SESSIONS)["status"], "none")
        self.assertEqual(m.find("🎬🎬", SESSIONS)["status"], "none")

    def test_objects_with_key(self):
        items = [{"name": "Not Me", "id": 1}, {"name": "The CED", "id": 2}]
        self.assertEqual(m.find("the ced", items, key=lambda i: i["name"])["best"]["id"], 2)


if __name__ == "__main__":
    unittest.main()
