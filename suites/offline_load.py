"""Offline load suite: the test-only generator writes hundreds of offline auditions (some with talents created offline) into the Test
app, then the app comes online and has to sync them by itself. Checks: every generated audition arrives once, in the right session,
uploaded; nothing created twice.
Options: picked (ONE session), auditions (default 100), sample_image, sample_video (paths of small test media, required), seed."""
import json
import os
import time

from tester import faults, oracle
from tester.runner import Skip
from . import common, recover
from .common import plan_from_options
from .realistic import _sessions


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)

    def generate(context):
        if not pairs:
            raise Skip("no session was chosen: pick one session on the page")
        image, video = options.get("sample_image"), options.get("sample_video")
        if not (image and video and os.path.exists(image) and os.path.exists(video)):
            raise Skip("give the paths of a small test photo and video on the page (sample_image, sample_video): the generator copies them")
        project, entry = pairs[0]
        request = {"projectId": project["id"], "projectName": project["name"], "sessionId": entry["id"], "sessionName": entry["name"],
                   "auditions": max(1, min(int(options.get("auditions") or 100), 1000)), "seed": seed, "offlineTalentShare": 0.5,
                   "scheduledTalents": [{"id": t["id"], "name": t["name"], "role": "Actor", "code": t["id"][:4]} for t in entry.get("talents", [])],
                   "imagePath": image, "videoPath": video}
        path = os.path.join(context.run_dir, "generate_request.json")
        with open(path, "w") as handle:
            json.dump(request, handle, indent=1)
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        faults.offline(True)
        time.sleep(8)
        state["pk"] = oracle.last_media_pk()
        faults.reset_events()
        faults._run("generate", path)
        end = time.time() + 1800
        result = None
        while time.time() < end and result is None:
            out = faults._run("generate-result")
            if out.startswith("{"):
                result = json.loads(out)
            time.sleep(5)
        if result is None:
            raise AssertionError("the generator wrote no result in 30 minutes")
        context.log(f"generator result: {result}")
        problems_now = oracle.check(state["pk"], uploaded=False)
        if problems_now:
            raise AssertionError("; ".join(problems_now))

    def sync(context):
        faults.offline(False)
        context.log("online again: waiting for the sync and uploads")
        end = time.time() + 7200
        while time.time() < end:
            left = [m for m in oracle.media_since(state["pk"]) if not m["uploaded"] and not m["deleted"] and oracle.classify(m) != "talent_photo_cache"]
            if not left:
                break
            time.sleep(30)
        bad = oracle.check(state["pk"], uploaded=True)
        if bad:
            raise AssertionError("; ".join(bad[:10]) + (f" (+{len(bad) - 10} more)" if len(bad) > 10 else ""))

    state = {"pk": 0}
    return [("Generate the offline auditions", generate), ("Go online: sync and upload, then check every file", sync)]
