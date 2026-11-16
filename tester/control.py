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


class StopRun(BaseException):
    """The person cancelled the run. A BaseException on purpose: the tests' own `except Exception` must not swallow it."""


def begin(thread=None):
    """A run starts: the checkpoint applies to this thread only (server and monitor threads are never paused)."""
    with _cond:
        _state.update(paused=False, cancel=False, thread=thread or threading.current_thread(), since=None, reason="")
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
    """True while the Esc key is physically held (the system's keyboard state; no special permission is needed to read it)."""
    try:
        import Quartz
        return bool(Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, ESC_KEYCODE))
    except Exception:
        return False


def watch_esc(is_running, on_hold, stop=lambda: False, pressed=esc_pressed, clock=_time.time, interval=0.1):
    """Background loop: while a test runs, holding Esc for HOLD_SECONDS calls on_hold()."""
    tracker = HoldTracker()
    while not stop():
        if is_running() and tracker.update(pressed(), clock()):
            on_hold()
        elif not is_running():
            tracker.update(False, clock())
        _real_sleep(interval)


def start_esc_watcher(is_running, on_hold):
    thread = threading.Thread(target=watch_esc, args=(is_running, on_hold), daemon=True)
    thread.start()
    return thread
