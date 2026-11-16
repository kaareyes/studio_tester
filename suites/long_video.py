"""Long video suite: the Realistic suite with the Long profile (25 to 50 minute takes) plus a memory check after every audition: the
app's memory has to come back near where it was before the audition, the upload has to finish, and nothing may freeze.
Options: same as Realistic (picked, auditions, mode, seed); the profile is forced to 'long' unless the page says otherwise."""
import time

from tester import monitor, ax, runner
from . import realistic


def build(options):
    options = dict(options)
    options["profile"] = options.get("profile") if options.get("profile") in ("long", "mixed") else "long"
    options["auditions"] = options.get("auditions") or "2"
    inner = realistic.build(options)
    state = {"baseline": None}
    out = []
    for name, function in inner:
        if "audition" in name and "Wait" not in name:
            def wrapped(context, _f=function):
                pid = ax.pid_of(runner.PROCESS_PATTERN)
                before = monitor.sample(pid) if pid else None
                if before and state["baseline"] is None:
                    state["baseline"] = before["rss_mb"]
                _f(context)
                time.sleep(60)                                    # let the export and upload start
                pid = ax.pid_of(runner.PROCESS_PATTERN)
                now = monitor.sample(pid) if pid else None
                context.log(f"memory: baseline {state['baseline']} MB, now {now['rss_mb'] if now else '?'} MB")
                problem = monitor.growth_problem(state["baseline"], now["rss_mb"] if now else None, allowed_mb=1500)
                if problem:
                    raise AssertionError(problem)
            out.append((name, wrapped))
        else:
            out.append((name, function))
    return out
