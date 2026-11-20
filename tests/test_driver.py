import json
import random
import unittest
from unittest import mock

from tester.ax import ControlNotFound
from suites import driver


class FakeApp:
    """A stand-in for the app: `screen` is the set of control names shown now; `on_press` changes it like the real app would;
    `texts` is what a control shows (for example the pop-up's title)."""

    def __init__(self, screen, on_press=None, texts=None):
        self.screen, self.pressed, self.on_press, self.texts = set(screen), [], on_press or {}, texts or {}

    def text(self, element):
        return self.texts.get(element, "")

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
            app.screen.add("alert.dialog"); app.screen.add("alert.button.proceed"); app.screen.add("alert.button.cancel")

        def confirm(app):
            for n in ("alert.dialog", "alert.button.proceed", "capture.finalize", "capture.record"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": finalize, "alert.button.proceed": confirm})
        seconds = driver.finalize(app, print, timeout=5)
        self.assertEqual(app.pressed, ["capture.finalize", "alert.button.proceed"])
        self.assertGreaterEqual(seconds, 0)

    def test_finalize_that_never_returns_fails(self):
        app = FakeApp({"capture.finalize", "capture.record"})
        with mock.patch("time.time", side_effect=[0, 0, 0, 1000, 1000, 1000, 1000]):
            with self.assertRaises(driver.StepFailed):
                driver.finalize(app, print, timeout=10)

    def test_stop_running_recordings_stops_a_take_and_a_slate_before_the_run(self):
        def stopped(app):
            app.screen.discard("capture.stop")
        app = FakeApp({"capture.stop"}, {"capture.stop": stopped})
        self.assertEqual(driver.stop_running_recordings(app, print), 1)
        sid = ids(1)[0]
        slate = "session.talent.slate." + sid
        app2 = FakeApp({slate, "mediaSide.slateTimer"}, {slate: lambda a: a.texts.update({"mediaSide.slateTimer": "00:00"})}, {"mediaSide.slateTimer": "04:32"})
        driver.SLATE_RECORDING["id"] = sid
        self.assertEqual(driver.stop_running_recordings(app2, print), 1)
        self.assertEqual(app2.pressed, [slate])
        app3 = FakeApp({slate, "mediaSide.slateTimer"}, {}, {"mediaSide.slateTimer": "00:05"})       # a timer that keeps its last time after the stop
        driver.SLATE_RECORDING["id"] = sid
        driver.stop_running_recordings(app3, print)
        self.assertEqual(app3.pressed, [slate])                                          # pressed once, never toggled again into a new slate
        self.assertEqual(driver.stop_running_recordings(FakeApp({"session.tab.scheduled"}), print), 0)   # nothing recording: nothing pressed

    def test_clear_leftovers_stops_a_slate_that_was_left_recording(self):
        sid = ids(1)[0]
        slate = "session.talent.slate." + sid
        def stop(app):
            app.texts["mediaSide.slateTimer"] = "00:00"
        app = FakeApp({slate, "mediaSide.slateTimer", "mediaSide.selectedTalentName", "session.tab.scheduled"}, {slate: stop},
                      {"mediaSide.slateTimer": "04:32", "mediaSide.selectedTalentName": "Ada Fernandez"})
        with mock.patch.object(driver, "talent_name", lambda a, i: "Ada Fernandez"):
            driver.SLATE_RECORDING["id"] = None
            driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed, [slate])                                           # stopped once, the slate is saved

    def test_clear_leftovers_never_presses_the_x_nor_clear_group(self):
        def back(app):
            app.screen.discard("capture.record"); app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.record", "capture.back", "session.clearGroup", "session.talent.cardName." + ids(1)[0]}, {"capture.back": back})
        driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed, ["capture.back"])                                  # Back only: the group is kept
        self.assertNotIn("session.clearGroup", app.pressed)                              # it deletes saved slates and photos

    def test_the_resume_popup_gets_proceed_never_the_x_and_the_resumed_audition_is_finalized(self):
        def proceed(app):
            for n in ("alert.dialog", "alert.okButton", "alert.closeButton", "alert.title"):
                app.screen.discard(n)
            app.screen.update({"capture.record", "capture.finalize", "capture.back"})
        def finalize(app):
            for n in ("capture.record", "capture.finalize", "capture.back"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"alert.dialog", "alert.title", "alert.okButton", "alert.closeButton", "session.tab.scheduled"},
                      {"alert.okButton": proceed, "capture.finalize": finalize}, texts={"alert.title": "Resume Audition"})
        driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed[0], "alert.okButton")
        self.assertNotIn("alert.closeButton", app.pressed)                               # the X abandons (deletes) the interrupted audition
        self.assertIn("capture.finalize", app.pressed)                                   # its takes are kept and uploaded
        self.assertNotIn("capture.back", app.pressed)

    def test_a_resume_browse_popup_is_left_alone_and_the_run_stops(self):
        app = FakeApp({"alert.dialog", "alert.title", "alert.okButton", "alert.closeButton"}, texts={"alert.title": "Resume Browse Audition"})
        with self.assertRaises(driver.StepFailed) as raised:
            driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed, [])                                                # nothing was pressed
        self.assertIn("Browse", str(raised.exception))

    def test_an_unknown_yes_no_popup_is_cancelled_never_confirmed(self):
        def cancel(app):
            for n in ("alert.dialog", "alert.button.cancel", "alert.button.proceed", "alert.closeButton", "alert.title"):
                app.screen.discard(n)
        app = FakeApp({"alert.dialog", "alert.title", "alert.button.cancel", "alert.button.proceed", "alert.closeButton", "session.tab.scheduled"},
                      {"alert.button.cancel": cancel}, texts={"alert.title": "Delete Audition?"})
        driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed, ["alert.button.cancel"])                              # Cancel; not Yes, not the X

    def test_a_recording_is_stopped_before_going_back(self):
        def stop(app):
            app.screen.discard("capture.stop")
        def back(app):
            app.screen.discard("capture.record"); app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.record", "capture.stop", "capture.back"}, {"capture.stop": stop, "capture.back": back})
        driver.clear_leftovers(app, print)
        self.assertEqual(app.pressed, ["capture.stop", "capture.back"])                  # the take is saved first

    def test_audition_mode_that_will_not_close_stops_the_run(self):
        app = FakeApp({"capture.record", "capture.back"})
        with self.assertRaises(driver.StepFailed):
            driver.clear_leftovers(app, print)

    def test_finalize_proceeds_only_on_the_finalize_popup(self):
        def popup(app):
            app.screen.update({"alert.dialog", "alert.title", "alert.button.proceed", "alert.button.cancel"})
        def proceed(app):
            for n in ("alert.dialog", "alert.title", "alert.button.proceed", "alert.button.cancel", "capture.record", "capture.finalize"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": popup, "alert.button.proceed": proceed}, texts={"alert.title": "Finalize Audition"})
        driver.finalize(app, print, timeout=5)
        self.assertEqual(app.pressed, ["capture.finalize", "alert.button.proceed"])

    def test_finalize_cancels_an_unexpected_yes_no_popup_and_fails(self):
        def popup(app):
            app.screen.update({"alert.dialog", "alert.title", "alert.button.proceed", "alert.button.cancel"})
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": popup}, texts={"alert.title": "Delete everything?"})
        with self.assertRaises(driver.StepFailed) as raised:
            driver.finalize(app, print, timeout=5)
        self.assertNotIn("alert.button.proceed", app.pressed)                               # never confirmed by accident
        self.assertIn("alert.button.cancel", app.pressed)
        self.assertIn("Delete everything?", str(raised.exception))

    def test_finalize_with_an_unreadable_title_is_still_the_confirmation_we_just_caused(self):
        def popup(app):
            app.screen.update({"alert.dialog", "alert.button.proceed", "alert.button.cancel"})            # no alert.title text at all
        def proceed(app):
            for n in ("alert.dialog", "alert.button.proceed", "alert.button.cancel", "capture.record", "capture.finalize"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": popup, "alert.button.proceed": proceed})
        driver.finalize(app, print, timeout=5)
        self.assertEqual(app.pressed, ["capture.finalize", "alert.button.proceed"])

    def test_finalize_acknowledges_a_plain_warning_and_goes_on(self):
        def warn(app):
            app.screen.update({"alert.dialog", "alert.title", "alert.okButton"})
        def ok(app):
            for n in ("alert.dialog", "alert.title", "alert.okButton", "capture.record", "capture.finalize"):
                app.screen.discard(n)
            app.screen.add("session.tab.scheduled")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": warn, "alert.okButton": ok}, texts={"alert.title": "Warning"})
        driver.finalize(app, print, timeout=5)                                           # does not hang for 90 s on the warning
        self.assertEqual(app.pressed, ["capture.finalize", "alert.okButton"])

    def test_record_that_does_nothing_is_reported_with_the_reason(self):
        app = FakeApp({"capture.record", "capture.finalize"})
        with mock.patch.object(driver, "recording_started", lambda a, timeout=8: False), mock.patch.object(driver, "_event_count", lambda: 0):
            with self.assertRaises(driver.StepFailed) as raised:
                driver.record_take(app, 1, print)
        self.assertIn("Record did nothing", str(raised.exception))

    def test_record_selects_a_talent_when_none_is_selected_then_records(self):
        tid = ids(1)[0]
        app = FakeApp({"capture.record", "capture.finalize", "capture.talent.select." + tid})
        started = iter([False, True])
        with mock.patch.object(driver, "recording_started", lambda a, timeout=8: next(started)), mock.patch.object(driver, "_event_count", lambda: 0), \
             mock.patch.object(driver, "wait_label", lambda *a, **k: "T-001"):
            app.screen.add("capture.stop")
            label = driver.record_take(app, 0, print)
        self.assertEqual(label, "T-001")
        self.assertEqual(app.pressed[:3], ["capture.record", "capture.talent.select." + tid, "capture.record"])

    def test_photo_and_slate_are_skipped_when_they_cannot_be_done(self):
        sid = ids(1)[0]
        self.assertFalse(driver.can_take_photo(FakeApp({"session.talent.photoDone." + sid}), sid))         # already has a photo
        self.assertTrue(driver.can_take_photo(FakeApp(set()), sid))
        self.assertFalse(driver.can_record_slate(FakeApp(set()), sid))                                      # stitched project: no slate control
        self.assertTrue(driver.can_record_slate(FakeApp({"session.talent.slate." + sid}), sid))

    def test_the_take_control_is_pressed_once_as_a_favorite_heart(self):
        app = FakeApp({"capture.take.rating.0"})
        app.frame = lambda element: (10, 20, 24, 24)
        with mock.patch.object(driver.ax, "click") as click, mock.patch("time.sleep", lambda s: None):
            self.assertTrue(driver.favorite_first_take(app))
        click.assert_called_once_with(22, 32)
        self.assertFalse(driver.favorite_first_take(FakeApp(set())))

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


class FinalizeAppearsLate(unittest.TestCase):
    """Found in the first live run: Finalize is redrawn a moment after a take saved; the tester must wait for it, not fail at once."""

    def run_take(self, shows_after):
        import time
        from unittest import mock
        started = time.time()

        class App(FakeApp):
            def wait_for(self, name, timeout=10, within=None, gone=False):
                end = time.time() + timeout
                while time.time() < end:
                    if time.time() - started >= shows_after:
                        return name
                    time.sleep(0.05)
                raise ControlNotFound(name)

        app = App({"capture.record", "capture.stop"})
        with mock.patch.object(driver, "_event_count", return_value=0), mock.patch.object(driver, "recording_started", return_value=True), \
                mock.patch.object(driver, "wait_label", return_value="T-001"):
            return driver.record_take(app, 0, lambda m: None)

    def test_waits_for_finalize(self):
        self.assertEqual(self.run_take(0.3), "T-001")

    def test_fails_when_finalize_never_comes(self):
        from unittest import mock
        import time
        with mock.patch.object(driver, "ControlNotFound", ControlNotFound):
            class App(FakeApp):
                def wait_for(self, name, timeout=10, within=None, gone=False):
                    raise ControlNotFound(name)
            app = App({"capture.record", "capture.stop"})
            with mock.patch.object(driver, "_event_count", return_value=0), mock.patch.object(driver, "recording_started", return_value=True), \
                    mock.patch.object(driver, "wait_label", return_value="T-001"):
                with self.assertRaises(driver.StepFailed):
                    driver.record_take(app, 0, lambda m: None)


class RetryOfFlakySteps(unittest.TestCase):
    """The user's rule: an automation retries a flaky screen step, but never retries a data-check failure."""

    def make_run(self, suite="realistic"):
        from unittest import mock
        from tester import runner
        run = runner.Run.__new__(runner.Run)
        run.suite_name, run.lines = suite, []
        run.log = lambda text: run.lines.append(text)
        run._make_screen_safe = lambda context: run.lines.append("made safe")
        class Context:
            log = staticmethod(lambda text: None)
        return run, Context()

    def test_screen_step_is_retried_until_it_works(self):
        run, context = self.make_run()
        calls = []
        def step(c):
            calls.append(1)
            if len(calls) < 3:
                raise ControlNotFound("capture.finalize")
        run._run_with_retries(context, "x", step)
        self.assertEqual(len(calls), 3)
        self.assertEqual(run.lines.count("made safe"), 2)

    def test_gives_up_after_three_tries(self):
        run, context = self.make_run()
        calls = []
        def step(c):
            calls.append(1)
            raise driver.StepFailed("nope")
        with self.assertRaises(driver.StepFailed):
            run._run_with_retries(context, "x", step)
        self.assertEqual(len(calls), 3)

    def test_a_data_check_failure_is_never_retried(self):
        run, context = self.make_run()
        calls = []
        def step(c):
            calls.append(1)
            raise AssertionError("1 take is missing on disk")
        with self.assertRaises(AssertionError):
            run._run_with_retries(context, "x", step)
        self.assertEqual(len(calls), 1)

    def test_chaos_recovery_network_are_not_retried(self):
        for suite in ("chaos", "recovery", "network"):
            run, context = self.make_run(suite)
            calls = []
            def step(c):
                calls.append(1)
                raise ControlNotFound("x")
            with self.assertRaises(ControlNotFound):
                run._run_with_retries(context, "x", step)
            self.assertEqual(len(calls), 1)


class PointerMovedByAPerson(unittest.TestCase):
    def test_click_puts_the_pointer_back_and_counts_it(self):
        from unittest import mock
        from tester import ax
        before = ax.POINTER_MOVED
        answers = iter([False, False, True])
        with mock.patch.object(ax.Quartz, "CGEventPost"), mock.patch.object(ax, "pointer_is_at", lambda x, y: next(answers)), \
                mock.patch.object(ax.time, "sleep"), mock.patch.object(ax.control, "checkpoint"):
            ax.click(10, 10)
        self.assertEqual(ax.POINTER_MOVED - before, 2)


class SettleStall(unittest.TestCase):
    def test_a_stuck_queue_fails_instead_of_waiting_an_hour(self):
        from unittest import mock
        from suites import realistic
        item = {"uploaded": False, "deleted": False}
        clock = {"now": 1000.0}
        def fake_time():
            return clock["now"]
        def fake_sleep(seconds):
            clock["now"] += 300
        class Context:
            app = None
            log = staticmethod(lambda text: None)
        with mock.patch.object(realistic.faults, "offline"), mock.patch.object(realistic.oracle, "pending_since", return_value=[item]), mock.patch.object(realistic, "relaunch_to_unstick", return_value=True), mock.patch.object(realistic.time, "time", fake_time), \
                mock.patch.object(realistic.time, "sleep", fake_sleep):
            with self.assertRaises(AssertionError) as caught:
                realistic.settle_test({}, {"pk": 0, "expected": {}})(Context())
        self.assertIn("stuck", str(caught.exception))
        self.assertIn("RESUMED", str(caught.exception))


class EscWatcherSurvives(unittest.TestCase):
    def test_a_failing_pause_does_not_end_the_watcher(self):
        from tester import control
        calls, state = [], {"n": 0}
        def on_hold():
            calls.append(1)
            raise RuntimeError("browser failed")
        steps = [(True, 0.0), (True, 4.0), (False, 5.0), (True, 6.0), (True, 10.0)]
        pressed_values, clocks = iter(p for p, _ in steps), iter(c for _, c in steps)
        remaining = {"n": len(steps)}
        def stop():
            remaining["n"] -= 1
            return remaining["n"] < 0
        control.watch_esc(lambda: True, on_hold, stop=stop, pressed=lambda: next(pressed_values), clock=lambda: next(clocks), interval=0)
        self.assertGreaterEqual(len(calls), 2)          # fired again after the first failure


class WatchdogInterrupts(unittest.TestCase):
    def test_interrupt_stops_the_running_step_once(self):
        import threading
        from tester import control
        errors = []
        def body():
            control.begin(threading.current_thread())
            try:
                control.interrupt("Studio crashed or closed")
                try:
                    control.checkpoint()
                except control.StepInterrupted as error:
                    errors.append(str(error))
                control.checkpoint()                 # the retry starts clean: no second interruption
                errors.append("clean")
            finally:
                control.end()
        thread = threading.Thread(target=body)
        thread.start(); thread.join()
        self.assertEqual(errors, ["Studio crashed or closed", "clean"])

    def test_interruption_is_retried_like_a_screen_failure(self):
        from tester import control
        self.assertTrue(issubclass(control.StepInterrupted, control.UiStep))
        run, context = RetryOfFlakySteps().make_run()
        calls = []
        def step(c):
            calls.append(1)
            if len(calls) == 1:
                raise control.StepInterrupted("Studio crashed or closed")
        run._run_with_retries(context, "x", step)
        self.assertEqual(len(calls), 2)


class UploadStartCheck(unittest.TestCase):
    def setUp(self):
        from suites import realistic
        self.realistic = realistic

    relaunch_result = False

    def run_check(self, waiting_sequence, queue, alive=True, timeout=60):
        from unittest import mock
        import time as real_time
        clock = {"now": 0.0}
        sequence = iter(waiting_sequence)
        last = {"value": waiting_sequence[-1]}
        def waiting(pk):
            try:
                last["value"] = next(sequence)
            except StopIteration:
                pass
            return [{"folder": "x"}] * last["value"]
        class Context:
            app = object()
            log = staticmethod(lambda t: None)
        with mock.patch.object(self.realistic, "not_uploaded_since", waiting), mock.patch.object(self.realistic, "queue_counts", lambda c: queue), mock.patch.object(self.realistic, "relaunch_to_unstick", lambda c, pk: self.relaunch_result), \
                mock.patch("tester.ax.pid_of", lambda pattern: 1 if alive else None), mock.patch.object(self.realistic.time, "time", lambda: clock["now"]), \
                mock.patch.object(self.realistic.time, "sleep", lambda s: clock.update(now=clock["now"] + s)):
            return self.realistic.verify_upload_started(Context(), 0, timeout=timeout)

    def test_started_when_the_database_shows_an_upload(self):
        self.assertIn("uploaded", self.run_check([4, 3], {"pending": 0, "completed": 1, "all": 1}))

    def test_started_when_the_queue_shows_pending(self):
        self.assertIn("pending", self.run_check([4, 4, 4], {"pending": 3, "completed": 1, "all": 4}))

    def test_never_started_is_a_finding_with_evidence(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_check([4], {"pending": 0, "completed": 37, "all": 37})
        self.assertIn("did not start", str(caught.exception))
        self.assertIn("Queue", str(caught.exception))
        self.assertIn("did NOT resume", str(caught.exception))

    def test_a_stall_that_a_relaunch_fixes_says_so(self):
        self.relaunch_result = True
        with self.assertRaises(AssertionError) as caught:
            self.run_check([4], {"pending": 0, "completed": 37, "all": 37})
        self.assertIn("RESUMED after Studio was closed", str(caught.exception))

    def test_a_crashed_studio_is_a_screen_failure_that_is_retried(self):
        from tester import control
        with self.assertRaises(control.UiStep):
            self.run_check([4], {"pending": 0, "completed": 1, "all": 1}, alive=False)

    def test_nothing_waiting_needs_no_check(self):
        self.assertIn("nothing", self.run_check([0], None))


class PopupPartsFromRoleAndPosition(unittest.TestCase):
    """Found live: SwiftUI names every part of a pop-up `alert.dialog`, so title, message and buttons are told apart by role and place."""

    def app_with(self, parts):
        from unittest import mock
        from tester import ax
        app = object.__new__(ax.App)
        roles = {id(p): p for p in parts}
        def attr(element, name):
            return {"AXRole": element["role"], "AXIdentifier": "alert.dialog"}.get(name)
        app.text = lambda e: e["text"]
        app.frame = lambda e: (e["x"], 0, 10, 10)
        original = ax.App.find_all
        def find_all(self, identifier=None, prefix=None, within=None):
            if identifier == "alert.dialog":
                return list(parts)
            return original(self, identifier=identifier, prefix=prefix, within=within) if False else []
        return app, mock.patch.object(ax, "_attr", attr), mock.patch.object(ax.App, "find_all", find_all)

    def parts(self, buttons):
        items = [{"role": "AXButton", "text": "Close", "x": 900}, {"role": "AXImage", "text": "alertWarning", "x": 400},
                 {"role": "AXStaticText", "text": "Resume Audition", "x": 400}, {"role": "AXStaticText", "text": "The app was interrupted", "x": 400}]
        return items + [{"role": "AXButton", "text": t, "x": x} for t, x in buttons]

    def test_one_button_is_ok_and_the_x_is_close(self):
        parts = self.parts([("Proceed", 500)])
        app, a, b = self.app_with(parts)
        with a, b:
            self.assertEqual(app._alert_part("alert.title")[0]["text"], "Resume Audition")
            self.assertEqual(app._alert_part("alert.message")[0]["text"], "The app was interrupted")
            self.assertEqual(app._alert_part("alert.okButton")[0]["text"], "Proceed")
            self.assertEqual(app._alert_part("alert.closeButton")[0]["text"], "Close")
            self.assertEqual(app._alert_part("alert.button.cancel"), [])

    def test_two_buttons_are_left_and_right(self):
        parts = self.parts([("Cancel", 300), ("Proceed", 600)])
        app, a, b = self.app_with(parts)
        with a, b:
            self.assertEqual(app._alert_part("alert.button.cancel")[0]["text"], "Cancel")
            self.assertEqual(app._alert_part("alert.button.proceed")[0]["text"], "Proceed")
            self.assertEqual(app._alert_part("alert.okButton"), [])


class LeftoverAuditionWithTakesIsFinalized(unittest.TestCase):
    def test_takes_are_finalized_not_left_behind_by_back(self):
        state = {"in_capture": True}
        def finalize_pressed(app):
            app.screen.discard("capture.finalize")
            app.screen.discard("capture.record")
            app.screen.discard("capture.back")
            app.screen.add("session.title")
            state["in_capture"] = False
        app = FakeApp({"capture.record", "capture.finalize", "capture.back", "capture.take.card.0"}, {"capture.finalize": finalize_pressed})
        from unittest import mock
        with mock.patch.object(driver, "finalize", lambda a, log, timeout=90: a.press("capture.finalize")), mock.patch.object(driver.time, "sleep", lambda s: None):
            driver.RESUMED["pending"] = False
            driver.clear_leftovers(app, lambda t: None)
        self.assertIn("capture.finalize", app.pressed)
        self.assertNotIn("capture.back", app.pressed)

    def test_no_takes_means_back(self):
        def back(app):
            app.screen.discard("capture.record"); app.screen.discard("capture.finalize"); app.screen.discard("capture.back"); app.screen.add("session.title")
        app = FakeApp({"capture.record", "capture.finalize", "capture.back"}, {"capture.back": back})
        from unittest import mock
        with mock.patch.object(driver.time, "sleep", lambda s: None):
            driver.RESUMED["pending"] = False
            driver.clear_leftovers(app, lambda t: None)
        self.assertEqual(app.pressed, ["capture.back"])


class SharedZipHasNoHeartbeatScreens(unittest.TestCase):
    def test_heartbeat_folder_is_left_out(self):
        import tempfile, zipfile, os
        from tester import share
        with tempfile.TemporaryDirectory() as folder:
            run = os.path.join(folder, "run1")
            os.makedirs(os.path.join(run, "heartbeat"))
            for name in ("report.html", "heartbeat/010101.jpg"):
                open(os.path.join(run, name), "w").write("x")
            path = share.make_copy(run, os.path.join(folder, "out"))
            names = zipfile.ZipFile(path).namelist()
        self.assertEqual(names, ["run1/report.html"])


class ProcessListIsRobust(unittest.TestCase):
    def test_a_continuation_line_does_not_crash_the_lookup(self):
        from unittest import mock
        from tester import ax
        out = "123 /Applications/Studio (macOS) - Test.app/Contents/MacOS/Studio (macOS) - Test\n    TARGET_PATH = 'x'\n"
        class Done:
            stdout = out
        with mock.patch.object(ax.subprocess, "run", lambda *a, **k: Done()):
            self.assertEqual([p for p, _ in ax._studio_processes("Studio")], [123])


class OfflineFinalizeEndsOnTheSessionsList(unittest.TestCase):
    def test_sessions_list_counts_as_done(self):
        def pressed(app):
            app.screen.discard("capture.finalize"); app.screen.discard("capture.record"); app.screen.add("projects.search")
        app = FakeApp({"capture.finalize", "capture.record"}, {"capture.finalize": pressed})
        from unittest import mock
        with mock.patch.object(driver.time, "sleep", lambda s: None):
            seconds = driver.finalize(app, lambda t: None, timeout=5)
        self.assertIsInstance(seconds, float)


class ButtonsAreChosenByTheirWords(unittest.TestCase):
    """Found live: in the Finalize pop-up Proceed is the LEFT button and Cancel the right one, so left/right can never decide."""

    def test_button_by_words_from_the_parts(self):
        from unittest import mock
        from tester import ax
        parts = [{"role": "AXButton", "text": "Close", "x": 900}, {"role": "AXStaticText", "text": "Finalize Audition", "x": 1},
                 {"role": "AXButton", "text": "Proceed", "x": 100}, {"role": "AXButton", "text": "Cancel", "x": 300}]
        app = object.__new__(ax.App)
        app.text = lambda e: e["text"]
        app.frame = lambda e: (e["x"], 0, 1, 1)
        with mock.patch.object(ax, "_attr", lambda e, n: {"AXRole": e["role"]}.get(n)), \
                mock.patch.object(ax.App, "find_all", lambda self, identifier=None, prefix=None, within=None: list(parts) if identifier == "alert.dialog" else []):
            self.assertEqual(app._alert_part("alert.button.proceed")[0]["x"], 100)
            self.assertEqual(app._alert_part("alert.button.cancel")[0]["x"], 300)
            self.assertEqual(app._alert_part("alert.button.delete"), [])

    def test_alert_button_picks_the_first_known_word(self):
        app = FakeApp({"alert.button.cancel", "alert.button.proceed"})
        self.assertEqual(driver.alert_button(app, driver.CANCEL_WORDS), "alert.button.cancel")
        self.assertEqual(driver.alert_button(app, driver.CONFIRM_WORDS), "alert.button.proceed")
        self.assertIsNone(driver.alert_button(FakeApp({"alert.button.delete"}), driver.CONFIRM_WORDS))


class LongTakeIsNotSilent(unittest.TestCase):
    def test_a_long_take_logs_progress_every_minute(self):
        from unittest import mock
        clock = {"now": 0.0}
        logs = []
        def fake_sleep(seconds):
            clock["now"] += seconds
        class App(FakeApp):
            pass
        app = App({"capture.record", "capture.stop", "capture.finalize"})
        with mock.patch.object(driver, "_event_count", return_value=0), mock.patch.object(driver, "recording_started", return_value=True), \
                mock.patch.object(driver, "wait_label", return_value="T-001"), mock.patch.object(driver.time, "time", lambda: clock["now"]), \
                mock.patch.object(driver.time, "sleep", fake_sleep), mock.patch.object(app, "wait_for", create=True, side_effect=lambda *a, **k: "x"):
            driver.record_take(app, 600, logs.append)
        self.assertGreaterEqual(len([l for l in logs if l.startswith("recording:")]), 8)


class CutShortAttemptsStillCountTheirTakes(unittest.TestCase):
    def test_takes_saved_by_an_interrupted_attempt_are_expected(self):
        from unittest import mock
        from suites import realistic
        state = {"rnd": __import__("random").Random(1), "pk": 0, "expected": {"takes": 0, "photos": 0, "slates": 0}}
        class Context:
            log = staticmethod(lambda t: None)
        rows = [{"pk": 1, "deleted": False, "folder": "/x/STUDIO APP/p/s/Audition 1/Audition/1A/Final/Scene 1.mp4", "uploaded": False, "audition": "a"},
                {"pk": 2, "deleted": False, "folder": "/x/STUDIO APP/p/s/Audition 1/Audition/1A/Final/Scene 2.mp4", "uploaded": False, "audition": "a"}]
        from tester import control
        function = realistic.audition_test(({"name": "P"}, {"id": "s" * 32, "name": "S"}), 1, {"mode": "online"}, state)
        with mock.patch.object(realistic.recover, "ensure_ready", lambda c, session=None: object()), mock.patch.object(realistic.faults, "offline"), \
                mock.patch.object(realistic.oracle, "last_media_pk", lambda: 0), mock.patch.object(realistic.oracle, "media_since", lambda pk, path=None: rows), \
                mock.patch.object(realistic.driver, "random_audition", side_effect=control.StepInterrupted("crash")), mock.patch("time.sleep", lambda s: None):
            with self.assertRaises(control.StepInterrupted):
                function(Context())
        self.assertEqual(state["expected"]["takes"], 2)


class AuditionDayTemplate(unittest.TestCase):
    """The default template: a real casting day in one run."""

    def build(self, seed, extra="3"):
        from suites import day
        from unittest import mock
        data = {"projects": [{"id": "p", "name": "QA", "sessions": [{"id": "s" * 32, "name": "S", "talents": [{"id": "t", "name": "A"}], "talents_read": True}]}]}
        with mock.patch("tester.catalog.load", return_value=data):
            return [n for n, _ in day.build({"picked": json.dumps(["s" * 32]), "seed": str(seed), "extra": extra})]

    def test_it_has_every_part_of_the_day(self):
        names = " | ".join(self.build(1))
        for part in ("Normal audition", "Internet drops in the middle of a take", "Long audition", "no internet at all",
                     "Internet is back: offline recordings sync", "Final check"):
            self.assertIn(part, names)

    def test_the_normal_audition_is_first_and_a_reconnect_follows_the_offline_one(self):
        names = self.build(7)
        self.assertIn("Normal audition", names[1])
        offline = next(i for i, n in enumerate(names) if "no internet at all" in n)
        self.assertIn("Internet is back", names[offline + 1])

    def test_the_same_seed_gives_the_same_day_and_another_seed_can_differ(self):
        self.assertEqual(self.build(5), self.build(5))
        self.assertTrue(any(self.build(5) != self.build(seed) for seed in range(6, 30)))

    def test_extra_random_auditions_follow_the_option(self):
        self.assertEqual(len([n for n in self.build(3, "5") if "Random audition" in n]), 5)
        self.assertEqual(len([n for n in self.build(3, "0") if "Random audition" in n]), 0)

    def test_the_page_and_the_suite_list_know_it(self):
        from suites import SUITES, RECORDING
        from tester import page
        self.assertIn("day", SUITES)
        self.assertIn("day", RECORDING)
        self.assertIn("active='day'", page.PAGE)


class PendingIgnoresNextAuditionsPlaceholder(unittest.TestCase):
    def test_a_lone_group_image_does_not_count_as_waiting(self):
        from unittest import mock
        from tester import oracle
        rows = [{"pk": 1, "audition": "a", "uploaded": True, "deleted": False, "folder": "/x/STUDIO APP/p/s/Audition 1/Audition/1A/Final/Scene 1.mp4"},
                {"pk": 2, "audition": "a", "uploaded": False, "deleted": False, "folder": "/x/STUDIO APP/p/s/Audition 1/Audition/1A/Final/Scene 2.mp4"},
                {"pk": 3, "audition": "b", "uploaded": False, "deleted": False, "folder": "/x/STUDIO APP/p/s/Audition 2/primaryImage/GroupImage.jpg"}]
        with mock.patch.object(oracle, "media_since", lambda pk, path=None: rows):
            self.assertEqual([i["pk"] for i in oracle.pending_since(0)], [2])
            self.assertEqual([p for p in oracle.check(0, uploaded=True, check_files=False) if "not uploaded" in p].__len__(), 1)


class DroppedInternetUploadIsChecked(unittest.TestCase):
    def test_an_audition_hit_by_a_drop_must_upload_by_itself_afterwards(self):
        from unittest import mock
        from suites import realistic
        import random as _random
        clock = {"now": 0.0}
        state = {"rnd": _random.Random(1), "pk": 0, "expected": {"takes": 0, "photos": 0, "slates": 0}}
        class Context:
            log = staticmethod(lambda t: None)
        done = {"talents": 1, "takes": 2, "photos": 0, "slates": 0, "labels": [], "seconds_finalize": 1, "extras": []}
        function = realistic.audition_test(({"name": "P"}, {"id": "s" * 32, "name": "S"}), 1, {}, state, plan={"mode": "online", "flaky": True})
        item = {"folder": "x", "uploaded": False}
        with mock.patch.object(realistic.recover, "ensure_ready", lambda c, session=None: object()), mock.patch.object(realistic.faults, "offline"), \
                mock.patch.object(realistic.oracle, "last_media_pk", lambda: 0), mock.patch.object(realistic.oracle, "check", lambda *a, **k: []), \
                mock.patch.object(realistic.driver, "random_audition", lambda *a, **k: done), mock.patch.object(realistic, "verify_upload_started", lambda *a, **k: "ok"), \
                mock.patch.object(realistic, "not_uploaded_since", lambda pk: [item]), mock.patch.object(realistic, "queue_counts", lambda c: {"pending": 0}), \
                mock.patch.object(realistic, "relaunch_to_unstick", lambda c, pk: True), mock.patch.object(realistic.time, "time", lambda: clock["now"]), \
                mock.patch.object(realistic.time, "sleep", lambda s: clock.update(now=clock["now"] + max(s, 1))):
            with self.assertRaises(AssertionError) as caught:
                function(Context())
        self.assertIn("were not retried", str(caught.exception))
        self.assertIn("uploaded after Studio was closed", str(caught.exception))


class RelaunchIsNotACrash(unittest.TestCase):
    def test_the_watchdog_is_told_the_quit_is_on_purpose(self):
        from unittest import mock
        from suites import realistic, recover
        seen = []
        class Context:
            build_path = "/Applications/Studio (macOS) - Test.app"
            app = object()
            log = staticmethod(lambda t: None)
            @staticmethod
            def launch():
                seen.append(recover.EXPECTED["gone"])
        with mock.patch.object(realistic.subprocess, "run"), mock.patch("tester.ax.pid_of", lambda pattern: None), \
                mock.patch.object(realistic, "not_uploaded_since", lambda pk: []), mock.patch.object(realistic.time, "sleep", lambda s: None):
            self.assertTrue(realistic.relaunch_to_unstick(Context, 0))
        self.assertEqual(seen, [True])                           # expected while Studio is being closed and opened
        self.assertFalse(recover.EXPECTED["gone"])               # and back to normal afterwards


class CleanQuit(unittest.TestCase):
    def test_cmd_q_first_then_terminate_only_that_pid(self):
        from unittest import mock
        from suites import realistic
        calls = []
        pids = iter([77, 77, 77, 77, 77, 77, 77, 77, 77, 77, 77, None, None])
        clock = {"now": 0.0}
        with mock.patch("tester.ax.pid_of", lambda pattern: next(pids, None)), mock.patch.object(realistic.subprocess, "run", lambda *a, **k: calls.append(a[0][0])), \
                mock.patch.object(realistic.os, "kill", lambda pid, sig: calls.append((pid, sig))), mock.patch.object(realistic.time, "time", lambda: clock["now"]), \
                mock.patch.object(realistic.time, "sleep", lambda s: clock.update(now=clock["now"] + 10)):
            realistic.quit_studio(patience=15)
        self.assertEqual(calls[0], "/usr/bin/osascript")        # Cmd-Q through System Events
        self.assertIn((77, 15), calls)                           # still running: that one pid is asked to terminate


class StudioIsStartedWithAnOpenInput(unittest.TestCase):
    def test_launch_keeps_an_input_pipe_open_for_script(self):
        import tempfile
        from unittest import mock
        from tester import runner
        seen = {}
        class Fake:
            pass
        def popen(args, **kwargs):
            seen.update(kwargs)
            return Fake()
        context = runner.Context("/Applications/Studio (macOS) - Test.app", None, tempfile.mkdtemp(), lambda t: None)
        with mock.patch.object(runner.subprocess, "Popen", popen), mock.patch("tester.ax.pid_of", side_effect=[None, 5, 5]), \
                mock.patch("tester.ax.App", lambda pid: object()), mock.patch.object(runner.time, "sleep", lambda s: None):
            context.launch(wait=2)
        self.assertEqual(seen.get("stdin"), runner.subprocess.PIPE)


class FailedStepClearsItsFaults(unittest.TestCase):
    def test_a_failed_step_removes_faults_and_offline(self):
        from unittest import mock
        from tester import runner
        run = runner.Run.__new__(runner.Run)
        run.suite_name, run.lines, run.stop_requested = "network", [], False
        run.results = [{"name": "x", "status": "waiting", "seconds": 0, "message": "", "screenshot": None}]
        run.tests = [("x", lambda c: (_ for _ in ()).throw(AssertionError("boom")))]
        run.log = lambda t: None
        run._failure_bundle = lambda c, i, n: []
        run.build_path, run.camera, run.camera_reason = "/x", None, ""
        calls = []
        class Context:
            log = staticmethod(lambda t: None)
        from tester import faults
        with mock.patch.object(faults, "clear", lambda: calls.append("clear")), mock.patch.object(faults, "offline", lambda on: calls.append(("offline", on))):
            run._run_tests(Context())
        self.assertIn("clear", calls)
        self.assertIn(("offline", False), calls)


class SharedUploadWait(unittest.TestCase):
    def test_returns_none_when_everything_uploads_and_a_note_when_a_relaunch_was_needed(self):
        from unittest import mock
        from suites import realistic
        clock = {"now": 0.0}
        class Context:
            log = staticmethod(lambda t: None)
        def run(pending, relaunch):
            seq = iter(pending)
            last = {"v": pending[-1]}
            def fake_pending(pk, path=None):
                try:
                    last["v"] = next(seq)
                except StopIteration:
                    pass
                return [{"x": 1}] * last["v"]
            with mock.patch.object(realistic.oracle, "pending_since", fake_pending), mock.patch.object(realistic, "relaunch_to_unstick", lambda c, pk: relaunch), \
                    mock.patch.object(realistic.time, "time", lambda: clock["now"]), mock.patch.object(realistic.time, "sleep", lambda s: clock.update(now=clock["now"] + 100)):
                return realistic.wait_for_uploads(Context(), 0, limit=3000, stall=300)
        self.assertIsNone(run([3, 2, 0], False))
        self.assertIn("uploaded after Studio was closed", run([3, 3, 3, 3, 3, 3, 3, 0], True))
        clock["now"] = 0.0
        self.assertIn("did NOT upload", run([3] * 40, False))


class StudioMustBeOnTopBeforeAClick(unittest.TestCase):
    def app(self):
        from tester import ax
        app = object.__new__(ax.App)
        app.pid = 10
        app.activate = lambda: self.activated.append(1)
        return app

    def test_raises_studio_when_another_window_covers_it(self):
        from unittest import mock
        from tester import ax
        self.activated = []
        answers = iter([(99, "Code"), (10, "Studio")])
        with mock.patch.object(ax, "window_owner_at", lambda x, y: next(answers)), mock.patch.object(ax.time, "sleep", lambda s: None):
            self.app().make_sure_studio_is_on_top(5, 5)
        self.assertEqual(len(self.activated), 1)

    def test_never_clicks_into_another_app(self):
        from unittest import mock
        from tester import ax
        self.activated = []
        with mock.patch.object(ax, "window_owner_at", lambda x, y: (99, "Code")), mock.patch.object(ax.time, "sleep", lambda s: None):
            with self.assertRaises(ControlNotFound) as caught:
                self.app().make_sure_studio_is_on_top(5, 5)
        self.assertIn("Code", str(caught.exception))


class NativeSheetIsAnsweredSafely(unittest.TestCase):
    """Found live: pressing Back during a take shows a native macOS sheet 'Stop Recording?'; it blocks every click and has no app names."""

    class Sheet:
        def __init__(self, title, buttons):
            self.title, self.buttons, self.pressed = title, buttons, []
        def native_sheet(self):
            return {"title": self.title, "message": "", "buttons": [(b, b) for b in self.buttons]} if self.buttons else None
        def press_element(self, element):
            self.pressed.append(element)
            self.buttons = []

    def test_stop_recording_gets_stop_and_save_never_keep_recording(self):
        from unittest import mock
        app = self.Sheet("Stop Recording?", ["Stop & Save", "Keep Recording"])
        with mock.patch.object(driver.time, "sleep", lambda s: None):
            self.assertTrue(driver.answer_native_sheet(app, lambda t: None))
        self.assertEqual(app.pressed, ["Stop & Save"])

    def test_no_sheet_means_nothing_to_do(self):
        self.assertFalse(driver.answer_native_sheet(self.Sheet("x", []), lambda t: None))

    def test_an_unknown_sheet_without_a_safe_button_is_left_alone(self):
        app = self.Sheet("Delete everything?", ["Delete", "Wipe"])
        with self.assertRaises(driver.StepFailed):
            driver.answer_native_sheet(app, lambda t: None)
        self.assertEqual(app.pressed, [])

    def test_an_unknown_sheet_gets_cancel(self):
        from unittest import mock
        app = self.Sheet("Quit?", ["Quit", "Cancel"])
        with mock.patch.object(driver.time, "sleep", lambda s: None):
            driver.answer_native_sheet(app, lambda t: None)
        self.assertEqual(app.pressed, ["Cancel"])


class ScrollIntoViewBeforeClicking(unittest.TestCase):
    def test_a_row_below_the_window_is_scrolled_to_before_the_click(self):
        from unittest import mock
        from tester import ax
        app = object.__new__(ax.App)
        app.activate = lambda: None
        window = (100.0, 100.0, 1000.0, 800.0)
        position = {"y": 1500.0}                                   # far below the window bottom (900)
        app.frame = lambda e: (300.0, position["y"], 50.0, 30.0)
        app.window_frame = lambda: window
        scrolls = []
        def fake_scroll(dx, dy, x, y):
            scrolls.append(dy)
            position["y"] -= 400
        with mock.patch.object(ax, "scroll", fake_scroll), mock.patch.object(ax.time, "sleep", lambda s: None):
            app.scroll_into_view(object())
        self.assertGreaterEqual(len(scrolls), 2)
        self.assertTrue(all(d > 0 for d in scrolls))               # towards the end of the list
        self.assertLess(position["y"], 900)

    def test_a_visible_row_is_not_scrolled(self):
        from unittest import mock
        from tester import ax
        app = object.__new__(ax.App)
        app.frame = lambda e: (300.0, 400.0, 50.0, 30.0)
        app.window_frame = lambda: (100.0, 100.0, 1000.0, 800.0)
        with mock.patch.object(ax, "scroll", lambda *a: self.fail("scrolled")):
            app.scroll_into_view(object())


class UnstoppableRecordingClosesStudio(unittest.TestCase):
    def test_after_four_stop_presses_that_do_nothing_studio_is_closed(self):
        from unittest import mock
        from tester import control
        from suites import realistic
        app = FakeApp({"capture.stop", "capture.recordingTimer", "capture.record"})        # Stop never changes anything
        closed = []
        with mock.patch.object(realistic, "quit_studio", lambda patience=25, pid=None: closed.append(patience)), mock.patch.object(driver.time, "sleep", lambda s: None):
            driver.RESUMED["pending"] = False
            with self.assertRaises(control.StepInterrupted):
                driver.clear_leftovers(app, lambda t: None)
        self.assertEqual(app.pressed.count("capture.stop"), 4)
        self.assertEqual(closed, [10])


class BuggyPresetsAreSwitchedOff(unittest.TestCase):
    def test_chaos_presets_are_off_and_the_good_ones_are_not(self):
        from tester import page
        text = page.PAGE
        start = text.index("const PRESETS={")
        block = text[start:text.index("function drawPresets", start)]
        self.assertEqual(block.count("Not ready yet"), 2)                          # Break it and Overnight
        self.assertIn("function preset(k){if(PRESETS[k][5])return;", text)          # clicking an off preset does nothing
        for good in ("day:[", "quick:[", "normal:["):
            self.assertIn(good, block)
        self.assertIn("active='day'", text)


class MergedGroupScenesAreNotWaiting(unittest.TestCase):
    """Studio uploads only the stitched merge video of a group audition; the individual group scenes stay isUploaded=0 on purpose."""

    def make(self, with_merge):
        import os, tempfile
        root = tempfile.mkdtemp()
        base = os.path.join(root, "STUDIO APP", "Proj", "Sess", "929d34f6-ce77")
        os.makedirs(os.path.join(base, "Audition", "15A15B", "Final"))
        if with_merge:
            os.makedirs(os.path.join(base, "GroupMerge-AAAA"))
        item = {"pk": 1, "audition": "929D34F6-CE77", "uploaded": False, "deleted": False, "audition_type": "group", "group_type": "audition",
                "filetype": "video", "name_tag": "Video 1", "folder": "file://" + os.path.join(base, "Audition", "15A15B", "Final", "Scene%201.mp4").replace(" ", "%20")}
        return item

    def test_scene_of_a_merged_group_is_not_pending(self):
        from tester import oracle
        item = self.make(True)
        self.assertTrue(oracle.is_merged_group_scene(item))

    def test_scene_without_a_merge_folder_is_still_pending(self):
        from tester import oracle
        self.assertFalse(oracle.is_merged_group_scene(self.make(False)))

    def test_individual_takes_are_never_exempt(self):
        from tester import oracle
        item = self.make(True)
        item.update(audition_type="individual", group_type="audition")
        self.assertFalse(oracle.is_merged_group_scene(item))

    def test_pending_since_skips_merged_scenes_but_not_other_clips(self):
        from unittest import mock
        from tester import oracle
        scene = self.make(True)
        scene["folder"] = scene["folder"].replace("Scene%201", "Scene%201")
        slate = dict(scene, pk=2, audition_type="individual", group_type="slate", filetype="video", name_tag="Slate 1",
                     folder=scene["folder"].replace("/Audition/15A15B/Final/", "/ImageAndSlate/15A/Final/"))
        with mock.patch.object(oracle, "media_since", lambda pk, path=None: [scene, slate]):
            self.assertEqual([i["pk"] for i in oracle.pending_since(0)], [2])


class WaitsAnswerTheResumePopup(unittest.TestCase):
    def test_popup_is_answered_safely_and_counts_as_progress(self):
        from unittest import mock
        from suites import realistic
        app = FakeApp({"alert.dialog"})
        calls = []
        class Context:
            log = staticmethod(lambda t: None)
        Context.app = app
        with mock.patch.object(realistic.driver, "clear_leftovers", lambda a, log: calls.append("cleared")):
            self.assertTrue(realistic.answer_resume_if_open(Context))
        self.assertEqual(calls, ["cleared"])

    def test_nothing_open_means_nothing_done(self):
        from unittest import mock
        from suites import realistic
        class Context:
            app = FakeApp({"session.title"})
            log = staticmethod(lambda t: None)
        with mock.patch.object(realistic.driver, "clear_leftovers", lambda a, log: self.fail("touched the screen")):
            self.assertFalse(realistic.answer_resume_if_open(Context))


class RecoveryOnlyOption(unittest.TestCase):
    def test_only_runs_the_chosen_scenarios(self):
        from unittest import mock
        from suites import recovery
        data = {"projects": [{"id": "p", "name": "QA", "sessions": [{"id": "s" * 32, "name": "S", "talents": [{"id": "t", "name": "A"}], "talents_read": True}]}]}
        with mock.patch("tester.catalog.load", return_value=data):
            names = [n for n, _ in recovery.build({"picked": json.dumps(["s" * 32]), "only": "PT-01, pt-03"})]
            every = [n for n, _ in recovery.build({"picked": json.dumps(["s" * 32])})]
        self.assertEqual([n.split(" ")[0] for n in names], ["Prepare:", "PT-01", "PT-03"])
        self.assertGreater(len(every), len(names))


class RecoveryStartsCleanAfterAFailure(unittest.TestCase):
    def test_flag_logic_is_wired(self):
        import inspect
        from suites import recovery
        source = inspect.getsource(recovery._crash_scenario)
        self.assertIn('state.get("ran_before")', source)
        self.assertIn("realistic.quit_studio", source)
        self.assertIn('state["last_failed"] = bool(problems)', source)


class NormalPresetHasNoVeryLongTakes(unittest.TestCase):
    def test_normal_uses_a_mix_without_25_to_50_minute_takes(self):
        from tester import page
        text = page.PAGE
        start = text.index("normal:[")
        block = text[start:text.index("chaos:[", start)]
        self.assertIn("mix:'60/40/0'", block)
        self.assertIn("if($('mix'))$('mix').value=v.mix||'';", text)


class UnverifiedSuitesAreSwitchedOff(unittest.TestCase):
    def test_server_refuses_them_unless_a_developer_asks(self):
        from unittest import mock
        from tester import server
        with mock.patch.dict(server.chosen, {"path": "/Applications/Studio (macOS) - Test.app"}), mock.patch.object(server, "support_problem", lambda p: None), \
                mock.patch.object(server.runner, "kind_of", lambda p: "test"):
            for suite in server.NOT_VERIFIED_SUITES:
                self.assertIn("not been verified", server.suite_problem(suite) or "")
                self.assertIsNone(server.suite_problem(suite, {"unverified": "yes"}))
            self.assertIsNone(server.suite_problem("day"))
            self.assertIsNone(server.suite_problem("realistic"))

    def test_the_page_disables_them(self):
        from tester import page
        self.assertIn("const NOT_READY=['chaos','offline_load','long_video','soak','friday']", page.PAGE)
        self.assertIn("disabled>", page.PAGE)


class CaptureLabelsCarryTheTalentName(unittest.TestCase):
    def test_name_is_read_cleaned_and_shortened(self):
        class App:
            def find(self, identifier):
                if identifier == "session.talent.abc":
                    return "card"
                raise ControlNotFound(identifier)
            def text(self, element):
                return "Mika \"Cole\" O'Neil-Smith the third of her name\nRole 2"
        name = driver.talent_name(App(), "abc")
        self.assertLessEqual(len(name), 18)
        self.assertNotIn('"', name)
        self.assertTrue(name.startswith("Mika"))

    def test_unreadable_name_gives_no_label_change(self):
        class App:
            def find(self, identifier):
                raise ControlNotFound(identifier)
        self.assertEqual(driver.talent_name(App(), "abc"), "")
        self.assertEqual(driver.named_label("P", ""), "")
        self.assertEqual(driver.named_label("P", "Mika Cole"), "P-# Mika Cole")

    def test_a_photo_label_is_set_then_the_base_label_comes_back(self):
        from unittest import mock
        from tester import faults
        calls = []
        class App(FakeApp):
            pass
        app = App({"session.talent.photo.abc"})
        with mock.patch.object(driver, "talent_name", lambda a, i: "Mika Cole"), mock.patch.object(driver, "_event_count", return_value=0), \
                mock.patch.object(driver, "wait_label", return_value="P-001"), mock.patch.object(faults, "temporary_label", lambda t: calls.append(("set", t))), \
                mock.patch.object(faults, "restore_label", lambda: calls.append(("restore",))):
            self.assertEqual(driver.take_photo(app, "abc", lambda t: None), "P-001")
        self.assertEqual(calls, [("set", "P-# Mika Cole"), ("restore",)])


class SaveWaitScalesWithTheTake(unittest.TestCase):
    def test_a_59_second_take_gets_well_over_the_80_seconds_it_needed(self):
        self.assertGreater(driver.save_wait_seconds(59), 150)
        self.assertGreater(driver.save_wait_seconds(37), 120)

    def test_long_takes_get_more_but_it_is_capped(self):
        self.assertGreater(driver.save_wait_seconds(1500), driver.save_wait_seconds(60))
        self.assertEqual(driver.save_wait_seconds(10 ** 6), 3600)
