"""Flexible waiting. A fixed number of seconds is wrong both ways: too short when Studio is slow but working (a 59 s take needed about 80 s to be
processed and was reported as "did not save"), too long when Studio is really hung. The rule used here: the wait has a base time; when the base
is over, it is extended (a little at a time, up to a cap) for as long as Studio is actually WORKING (its CPU, with its helper processes, is busy),
and it ends at once when Studio is idle. A hung Studio sits at 0% CPU, so it is noticed quickly; a busy one is given the time it needs."""
import subprocess
import time

BUSY_CPU = 15.0         # % of one core, Studio and its helper processes together, above which Studio counts as working
IDLE_CPU = 1.0          # below this Studio is doing nothing at all


def process_tree_cpu(pid, ps_output=None):
    """Total %CPU of `pid` and everything it started (export helpers, encoders). 0.0 when the process is gone or ps cannot be read."""
    try:
        text = ps_output if ps_output is not None else subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,pcpu="], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return 0.0
    children, cpu = {}, {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            p, parent, c = int(parts[0]), int(parts[1]), float(parts[2])
        except ValueError:
            continue
        cpu[p] = c
        children.setdefault(parent, []).append(p)
    if pid is None or pid not in cpu:
        return 0.0
    total, stack, seen = 0.0, [pid], set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        total += cpu.get(current, 0.0)
        stack.extend(children.get(current, []))
    return total


class Patience:
    """`expired()` is False until the base time has passed; after that it stays False (extending by `extend` seconds each time) while Studio is
    busy, up to `cap` seconds of extension in total, and turns True as soon as Studio is idle or the cap is used up."""

    def __init__(self, base, cpu, extend=20.0, cap=600.0, busy_cpu=BUSY_CPU, now=time.time):
        self.now, self.cpu, self.extend, self.cap, self.busy_cpu = now, cpu, extend, cap, busy_cpu
        self.deadline = now() + base
        self.extended = 0.0
        self.extensions = 0

    def expired(self):
        now = self.now()
        if now < self.deadline:
            return False
        if self.extended < self.cap and self.cpu() >= self.busy_cpu:
            self.deadline = now + self.extend
            self.extended += self.extend
            self.extensions += 1
            return False
        return True


def for_studio(base, cap=600.0, extend=20.0):
    """A Patience that watches the running Studio (looked up when needed, so it follows a restarted app)."""
    from . import ax, runner
    return Patience(base, lambda: process_tree_cpu(ax.pid_of(runner.PROCESS_PATTERN)), extend=extend, cap=cap)


def studio_is_idle():
    from . import ax, runner
    return process_tree_cpu(ax.pid_of(runner.PROCESS_PATTERN)) < IDLE_CPU
