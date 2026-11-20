import unittest

from tester import patience


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t


class PatienceRule(unittest.TestCase):
    def make(self, cpu_values, base=60, cap=100, extend=20):
        clock = FakeClock()
        values = iter(cpu_values)
        last = {"v": cpu_values[-1]}
        def cpu():
            try:
                last["v"] = next(values)
            except StopIteration:
                pass
            return last["v"]
        return clock, patience.Patience(base, cpu, extend=extend, cap=cap, now=clock.now)

    def test_nothing_happens_before_the_base_time(self):
        clock, wait = self.make([90])
        clock.t = 59.9
        self.assertFalse(wait.expired())

    def test_an_idle_studio_ends_the_wait_at_the_base_time(self):
        clock, wait = self.make([0.2])
        clock.t = 60
        self.assertTrue(wait.expired())

    def test_a_busy_studio_gets_more_time_up_to_the_cap(self):
        clock, wait = self.make([80] * 50, base=60, cap=100, extend=20)
        clock.t = 60
        results = []
        for _ in range(8):
            results.append(wait.expired())
            clock.t = wait.deadline                      # the next moment the wait could end
        self.assertEqual(results[:5], [False] * 5)       # 5 extensions of 20 s = the 100 s cap
        self.assertTrue(results[5])
        self.assertEqual(wait.extended, 100)

    def test_it_ends_as_soon_as_a_busy_studio_goes_idle(self):
        clock, wait = self.make([80, 80, 0.3], base=60, cap=500, extend=20)
        clock.t = 60
        self.assertFalse(wait.expired())
        clock.t = wait.deadline
        self.assertFalse(wait.expired())
        clock.t = wait.deadline
        self.assertTrue(wait.expired())                  # a hung Studio sits at 0% CPU


class ProcessTreeCpu(unittest.TestCase):
    PS = "  100     1   2.0\n  200   100  40.0\n  300   200  30.0\n  400     1  90.0\n  bad line\n"

    def test_sums_the_process_and_all_its_helpers(self):
        self.assertEqual(patience.process_tree_cpu(100, self.PS), 72.0)
        self.assertEqual(patience.process_tree_cpu(200, self.PS), 70.0)

    def test_unknown_or_missing_process_is_zero(self):
        self.assertEqual(patience.process_tree_cpu(999, self.PS), 0.0)
        self.assertEqual(patience.process_tree_cpu(None, self.PS), 0.0)


class WaitsUseIt(unittest.TestCase):
    def test_wait_label_keeps_waiting_while_studio_is_busy_and_stops_when_idle(self):
        from unittest import mock
        from suites import driver
        clock = FakeClock()
        busy = iter([80, 80, 80, 0.1])
        with mock.patch.object(driver.faults, "events", lambda n: []), mock.patch.object(driver.time, "sleep", lambda s: setattr(clock, "t", clock.t + 10)), \
                mock.patch.object(patience, "for_studio", lambda base, cap=600.0, extend=20.0: patience.Patience(base, lambda: next(busy, 0.1), extend=extend, cap=cap, now=clock.now)):
            self.assertIsNone(driver.wait_label("video", 0, timeout=30, cap=200))
        self.assertGreater(clock.t, 40)                  # it waited past the base time because Studio was busy
        self.assertLess(clock.t, 200)                    # and stopped when Studio went idle, long before the cap


if __name__ == "__main__":
    unittest.main()
