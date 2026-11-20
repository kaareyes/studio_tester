"""Network suite: one audition per network fault (upload cut at 50% / 90%, response lost, slow server, server down, timeout then
recover, intermittent), then the faults are removed and the Queue has to recover by itself: every file uploaded exactly once, nothing
lost, 100% only after the server confirmed. The fault events log is saved with the run.
Options: picked (session ids JSON), allow_real, presets (comma list of preset file names; empty = the default set), seed."""
import json
import os
import shutil
import time

from tester import faults, oracle
from tester.runner import Skip
from . import common, driver, realistic, recover
from .common import plan_from_options
from .realistic import _sessions

DEFAULT_PRESETS = ["s3-cut-at-50.json", "s3-cut-at-90.json", "s3-lost-response.json", "media-lost-response.json", "attach-lost-response.json", "attach-exact-lost-response.json",
                   "rest-slow-3s.json", "s3-slow.json", "server-down.json", "timeout-then-recover.json", "intermittent-seed-42.json",
                   "wifi-up-no-internet.json"]


def preset_test(preset, state):
    def test(context):
        rnd = state["rnd"]
        project, entry = state["pairs"][0]
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        faults.clear()
        faults.offline(False)
        faults.reset_events()
        pk = oracle.last_media_pk()
        faults.set_preset(preset)
        context.log(f"fault on: {preset}")
        try:
            done = driver.random_audition(app, rnd, context.log, lambda: rnd.randint(3, 8), max_talents=2)
        except driver.StepFailed as error:
            if "did not leave Audition Mode" not in str(error):
                raise
            # Some faults (server down) keep Finalize from completing while they are on. The takes are on screen and safe: the fault is
            # removed and Finalize pressed again; it must complete now, and everything must still upload.
            context.log("Finalize did not complete while the fault was on: removing the fault and finalizing again")
            faults.clear()
            faults.offline(False)
            driver.finalize(app, context.log)
            done = {"takes": sum(1 for m in oracle.media_since(pk) if not m["deleted"] and oracle.classify(m) == "take")}
        time.sleep(20)                                     # the upload runs into the fault now
        saved = os.path.join(context.run_dir, f"events_{preset}.log")
        with open(saved, "w") as handle:
            handle.write("\n".join(faults.events(5000)))
        fired = [l for l in faults.events(5000) if "fault" in l.lower() or "fail" in l.lower() or "cut" in l.lower() or "drop" in l.lower()]
        context.log(f"fault events seen: {len(fired)} (saved {os.path.basename(saved)})")
        problems = oracle.check(pk, uploaded=None)
        faults.clear()
        faults.offline(False)
        end = time.time() + 1200
        last_log, last_count, last_change = 0.0, None, time.time()
        unstuck = None
        while time.time() < end:
            waiting = oracle.pending_since(pk)
            if not waiting:
                break
            if realistic.answer_resume_if_open(context):
                last_change = time.time()
            if time.time() - last_log > 60:                  # a silent wait looks stuck to the watchdog
                last_log = time.time()
                context.log(f"after the fault: {len(waiting)} clip(s) still waiting to upload")
            if len(waiting) != last_count:
                last_count, last_change = len(waiting), time.time()
            elif unstuck is None and time.time() - last_change > 300:
                # Nothing moved for 5 minutes after the fault was removed: close and open Studio like a person would, and note whether
                # that is what it takes (the finding: the upload that failed is not retried by itself).
                unstuck = realistic.relaunch_to_unstick(context, pk)
                last_change = time.time()
            time.sleep(15)
        problems += oracle.check(pk, expect={"takes": done["takes"]}, uploaded=True)
        if unstuck is not None:
            problems.insert(0, "the upload was not retried by itself after the fault was removed (nothing moved for 5 minutes); "
                               + ("it uploaded after Studio was closed and opened again" if unstuck else "it did NOT upload even after Studio was closed and opened again"))
        if problems:
            raise AssertionError(f"{preset}: " + "; ".join(problems))
    return test


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    wanted = [p.strip() for p in (options.get("presets") or "").split(",") if p.strip()] or DEFAULT_PRESETS
    available = set(faults.list_presets())
    state = {"rnd": rnd, "pairs": pairs}

    def prepare(context):
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        if not pairs:
            raise Skip("no session was chosen: pick one session with scheduled talents on the page")
        missing = [p for p in wanted if p not in available]
        if missing:
            context.log("presets not found (skipped): " + ", ".join(missing))
        faults.label("N-#", 1)
        context.log(f"seed {seed}; session {pairs[0][0]['name']} / {pairs[0][1]['name']}")
    tests = [("Prepare: session and camera label", prepare)]
    for preset in wanted:
        if preset in available:
            tests.append((f"Fault: {preset}", preset_test(preset, state)))
    return tests
