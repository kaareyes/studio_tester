import random
import unittest
from unittest import mock

from tester.ax import ControlNotFound
from suites import driver


class FakeApp:
    """A stand-in for the app: `screen` is the set of control names shown now; `on_press` changes it like the real app would."""

    def __init__(self, screen, on_press=None):
        self.screen, self.pressed, self.on_press = set(screen), [], on_press or {}

    def exists(self, name, within=None):
        return name in self.screen

    def find_all(self, identifier=None, prefix=None, within=None):
        return [n for n in self.screen if n == identifier or (prefix and n.startswith(prefix))]

    def press(self, name, within=None, timeout=15.0):
        if name not in self.screen:
            raise ControlNotFound(name)
        self.pressed.append(name)
        if name in self.on_press:
            self.on_press[name](self)

    def wait_for(self, name, timeout=15.0, within=None, gone=False):
        if (name in self.screen) != gone:
            return name
        raise ControlNotFound(name)

    def find(self, name):
        return name

    @staticmethod
    def enabled(_):
        return True


def ids(n):
    return ["%032x" % (i + 1) for i in range(n)]


class Driver(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(driver, "name_of", lambda e: e)
        patcher.start()
        self.addCleanup(patcher.stop)
        sleeper = mock.patch("time.sleep", lambda s: None)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_add_talents_and_enter_ready(self):
        a, b = ids(2)
        app = FakeApp({"session.talent.add." + a, "session.talent.add." + b},
                      {"session.talent.add." + a: lambda app: (app.screen.discard("session.talent.add." + a), app.screen.add("session.enterAuditionMode")),
                       "session.talent.add." + b: lambda app: (app.screen.discard("session.talent.add." + b), app.screen.add("session.enterAuditionMode"))})
        self.assertEqual(driver.add_talents(app, random.Random(1), 2, print), 2)
        self.assertEqual(len(app.pressed), 2)

    def test_add_talents_never_ready_is_a_failure(self):
        a = ids(1)[0]
        app = FakeApp({"session.talent.add." + a})
        with mock.patch.object(driver, "wait_enter_ready", lambda *_a, **_k: False):
            with self.assertRaises(driver.StepFailed):
                driver.add_talents(app, random.Random(1), 1, print)

    def test_finalize_answers_the_confirmation_and_returns(self):
        def finalize(app):
            app.screen.add("alert.dialog"); app.screen.add("alert.rightButton")

        def confirm(app):
            for n in ("alert.dialog", "alert.rightButton", "capture.finalize", "capture.record"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": finalize, "alert.rightButton": confirm})
        seconds = driver.finalize(app, print, timeout=5)
        self.assertEqual(app.pressed, ["capture.finalize", "alert.rightButton"])
        self.assertGreaterEqual(seconds, 0)

    def test_finalize_that_never_returns_fails(self):
        app = FakeApp({"capture.finalize", "capture.record"})
        with mock.patch("time.time", side_effect=[0, 0, 0, 1000, 1000, 1000, 1000]):
            with self.assertRaises(driver.StepFailed):
                driver.finalize(app, print, timeout=10)

    def test_clear_leftovers_closes_popup_leaves_capture_and_clears_group(self):
        def back(app):
            app.screen.discard("capture.record"); app.screen.add("session.tab.scheduled")
        app = FakeApp({"alert.dialog", "alert.leftButton", "capture.record", "session.clearGroup"},
                      {"alert.leftButton": lambda app: app.screen.discard("alert.dialog"), "capture.back": back,
                       "session.clearGroup": lambda app: app.screen.discard("session.clearGroup")})
        app.screen.add("capture.back")
        driver.clear_leftovers(app, print)
        self.assertIn("alert.leftButton", app.pressed)
        self.assertIn("capture.back", app.pressed)
        self.assertIn("session.clearGroup", app.pressed)

    def test_wait_label_reads_the_event_log(self):
        lines = ["x", "camera label T-007 -> photo", "camera label T-008 -> video"]
        with mock.patch.object(driver.faults, "events", lambda n=200: lines):
            self.assertEqual(driver.wait_label("video", 0, timeout=1), "T-008")
            self.assertEqual(driver.wait_label("photo", 2, timeout=0.1), None)


if __name__ == "__main__":
    unittest.main()


class Guards(unittest.TestCase):
    def test_kill_refuses_a_non_test_build(self):
        from suites import recover
        with mock.patch.object(recover.ax, "pid_of", lambda pattern: 4242), \
             mock.patch.object(recover, "command_of", lambda pid: "/Applications/Studio (macOS).app/Contents/MacOS/Studio (macOS)"), \
             mock.patch.object(recover.os, "kill") as kill:
            with self.assertRaises(RuntimeError):
                recover.kill_app()
            kill.assert_not_called()

    def test_kill_allows_the_test_build(self):
        from suites import recover
        with mock.patch.object(recover.ax, "pid_of", lambda pattern: 4242), \
             mock.patch.object(recover, "command_of", lambda pid: "/x/Studio (macOS) - Test.app/Contents/MacOS/Studio (macOS) - Test"), \
             mock.patch.object(recover.os, "kill") as kill, mock.patch("time.sleep", lambda s: None):
            recover.kill_app()
            kill.assert_called_once()

    def test_bad_picked_json_does_not_crash_the_build(self):
        from suites import realistic
        pairs, problems = realistic._sessions({"picked": "{broken"})
        self.assertEqual(pairs, [])
        self.assertTrue(problems)
