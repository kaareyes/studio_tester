"""Runs a suite: one test after another, each with its own result. A failed test keeps a screenshot and the reason."""
import datetime
import glob
import json
import os
import sqlite3
import subprocess
import threading
import time
import traceback

from . import activity, awake, cameras, control

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
PROCESS_PATTERN = r"\.app/Contents/MacOS/Studio"
STUDIO_DB_GLOB = os.path.expanduser("~/Library/Application Support/Studio*/StudioApp.sqlite")


def studio_database_summary():
    """Row counts that explain most upload problems (read-only copy of the numbers; never changes the database)."""
    summary = {}
    for path in glob.glob(STUDIO_DB_GLOB):
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            def query(sql):
                try:
                    return connection.execute(sql).fetchone()[0]
                except Exception as error:   # an older database version may not have a column yet
                    return f"n/a ({error})"
            summary[os.path.basename(os.path.dirname(path))] = {
                "clips": query("select count(*) from ZDBMEDIA where ZISDELETED=0"),
                "clips_waiting_to_upload": query("select count(*) from ZDBMEDIA where ZISDELETED=0 and ZISUPLOADED=0"),
                "auditions_flagged_resume": query("select count(*) from ZDBAUDITION where ZRESUMEAUDITION=1"),
                "talent_rows": query("select count(*) from ZDBTALENT"),
                "clips_with_owner_list": query("select count(*) from ZDBMEDIA where ZTALENTSBACKUP is not null"),
            }
            connection.close()
        except Exception as error:
            summary[path] = {"error": str(error)}
    return summary


def kind_of(path):
    """'test' | 'develop' | 'staging' | 'production' from the app's name ('Studio (macOS) - Test.app')."""
    name = os.path.basename(path or "").lower()
    for kind in ("test", "develop", "staging"):
        if name.endswith(f"- {kind}.app"):
            return kind
    return "production"


def running_build():
    """Path of the .app of the Studio that is running now, or None."""
    from . import ax
    pid = ax.pid_of(PROCESS_PATTERN)
    if pid is None:
        return None
    command = subprocess.run(["/bin/ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return command.split(".app/")[0] + ".app" if ".app/" in command else None


def dismiss_crash_dialog():
    """macOS shows 'Problem Report for Studio ... quit unexpectedly' after a crash and it stays on top of the next steps. Its OK button is
    pressed (never Reopen: the tester opens Studio itself). Returns True when such a window was closed."""
    script = ('tell application "System Events"\n'
              ' if exists process "Problem Reporter" then\n'
              '  tell process "Problem Reporter"\n'
              '   repeat with w in windows\n'
              '    if (name of w) contains "Studio" then\n'
              '     click button "OK" of w\n'
              '     return "closed"\n'
              '    end if\n'
              '   end repeat\n'
              '  end tell\n'
              ' end if\n'
              'end tell\n'
              'return "none"')
    try:
        out = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=15).stdout.strip()
        return out == "closed"
    except Exception:
        return False


def should_reopen(was_running, alive, expected_gone, gone_for, grace=10):
    """The watchdog's decision: Studio was running during this run, is not any more, the run is not crashing it on purpose,
    and it has been gone long enough that a normal restart is not already under way."""
    return bool(was_running and not alive and not expected_gone and gone_for >= grace)


UiStep = control.UiStep      # a failure of a screen step: retried (a failed data check is a plain AssertionError and never is)


ESC_SELFCHECK_SUITES = ("day", "realistic", "network", "recovery", "chaos")      # suites that record: the Esc pause is tested once per run
HEARTBEAT_SECONDS = 60        # a look at the screen this often during a run
STUCK_IDLE_SECONDS = 5 * 60    # no log line AND an idle Studio for this long = hung
STUCK_SECONDS = 15 * 60       # no log line for this long = the step is stuck and is interrupted and retried
RETRIES = 3                                     # tries per step for a flaky screen
NO_RETRY_SUITES = ("recovery", "network", "chaos")      # these break Studio on purpose: a failure there is the result, not a flake


class Skip(Exception):
    """Raise inside a test that cannot run here (no camera, wrong build type): reported as skipped, not failed."""


class Context:
    """What a test gets: the Studio build, the camera, the app handle, and helpers."""

    def __init__(self, build_path, camera, run_dir, log, options=None):
        self.build_path = build_path
        self.options = options or {}       # from the test page: sessions, auditions, rounds, seed
        self.camera = camera
        self.run_dir = run_dir
        self._log = log
        self.app = None
        self.process = None
        self.console_path = None
        self.stop = lambda: False          # set by the Run: True once the tester pressed Stop (long suites check it between steps)

    def log(self, text):
        """Every line goes to the page, to run.log (with the time) and stays in the report."""
        self._log(text)
        with open(os.path.join(self.run_dir, "run.log"), "a") as handle:
            handle.write(datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + " " + text + "\n")

    def binary(self):
        name = os.path.splitext(os.path.basename(self.build_path.rstrip("/")))[0]
        return os.path.join(self.build_path, "Contents", "MacOS", name)

    def launch(self, wait=25):
        """Starts the chosen Studio build (if it is not running) and connects to it."""
        from . import ax
        pid = ax.pid_of(PROCESS_PATTERN)
        if pid is None:
            # `script` gives Studio a terminal, so its console is written line by line (a plain file would be buffered and the
            # last lines before a failure would be missing).
            # One file per start: a restarted Studio used to overwrite the log of the launch before it (the crash and the upload of the
            # recovered take were lost). The first launch keeps the old name.
            self.launches = getattr(self, "launches", 0) + 1
            self.console_path = os.path.join(self.run_dir, "studio_console.log" if self.launches == 1 else f"studio_console_{self.launches}.log")
            # `script` ends its session (and Studio with it) when its input closes: when the tester itself was started with no input
            # (a background job, a closed terminal) Studio died at once. A pipe that stays open keeps it alive. (Found live.)
            self.process = subprocess.Popen(["/usr/bin/script", "-q", self.console_path, self.binary()],
                                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log("started Studio: " + self.binary())
            deadline = time.time() + wait
            while pid is None and time.time() < deadline:
                time.sleep(1)
                pid = ax.pid_of(PROCESS_PATTERN)
            if pid is None:
                raise RuntimeError("Studio did not start")
            time.sleep(8)
        self.app = ax.App(pid)
        return self.app

    def require_camera(self):
        if self.camera is None:
            raise Skip("no camera can be used on this Mac right now")
        return self.camera

    def screenshot(self, name):
        path = os.path.join(self.run_dir, name + ".png")
        subprocess.run(["/usr/sbin/screencapture", "-x", path], capture_output=True)
        return path if os.path.exists(path) else None


def thread_stacks():
    """The Python stack of every thread except the caller (shows which line a hung step is waiting in)."""
    import sys, threading, traceback
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    for ident, frame in sys._current_frames().items():
        if ident == threading.get_ident():
            continue
        out.append(f"--- thread {names.get(ident, ident)}\n" + "".join(traceback.format_stack(frame, limit=8)))
    return "\n".join(out)[-3000:]


class Run:
    """One run of a suite. `state()` is what the page shows."""

    def __init__(self, suite_name, tests, build_path, camera_name=None, options=None):
        self.suite_name = suite_name
        self.options = options or {}
        # A suite can be a function of the page options (it decides how many tests there are).
        self.tests = tests(self.options) if callable(tests) else tests
        self.build_path = build_path
        self.camera, self.camera_reason = cameras.choose_camera(camera_name)
        self.started = datetime.datetime.now()
        self.run_dir = os.path.join(REPORTS, self.started.strftime("%Y-%m-%d_%H%M%S") + "_" + suite_name)
        os.makedirs(self.run_dir, exist_ok=True)
        self.results = [{"name": name, "status": "waiting", "seconds": 0, "message": "", "screenshot": None} for name, _ in self.tests]
        self.finished = None
        self.stop_requested = False
        self.lines = []
        self.thread = None
        self.shared_zip = None
        self.caffeinate = None
        self.current_step = ""
        self.last_activity = time.time()

    def log(self, text):
        self.lines.append(datetime.datetime.now().strftime("%H:%M:%S ") + text)
        self.last_activity = time.time()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        from . import faults, monitor
        context = Context(self.build_path, self.camera, self.run_dir, self.log, self.options)
        context.stop = lambda: self.stop_requested
        control.begin(threading.current_thread())          # pause / cancel apply to this thread only
        self.caffeinate = awake.start()                    # the Mac must not go to sleep during the run
        self.log("keeping the Mac awake (caffeinate)" if self.caffeinate else "could not keep the Mac awake: set Sleep to Never in System Settings")
        watcher = monitor.Monitor(self.run_dir)
        watcher.start()
        self.watchdog_stop = threading.Event()
        threading.Thread(target=self._watchdog, args=(context,), daemon=True).start()
        try:
            self._run_tests(context)
        finally:
            control.end()
            awake.stop(self.caffeinate)
            self.watchdog_stop.set()
            # Whatever happened (finished, failed or Stop): no faults, online, no camera label, so the app is left like a person uses it.
            watcher.stop()
            faults.reset_all()
            self.finished = datetime.datetime.now()
            self.save()
            try:
                from . import share
                self.shared_zip = share.make_copy(self.run_dir)       # a visible zip next to Studio Tester.command, ready to send
                if self.shared_zip:
                    self.log("report zip ready to share: " + self.shared_zip)
                    self.save()
            except Exception as error:
                self.log(f"could not make the shareable zip ({error})")

    def incident(self, context, text):
        """One line in incidents.txt (linked from the report) and in the log."""
        context.log("INCIDENT: " + text)
        with open(os.path.join(self.run_dir, "incidents.txt"), "a") as handle:
            handle.write(time.strftime("%H:%M:%S ") + text + "\n")

    def _watchdog(self, context):
        """Runs beside the tests. (1) Studio closed or crashed (and the test is not doing it on purpose): the crash report and the step
        that was running are saved, the running step is interrupted (it is retried), Studio is opened again. (2) Every HEARTBEAT seconds:
        a screenshot, a look for pop-ups, and a check that the step is still making progress (no log line for STUCK_SECONDS = stuck:
        the step is interrupted and retried instead of waiting forever)."""
        from . import ax
        from suites import recover
        was_running, gone_since, last_beat, alert_beats, logged_activity = False, None, 0.0, 0, ""
        while not self.watchdog_stop.wait(3):
            alive = ax.pid_of(PROCESS_PATTERN) is not None
            if alive:
                was_running, gone_since = True, None
                now_doing = activity.info()
                if now_doing["text"] and now_doing["seconds"] >= 6 and now_doing["text"] != logged_activity:
                    logged_activity = now_doing["text"]       # a wait that lasts is written to the live log, so the log says what is being waited for
                    self.log("... " + now_doing["text"])
                if time.time() - last_beat >= HEARTBEAT_SECONDS:
                    last_beat = time.time()
                    alert_beats = self._heartbeat(context, alert_beats)
                continue
            if gone_since is None and was_running and not recover.EXPECTED["gone"]:
                crashed_during = self.current_step or "(between steps)"
                self.incident(context, f"Studio is not running (crashed or closed). Step that was running: {crashed_during}")
                control.interrupt("Studio crashed or closed")      # the step does not keep waiting for something that can no longer happen
            gone_since = gone_since or time.time()
            if should_reopen(was_running, alive, recover.EXPECTED["gone"], time.time() - gone_since):
                try:
                    context.log("WATCHDOG: Studio is closed: opening it again")
                    context.app = None
                    context.launch()
                    if dismiss_crash_dialog():
                        context.log("WATCHDOG: closed the macOS 'Studio quit unexpectedly' window (OK)")
                    saved = recover.save_crash_reports(context, since=gone_since - 120)
                    self.incident(context, "Studio was opened again by the tester" + (f"; crash report(s) saved: {', '.join(saved)}" if saved
                                                                                   else "; no crash report was found (it can appear a minute later)"))
                    self._late_crash_reports = (gone_since - 120, saved)
                except Exception as error:
                    context.log(f"WATCHDOG: could not open Studio ({error})")
                gone_since = None

    def _heartbeat(self, context, alert_beats):
        """One look at the screen. Returns the number of beats in a row with a pop-up on screen."""
        folder = os.path.join(self.run_dir, "heartbeat")
        os.makedirs(folder, exist_ok=True)
        shot = os.path.join(folder, time.strftime("%H%M%S") + ".jpg")
        subprocess.run(["/usr/sbin/screencapture", "-x", "-t", "jpg", shot], capture_output=True)
        for old in sorted(glob.glob(os.path.join(folder, "*.jpg")))[:-60]:        # the last hour is kept
            try:
                os.remove(old)
            except OSError:
                pass
        if dismiss_crash_dialog():
            self.log("HEARTBEAT: closed the macOS 'Studio quit unexpectedly' window (OK)")
        quiet = time.time() - self.last_activity
        paused = control.is_paused()
        if not paused and self.current_step and quiet > STUCK_IDLE_SECONDS and quiet <= STUCK_SECONDS:
            try:
                from . import patience
                idle = patience.studio_is_idle()
            except Exception:
                idle = False
            if idle:                                   # nothing logged AND Studio does nothing at all (0% CPU): it is hung, no need to wait 15 minutes
                self.incident(context, f"HEARTBEAT: step '{self.current_step}' made no progress for {int(quiet // 60)} minutes and Studio is idle "
                                       f"(0% CPU): interrupting it to retry (screenshot heartbeat/{os.path.basename(shot)})")
                self.last_activity = time.time()
                self.log("HEARTBEAT: where the test code is stuck:\n" + thread_stacks())
                control.interrupt(f"Studio is idle and the step made no progress for {int(quiet // 60)} minutes")
                quiet = 0
        if not paused and quiet > STUCK_SECONDS and self.current_step:
            self.incident(context, f"HEARTBEAT: step '{self.current_step}' made no progress for {int(quiet // 60)} minutes: interrupting it "
                                   f"to retry (screenshot heartbeat/{os.path.basename(shot)})")
            self.last_activity = time.time()
            self.log("HEARTBEAT: where the test code is stuck:\n" + thread_stacks())
            control.interrupt(f"step made no progress for {int(quiet // 60)} minutes")
        try:
            app = context.app
            if app is not None and app.exists("alert.dialog"):
                alert_beats += 1
                title = app.text(app.find("alert.title")) if app.exists("alert.title") else "(no title)"
                self.log(f"HEARTBEAT: a pop-up is on screen: {title}")
                if alert_beats == 3:
                    self.incident(context, f"HEARTBEAT: the pop-up '{title}' has been on screen for 3 checks in a row (heartbeat/{os.path.basename(shot)})")
                return alert_beats
        except Exception:
            pass
        return 0

    def _run_tests(self, context):
        self.log(f"suite {self.suite_name}; build {self.build_path}; camera {self.camera['name'] if self.camera else 'none (' + self.camera_reason + ')'}")
        # Once per run, at a random step boundary (not the first or the last), the Esc pause is proven for real; see control.esc_selfcheck.
        import random as _random
        esc_index = _random.randrange(1, len(self.tests) - 1) if len(self.tests) >= 4 and self.suite_name in ESC_SELFCHECK_SUITES else None
        self._stop_recordings(context)
        for index, (name, function) in enumerate(self.tests):
            result = self.results[index]
            if self.stop_requested:
                result.update(status="skipped", message="stopped by the tester")
                continue
            if index == esc_index:
                self._esc_selfcheck(context)
            result["status"] = "running"
            activity.set(f"working on: {name}")
            self.current_step = name
            self.last_activity = time.time()
            began = time.time()
            try:
                self._run_with_retries(context, name, function)
                result["status"] = "passed"
            except control.StopRun:
                # cancelled by the person (Esc held, or Cancel testing): this step stops where it is, the rest are skipped, cleanup still runs
                result.update(status="skipped", message="cancelled by the tester")
                self.stop_requested = True
                self.log("CANCELLED by the tester during: " + name)
            except Skip as skip:
                result.update(status="skipped", message=str(skip))
            except Exception as error:
                result.update(status="failed", message=f"{type(error).__name__}: {error}")
                result["files"] = self._failure_bundle(context, index + 1, name)
                result["screenshot"] = next((f for f in result["files"] if f.endswith(".png")), None)
                context.log("FAIL " + name + ": " + result["message"])
                self.log("FAIL " + name + ": " + result["message"])
                try:
                    from . import faults as fault_tools
                    fault_tools.clear()               # a failed step must never leave its fault on for the next one (found live: server-down cascade)
                    fault_tools.offline(False)
                except Exception:
                    pass
            result["seconds"] = round(time.time() - began, 1)

    def _esc_selfcheck(self, context):
        """Esc pause test inside the run (between two steps). A failure is an incident in the report, never a crash of the run."""
        try:
            ok, sentence = control.esc_selfcheck()
        except control.StopRun:
            raise
        except Exception as error:
            ok, sentence = False, f"the Esc self-check could not run ({type(error).__name__}: {error})"
        if ok:
            context.log("ESC SELF-CHECK passed: " + sentence)          # run.log (the report) AND the page log
        else:
            self.incident(context, "ESC SELF-CHECK FAILED: " + sentence)
        try:                                                  # Studio back to the front for the next step
            if context.app is not None:
                context.app.activate()
        except Exception:
            pass

    def _run_with_retries(self, context, name, function):
        """Runs one step; when a SCREEN step fails (control not shown, step did nothing) it is made safe again and run once more, up to
        RETRIES tries. Data-check failures, skips and cancels pass straight through."""
        from . import ax
        tries = 1 if self.suite_name in NO_RETRY_SUITES else RETRIES
        for attempt in range(1, tries + 1):
            moved_before = ax.POINTER_MOVED
            try:
                return function(context)
            except (ax.ControlNotFound, UiStep) as error:
                if attempt == tries:
                    raise
                note = f"try {attempt} of {tries} failed ({type(error).__name__}: {error}); making the screen safe and trying again"
                if ax.POINTER_MOVED != moved_before:
                    note += f" [the mouse was moved by somebody {ax.POINTER_MOVED - moved_before} time(s) during this try]"
                context.log(note)
                self.log(note)
                self._make_screen_safe(context)

    def _stop_recordings(self, context):
        """Before the first test: a Studio that is already open and still recording (left by an earlier run) is stopped first."""
        try:
            from . import ax
            pid = ax.pid_of(PROCESS_PATTERN)
            if pid is None:
                return
            from suites import driver
            driver.stop_running_recordings(context.app or ax.App(pid), context.log)
        except control.StopRun:
            raise
        except Exception as error:
            context.log(f"(could not check for a recording that was left running: {error})")

    def _make_screen_safe(self, context):
        """Between tries: answer a pop-up the safe way, leave Audition Mode, go to the projects list. Never deletes anything."""
        try:
            dismiss_crash_dialog()
            from . import ax
            deadline = time.time() + 60
            while ax.pid_of(PROCESS_PATTERN) is None and time.time() < deadline:      # the watchdog is opening Studio again: let it
                time.sleep(2)
            if context.app is None or ax.pid_of(PROCESS_PATTERN) is None:
                context.app = None
                context.launch()
            from suites import driver, common
            app = context.app
            for _ in range(15):                                  # a freshly opened Studio needs a few seconds before it shows controls
                if len(app.names()) >= 3:
                    break
                time.sleep(2)
            try:
                driver.stop_running_recordings(app, context.log)
                driver.clear_leftovers(app, context.log)
            except Exception as error:
                context.log(f"(clear before retry: {error})")
            common.go_home(app)
        except control.StopRun:
            raise
        except Exception as error:
            context.log(f"(could not make the screen safe before the retry: {error})")
        time.sleep(2)

    def _failure_bundle(self, context, number, name):
        """Everything needed to debug a failure without running it again. Returns the file names (inside the run folder)."""
        prefix = f"fail_{number:02d}"
        files = []

        def write(suffix, text):
            with open(os.path.join(self.run_dir, prefix + suffix), "w") as handle:
                handle.write(text)
            files.append(prefix + suffix)

        shot = context.screenshot(prefix)
        if shot:
            files.append(os.path.basename(shot))
        write("_traceback.txt", traceback.format_exc())
        try:
            if context.app is not None:
                from . import ax
                write("_controls_on_screen.txt", "\n".join(context.app.names()) or "(no named controls on screen)")
        except Exception as error:
            write("_controls_on_screen.txt", f"could not read the screen: {error}")
        write("_database.json", json.dumps(studio_database_summary(), indent=2))
        console = context.console_path
        if console and os.path.exists(console):
            with open(console, "rb") as handle:
                tail = handle.read()[-60000:].decode("utf-8", "replace")
            write("_studio_console_tail.txt", tail)
        write("_context.txt", f"test: {name}\nbuild: {self.build_path}\ncamera: {self.camera['name'] if self.camera else 'none'}\n"
                              f"time: {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        return files

    def state(self):
        counts = {key: sum(1 for r in self.results if r["status"] == key) for key in ("passed", "failed", "skipped", "running", "waiting")}
        return {"suite": self.suite_name, "build": self.build_path, "camera": self.camera["name"] if self.camera else None,
                "camera_reason": self.camera_reason, "started": self.started.isoformat(timespec="seconds"),
                "finished": self.finished.isoformat(timespec="seconds") if self.finished else None,
                "counts": counts, "results": self.results, "log": self.lines[-120:], "folder": os.path.basename(self.run_dir),
                "shared_zip": os.path.basename(self.shared_zip) if self.shared_zip else None,
                "control": control.info() if not self.finished else {"paused": False, "reason": "", "paused_for": 0, "cancelling": False},
                "activity": activity.info() if not self.finished else {"text": "", "seconds": 0},
                "options": self.options}

    def save(self):
        from . import report
        with open(os.path.join(self.run_dir, "results.json"), "w") as handle:
            json.dump(self.state(), handle, indent=2)
        report.write_html(self.state(), os.path.join(self.run_dir, "report.html"))
