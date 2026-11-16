import threading
import time
import unittest
from unittest import mock

from tester import control, runner


def run_thread(target):
    box = {}
    def body():
        control.begin(threading.current_thread())
        try:
            target(box)
        except control.StopRun:
            box["cancelled"] = True
        finally:
            control.end()
            box["done"] = True
    t = threading.Thread(target=body)
    t.start()
    return t, box


class Control(unittest.TestCase):
    def tearDown(self):
        control.end()

    def test_pause_holds_the_test_until_continue(self):
        started = threading.Event()
        def work(box):
            started.set()
            time.sleep(0.05)
            control.checkpoint()
            box["passed_checkpoint"] = True
        t, box = run_thread(work)
        started.wait(2)
        self.assertTrue(control.pause("test"))
        time.sleep(0.8)
        self.assertNotIn("passed_checkpoint", box)                   # held while paused
        self.assertTrue(control.is_paused())
        self.assertTrue(control.resume())
        t.join(3)
        self.assertTrue(box.get("passed_checkpoint"))

    def test_cancel_unwinds_a_long_wait_at_once(self):
        def work(box):
            box["began"] = time.time()
            time.sleep(60)                                           # a long take: the patched sleep can be interrupted
        t, box = run_thread(work)
        time.sleep(0.5)
        control.cancel()
        t.join(3)
        self.assertTrue(box.get("cancelled"))
        self.assertLess(time.time() - box["began"], 3)

    def test_cancel_while_paused(self):
        def work(box):
            control.checkpoint()
            time.sleep(0.3)
            control.checkpoint()
        t, box = run_thread(work)
        time.sleep(0.1)
        control.pause("x")
        time.sleep(0.6)
        control.cancel()
        t.join(3)
        self.assertTrue(box.get("cancelled"))

    def test_other_threads_are_never_paused_or_cancelled(self):
        t, box = run_thread(lambda b: time.sleep(0.8))
        time.sleep(0.1)
        control.pause("x")
        control.cancel()
        began = time.time()
        control.checkpoint()                                          # this (main) thread is not the run thread
        time.sleep(0.2)                                               # normal sleep, not interrupted
        self.assertLess(time.time() - began, 1)
        t.join(3)

    def test_time_spent_paused_does_not_eat_the_wait(self):
        def work(box):
            box["t0"] = time.time()
            time.sleep(0.6)
            box["t1"] = time.time()
        t, box = run_thread(work)
        time.sleep(0.2)
        control.pause("x")
        time.sleep(1.0)
        control.resume()
        t.join(4)
        self.assertGreaterEqual(box["t1"] - box["t0"], 1.5)           # 0.6 s of work + about 1 s paused

    def test_nothing_happens_without_a_run(self):
        self.assertFalse(control.pause("x"))
        self.assertFalse(control.cancel())
        control.checkpoint()

    def test_esc_hold_fires_once_per_hold(self):
        h = control.HoldTracker(hold=1.5)
        self.assertFalse(h.update(True, 0.0))
        self.assertFalse(h.update(True, 1.0))
        self.assertTrue(h.update(True, 1.6))
        self.assertFalse(h.update(True, 2.5))                         # still held: not again
        self.assertFalse(h.update(False, 2.6))
        self.assertFalse(h.update(True, 3.0))
        self.assertTrue(h.update(True, 4.6))                          # released and held again
        h2 = control.HoldTracker(hold=1.5)
        h2.update(True, 0.0)
        h2.update(False, 0.5)                                         # a short tap never fires
        self.assertFalse(h2.update(True, 1.0))

    def test_default_hold_is_three_seconds(self):
        self.assertEqual(control.HOLD_SECONDS, 3.0)
        h = control.HoldTracker()
        h.update(True, 0.0)
        self.assertFalse(h.update(True, 2.9))                         # almost 3 s: not yet
        self.assertTrue(h.update(True, 3.0))

    def test_watch_esc_only_acts_during_a_run(self):
        calls, clock = [], {"t": 0.0}
        steps = iter(range(40))
        def clk():
            clock["t"] += 0.5
            return clock["t"]
        def stop():
            return next(steps, 99) >= 30
        control.watch_esc(lambda: True, lambda: calls.append(1), stop=stop, pressed=lambda: True, clock=clk, interval=0)
        self.assertEqual(len(calls), 1)
        calls.clear(); steps = iter(range(40)); clock["t"] = 0.0
        control.watch_esc(lambda: False, lambda: calls.append(1), stop=stop, pressed=lambda: True, clock=clk, interval=0)
        self.assertEqual(calls, [])                                   # no run: holding Esc does nothing


class RunCancel(unittest.TestCase):
    def test_run_stops_in_the_middle_of_a_long_step_and_cleans_up(self):
        def long_step(context):
            time.sleep(120)                                            # would be a 2 minute take
        def never(context):
            raise AssertionError("must not run after a cancel")
        tests = [("one", lambda c: None), ("long", long_step), ("after", never)]
        with mock.patch("tester.cameras.choose_camera", lambda name=None: (None, "no camera in tests")), \
             mock.patch("tester.faults.reset_all") as reset, mock.patch("tester.monitor.Monitor"), \
             mock.patch("tester.share.make_copy", lambda d: None), mock.patch("tester.runner.REPORTS", __import__("tempfile").mkdtemp()):
            run = runner.Run("t", tests, "/x/Studio (macOS) - Test.app")
            run.start()
            for _ in range(40):
                if run.results[1]["status"] == "running":
                    break
                time.sleep(0.1)
            began = time.time()
            run.stop_requested = True
            control.cancel()
            run.thread.join(10)
        self.assertLess(time.time() - began, 5)
        self.assertEqual([r["status"] for r in run.results], ["passed", "skipped", "skipped"])
        self.assertIn("cancelled", run.results[1]["message"])
        reset.assert_called()                                          # faults, offline and camera label are put back
        self.assertIsNotNone(run.finished)
        self.assertFalse(control.is_paused())


if __name__ == "__main__":
    unittest.main()
