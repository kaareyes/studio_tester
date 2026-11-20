import re
import unittest

from tester import activity


class ActivityText(unittest.TestCase):
    def setUp(self):
        activity.clear()

    def test_the_same_text_does_not_restart_the_clock(self):
        activity.set("waiting for X")
        first = activity._state["since"]
        activity.set("waiting for X")
        self.assertEqual(activity._state["since"], first)
        activity.set("waiting for Y")
        self.assertGreaterEqual(activity._state["since"], first)

    def test_info_gives_text_and_seconds_and_clear_empties_it(self):
        activity.set("recording a take (60 s)")
        info = activity.info(now=activity._state["since"] + 42)
        self.assertEqual(info, {"text": "recording a take (60 s)", "seconds": 42})
        activity.clear()
        self.assertEqual(activity.info(), {"text": "", "seconds": 0})


class PageShowsIt(unittest.TestCase):
    def test_the_page_has_an_activity_line_and_an_open_live_log(self):
        from tester import page
        self.assertIn('id="activity"', page.PAGE)
        self.assertIn("Live log", page.PAGE)
        self.assertNotIn('<details id="logBox"', page.PAGE)           # no longer a closed box
        self.assertIn("s.activity", page.PAGE)

    def test_the_page_script_declares_no_name_twice(self):
        from tester import page
        script = re.search(r"<script>(.*?)</script>", page.PAGE, re.S).group(1)
        body = script[script.index("function render") if "function render" in script else 0:]
        self.assertEqual(len(re.findall(r"\bconst act=", body)), 1)


class StateCarriesIt(unittest.TestCase):
    def test_run_state_has_the_activity_and_more_log_lines(self):
        import inspect
        from tester import runner
        source = inspect.getsource(runner.Run.state)
        self.assertIn('"activity"', source)
        self.assertIn("self.lines[-120:]", source)


if __name__ == "__main__":
    unittest.main()
