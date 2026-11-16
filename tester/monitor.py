"""Samples the Studio process (memory, CPU, open files) in the background while a run goes on, writes a CSV, and judges growth."""
import csv
import os
import subprocess
import threading
import time

from . import ax, runner


def sample(pid):
    """{'rss_mb', 'cpu', 'open_files'} for a process id, or None when it is gone."""
    out = subprocess.run(["/bin/ps", "-o", "rss=,%cpu=", "-p", str(pid)], capture_output=True, text=True).stdout.split()
    if len(out) < 2:
        return None
    files = subprocess.run(["/usr/sbin/lsof", "-p", str(pid)], capture_output=True, text=True).stdout.count("\n")
    return {"rss_mb": round(int(out[0]) / 1024, 1), "cpu": float(out[1]), "open_files": max(0, files - 1)}


class Monitor:
    def __init__(self, run_dir, every=30):
        self.path = os.path.join(run_dir, "monitor.csv")
        self.every = every
        self.rows = []
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        with open(self.path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time", "rss_mb", "cpu", "open_files"])
            while not self._stop.is_set():
                pid = ax.pid_of(runner.PROCESS_PATTERN)
                data = sample(pid) if pid else None
                if data:
                    self.rows.append((time.time(), data))
                    writer.writerow([time.strftime("%H:%M:%S"), data["rss_mb"], data["cpu"], data["open_files"]])
                    handle.flush()
                self._stop.wait(self.every)

    def mark(self):
        """The latest sample (call after an upload settles to compare with the baseline)."""
        return self.rows[-1][1] if self.rows else None


def growth_problem(baseline_mb, now_mb, allowed_mb=600):
    """Memory has to come back near the start after an upload: a sentence when it did not."""
    if baseline_mb and now_mb and now_mb - baseline_mb > allowed_mb:
        return f"memory did not return near the start: {baseline_mb:.0f} MB at the start, {now_mb:.0f} MB now (+{now_mb - baseline_mb:.0f} MB, allowed +{allowed_mb})"
    return None


def leak_count(pid):
    """Number of ROOT LEAK lines in `leaks <pid>` (0 = clean). None when the tool could not run."""
    try:
        out = subprocess.run(["/usr/bin/leaks", str(pid)], capture_output=True, text=True, timeout=180).stdout
    except Exception:
        return None
    return sum(1 for line in out.splitlines() if "ROOT LEAK" in line)
