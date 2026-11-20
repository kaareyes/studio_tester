"""Realistic suite: works like a casting user, in the sessions QA ticked on the page. For every session it runs N random auditions
(1-3 talents, photo/slate redo, group image, 1-4 takes of the chosen length profile, Back, rating), online or offline, and after each
audition the data-integrity check looks for lost, duplicated or misplaced data. After the run it waits for the Queue to settle and
checks that everything was uploaded (online) or is still safely on disk (offline).

Options (from the test page): picked (JSON list of session ids), allow_real (project ids confirmed), auditions (per session, default 3),
profile (short|normal|long|mixed), mix ('50/40/10'), mode (online|offline|mixed), seed."""
import json
import os
import subprocess
import random
import time

from tester import catalog, control, faults, oracle, profiles, runner
from tester.runner import Skip
from . import common, driver, recover
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


def queue_counts(context):
    """What the app itself shows in its Queue ({'all','pending','completed'}), read from the screen; None when it cannot be read.
    The Queue is opened and closed again; nothing is pressed inside it."""
    app = getattr(context, "app", None)
    if app is None:
        return None
    try:
        counts = common.open_queue(app)
        common.close_queue(app)
        return counts
    except Exception:
        try:
            common.close_queue(app)
        except Exception:
            pass
        return None


def not_uploaded_since(pk):
    return oracle.pending_since(pk or 0)


def quit_studio(pid=None, patience=25):
    """Closes the running Studio the way a person does: Cmd-Q. (An instance the tester started itself does not answer the AppleScript
    'quit' command: it times out.) When it is still running after `patience` seconds that exact process is asked to terminate."""
    from tester import ax
    pid = pid or ax.pid_of(runner.PROCESS_PATTERN)
    if pid is None:
        return
    script = ('tell application "System Events"\n'
              f' set p to first process whose unix id is {int(pid)}\n'
              ' set frontmost of p to true\n'
              ' delay 0.5\n'
              ' keystroke "q" using command down\n'
              'end tell')
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, timeout=20)
    except Exception:
        pass
    end = time.time() + patience
    while ax.pid_of(runner.PROCESS_PATTERN) == pid and time.time() < end:
        time.sleep(1)
    if ax.pid_of(runner.PROCESS_PATTERN) == pid:
        try:
            os.kill(int(pid), 15)                             # SIGTERM to this one process only
        except OSError:
            pass
        end = time.time() + 15
        while ax.pid_of(runner.PROCESS_PATTERN) == pid and time.time() < end:
            time.sleep(1)


def relaunch_to_unstick(context, since_pk, wait=240):
    """The upload stalled with nothing pending in the Queue. A person would close and open Studio; so does the tester (a clean quit, never
    a kill: nothing is lost, the clips stay on disk). Returns True when the clips upload after the relaunch. Found live: this unstuck a
    Studio whose Queue said 'Pending 0' while 9 clips were not uploaded."""
    from tester import ax
    context.log("upload stalled: closing Studio cleanly and opening it again to see whether the uploads resume")
    recover.EXPECTED["gone"] = True          # this quit is on purpose: the watchdog must not call it a crash or reopen Studio itself
    try:
        quit_studio()
        context.app = None
        context.launch()
        try:
            driver.clear_leftovers(context.app, context.log)      # the 'Resume Audition' pop-up after a reopen: Proceed, never the X
        except Exception as error:
            context.log(f"(after the relaunch: {error})")
    except Exception as error:
        context.log(f"(relaunch failed: {error})")
        return False
    finally:
        recover.EXPECTED["gone"] = False
    end = time.time() + wait
    while time.time() < end:
        if not not_uploaded_since(since_pk):
            return True
        time.sleep(15)
    return False


def answer_resume_if_open(context):
    """After a crash Studio shows 'Resume Audition' and the recovered take is uploaded only once a person presses Proceed and finalizes it.
    A wait for uploads must do what that person does (Proceed, never the X; then Finalize), or it just waits for a click nobody makes
    (found live in Recovery PT-01). Does nothing when no pop-up or capture screen is open."""
    app = getattr(context, "app", None)
    if app is None:
        return False
    try:
        if app.exists("alert.dialog") or app.exists("capture.finalize"):
            driver.clear_leftovers(app, context.log)
            return True
    except control.UiStep:
        raise
    except Exception as error:
        context.log(f"(could not answer the Resume pop-up: {error})")
    return False


def wait_for_uploads(context, since_pk, limit=900, stall=300):
    """Waits until every clip of this run's auditions is uploaded, logging every minute. When nothing moves for `stall` seconds Studio is
    closed and opened again once (see relaunch_to_unstick). Returns None when all uploaded by themselves, else a sentence for the report:
    whether the relaunch made them upload."""
    from tester import activity
    end = time.time() + limit
    last_log, last_count, last_change, unstuck = 0.0, None, time.time(), None
    while time.time() < end:
        activity.set("waiting for the uploads to finish (checked in the database and on the Queue screen)")
        waiting = oracle.pending_since(since_pk)
        if not waiting:
            break
        if time.time() - last_log > 60:
            last_log = time.time()
            names = ", ".join(f"{m.get('name_tag') or m.get('filetype') or '?'} ({str(m.get('folder', ''))[-48:]})" for m in waiting[:2])
            context.log(f"waiting for uploads: {len(waiting)} clip(s) still waiting: {names}")
        if answer_resume_if_open(context):
            last_change = time.time()                 # answering the pop-up is progress: the take is restored and finalized now
        if len(waiting) != last_count:
            last_count, last_change = len(waiting), time.time()
        elif unstuck is None and time.time() - last_change > stall:
            unstuck = relaunch_to_unstick(context, since_pk)
            last_change = time.time()
        time.sleep(10)
    if unstuck is None:
        return None
    return ("the uploads did not move for 5 minutes and were not retried by themselves; "
            + ("they uploaded after Studio was closed and opened again" if unstuck else "they did NOT upload even after Studio was closed and opened again"))


def verify_upload_started(context, since_pk, timeout=180):
    """After Finalize: proves the upload really started before the run goes on, from TWO sources: the database (a clip of this audition
    became uploaded) and the app's own Queue (something is pending or uploading). A crashed Studio is a screen failure (retried after
    the app is opened again); an upload that never starts is a FINDING with its evidence, and the run moves on instead of waiting."""
    from tester import ax
    waiting = not_uploaded_since(since_pk)
    if not waiting:
        return "nothing was waiting"
    from tester import activity
    began = time.time()
    first_counts = None
    while time.time() - began < timeout:
        activity.set("checking that the upload really started (database + Queue screen)")
        if ax.pid_of(runner.PROCESS_PATTERN) is None:
            raise control.UiStep("Studio is not running: it closed or crashed before the upload could start")
        now_waiting = not_uploaded_since(since_pk)
        if len(now_waiting) < len(waiting):
            return f"the database shows {len(waiting) - len(now_waiting)} clip(s) uploaded"
        counts = queue_counts(context)
        if counts and counts["pending"]:
            return f"the Queue shows {counts['pending']} pending"
        first_counts = first_counts or counts
        time.sleep(20)
    summary = (f"the upload did not start within {timeout} s of Finalize: {len(waiting)} clip(s) are still not uploaded in the database "
               f"and the Queue shows pending 0 (Queue now: {queue_counts(context)}, before: {first_counts})")
    resumed = relaunch_to_unstick(context, since_pk)
    raise AssertionError(summary + ("; the uploads RESUMED after Studio was closed and opened again (Studio's upload stalled silently)"
                                    if resumed else "; they did NOT resume after Studio was closed and opened again"))


def audition_test(session, number, options, state, plan=None, title=None):
    """One audition. `plan` (the day template) sets mode online/offline, profile, takes, talents and flaky (the internet drops in the middle
    of a take and comes back); without a plan the page options decide."""
    plan = plan or {}
    def test(context):
        rnd = state["rnd"]
        project, entry = session
        # Before EVERY audition: Studio is running (opened again if it crashed), signed in, and on this session. After a crash in the
        # middle of the night the next audition starts clean instead of failing from the wrong screen.
        app = recover.ensure_ready(context, (entry["id"], entry["name"]))
        mode = plan.get("mode") or options.get("mode") or "online"
        offline = mode == "offline" or (mode == "mixed" and rnd.random() < 0.5)
        faults.offline(offline)
        time.sleep(8 if offline != state.get("last_offline") else 0)
        state["last_offline"] = offline
        if state.get("pk") is None:
            state["pk"] = oracle.last_media_pk()
        profile = plan.get("profile") or options.get("profile") or "mixed"
        take = lambda: profiles.pick_length(profile, rnd, options.get("mix"))[1]
        audition_pk = oracle.last_media_pk()
        context.log(f"{project['name']} / {entry['name']}: audition {number} ({'offline' if offline else 'online'}, profile {profile})")
        try:
            kwargs = {}
            if plan.get("takes"):
                kwargs["takes"] = plan["takes"]
            if plan.get("talents"):
                kwargs["talents"] = plan["talents"]
            if plan.get("flaky") and not offline:
                kwargs.update(flaky=drop_and_reconnect(context), flaky_always=True)
            done = driver.random_audition(app, rnd, context.log, take, **kwargs)
        except BaseException:
            # An attempt that was cut short (crash, interrupted step, retry) can still have saved takes: they are real, they get
            # uploaded, so they are counted as recorded. Otherwise the final check calls them "extra takes".
            try:
                state["expected"]["takes"] += sum(1 for m in oracle.media_since(audition_pk) if not m["deleted"] and oracle.classify(m) == "take")
            except Exception:
                pass
            raise
        context.log(f"recorded: {done['talents']} talent(s), {done['takes']} take(s), labels {' '.join(done['labels'])}; finalize {done['seconds_finalize']} s")
        state["expected"]["takes"] += done["takes"]
        state["expected"]["photos"] += done["photos"]
        state["expected"]["slates"] += done["slates"]
        if not offline:
            context.log("upload check: " + verify_upload_started(context, audition_pk))
        if plan.get("flaky") and not offline:
            # The internet dropped during this audition's takes: once it is back, THIS audition's clips must upload by themselves.
            end = time.time() + 300
            while time.time() < end and not_uploaded_since(audition_pk):
                time.sleep(15)
            left = not_uploaded_since(audition_pk)
            if left:
                shown = queue_counts(context)
                resumed = relaunch_to_unstick(context, audition_pk)
                raise AssertionError(f"the internet dropped during this audition and came back, but {len(left)} clip(s) were not uploaded 5 minutes "
                                     f"later and were not retried (Queue shows {shown}); "
                                     + ("they uploaded after Studio was closed and opened again" if resumed else "they did NOT upload after Studio was closed and opened again"))
        # The offline rule ("nothing uploaded yet") is judged on THIS audition only: earlier online auditions of a mixed run are uploaded.
        problems = oracle.check(state["pk"], uploaded=None)
        if offline:
            problems += oracle.check(audition_pk, uploaded=False)
        if problems:
            raise AssertionError("; ".join(problems))
    return test


def drop_and_reconnect(context, seconds=25):
    """The internet goes away in the middle of a take and comes back `seconds` later (Test build simulated offline: only Studio's own
    network calls fail)."""
    def flip():
        context.log(f"the internet drops in the middle of the take (back in {seconds} s)")
        faults.offline(True)
        time.sleep(seconds)
        faults.offline(False)
        context.log("the internet is back")
    return flip


STALL_SECONDS = 300           # no upload progress for this long = the Queue is stuck (a finding), not "still busy"


def settle_test(options, state):
    def test(context):
        faults.offline(False)
        app = getattr(context, "app", None)
        if app is not None:
            # A failed audition can leave takes in Audition Mode that were never finalized: they can never upload. Keep and finalize
            # them (nothing is deleted) so the wait below measures the real upload, not a state the tester left behind.
            try:
                if app.exists("capture.finalize"):
                    context.log("an audition was left open by an earlier step: finalizing it so its takes are kept and uploaded")
                    driver.finalize(app, context.log)
                driver.clear_leftovers(app, context.log)
            except Exception as error:
                context.log(f"(could not finalize the leftover audition: {error})")
        context.log("online again: waiting for the Queue to finish uploading")
        end = time.time() + 3600
        last_count, last_change, last_log = None, time.time(), 0.0
        left = []
        while time.time() < end:
            left = not_uploaded_since(state["pk"])
            if not left:
                counts = queue_counts(context)
                if counts is None or not counts["pending"]:
                    break                                    # the database AND the app agree: everything is uploaded
                context.log(f"the database says all uploaded but the Queue still shows {counts['pending']} pending: waiting")
            if time.time() - last_log > 60:
                last_log = time.time()
                context.log(f"waiting for uploads: {len(left)} clip(s) not uploaded in the database; Queue shows {queue_counts(context)}")
            if len(left) != last_count:
                last_count, last_change = len(left), time.time()
            elif time.time() - last_change > STALL_SECONDS:
                shown = queue_counts(context)
                items = [m.get("folder", "")[-70:] for m in left[:3]]
                resumed = relaunch_to_unstick(context, state["pk"])
                raise AssertionError(f"the upload Queue is stuck: {len(left)} item(s) did not upload and nothing changed for "
                                     f"{STALL_SECONDS // 60} minutes (online); Queue shows {shown}; first items: {items}; "
                                     + ("the uploads RESUMED after Studio was closed and opened again" if resumed
                                        else "they did NOT resume after Studio was closed and opened again"))
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
