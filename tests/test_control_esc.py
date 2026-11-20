import unittest

from tester import control


class EscSelfCheck(unittest.TestCase):
    def run_check(self, pauses, already_paused=False):
        events, state = [], {"paused": already_paused, "resumed": 0, "t": 0.0}
        def clock():
            return state["t"]
        def sleep(seconds):
            state["t"] += seconds
            if pauses and any(e is True for e in events) and state["t"] >= 3.7:
                state["paused"] = True
        def resume_fn():
            state["paused"] = False
            state["resumed"] += 1
        result = control.esc_selfcheck(post=lambda down: events.append(down), front=lambda name: events.append(("front", name)),
                                       paused=lambda: state["paused"], resume_fn=resume_fn, sleep=sleep, clock=clock)
        return result, events, state

    def test_passes_when_the_run_pauses_and_then_continues(self):
        (ok, text), events, state = self.run_check(pauses=True)
        self.assertTrue(ok)
        self.assertIn("paused the run by itself", text)
        self.assertEqual(state["resumed"], 1)
        self.assertEqual(events[0], ("front", "Finder"))
        self.assertIs(events[-1], False)                      # the key is always released

    def test_fails_with_the_permission_hint_when_nothing_pauses(self):
        (ok, text), events, state = self.run_check(pauses=False)
        self.assertFalse(ok)
        self.assertIn("Input Monitoring", text)
        self.assertEqual(state["resumed"], 0)
        self.assertIs(events[-1], False)

    def test_skipped_when_already_paused(self):
        (ok, text), events, state = self.run_check(pauses=True, already_paused=True)
        self.assertFalse(ok)
        self.assertIn("already paused", text)
        self.assertEqual(events, [])

    def test_the_key_is_released_even_if_bringing_an_app_to_front_fails(self):
        events = []
        def boom(name):
            raise RuntimeError("no System Events")
        with self.assertRaises(RuntimeError):
            control.esc_selfcheck(post=lambda down: events.append(down), front=boom, paused=lambda: False, resume_fn=lambda: None, sleep=lambda s: None)
        self.assertEqual(events, [False])


if __name__ == "__main__":
    unittest.main()


class StuckEsc(unittest.TestCase):
    def test_release_sends_a_key_up_only_when_esc_is_down(self):
        from unittest import mock
        import Quartz
        posted = []
        with mock.patch.object(Quartz, "CGEventSourceKeyState", return_value=True), mock.patch.object(Quartz, "CGEventPost", lambda tap, event: posted.append(event)), \
                mock.patch.object(Quartz, "CGEventCreateKeyboardEvent", lambda src, code, down: ("key", code, down)):
            self.assertTrue(control.release_stuck_esc())
        self.assertEqual(posted, [("key", 53, False)])
        posted.clear()
        with mock.patch.object(Quartz, "CGEventSourceKeyState", return_value=False), mock.patch.object(Quartz, "CGEventPost", lambda tap, event: posted.append(event)):
            self.assertFalse(control.release_stuck_esc())
        self.assertEqual(posted, [])
