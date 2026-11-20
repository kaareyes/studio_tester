import unittest
from unittest import mock

from tester import ax, patience


class PressWaitsForEnabled(unittest.TestCase):
    def _app(self, enabled_after):
        app = ax.App.__new__(ax.App)
        state = {"n": 0}

        def enabled(_element):
            state["n"] += 1
            return state["n"] > enabled_after
        app.wait_for = lambda *a, **k: object()
        app.enabled = enabled
        app.scroll_into_view = lambda e: None
        app.stable_frame = lambda e: None
        return app

    def test_a_control_that_is_enabled_a_moment_later_is_pressed(self):
        app = self._app(enabled_after=3)
        with mock.patch.object(ax, "AXUIElementPerformAction", return_value=0) as press, mock.patch.object(ax.time, "sleep"):
            app.press("nav.projects")
        press.assert_called_once()

    def test_a_control_that_stays_disabled_fails_after_the_wait(self):
        app = self._app(enabled_after=10**9)
        with mock.patch.object(patience, "for_studio", return_value=mock.Mock(expired=mock.Mock(side_effect=[False, False, True]))), \
                mock.patch.object(ax.time, "sleep"):
            with self.assertRaises(ax.ControlNotFound):
                app.press("nav.projects")


if __name__ == "__main__":
    unittest.main()
