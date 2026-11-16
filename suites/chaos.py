"""Chaos suite: a careless or hostile user. Random actions at bad moments, from a seed (repeat any failure with the same seed).
After every scenario: is Studio still alive and answering, and does the data-integrity check pass? A crash or hang is not the end of
the run: the tester saves the evidence (crash report, `sample`), starts Studio again, writes an incident line and goes on.

Scenarios (each picked at random, weights below): flaky network during takes, Finalize/Back spam, add and remove talents during
Audition Mode, kill the app mid-take and reopen it, go offline during Finalize, camera switch mid-take, leave a half-built audition
and open another session, empty add-talent form.
Options: picked (session ids JSON), allow_real, rounds (default 20), profile, mix, seed."""
import json
import random
import time

from tester import faults, oracle, profiles
from tester.ax import ControlNotFound
from tester.runner import Skip
from . import common, driver, recover
from .common import plan_from_options
from .realistic import _sessions


def _quick(options, rnd):
    profile = options.get("profile") or "short"
    return lambda: profiles.pick_length(profile, rnd, options.get("mix"))[1]


def flaky_network(context, app, rnd, options, extra):
    flip = lambda: faults.offline(not faults.is_offline())
    driver.random_audition(app, rnd, context.log, _quick(options, rnd), flaky=flip)
    faults.offline(False)


def finalize_offline(context, app, rnd, options, extra):
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    driver.record_take(app, _quick(options, rnd)(), context.log)
    faults.offline(True)
    time.sleep(5)
    driver.finalize(app, context.log)
    faults.offline(False)


def spam_buttons(context, app, rnd, options, extra):
    """Presses Finalize / Back / Stop / Record again and again, ignoring 'control not there' (a person would just keep clicking)."""
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, rnd.randint(1, 2), context.log)
    driver.enter_audition_mode(app)
    for _ in range(rnd.randint(8, 20)):
        name = rnd.choice(["capture.record", "capture.stop", "capture.finalize", "capture.back", "capture.takePhoto", "capture.exit"])
        try:
            app.press(name, timeout=1.5)
        except ControlNotFound:
            pass
        time.sleep(rnd.random() * 0.4)
        if app.exists("alert.dialog"):
            app.press(rnd.choice(["alert.leftButton", "alert.rightButton"]), timeout=2) if app.exists("alert.leftButton") else None
    extra.append("spam")


def add_remove_talents(context, app, rnd, options, extra):
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, 2, context.log)
    driver.enter_audition_mode(app)
    for _ in range(rnd.randint(2, 5)):
        removers = app.find_all(prefix="capture.talent.remove.")
        if removers and rnd.random() < 0.5:
            app.press(driver.name_of(removers[0]))
        elif app.exists("capture.addTalent"):
            app.press("capture.addTalent")
            time.sleep(1)
            if app.exists("addTalent.close"):
                app.press("addTalent.close")
        time.sleep(1)
    if app.exists("capture.record"):
        driver.record_take(app, _quick(options, rnd)(), context.log)
    if app.exists("capture.finalize"):
        driver.finalize(app, context.log)


def kill_mid_take(context, app, rnd, options, extra):
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    app.press("capture.record")
    time.sleep(rnd.randint(3, 10))
    recover.kill_app()
    extra.append("killed mid-take")


def camera_switch_mid_take(context, app, rnd, options, extra):
    names = [line for line in faults.camera().splitlines() if line.strip()]
    if len(names) < 2:
        raise Skip("only one camera on this Mac: nothing to switch to")
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, 1, context.log)
    driver.enter_audition_mode(app)
    app.press("capture.record")
    time.sleep(3)
    faults.camera(rnd.choice(names))
    time.sleep(6)
    app.press("capture.stop" if app.exists("capture.stop") else "capture.fullscreenStop")
    time.sleep(3)
    if app.exists("capture.finalize"):
        driver.finalize(app, context.log)


def leave_half_built(context, app, rnd, options, extra):
    """Talents in the audition, then walk away to the projects list and another session, then come back."""
    driver.clear_leftovers(app, context.log)
    driver.add_talents(app, rnd, 2, context.log)
    common.go_home(app)
    extra.append("left a half-built audition")


def empty_talent_form(context, app, rnd, options, extra):
    if not app.exists("session.addTalent"):
        raise Skip("this session has no Add Talent button")
    app.press("session.addTalent")
    app.wait_for("addTalent.title", timeout=8)
    if app.exists("addTalent.submit") and app.enabled(app.find("addTalent.submit")):
        context.log("note: the form allows submitting with empty names (checked, not pressed)")
    app.press("addTalent.close")


SCENARIOS = [
    ("flaky network during takes", flaky_network, 25),
    ("Finalize while going offline", finalize_offline, 10),
    ("button spam in Audition Mode", spam_buttons, 15),
    ("add / remove talents in Audition Mode", add_remove_talents, 15),
    ("app killed mid-take", kill_mid_take, 10),
    ("camera switched mid-take", camera_switch_mid_take, 8),
    ("half-built audition abandoned", leave_half_built, 10),
    ("empty Add Talent form", empty_talent_form, 7),
]


def scenario_test(index, state, options):
    def test(context):
        rnd = state["rnd"]
        name, function, _ = rnd.choices(SCENARIOS, weights=[w for *_, w in SCENARIOS])[0]
        pairs = state["pairs"]
        project, entry = pairs[index % len(pairs)]
        context.log(f"scenario {index + 1}: {name} in {project['name']} / {entry['name']}")
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        pk = oracle.last_media_pk()
        extra = []
        began = time.time()
        try:
            function(context, app, rnd, options, extra)
        except Skip:
            raise
        except Exception as error:
            if not recover.app_alive():
                recover.incident(context, f"Studio crashed during '{name}' ({error})")
            else:
                recover.sample_hang(context, f"hang_{index + 1}")
                recover.incident(context, f"'{name}' failed: {error}")
                raise
        finally:
            faults.offline(False)
        if not recover.app_alive():
            recover.incident(context, f"Studio is gone after '{name}' ({' '.join(extra) or 'expected for this scenario'})")
            crashes = recover.save_crash_reports(context, began - 5)
            if "killed" not in " ".join(extra):
                raise AssertionError(f"Studio crashed during '{name}'" + (f"; crash report {crashes[0]}" if crashes else ""))
            app = recover.ensure_ready(context, (entry["id"], entry["name"]))
            time.sleep(15)                                   # the app restores the take it was recording
        time.sleep(5)
        problems = oracle.check(pk)
        if problems:
            raise AssertionError(f"after '{name}': " + "; ".join(problems))
    return test


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    state = {"rnd": rnd, "pairs": pairs}
    rounds = max(1, min(int(options.get("rounds") or 20), 500))

    def prepare(context):
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        if not pairs:
            raise Skip("no session was chosen: pick sessions on the page")
        context.log(f"seed {seed} (type it on the page to repeat this run); {rounds} scenarios over {len(pairs)} session(s)")
        faults.reset_events()
        faults.label("C-#", 1)
    tests = [("Prepare: seed, sessions, camera label", prepare)]
    tests += [(f"Chaos {i + 1}", scenario_test(i, state, options)) for i in range(rounds)]
    return tests
