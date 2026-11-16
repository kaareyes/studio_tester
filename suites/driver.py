"""Drives ONE session screen the way a casting user does, by control name: add talents to the audition, photo, slate, group image,
Audition Mode, record, rating, Back, Finalize. Every wait is for a real state (a control appears, a camera event is logged), not a
fixed delay. Used by Realistic, Chaos, Recovery, Network, Long video and Soak."""
import random
import time

from tester import ax, faults
from tester.ax import ControlNotFound
from suites import common


class StepFailed(AssertionError):
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

def clear_leftovers(app, log):
    """Start from the session screen with an empty audition: close popups, leave Audition Mode, clear a group left from before."""
    for _ in range(4):
        if app.exists("alert.dialog"):
            for button in ("alert.leftButton", "alert.closeButton", "alert.okButton"):
                if app.exists(button):
                    app.press(button)
                    break
            time.sleep(1)
        elif app.exists("resume.dialog"):
            log("a Resume dialog was open: closing it")
            app.press("resume.close" if app.exists("resume.close") else "resume.cancel")
            time.sleep(1)
        elif in_capture(app):
            log("still in Audition Mode: going Back")
            app.press("capture.back")
            time.sleep(3)
        else:
            break
    if app.exists("session.clearGroup"):
        log("a group was left in the audition: Clear Group")
        app.press("session.clearGroup")
        time.sleep(2)
        if app.exists("alert.rightButton"):
            app.press("alert.rightButton")
            time.sleep(2)
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


def wait_label(kind, after, timeout=25):
    """Waits for the camera-label event of a finished photo / video ('-> photo' / '-> video'). Returns the label."""
    end = time.time() + timeout
    while time.time() < end:
        for line in faults.events(10**6)[after:]:
            if "camera label" in line and ("-> " + kind) in line:
                return line.split("camera label ")[1].split(" ->")[0]
        time.sleep(0.5)
    return None


def take_photo(app, schedule_id, log):
    before = _event_count()
    app.press("session.talent.photo." + schedule_id)
    label = wait_label("photo", before)
    if label is None:
        raise StepFailed("a talent photo was not taken (no photo finished in 25 s)")
    return label


def record_slate(app, schedule_id, seconds, log):
    before = _event_count()
    app.press("session.talent.slate." + schedule_id)
    time.sleep(seconds)
    app.press("session.talent.slate." + schedule_id)
    label = wait_label("video", before)
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


def record_take(app, seconds, log, on_midpoint=None):
    """Record, wait `seconds` (calling `on_midpoint` halfway, e.g. to drop the network), Stop. Returns the label burned into the take."""
    before = _event_count()
    app.press("capture.record")
    if on_midpoint:
        time.sleep(seconds / 2)
        on_midpoint()
        time.sleep(seconds / 2)
    else:
        time.sleep(seconds)
    stop = "capture.stop" if app.exists("capture.stop") else "capture.fullscreenStop"
    app.press(stop)
    label = wait_label("video", before, timeout=60 + seconds * 0.05)
    if label is None:
        raise StepFailed(f"a {seconds} s take did not stop and save")
    if not app.exists("capture.finalize"):
        raise StepFailed("the Finalize button is gone after a take")
    return label


def rate_first_take(app, rnd):
    stars = [e for e in app.find_all(prefix="capture.take.rating.")]
    if not stars:
        return None
    frame = app.frame(stars[0])
    if not frame:
        return None
    x, y, width, height = frame
    pick = rnd.randint(1, 5)
    ax.click(x + width * (pick - 0.5) / 5, y + height / 2)
    time.sleep(1)
    return pick


def go_back(app, log):
    app.press("capture.back")
    if not wait_enter_ready(app, timeout=15):
        raise StepFailed("Back did not return to the audition with its talents")


def finalize(app, log, timeout=90):
    """Presses Finalize, answers the 'no group image' confirmation if it shows, and waits until the session screen is back.
    Returns the seconds it took (the confirmation's own time is not counted)."""
    app.press("capture.finalize")
    began = time.time()
    confirmed = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app.exists("alert.dialog") and app.exists("alert.rightButton") and not confirmed:
            app.press("alert.rightButton")
            confirmed = True
            began = time.time()
        if not in_capture(app) and app.exists("session.tab.scheduled"):
            return round(time.time() - began, 1)
        time.sleep(0.5)
    raise StepFailed(f"the session screen did not come back {timeout} s after Finalize")


# ---------------------------------------------------------------- a whole random audition

def random_audition(app, rnd, log, take_seconds, flaky=None, max_talents=3, extras=None):
    """One realistic audition. `take_seconds()` returns the length of the next take. Returns what was recorded:
    {'talents', 'takes', 'photos', 'slates', 'labels', 'seconds_finalize', 'extras'}."""
    extras = extras if extras is not None else []
    clear_leftovers(app, log)
    wanted = rnd.choices([1, 2, 3], weights=[50, 35, 15])[0]
    added = add_talents(app, rnd, min(wanted, max_talents), log)
    if added == 0:
        raise StepFailed("no scheduled talent can be added in this session")
    labels, photos, slates = [], 0, 0
    cards = group_cards(app)
    for schedule_id in cards:
        if rnd.random() < 0.6:
            labels.append("P:" + take_photo(app, schedule_id, log))
            photos += 1
        if rnd.random() < 0.5:
            labels.append("S:" + record_slate(app, schedule_id, rnd.randint(3, 7), log))
            slates += 1
    if added > 1 and rnd.random() < 0.7:
        labels.append("G:" + group_image(app, log))
        photos += 1
    enter_audition_mode(app)
    if rnd.random() < 0.15:
        extras.append("back")
        go_back(app, log)
        enter_audition_mode(app)
    takes = rnd.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    for number in range(1, takes + 1):
        midpoint = None
        if flaky and rnd.random() < 0.3:
            midpoint = flaky
            extras.append("net-flip-mid-take")
        seconds = take_seconds()
        labels.append("T:" + record_take(app, seconds, log, on_midpoint=midpoint))
        extras.append(f"take{number}:{seconds}s")
    rating = rate_first_take(app, rnd)
    if rating:
        extras.append(f"rate{rating}")
    seconds_finalize = finalize(app, log)
    return {"talents": added, "takes": takes, "photos": photos, "slates": slates, "labels": labels,
            "seconds_finalize": seconds_finalize, "extras": extras}
