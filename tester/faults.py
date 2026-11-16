"""Python access to scripts/fault_injection/fault.sh (Test build only): simulated offline, upload cuts, crash points, camera labels,
camera switch. `reset_all()` puts the Test app back to a normal state and is called after every run, even a stopped one."""
import os
import subprocess

from . import runner

SCRIPT = os.path.join(os.path.dirname(runner.ROOT), "scripts", "fault_injection", "fault.sh")
PRESETS = os.path.join(os.path.dirname(runner.ROOT), "scripts", "fault_injection", "presets")
EVENTS = os.path.expanduser("~/Library/Application Support/com.castingapp.studio-test/FaultInjection/events.log")


def _run(*args, timeout=20):
    result = subprocess.run(["/bin/bash", SCRIPT] + [str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    return (result.stdout + result.stderr).strip()


def offline(on):
    return _run("offline", "on" if on else "off")


def is_offline():
    return "ON" in _run("offline")


def label(text="", start=None):
    """Burns a label into every camera frame. 'T-#' counts up by itself; no text removes it."""
    return _run("label", text, *([start] if (start is not None and text) else [])) if text else _run("label")


def camera(name=None):
    return _run("camera", name) if name else _run("camera")


def list_presets():
    try:
        return sorted(f for f in os.listdir(PRESETS) if f.endswith(".json"))
    except OSError:
        return []


def set_preset(name):
    path = os.path.join(PRESETS, name)
    return _run("set", path)


def clear():
    return _run("clear")


def events(last=200):
    try:
        with open(EVENTS, errors="replace") as handle:
            return handle.read().splitlines()[-last:]
    except OSError:
        return []


def reset_events():
    return _run("reset-events")


def reset_all():
    """No faults, online, no label: the app is left the way a person would use it."""
    for step in (clear, lambda: offline(False), label, lambda: _run("enable")):
        try:
            step()
        except Exception:
            pass
