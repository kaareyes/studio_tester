"""Getting the app back to a known state, and keeping evidence when it crashed or hung. Used by every stress suite, so a QA who
knows nothing about the app never has to fix a stuck screen by hand."""
import glob
import os
import shutil
import signal
import subprocess
import time

from tester import ax, runner
from tester.ax import ControlNotFound
from tester.runner import Skip
from . import common, driver

CRASH_DIRS = [os.path.expanduser("~/Library/Logs/DiagnosticReports")]


def app_alive():
    return ax.pid_of(runner.PROCESS_PATTERN) is not None


def command_of(pid):
    return subprocess.run(["/bin/ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def is_test_build(pid):
    """Only the Test build may be crashed or driven by the stress suites: the production app can hold real, not yet uploaded takes."""
    return pid is not None and "Test.app/Contents/MacOS/" in command_of(pid)


def kill_app(hard=True):
    """The same as a crash: the app is gone at once, nothing is saved on the way out. Refuses anything but the Test build."""
    pid = ax.pid_of(runner.PROCESS_PATTERN)
    if pid and not is_test_build(pid):
        raise RuntimeError("the running Studio is not the Test build: the tester will not kill it (quit it yourself, then start the Test build)")
    if pid:
        os.kill(pid, signal.SIGKILL if hard else signal.SIGTERM)
        time.sleep(2)
    return pid


def save_crash_reports(context, since):
    """Copies Studio crash reports newer than `since` (epoch seconds) into the run folder. Returns their names."""
    saved = []
    for folder in CRASH_DIRS:
        for path in glob.glob(os.path.join(folder, "Studio*")):
            if os.path.getmtime(path) >= since:
                shutil.copy(path, context.run_dir)
                saved.append(os.path.basename(path))
    return saved


def incident(context, text):
    """One line in incidents.txt (the report links it) and in the log."""
    context.log("INCIDENT: " + text)
    with open(os.path.join(context.run_dir, "incidents.txt"), "a") as handle:
        handle.write(time.strftime("%H:%M:%S ") + text + "\n")


def sample_hang(context, name="hang"):
    """Saves a `sample` of the Studio process (what it was doing) when it stops answering."""
    pid = ax.pid_of(runner.PROCESS_PATTERN)
    if pid:
        subprocess.run(["/usr/bin/sample", str(pid), "5", "-file", os.path.join(context.run_dir, name + "_sample.txt")], capture_output=True, timeout=30)


def ensure_ready(context, session=None):
    """Makes sure Studio runs, is signed in, and shows the projects list (or the given session). Relaunches after a crash.
    `session` is (id, name). Returns the app. Raises Skip when only a person can fix it (login)."""
    started = time.time()
    if not app_alive():
        incident(context, "Studio was not running (crashed or closed): starting it again")
        context.app = None
        crashes = save_crash_reports(context, since=started - 600)
        if crashes:
            incident(context, "crash report(s) saved: " + ", ".join(crashes))
    running = ax.pid_of(runner.PROCESS_PATTERN)
    if running and not is_test_build(running):
        raise Skip("the running Studio is not the Test build ('Studio (macOS) - Test'). Quit it and start the Test build: "
                   "the stress suites never drive another build")
    app = common.app_of(context)
    if app.exists("login.signIn"):
        raise Skip("Studio is on the login screen: sign in with the test account (the tester never types passwords)")
    try:
        driver.clear_leftovers(app, context.log)
    except Exception as error:
        context.log(f"could not clear the screen ({error}): going to the projects list")
    common.go_home(app)
    if session:
        common.open_session_by_id(app, session[0], session[1])
    return app
