"""What the script is doing RIGHT NOW (shown on the page, and written to the live log when it lasts): not just 'running' but 'waiting for Studio to
save the take', 'waiting for 3 clips to upload', 'recording a take (60 s)'. Set by the code that waits; read by the run state and the heartbeat."""
import threading
import time

_lock = threading.Lock()
_state = {"text": "", "since": 0.0}


def set(text):
    """Says what is being done/waited for now. The same text again does not restart the clock."""
    text = text or ""
    with _lock:
        if text != _state["text"]:
            _state["text"], _state["since"] = text, time.time()


def clear():
    set("")


def info(now=None):
    """{'text', 'seconds'}: what is going on and for how long (0 when nothing is announced)."""
    with _lock:
        text, since = _state["text"], _state["since"]
    return {"text": text, "seconds": int((now or time.time()) - since) if text else 0}
