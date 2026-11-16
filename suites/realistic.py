"""Realistic suite: works like a casting user, in the sessions QA ticked on the page. For every session it runs N random auditions
(1-3 talents, photo/slate redo, group image, 1-4 takes of the chosen length profile, Back, rating), online or offline, and after each
audition the data-integrity check looks for lost, duplicated or misplaced data. After the run it waits for the Queue to settle and
checks that everything was uploaded (online) or is still safely on disk (offline).

Options (from the test page): picked (JSON list of session ids), allow_real (project ids confirmed), auditions (per session, default 3),
profile (short|normal|long|mixed), mix ('50/40/10'), mode (online|offline|mixed), seed."""
import json
import random
import time

from tester import catalog, faults, oracle, profiles
from tester.runner import Skip
from . import common, driver
from .common import plan_from_options


def _sessions(options):
    data = catalog.load()
    try:
        ids = json.loads(options.get("picked") or "[]")
        allow = json.loads(options.get("allow_real") or "[]")
    except ValueError:
        return [], ["the ticked sessions could not be read: tick them again"]
    pairs, problems = catalog.resolve_selection(data, ids, allow)
    return pairs, problems


def audition_test(session, number, options, state):
    def test(context):
        app = common.app_of(context)
        rnd = state["rnd"]
        project, entry = session
        if state.get("opened") != entry["id"]:
            common.open_session_by_id(app, entry["id"], entry["name"])
            state["opened"] = entry["id"]
        mode = options.get("mode") or "online"
        offline = mode == "offline" or (mode == "mixed" and rnd.random() < 0.5)
        faults.offline(offline)
        time.sleep(8 if offline != state.get("last_offline") else 0)
        state["last_offline"] = offline
        if state.get("pk") is None:
            state["pk"] = oracle.last_media_pk()
        profile = options.get("profile") or "mixed"
        take = lambda: profiles.pick_length(profile, rnd, options.get("mix"))[1]
        audition_pk = oracle.last_media_pk()
        context.log(f"{project['name']} / {entry['name']}: audition {number} ({'offline' if offline else 'online'}, profile {profile})")
        done = driver.random_audition(app, rnd, context.log, take)
        context.log(f"recorded: {done['talents']} talent(s), {done['takes']} take(s), labels {' '.join(done['labels'])}; finalize {done['seconds_finalize']} s")
        state["expected"]["takes"] += done["takes"]
        state["expected"]["photos"] += done["photos"]
        state["expected"]["slates"] += done["slates"]
        # The offline rule ("nothing uploaded yet") is judged on THIS audition only: earlier online auditions of a mixed run are uploaded.
        problems = oracle.check(state["pk"], uploaded=None)
        if offline:
            problems += oracle.check(audition_pk, uploaded=False)
        if problems:
            raise AssertionError("; ".join(problems))
    return test


def settle_test(options, state):
    def test(context):
        faults.offline(False)
        context.log("online again: waiting for the Queue to finish uploading")
        end = time.time() + 3600
        while time.time() < end:
            left = [m for m in oracle.media_since(state["pk"] or 0) if not m["uploaded"] and not m["deleted"] and oracle.classify(m) != "talent_photo_cache"]
            if not left:
                break
            time.sleep(20)
        problems = oracle.check(state["pk"] or 0, expect=state["expected"], uploaded=True)
        if problems:
            raise AssertionError("; ".join(problems))
        context.log(f"all clean: {state['expected']}")
    return test


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    state = {"rnd": rnd, "pk": None, "expected": {"takes": 0, "photos": 0, "slates": 0}}
    count = max(1, min(int(options.get("auditions") or 3), 500))
    tests = []

    def prepare(context):
        app = common.app_of(context)
        if app.exists("login.signIn"):
            raise Skip("Studio is on the login screen: sign in with the test account first")
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        if not pairs:
            raise Skip("no session was chosen (or none can be used): pick sessions on the page")
        context.log(f"seed {seed}; {len(pairs)} session(s) x {count} audition(s); profile {options.get('profile') or 'mixed'}")
        reason = profiles.disk_problem(len(pairs) * count * 2, options.get("profile") or "mixed", options.get("mix"))
        if reason:
            raise Skip(reason)
        faults.reset_events()
        faults.label("T-#", 1)
        state["pk"] = oracle.last_media_pk()
    tests.append(("Prepare: seed, sessions, disk, camera label", prepare))
    for s_index, session in enumerate(pairs):
        for n in range(1, count + 1):
            tests.append((f"{session[0]['name']} / {session[1]['name']}: audition {n}", audition_test(session, n, options, state)))
    tests.append(("Wait for uploads and check every file", settle_test(options, state)))
    return tests
