"""Drives ONE session screen the way a casting user does, by control name: add talents to the audition, photo, slate, group image,
Audition Mode, record, rating, Back, Finalize. Every wait is for a real state (a control appears, a camera event is logged), not a
fixed delay. Used by Realistic, Chaos, Recovery, Network, Long video and Soak."""
import random
import time

from tester import ax, faults
from tester.ax import ControlNotFound
from tester.runner import UiStep
from suites import common


class StepFailed(AssertionError, UiStep):
    """A step did not do what a person would see (a plain sentence for the report)."""


def name_of(element):
    return ax._attr(element, "AXIdentifier") or ""


def tail_id(element):
    return name_of(element).split(".")[-1]


# ---------------------------------------------------------------- reading the session screen

def addable_talents(app):
    """[(talent id, add button)] of the scheduled talents that can still be added to the audition."""
    out = []
    for element in app.find_all(prefix="session.talent.add."):
        if len(tail_id(element)) >= 32:
            out.append((tail_id(element), element))
    return out


def group_cards(app):
    """Schedule ids of the talents already in the audition (their cards on the right)."""
    return [tail_id(e) for e in app.find_all(prefix="session.talent.cardName.") if len(tail_id(e)) >= 32]


def enter_ready(app):
    return app.exists("session.enterAuditionMode")


def wait_enter_ready(app, timeout=12):
    try:
        app.wait_for("session.enterAuditionMode", timeout=timeout)
        return True
    except ControlNotFound:
        return False


def in_capture(app):
    return app.exists("capture.record") or app.exists("capture.finalize")


# ---------------------------------------------------------------- the audition steps

CONFIRM_WORDS = ("proceed", "yes", "confirm", "continue", "finalize", "ok")      # never "delete", "remove", "discard"
CANCEL_WORDS = ("cancel", "no", "not now", "later", "back", "dismiss")


def alert_button(app, words):
    """The name of the first pop-up button whose WORDS are in `words` (the left/right place of Cancel and Proceed differs per pop-up:
    found live, the Finalize pop-up has Proceed on the left), or None."""
    for word in words:
        name = "alert.button." + word.replace(" ", "_")
        if app.exists(name):
            return name
    return None


def alert_text(app):
    """(title, message) of the pop-up on screen."""
    def read(name):
        try:
            return (app.text(app.find(name)) or "").strip()
        except ControlNotFound:
            return ""
    return read("alert.title"), read("alert.message")


def answer_alert_safely(app, log):
    """Answers a pop-up the tester did not cause, in the one way that cannot destroy anything. Returns 'resumed' or 'answered'.
    The Resume Audition pop-up is the dangerous one: its X (`alert.closeButton`) ABANDONS the interrupted audition (the app removes its
    record), so the X is never pressed; Proceed brings the audition back. Any other yes/no pop-up gets its left button (Cancel/No),
    a plain pop-up gets OK. The X of any pop-up is never used."""
    title, message = alert_text(app)
    lowered = title.lower()
    if "resume" in lowered:
        if "browse" in lowered:
            raise StepFailed("a 'Resume Browse Audition' pop-up is on screen. The tester does not touch it: its X deletes the audition and "
                             "Proceed opens a Browse edit. Choose Proceed or X yourself, then run again.")
        if not app.exists("alert.okButton"):
            raise StepFailed("a 'Resume Audition' pop-up is on screen without a Proceed button: left alone (its X would delete the audition)")
        log("a 'Resume Audition' pop-up was open: pressed Proceed (the interrupted audition is kept; the X would have deleted it)")
        app.press("alert.okButton")
        return "resumed"
    cancel = alert_button(app, CANCEL_WORDS)
    if cancel:
        log(f"an unexpected pop-up ('{title}') was open: pressed its Cancel/No button")
        app.press(cancel)
        return "answered"
    if app.exists("alert.okButton"):
        log(f"a pop-up ('{title}') was open: pressed OK")
        app.press("alert.okButton")
        return "answered"
    raise StepFailed(f"an unexpected pop-up is on screen ('{title}': {message[:80]}) with no safe button: left alone")


RESUMED = {"pending": False}      # a resumed audition has not been finalized yet (survives a cleanup that was cut short)


SAFE_SHEET_BUTTONS = ("stop & save", "stop and save", "save", "ok")       # the answers that keep everything
SHEET_CANCEL_BUTTONS = ("cancel", "no", "not now")


def answer_native_sheet(app, log):
    """Answers a native macOS sheet over Studio the way that loses nothing: 'Stop Recording?' gets 'Stop & Save' (the take is saved); any
    other sheet gets Cancel/No when it has one. Returns True when a sheet was answered, False when there is none. A sheet it cannot answer
    safely stops the step (a screen failure) instead of being guessed."""
    finder = getattr(app, "native_sheet", None)
    sheet = finder() if finder else None
    if not sheet:
        return False
    texts = {button.strip().lower(): element for button, element in sheet["buttons"]}
    title = sheet["title"]
    wanted = SAFE_SHEET_BUTTONS if "recording" in title.lower() else SHEET_CANCEL_BUTTONS
    for word in wanted:
        if word in texts:
            log(f"a macOS sheet ('{title}') was open: pressed '{word.title()}'")
            app.press_element(texts[word])
            time.sleep(2)
            return True
    raise StepFailed(f"a macOS sheet ('{title}: {sheet['message'][:60]}') is open with buttons {list(texts)}: no safe answer, left alone")


def clear_leftovers(app, log):
    """Gets back to the session screen WITHOUT destroying anything that can be recovered: a pop-up is answered safely (see
    answer_alert_safely), a take that is still recording is stopped and saved, a resumed audition is finalized so its takes are kept and
    uploaded, and Audition Mode is left with Back (a normal audition keeps its talents and takes). It never presses Clear Group
    (that deletes the group's saved slates and photos) and never an X."""
    resumed = RESUMED["pending"]            # a Resume pop-up answered by an earlier try that did not finish its cleanup
    stop_presses = 0
    for _ in range(8):
        if answer_native_sheet(app, log):
            continue
        if app.exists("alert.dialog"):
            if answer_alert_safely(app, log) == "resumed":
                resumed = RESUMED["pending"] = True
                try:
                    app.wait_for("capture.record", timeout=25)           # the resumed Audition Mode needs a moment to appear
                except ControlNotFound:
                    pass
            time.sleep(2)
            continue
        if slate_is_recording(app) and not SLATE_RECORDING["id"]:
            SLATE_RECORDING["id"] = _slate_talent_on_panel(app)       # recording from before this tester started: find whose slate it is
        if SLATE_RECORDING["id"] and slate_is_recording(app) and app.exists("session.talent.slate." + SLATE_RECORDING["id"]):
            log("a slate is still recording (a step was interrupted): stopping it, it is saved")
            app.press("session.talent.slate." + SLATE_RECORDING["id"])
            SLATE_RECORDING["id"] = None
            time.sleep(4)
            continue
        if app.exists("capture.stop") or app.exists("capture.fullscreenStop"):
            stop_presses += 1
            if stop_presses > 4:
                # Found live (chaos: camera switched mid-take): the Stop button did nothing and the take ran for 10+ minutes. Studio is
                # closed (Cmd-Q, then that one pid) so the next step starts clean; the take is restored from the journal on the next start.
                from tester import control
                from . import realistic, recover
                log("INCIDENT: the Stop button does nothing and the recording keeps running: closing Studio so the run can go on")
                recover.EXPECTED["gone"] = False
                realistic.quit_studio(patience=10)
                raise control.StepInterrupted("a recording could not be stopped (Stop did nothing 4 times): Studio was closed")
            log("a take is still recording: stopping it (it is saved) instead of going Back")
            app.press("capture.stop" if app.exists("capture.stop") else "capture.fullscreenStop")
            time.sleep(4)
            continue
        if in_capture(app):
            has_takes = bool(app.find_all(prefix="capture.take.card."))
            if app.exists("capture.finalize") and (resumed or has_takes):
                # Takes that exist are finalized (kept AND uploaded), never left behind by going Back: found live, an audition left that
                # way keeps its clips on this Mac and they are never uploaded.
                log("the audition has takes: it is finalized so they are kept and uploaded" + (" (it was resumed after a crash)" if resumed else ""))
                finalize(app, log)
                resumed = RESUMED["pending"] = False
                continue
            log("still in Audition Mode: going Back (a normal audition keeps its talents and takes)")
            app.press("capture.back")
            time.sleep(3)
            continue
        break
    if in_capture(app):
        raise StepFailed("Audition Mode would not close: the tester stopped before touching anything else")
    if not app.exists("session.tab.scheduled") and not app.exists("session.title"):
        raise StepFailed("not on a session screen")


def add_talents(app, rnd, count, log):
    """Presses '+' on `count` random scheduled talents. Returns how many were really added."""
    added = 0
    for _ in range(count):
        candidates = addable_talents(app)
        if not candidates:
            break
        talent_id, _ = rnd.choice(candidates)
        app.press("session.talent.add." + talent_id)
        time.sleep(1.5)
        added += 1
    if added and not wait_enter_ready(app):
        raise StepFailed(f"{added} talent(s) were added but Enter Audition Mode never became available")
    log(f"talents added: {added}")
    return added


def _event_count():
    return len(faults.events(10**6))


def save_wait_seconds(take_seconds):
    """How long Studio gets to finish saving a take after Stop. Found live: a 59 s take needed about 80 s to be processed (and a 37 s take
    more than 60 s) while other work ran, so the old 60 s + 5% gave up on takes that were still being saved. Roughly 2 minutes plus 60% of
    the take; a take that really never saves is still reported, and a recording that cannot be stopped is caught by the stuck-step check."""
    return min(3600, 120 + take_seconds * 0.6)


def wait_label(kind, after, timeout=25, cap=900):
    """Waits for the camera-label event of a finished photo / video ('-> photo' / '-> video'). Returns the label.
    The time is flexible (tester/patience.py): after `timeout` it keeps waiting, up to `cap` more seconds, while Studio is busy working (a
    long take is still being processed) and stops as soon as Studio is idle (a hung or finished Studio)."""
    from tester import activity, patience
    wait = patience.for_studio(timeout, cap=cap, extend=20)
    activity.set(f"waiting for Studio to finish saving the {kind} (up to {int(timeout)} s, longer while Studio is busy)")
    while True:
        for line in faults.events(10**6)[after:]:
            if "camera label" in line and ("-> " + kind) in line:
                activity.clear()
                return line.split("camera label ")[1].split(" ->")[0]
        if wait.expired():
            activity.clear()
            return None
        time.sleep(0.5)


def can_take_photo(app, schedule_id):
    """A talent that already has a photo (a callback, or one taken earlier) only shows it when the icon is pressed: no new photo."""
    return not app.exists("session.talent.photoDone." + schedule_id)


def can_record_slate(app, schedule_id):
    """The slate control is not drawn for stitched-video projects."""
    return app.exists("session.talent.slate." + schedule_id)


def talent_name(app, schedule_id):
    """The talent's name as the screen shows it (first line of the card text), cleaned for a camera label; '' when it cannot be read."""
    for identifier in ("capture.talent." + schedule_id, "session.talent." + schedule_id):
        try:
            text = (app.text(app.find(identifier)) or "").strip()
        except Exception:
            continue
        first = text.splitlines()[0] if text else ""
        cleaned = "".join(ch for ch in first if ch.isalnum() or ch in " -'").strip()
        if cleaned:
            return cleaned[:18]
    return ""


def named_label(kind, name):
    """'P-# Mika Cole' for a photo, 'S-# Mika Cole' for a slate: the picture shows who it is of."""
    return f"{kind}-# {name}".strip() if name else ""


def take_photo(app, schedule_id, log):
    before = _event_count()
    text = named_label("P", talent_name(app, schedule_id))
    if text:
        faults.temporary_label(text)                 # the burned-in label carries the talent's name for this one photo
    try:
        app.press("session.talent.photo." + schedule_id)
        label = wait_label("photo", before)
    finally:
        if text:
            faults.restore_label()
    if label is None:
        raise StepFailed("a talent photo was not taken (no photo finished in 25 s)")
    return label


SLATE_RECORDING = {"id": None}     # the talent whose slate was started and not yet stopped (an interrupted step leaves it recording)


def slate_is_recording(app):
    """The slate timer in the side panel shows a time other than 0:00 while a slate is rolling."""
    if not app.exists("mediaSide.slateTimer"):
        return False
    text = (app.text(app.find("mediaSide.slateTimer")) or "").strip()
    return bool(text) and set(text) - set("0:. ")


def _slate_talent_on_panel(app):
    """The schedule id of the talent named in the side panel (the one whose slate is open), or None."""
    if not app.exists("mediaSide.selectedTalentName"):
        return None
    shown = (app.text(app.find("mediaSide.selectedTalentName")) or "").strip().lower()
    for element in app.find_all(prefix="session.talent.slate."):
        schedule_id = name_of(element).rsplit(".", 1)[-1]
        name = (talent_name(app, schedule_id) or "").lower()
        if shown and name and (name in shown or shown in name):
            return schedule_id
    return None


def stop_running_recordings(app, log):
    """First thing a run does (and before every retry): a take or a slate that is still recording from before (an earlier run, a crash, a
    cancelled test) is stopped and saved. It greys out the navigation, so nothing else can work until it is stopped. Returns how many were stopped."""
    stopped = 0
    slate_pressed = False          # the slate button is a toggle: pressed once at most, a stale timer must never make it start a new slate
    for _ in range(6):
        if app.exists("capture.stop") or app.exists("capture.fullscreenStop"):
            log("Studio was still recording a take: stopping it (it is saved) before the test starts")
            app.press("capture.stop" if app.exists("capture.stop") else "capture.fullscreenStop")
            stopped += 1
            time.sleep(4)
            continue
        if not slate_pressed and slate_is_recording(app):
            schedule_id = SLATE_RECORDING["id"] or _slate_talent_on_panel(app)
            if schedule_id and app.exists("session.talent.slate." + schedule_id):
                log("Studio was still recording a slate: stopping it (it is saved) before the test starts")
                app.press("session.talent.slate." + schedule_id)
                SLATE_RECORDING["id"] = None
                slate_pressed = True
                stopped += 1
                time.sleep(4)
                continue
        break
    return stopped


def record_slate(app, schedule_id, seconds, log):
    before = _event_count()
    text = named_label("S", talent_name(app, schedule_id))
    if text:
        faults.temporary_label(text)
    try:
        SLATE_RECORDING["id"] = schedule_id
        app.press("session.talent.slate." + schedule_id)
        time.sleep(seconds)
        app.press("session.talent.slate." + schedule_id)
        SLATE_RECORDING["id"] = None
        label = wait_label("video", before)
    finally:
        if text:
            faults.restore_label()
    if label is None:
        raise StepFailed("a slate did not finish recording")
    return label


def group_image(app, log):
    before = _event_count()
    app.press("session.groupImage.photo")
    label = wait_label("photo", before)
    if label is None:
        raise StepFailed("the group image was not taken")
    return label


def enter_audition_mode(app):
    app.press("session.enterAuditionMode")
    try:
        app.wait_for("capture.record", timeout=25)
    except ControlNotFound:
        raise StepFailed("Audition Mode did not open (no Record button)")


def recording_started(app, timeout=8):
    """True once the app shows that it is recording (timer, indicator or the Stop button)."""
    from tester import patience
    wait = patience.for_studio(timeout, cap=20, extend=5)
    while True:
        if any(app.exists(n) for n in ("capture.recordingTimer", "capture.recordingIndicator", "capture.stop", "capture.fullscreenStop")):
            return True
        if wait.expired():
            return False
        time.sleep(0.4)


def record_take(app, seconds, log, on_midpoint=None):
    """Record, wait `seconds` (calling `on_midpoint` halfway, e.g. to drop the network), Stop. Returns the label burned into the take.
    Record is ignored by the app while no talent is selected: that is detected (and one talent selected) instead of failing later."""
    before = _event_count()
    app.press("capture.record")
    if not recording_started(app):
        selectors = app.find_all(prefix="capture.talent.select.")
        if selectors:
            log("Record did nothing: selecting a talent first, then Record again")
            app.press(name_of(selectors[0]))
            time.sleep(1)
            app.press("capture.record")
        if not recording_started(app):
            raise StepFailed("Record did nothing (no talent is selected in Audition Mode, or the camera is not ready)")
    def wait(total):
        """Waits `total` seconds, one log line a minute: the watchdog treats a silent step as stuck, a long take is not silent."""
        from tester import activity
        activity.set(f"recording a take ({int(seconds)} s)")
        end = time.time() + total
        while True:
            remaining = end - time.time()
            if remaining <= 0:
                return
            time.sleep(min(60, remaining))
            if end - time.time() > 1:
                log(f"recording: {int(seconds - (end - time.time()))} of {int(seconds)} s")

    if on_midpoint:
        wait(seconds / 2)
        on_midpoint()
        wait(seconds / 2)
    else:
        wait(seconds)
    stop = "capture.stop" if app.exists("capture.stop") else "capture.fullscreenStop"
    app.press(stop)
    label = wait_label("video", before, timeout=save_wait_seconds(seconds))
    if label is None:
        raise AssertionError(f"a {seconds} s take did not stop and save")   # a finding, never retried
    try:
        app.wait_for("capture.finalize", timeout=15)       # the screen is still redrawing right after the take saved
    except ControlNotFound:
        raise StepFailed("the Finalize button is gone after a take (waited 15 s)")
    return label


def favorite_first_take(app):
    """The control on a take card is a Favorite heart (one toggle), not a 1-5 rating: press its centre once. Returns True when pressed."""
    hearts = app.find_all(prefix="capture.take.rating.")
    if not hearts:
        return False
    frame = app.frame(hearts[0])
    if not frame:
        return False
    x, y, width, height = frame
    ax.click(x + width / 2, y + height / 2)
    time.sleep(1)
    return True


def go_back(app, log):
    app.press("capture.back")
    if not wait_enter_ready(app, timeout=15):
        raise StepFailed("Back did not return to the audition with its talents")


def finalize(app, log, timeout=90):
    """Presses Finalize, answers the 'Finalize Audition' confirmation (its Proceed) when it shows, and waits until the session screen is
    back. Returns the seconds it took (the confirmation's own time is not counted). Pop-ups are read by title: only the Finalize
    confirmation gets Proceed. A plain warning (for example a large file) gets OK and the wait goes on; any other yes/no pop-up is
    cancelled and the step fails with its text, so nothing is confirmed by accident."""
    app.press("capture.finalize")
    began = time.time()
    confirmed = False
    from tester import patience
    from tester import activity
    wait = patience.for_studio(timeout, cap=600, extend=20)       # a big audition takes longer to finalize: wait while Studio is working
    activity.set("waiting for Finalize to finish (Studio leaves Audition Mode)")
    while not wait.expired():
        if app.exists("alert.dialog"):
            title, message = alert_text(app)
            # We just pressed Finalize: a yes/no pop-up whose title cannot be read is taken as its confirmation; a title that is readable
            # and says something else is not confirmed.
            confirm = alert_button(app, CONFIRM_WORDS)
            if ("finalize" in title.lower() or not title) and confirm and alert_button(app, CANCEL_WORDS) and not confirmed:
                app.press(confirm)                      # the Proceed of 'Finalize Audition' (it is the LEFT button of that pop-up)
                confirmed = True
                began = time.time()
            elif app.exists("alert.okButton") and not alert_button(app, CANCEL_WORDS):
                log(f"Finalize showed a warning ('{title}': {message[:80]}): pressed OK")
                app.press("alert.okButton")
                time.sleep(1)
            else:
                cancel = alert_button(app, CANCEL_WORDS)
                if cancel:
                    app.press(cancel)
                raise StepFailed(f"Finalize showed a pop-up the tester does not expect ('{title}': {message[:80]}): it was cancelled, nothing was confirmed")
        # Online Finalize returns to the session screen; offline it returns to the Sessions list (found live): both mean it is done.
        if not in_capture(app) and (app.exists("session.tab.scheduled") or app.exists("projects.search")):
            return round(time.time() - began, 1)
        time.sleep(0.5)
    raise StepFailed(f"Studio did not leave Audition Mode {timeout} s after Finalize (neither the session screen nor the sessions list came back)")


# ---------------------------------------------------------------- a whole random audition

def random_audition(app, rnd, log, take_seconds, flaky=None, max_talents=3, extras=None, takes=None, talents=None, flaky_always=False):
    """One realistic audition. `take_seconds()` returns the length of the next take. Returns what was recorded:
    {'talents', 'takes', 'photos', 'slates', 'labels', 'seconds_finalize', 'extras'}."""
    extras = extras if extras is not None else []
    clear_leftovers(app, log)
    wanted = talents or rnd.choices([1, 2, 3], weights=[50, 35, 15])[0]
    leftover = len(group_cards(app))
    if leftover:
        log(f"{leftover} talent(s) are already in the audition (left from before): they are kept and used, never cleared")
    added = add_talents(app, rnd, max(0, min(wanted, max_talents) - leftover), log) if leftover < wanted else 0
    cards = group_cards(app)
    if not cards:
        raise StepFailed("no scheduled talent can be added in this session")
    labels, photos, slates = [], 0, 0
    for schedule_id in cards:
        if rnd.random() < 0.6:
            if can_take_photo(app, schedule_id):
                labels.append("P:" + take_photo(app, schedule_id, log))
                photos += 1
            else:
                extras.append("photo-already-there")
        if rnd.random() < 0.5:
            if can_record_slate(app, schedule_id):
                labels.append("S:" + record_slate(app, schedule_id, rnd.randint(3, 7), log))
                slates += 1
            else:
                extras.append("no-slate-control")
    if len(cards) > 1 and rnd.random() < 0.7:
        labels.append("G:" + group_image(app, log))
        photos += 1
    enter_audition_mode(app)
    if rnd.random() < 0.15:
        extras.append("back")
        go_back(app, log)
        enter_audition_mode(app)
    takes = takes or rnd.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    for number in range(1, takes + 1):
        midpoint = None
        if flaky and (flaky_always or rnd.random() < 0.3):
            midpoint = flaky
            extras.append("net-flip-mid-take")
        seconds = take_seconds()
        labels.append("T:" + record_take(app, seconds, log, on_midpoint=midpoint))
        extras.append(f"take{number}:{seconds}s")
    if rnd.random() < 0.5 and favorite_first_take(app):
        extras.append("favorite")
    seconds_finalize = finalize(app, log)
    return {"talents": len(cards), "takes": takes, "photos": photos, "slates": slates, "labels": labels,
            "seconds_finalize": seconds_finalize, "extras": extras}
