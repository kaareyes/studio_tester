"""Recovery suite: the pending-take scenarios (PT-xx) automated. A take is recorded, the app is crashed at an exact point (test-only crash
points) or killed at a measured moment, Studio is started again, and the checks C-J0..C-NODUP of
scripts/pending_take_recovery/SCENARIOS.md run: the take is restored exactly once, in the right audition, nothing is lost or doubled,
the journal ends empty, and (online) it uploads.
Options: picked (session ids JSON), allow_real, seed."""
import json
import os
import time

from tester import faults, oracle
from tester.runner import Skip
from . import common, driver, realistic, recover
from .common import plan_from_options
from .realistic import _sessions

RESTORE_WAIT = 180      # seconds the app gets to restore and finish a take after it was started again


def _crash_scenario(preset, title, offline=False, long_take=False, kill_after=None, record=None, expect=None, open_session=True, broken_journal=False):
    """preset: a crash preset file (exact point) or None with kill_after (timed kill, K method).
    record: optional function(context, app, rnd) that does the recording of this scenario (default: one talent, one take).
    expect: what must exist afterwards (default one take). open_session=False stays on the projects list after the relaunch (PT-13).
    broken_journal=True writes a corrupt journal file while the app is down (PT-16)."""
    expect = expect or {"takes": 1}

    def test(context, state):
        rnd = state["rnd"]
        project, entry = state["pairs"][0]
        if state.get("ran_before"):
            # Every scenario starts from a cleanly restarted Studio with an empty take journal. Found live: PT-10, PT-13 and PT-16 pass when
            # run alone and failed in the full suite because the scenario before them left a resumed audition / pending takes behind.
            context.log("starting this scenario from a cleanly restarted Studio")
            recover.EXPECTED["gone"] = False
            realistic.quit_studio(patience=15)
            context.app = None
        state["ran_before"] = True
        state["last_failed"] = True                    # cleared again below when this scenario finishes without a problem
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        end_wait = time.time() + 90                    # the previous scenario's takes must all be restored before the next one begins
        while time.time() < end_wait and [f for f in oracle.journal_files() if f != "broken.json"]:
            realistic.answer_resume_if_open(context)
            time.sleep(3)
        faults.reset_events()
        faults.label("PT-#", state["number"])
        faults.offline(offline)
        time.sleep(6 if offline else 0)
        pk = oracle.last_media_pk()
        if preset:
            recover.EXPECTED["gone"] = True          # the crash is the point of this test: the watchdog waits
            faults.set_preset(preset)
        driver.clear_leftovers(app, context.log)
        try:
            if record:
                record(context, app, rnd)
            else:
                driver.add_talents(app, rnd, 1, context.log)
                driver.enter_audition_mode(app)
                driver.record_take(app, 90 if long_take else 4, context.log)
        except Exception as error:
            if not preset:
                raise                                     # a crash is expected only with a crash preset
            context.log(f"(the steps before the crash point stopped: {type(error).__name__}: {error})")   # was swallowed silently
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
        broken = os.path.join(oracle.JOURNAL_DIR, "broken.json")
        if broken_journal:
            os.makedirs(oracle.JOURNAL_DIR, exist_ok=True)
            with open(broken, "w") as handle:
                handle.write("not json")                  # a corrupt entry next to the valid one: it must be ignored, not crash the app
        app = recover.ensure_ready(context, (entry["id"], entry["name"]) if open_session else None)
        faults.offline(offline)

        def pending():
            return [f for f in oracle.journal_files() if f != "broken.json"]
        end = time.time() + RESTORE_WAIT
        while time.time() < end and pending():
            realistic.answer_resume_if_open(context)
            time.sleep(3)
        problems = [f"pending-take journal is not empty while idle: {pending()[:3]}"] if pending() else []
        faults.offline(False)
        if broken_journal:
            if not recover.app_alive():
                problems.append("Studio crashed because of the broken journal file")
            if os.path.exists(broken):
                os.remove(broken)
        problems += oracle.check(pk, expect=expect, uploaded=None)
        if not offline:
            note = realistic.wait_for_uploads(context, pk, limit=900)
            if note:
                problems.append(note)
            problems += oracle.check(pk, expect=expect, uploaded=True)
        state["number"] += 1
        state["last_failed"] = bool(problems)
        if problems:
            raise AssertionError(f"{title}: " + "; ".join(problems))
    return test


# ---- how each scenario records (SCENARIOS.md PT-06 .. PT-10)

def _delete_take_while_processing(context, app, rnd):
    """PT-06: record a long take, Stop, delete it from the strip while it is processing: it must NOT come back after the kill."""
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    driver.record_take(app, 60, context.log)
    deleters = app.find_all(prefix="capture.take.delete.")
    if not deleters:
        # The delete control only shows after the card's options menu is opened (the three dots), like for a person.
        menus = app.find_all(prefix="capture.take.options.")
        if menus:
            app.press(driver.name_of(menus[0]))
            time.sleep(1)
            deleters = app.find_all(prefix="capture.take.delete.")
    if not deleters:
        raise AssertionError("no take to delete on the strip (the take card has no delete control)")
    app.press(driver.name_of(deleters[0]))
    time.sleep(1)
    confirm = driver.alert_button(app, ("yes", "delete", "confirm", "proceed", "ok"))     # this one is meant to confirm the take's deletion
    if confirm:
        app.press(confirm)
    recover.kill_app()


def _several_pending_takes(context, app, rnd):
    """PT-07: three takes back to back, kill while the last is still processing: all three come back."""
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    for _ in range(3):
        driver.record_take(app, 20, context.log)
    time.sleep(1)
    recover.kill_app()


def _slate_take(context, app, rnd):
    """PT-08: a long slate, kill during processing: the slate comes back under the same audition."""
    driver.add_talents(app, rnd, 1, context.log)
    cards = driver.group_cards(app)
    if not cards:
        raise AssertionError("no talent card to record a slate for")
    driver.record_slate(app, cards[0], 20, context.log)
    time.sleep(1)
    recover.kill_app()


def _group_take(context, app, rnd):
    """PT-09: two talents in the audition, one group take, kill during processing: ONE row linked to both talents."""
    if driver.add_talents(app, rnd, 2, context.log) < 2:
        raise Skip("this session has fewer than two scheduled talents")
    driver.enter_audition_mode(app)
    driver.record_take(app, 20, context.log)
    time.sleep(1)
    recover.kill_app()


def _fast_track(context, app, rnd):
    """PT-10: audition A with a long take, Finalize at once, audition B with a short take, kill while A's take still processes."""
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    driver.record_take(app, 60, context.log)
    driver.finalize(app, context.log)
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    driver.record_take(app, 5, context.log)
    time.sleep(1)
    recover.kill_app()


SCENARIOS = [
    ("PT-01 crash right after Stop", _crash_scenario("crash-take-after-stop.json", "PT-01")),
    ("PT-03 crash after export, before the database save", _crash_scenario("crash-take-after-export.json", "PT-03")),
    ("PT-04 crash after the database save, journal not cleared", _crash_scenario("crash-take-after-save.json", "PT-04")),
    ("PT-02 killed 1 s after Stop (long take, processing)", _crash_scenario(None, "PT-02", long_take=True, kill_after=1)),
    ("PT-05 no crash (normal run, journal must end empty)", _crash_scenario(None, "PT-05")),
    ("PT-06 take deleted while still processing must not come back", _crash_scenario(None, "PT-06", record=_delete_take_while_processing, expect={"takes": 0})),
    ("PT-07 several pending takes are all restored", _crash_scenario(None, "PT-07", record=_several_pending_takes, expect={"takes": 3})),
    ("PT-08 slate take restored", _crash_scenario(None, "PT-08", record=_slate_take, expect={"slates": 1})),
    ("PT-09 group take restored as one row", _crash_scenario(None, "PT-09", record=_group_take, expect={"takes": 1})),
    ("PT-10 fast-track: the finalized audition's take goes back into ITS audition", _crash_scenario(None, "PT-10", record=_fast_track, expect={"takes": 2})),
    ("PT-11 offline crash, offline reopen", _crash_scenario("crash-take-after-stop.json", "PT-11", offline=True)),
    ("PT-13 session never reopened: the take is restored at launch", _crash_scenario("crash-take-after-stop.json", "PT-13", open_session=False)),
    ("PT-16 a broken journal file is ignored, the valid take is restored", _crash_scenario("crash-take-after-stop.json", "PT-16", broken_journal=True)),
]


# Scenarios of SCENARIOS.md the tester does not drive yet: listed so they are never silently missing (see COVERAGE.md)
MANUAL = [
    ("PT-12", "another user signs in after the crash", "needs a second test account: run it by hand (SCENARIOS.md PT-12)"),
    ("PT-14", "a take that fails processing 5 times", "not automated yet: needs the raw audio file's permissions changed (chmod) while the app runs"),
    ("PT-15", "restore interrupted by the editor's own export", "not automated yet: needs PT-07 setup, then recording inside the reopened session"),
    ("PT-17", "Test and Production apps never share takes", "not automated yet: needs the Production app running next to the Test app"),
    ("RF-01", "'Not rendered' hold survives a relaunch", "not automated yet: needs a trim in Browse and a render failure (chmod) before Finalize"),
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
    for ident, title, reason in MANUAL:
        tests.append((f"{ident} {title}", (lambda r: (lambda context: (_ for _ in ()).throw(Skip(r))))(reason)))
    only = [word.strip().upper() for word in str((options or {}).get("only") or "").split(",") if word.strip()]
    if only:                                                  # e.g. "PT-01,PT-03": just those scenarios (quick diagnosis)
        tests = [tests[0]] + [t for t in tests[1:] if any(t[0].upper().startswith(word) for word in only)]
    return tests
