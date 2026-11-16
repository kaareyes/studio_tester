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
from . import common, driver, recover
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
        done = driver.random_audition(app, rnd, context.log, lambda: rnd.randint(3, 8), max_talents=2)
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
        while time.time() < end:
            if all(m["uploaded"] for m in oracle.media_since(pk) if not m["deleted"] and oracle.classify(m) != "talent_photo_cache"):
                break
            time.sleep(15)
        problems += oracle.check(pk, expect={"takes": done["takes"]}, uploaded=True)
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
