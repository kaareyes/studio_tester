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

from . import cameras

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


def should_reopen(was_running, alive, expected_gone, gone_for, grace=10):
    """The watchdog's decision: Studio was running during this run, is not any more, the run is not crashing it on purpose,
    and it has been gone long enough that a normal restart is not already under way."""
    return bool(was_running and not alive and not expected_gone and gone_for >= grace)


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
            self.console_path = os.path.join(self.run_dir, "studio_console.log")
            self.process = subprocess.Popen(["/usr/bin/script", "-q", self.console_path, self.binary()],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def log(self, text):
        self.lines.append(datetime.datetime.now().strftime("%H:%M:%S ") + text)

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        from . import faults, monitor
        context = Context(self.build_path, self.camera, self.run_dir, self.log, self.options)
        context.stop = lambda: self.stop_requested
        watcher = monitor.Monitor(self.run_dir)
        watcher.start()
        self.watchdog_stop = threading.Event()
        threading.Thread(target=self._watchdog, args=(context,), daemon=True).start()
        try:
            self._run_tests(context)
        finally:
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

    def _watchdog(self, context):
        """If Studio is closed or crashes while a test runs (and the test is not doing it on purpose), open it again by itself."""
        from . import ax
        from suites import recover
        was_running, gone_since = False, None
        while not self.watchdog_stop.wait(3):
            alive = ax.pid_of(PROCESS_PATTERN) is not None
            if alive:
                was_running, gone_since = True, None
                continue
            gone_since = gone_since or time.time()
            if should_reopen(was_running, alive, recover.EXPECTED["gone"], time.time() - gone_since):
                try:
                    context.log("WATCHDOG: Studio is closed: opening it again")
                    with open(os.path.join(self.run_dir, "incidents.txt"), "a") as handle:
                        handle.write(time.strftime("%H:%M:%S ") + "Studio was closed during the run: the tester opened it again\n")
                    context.app = None
                    context.launch()
                except Exception as error:
                    context.log(f"WATCHDOG: could not open Studio ({error})")
                gone_since = None

    def _run_tests(self, context):
        self.log(f"suite {self.suite_name}; build {self.build_path}; camera {self.camera['name'] if self.camera else 'none (' + self.camera_reason + ')'}")
        for index, (name, function) in enumerate(self.tests):
            result = self.results[index]
            if self.stop_requested:
                result.update(status="skipped", message="stopped by the tester")
                continue
            result["status"] = "running"
            began = time.time()
            try:
                function(context)
                result["status"] = "passed"
            except Skip as skip:
                result.update(status="skipped", message=str(skip))
            except Exception as error:
                result.update(status="failed", message=f"{type(error).__name__}: {error}")
                result["files"] = self._failure_bundle(context, index + 1, name)
                result["screenshot"] = next((f for f in result["files"] if f.endswith(".png")), None)
                context.log("FAIL " + name + ": " + result["message"])
                self.log("FAIL " + name + ": " + result["message"])
            result["seconds"] = round(time.time() - began, 1)

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
                "counts": counts, "results": self.results, "log": self.lines[-40:], "folder": os.path.basename(self.run_dir),
                "shared_zip": os.path.basename(self.shared_zip) if self.shared_zip else None,
                "options": self.options}

    def save(self):
        from . import report
        with open(os.path.join(self.run_dir, "results.json"), "w") as handle:
            json.dump(self.state(), handle, indent=2)
        report.write_html(self.state(), os.path.join(self.run_dir, "report.html"))
