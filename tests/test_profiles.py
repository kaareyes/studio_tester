import random
import unittest
from tester import profiles as p


class Profiles(unittest.TestCase):
    def test_ranges(self):
        rnd = random.Random(1)
        for name, (low, high) in p.PROFILES.items():
            for _ in range(200):
                kind, seconds = p.pick_length(name, rnd)
                self.assertEqual(kind, name)
                self.assertTrue(low <= seconds <= high)
        self.assertEqual(p.PROFILES["short"], (30, 60))
        self.assertEqual(p.PROFILES["normal"], (60, 300))
        self.assertEqual(p.PROFILES["long"], (1500, 3000))

    def test_mixed_follows_weights_and_seed(self):
        a = [p.pick_kind("mixed", random.Random(7)) for _ in range(5)]
        b = [p.pick_kind("mixed", random.Random(7)) for _ in range(5)]
        self.assertEqual(a, b)
        rnd = random.Random(3)
        kinds = [p.pick_kind("mixed", rnd) for _ in range(4000)]
        self.assertAlmostEqual(kinds.count("short") / 4000, 0.5, delta=0.05)
        self.assertAlmostEqual(kinds.count("long") / 4000, 0.1, delta=0.03)

    def test_mix_parsing(self):
        self.assertEqual(p.parse_mix("10/20/70"), {"short": 10, "normal": 20, "long": 70})
        self.assertEqual(p.parse_mix("nonsense"), p.DEFAULT_MIX)
        self.assertEqual(p.parse_mix("0/0/0"), p.DEFAULT_MIX)
        self.assertEqual(p.parse_mix("-1/2/3"), p.DEFAULT_MIX)

    def test_estimate(self):
        e = p.estimate(10, "long")
        self.assertEqual(e["average_take_seconds"], 2250)
        self.assertGreater(e["disk_mb"], 10000)
        self.assertLess(p.estimate(10, "short")["disk_mb"], 400)

    def test_disk_problem(self):
        self.assertIsNone(p.disk_problem(1, "short"))
        self.assertIn("GB", p.disk_problem(10**6, "long"))


if __name__ == "__main__":
    unittest.main()
