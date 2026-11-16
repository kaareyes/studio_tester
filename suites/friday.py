"""Friday scope: one test per row of the weekly stress scope (STRESS_TEST_RULES.md in the vault). Rows that can be driven by control
name run for real; the rest say, in plain words, why they are not automated yet (they are never silently passed).
Options: picked (session ids), seed."""
import time

from tester import faults, monitor, oracle, ax, runner
from tester.ax import ControlNotFound
from tester.runner import Skip
from . import chaos, common, driver, recover
from .common import plan_from_options
from .realistic import _sessions


def _scenario(function, label):
    def test(context, state):
        project, entry = state["pairs"][0]
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        pk = oracle.last_media_pk()
        function(context, app, state["rnd"], {"profile": "short"}, [])
        problems = oracle.check(pk)
        if problems:
            raise AssertionError("; ".join(problems))
    return test


def row7_paging(context, state):
    app = recover.ensure_ready(context)
    common.scroll_page(app, -40)
    seen = set()
    for _ in range(60):
        seen |= {driver.tail_id(e) for e in app.find_all(prefix="sessions.row.name.")}
        common.scroll_page(app, 6, settle=1.0)
    context.log(f"sessions seen while scrolling to the bottom: {len(seen)}")
    time.sleep(3)
    if app.exists("sessions.pagingLoader"):
        raise AssertionError("the paging loader is still showing after the list stopped loading")


def row8_settings(context, state):
    app = recover.ensure_ready(context)
    app.press("nav.settings")
    time.sleep(3)
    if not recover.app_alive():
        raise AssertionError("Studio crashed when Settings opened")


def row13_leaks(context, state):
    pid = ax.pid_of(runner.PROCESS_PATTERN)
    if not pid:
        raise Skip("Studio is not running")
    count = monitor.leak_count(pid)
    if count is None:
        raise Skip("`leaks` could not run")
    context.log(f"ROOT LEAK count: {count}")
    if count > 5:
        raise AssertionError(f"{count} root leaks (expected only a handful)")


def row17_interrupted_upload(context, state):
    project, entry = state["pairs"][0]
    for wait in (4, 60):
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        pk = oracle.last_media_pk()
        driver.random_audition(app, state["rnd"], context.log, lambda: 5, max_talents=1)
        time.sleep(wait)
        recover.kill_app()
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        time.sleep(30)
        end = time.time() + 900
        while time.time() < end and any(not m["uploaded"] for m in oracle.media_since(pk) if not m["deleted"] and oracle.classify(m) != "talent_photo_cache"):
            time.sleep(10)
        problems = oracle.check(pk, uploaded=True)
        if problems:
            raise AssertionError(f"killed {wait} s after Finalize: " + "; ".join(problems))


MANUAL = "not automated yet: "
ROWS = [
    (1, "Offline agency sync: full pull", None, MANUAL + "needs a test agency with a known backend count"),
    (2, "Offline agency sync: delta", None, MANUAL + "needs a controllable backend change"),
    (3, "Media identity (one ID per file)", None, MANUAL + "covered by the unit tests; a UI version needs same-name file fixtures"),
    (4, "Capture screen: add/remove talents", _scenario(chaos.add_remove_talents, "x"), None),
    (5, "Offline resume: quit mid-audition", _scenario(chaos.kill_mid_take, "x"), None),
    (6, "Syncing Talent screen", None, MANUAL + "needs offline-created talents (run the Offline load suite first)"),
    (7, "Sessions list paging loader", row7_paging, None),
    (8, "Settings > General with empty picture URL", row8_settings, None),
    (9, "Offline upload queue", _scenario(chaos.finalize_offline, "x"), None),
    (13, "Memory leaks (ROOT LEAK count)", row13_leaks, None),
    (14, "Camera/mic unplug and replug", None, MANUAL + "needs a person to unplug the camera"),
    (16, "Large-video upload", None, MANUAL + "use the Long video suite"),
    (17, "Interrupted upload (kill 4 s and 60 s after Finalize)", row17_interrupted_upload, None),
]


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    state = {"rnd": rnd, "pairs": pairs}
    tests = []
    for number, title, function, reason in ROWS:
        def test(context, _f=function, _r=reason):
            if _f is None:
                raise Skip(_r)
            if not state["pairs"]:
                raise Skip("no session was chosen: pick one session on the page")
            _f(context, state)
        tests.append((f"Row {number}: {title}", test))
    return tests
