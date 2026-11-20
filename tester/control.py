"""Pause and cancel for a running test, from the keyboard (hold Esc) or from the page (Pause / Continue / Cancel testing).

How it works: the test runs in its own thread. Every real click, scroll and key press the tester sends, and every wait, first passes a
checkpoint. While the run is PAUSED the checkpoint holds the test where it is (nothing more is clicked; a take that is already recording
keeps recording, a camera cannot be paused). When the run is CANCELLED the checkpoint raises StopRun, which unwinds the test at once
(the cleanup code of the tests still runs: faults off, offline off, camera label off). Cancel therefore takes effect within a fraction of
a second, not at the end of a 30 minute take."""
import threading
import time as _time

_real_sleep = _time.sleep
_cond = threading.Condition()
_state = {"paused": False, "cancel": False, "thread": None, "since": None, "reason": ""}
HOLD_SECONDS = 3.0          # how long Esc must be held to pause (a tap or a short hold never pauses)
ESC_KEYCODE = 53


class UiStep(Exception):
    """A screen step failed because of a flaky screen, a crash or a stuck step (not because of a data finding). Steps raising it are retried."""


class StepInterrupted(UiStep):
    """Raised inside the running step by the watchdog: Studio crashed, or the step made no progress for too long."""


class StopRun(BaseException):
    """The person cancelled the run. A BaseException on purpose: the tests' own `except Exception` must not swallow it."""


def begin(thread=None):
    """A run starts: the checkpoint applies to this thread only (server and monitor threads are never paused)."""
    with _cond:
        _state.update(paused=False, cancel=False, thread=thread or threading.current_thread(), since=None, reason="", interrupt="")
    _time.sleep = _sleep_for_run


def end():
    with _cond:
        _state.update(paused=False, cancel=False, thread=None, since=None, reason="")
        _cond.notify_all()
    _time.sleep = _real_sleep


def _is_run_thread():
    return _state["thread"] is not None and threading.current_thread() is _state["thread"]


def pause(reason="paused"):
    with _cond:
        if _state["thread"] is None or _state["cancel"] or _state["paused"]:
            return False
        _state.update(paused=True, since=_time.time(), reason=reason)
        return True


def resume():
    with _cond:
        was = _state["paused"]
        _state.update(paused=False, since=None, reason="")
        _cond.notify_all()
        return was


def cancel():
    with _cond:
        if _state["thread"] is None:
            return False
        _state.update(cancel=True, paused=False)
        _cond.notify_all()
        return True


def is_paused():
    return bool(_state["paused"])


def is_cancelled():
    return bool(_state["cancel"])


def info():
    return {"paused": bool(_state["paused"]), "reason": _state["reason"],
            "paused_for": int(_time.time() - _state["since"]) if _state["since"] else 0, "cancelling": bool(_state["cancel"])}


def checkpoint():
    """Called before every click, scroll, key press and wait of the test thread. Blocks while paused; raises StopRun when cancelled."""
    if not _is_run_thread():
        return
    with _cond:
        while _state["paused"] and not _state["cancel"]:
            _cond.wait(0.5)
        if _state["cancel"]:
            raise StopRun()
        reason = _state.get("interrupt")
        if reason:
            _state["interrupt"] = ""                    # once: the retry that follows starts clean
            raise StepInterrupted(reason)


def interrupt(reason):
    """The watchdog stops the step that is running right now (it raises StepInterrupted at its next click, wait or scroll)."""
    with _cond:
        _state["interrupt"] = reason


def sleep(seconds):
    """A wait that notices pause and cancel (a 30 minute take can be cancelled at once). Time spent paused does not count."""
    end_at = _time.time() + max(0.0, seconds)
    while True:
        blocked_from = _time.time()
        checkpoint()
        end_at += _time.time() - blocked_from              # a pause does not eat the wait
        remaining = end_at - _time.time()
        if remaining <= 0:
            return
        _real_sleep(min(0.25, remaining))


def _sleep_for_run(seconds):
    """Installed as time.sleep while a run is active: the test thread gets the interruptible sleep, every other thread the normal one."""
    if _is_run_thread():
        sleep(seconds)
    else:
        _real_sleep(seconds)


class HoldTracker:
    """Decides when a key has been held long enough. update(pressed, now) returns True once per hold (it must be released to fire again)."""

    def __init__(self, hold=HOLD_SECONDS):
        self.hold = hold
        self.since = None
        self.fired = False

    def update(self, pressed, now):
        if not pressed:
            self.since, self.fired = None, False
            return False
        if self.since is None:
            self.since = now
        if not self.fired and now - self.since >= self.hold:
            self.fired = True
            return True
        return False


def esc_pressed():
    """True while the Esc key is physically held, whichever app is in front (the system's keyboard state; macOS needs the Input Monitoring
    permission for the program to see keys typed into other apps: see keyboard_watch_allowed)."""
    try:
        import Quartz
        return bool(Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateHIDSystemState, ESC_KEYCODE)
                    or Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, ESC_KEYCODE))
    except Exception:
        return False


def watch_esc(is_running, on_hold, stop=lambda: False, pressed=esc_pressed, clock=_time.time, interval=0.1):
    """Background loop: while a test runs, holding Esc for HOLD_SECONDS calls on_hold()."""
    tracker = HoldTracker()
    while not stop():
        try:
            if is_running() and tracker.update(pressed(), clock()):
                on_hold()
            elif not is_running():
                tracker.update(False, clock())
        except Exception as error:               # one failure (a sound, the browser) must never end the watcher: Esc has to keep working
            print(f"(Esc watcher: {type(error).__name__}: {error})")
        _real_sleep(interval)


def esc_selfcheck(front_app="Finder", hold=HOLD_SECONDS + 0.6, wait=4.0, post=None, front=None, paused=None, resume_fn=None, sleep=None, clock=_time.time):
    """Proves the Esc pause end to end, from inside a run: another app is brought to the front, Esc is held for a little over the hold time
    with real keyboard events, and the run must pause by itself (the same path a person's held key takes). Then it continues.
    Call it BETWEEN steps only (nothing is clicking then) and from the run thread: it waits with the real sleep, so the pause it causes
    does not block it. Returns (ok, sentence). The key is always released."""
    sleep = sleep or _real_sleep
    paused = paused or is_paused
    resume_fn = resume_fn or resume
    front = front or (lambda name: _bring_to_front(name))
    if post is None:
        def post(down):
            import Quartz
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateKeyboardEvent(None, ESC_KEYCODE, down))
    if paused():
        return False, "the run was already paused: the Esc self-check was skipped"
    try:
        front(front_app)
        sleep(1.0)
        began = clock()
        post(True)
        while clock() - began < hold:
            sleep(0.4)
            post(True)                                     # key repeat, like a held key
    finally:
        post(False)
    end = clock() + wait
    while clock() < end and not paused():
        sleep(0.25)
    ok = bool(paused())
    if ok:
        resume_fn()
        return True, f"holding Esc for {hold:.1f} s with {front_app} in front paused the run by itself; it continues"
    return False, (f"holding Esc for {hold:.1f} s with {front_app} in front did NOT pause the run: check System Settings > Privacy & Security > "
                   "Input Monitoring for the program that runs the tester")


def _bring_to_front(name):
    import subprocess
    subprocess.run(["/usr/bin/osascript", "-e", f'tell application "System Events" to set frontmost of first process whose name is "{name}" to true'],
                   capture_output=True, timeout=15)


def release_stuck_esc():
    """A synthetic Esc that was pressed but never released (a program that was killed in the middle of a key press) keeps the system believing
    Esc is held: every run would pause 3 seconds after it starts. A key-up for Esc is harmless when it is not held, so one is sent when the
    tester starts. Returns True when Esc was down."""
    try:
        import Quartz
        down = bool(Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateHIDSystemState, ESC_KEYCODE))
        if down:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateKeyboardEvent(None, ESC_KEYCODE, False))
        return down
    except Exception:
        return False


def keyboard_watch_allowed():
    """True when macOS lets this program read the keyboard state of OTHER apps (Input Monitoring). Without it the Esc key is not seen
    while another app is in front. Asks once (the system shows its own question) when it is not allowed yet."""
    try:
        import Quartz
        if Quartz.CGPreflightListenEventAccess():
            return True
        Quartz.CGRequestListenEventAccess()
        return bool(Quartz.CGPreflightListenEventAccess())
    except Exception:
        return True


def start_esc_watcher(is_running, on_hold):
    thread = threading.Thread(target=watch_esc, args=(is_running, on_hold), daemon=True)
    thread.start()
    return thread
