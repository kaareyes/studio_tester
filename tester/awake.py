"""Keeps the Mac awake while a test runs (an overnight run must not stop because the Mac went to sleep): macOS `caffeinate` holds the
display, the system and the disk awake. It is tied to this program (`-w <pid>`): if the tester ends in any way, caffeinate ends too."""
import os
import subprocess


def start():
    """Returns the caffeinate process, or None when it cannot be started (a run then goes on without it)."""
    try:
        return subprocess.Popen(["/usr/bin/caffeinate", "-dimsu", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
