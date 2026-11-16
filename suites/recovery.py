"""Recovery suite: the pending-take scenarios (PT-xx) automated. A take is recorded, the app is crashed at an exact point (test-only crash
points) or killed at a measured moment, Studio is started again, and the checks C-J0..C-NODUP of
scripts/pending_take_recovery/SCENARIOS.md run: the take is restored exactly once, in the right audition, nothing is lost or doubled,
the journal ends empty, and (online) it uploads.
Options: picked (session ids JSON), allow_real, seed."""
import json
import time

from tester import faults, oracle
from tester.runner import Skip
from . import common, driver, recover
from .common import plan_from_options
from .realistic import _sessions

RESTORE_WAIT = 180      # seconds the app gets to restore and finish a take after it was started again


def _crash_scenario(preset, title, offline=False, long_take=False, kill_after=None):
    """preset: a crash preset file (exact point) or None with kill_after (timed kill, K method)."""
    def test(context, state):
        rnd = state["rnd"]
        project, entry = state["pairs"][0]
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        faults.reset_events()
        faults.label("PT-#", state["number"])
        faults.offline(offline)
        time.sleep(6 if offline else 0)
        pk = oracle.last_media_pk()
        began = time.time()
        if preset:
            faults.set_preset(preset)
        driver.clear_leftovers(app, context.log)
        driver.add_talents(app, rnd, 1, context.log)
        driver.enter_audition_mode(app)
        seconds = 90 if long_take else 4
        try:
            driver.record_take(app, seconds, context.log)
        except Exception:
            if not preset:
                raise                                     # a crash is expected only with a crash preset
        if kill_after is not None:
            time.sleep(kill_after)
            recover.kill_app()
        if preset:
            for _ in range(60):
                if not recover.app_alive():
                    break
                time.sleep(1)
        if not recover.app_alive():
            context.log("Studio is gone (expected): starting it again")
        elif preset or kill_after is not None:
            raise AssertionError("the crash point was set but Studio is still running (the preset did not fire)")
        faults.clear()
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        faults.offline(offline)
        end = time.time() + RESTORE_WAIT
        while time.time() < end and oracle.journal_files():
            time.sleep(3)
        problems = oracle.check_idle_journal()
        faults.offline(False)
        problems += oracle.check(pk, expect={"takes": 1}, uploaded=None)
        if not offline:
            end = time.time() + 900
            while time.time() < end and any(not m["uploaded"] for m in oracle.media_since(pk) if oracle.classify(m) == "take" and not m["deleted"]):
                time.sleep(10)
            problems += oracle.check(pk, expect={"takes": 1}, uploaded=True)
        state["number"] += 1
        if problems:
            raise AssertionError(f"{title}: " + "; ".join(problems))
    return test


SCENARIOS = [
    ("PT-01 crash right after Stop", _crash_scenario("crash-take-after-stop.json", "PT-01")),
    ("PT-03 crash after export, before the database save", _crash_scenario("crash-take-after-export.json", "PT-03")),
    ("PT-04 crash after the database save, journal not cleared", _crash_scenario("crash-take-after-save.json", "PT-04")),
    ("PT-02 killed 1 s after Stop (long take, processing)", _crash_scenario(None, "PT-02", long_take=True, kill_after=1)),
    ("PT-05 no crash (normal run, journal must end empty)", _crash_scenario(None, "PT-05")),
    ("PT-11 offline crash, offline reopen", _crash_scenario("crash-take-after-stop.json", "PT-11", offline=True)),
]


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    state = {"rnd": rnd, "pairs": pairs, "number": 1}

    def prepare(context):
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        if not pairs:
            raise Skip("no session was chosen: pick one session with scheduled talents on the page")
        context.log(f"seed {seed}; every scenario uses {pairs[0][0]['name']} / {pairs[0][1]['name']}")
    tests = [("Prepare: session", prepare)]
    for name, function in SCENARIOS:
        tests.append((name, (lambda f: (lambda context: f(context, state)))(function)))
    tests.append(("PT-12 another user signs in after the crash", lambda context: (_ for _ in ()).throw(
        Skip("needs a second test account: run this one by hand (SCENARIOS.md PT-12)"))))
    return tests
