"""Soak suite: audition cycles for hours, switching online and offline, watching memory, CPU and open files. A failed cycle is logged
as an incident and the soak goes on (unattended); the run fails at the end if any cycle failed.
Options: picked (session ids), hours (default 2), profile, mix, seed."""
import time

from tester import faults, monitor, oracle, ax, runner
from tester.runner import Skip
from . import common, driver, recover
from .common import plan_from_options
from .realistic import _sessions
from tester import profiles


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = _sessions(options)
    hours = max(0.05, min(float(options.get("hours") or 2), 24))

    def soak(context):
        if not pairs:
            raise Skip("no session was chosen: pick sessions on the page")
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        context.log(f"seed {seed}; soak for {hours} h over {len(pairs)} session(s)")
        faults.reset_events()
        faults.label("K-#", 1)
        profile = options.get("profile") or "normal"
        take = lambda: profiles.pick_length(profile, rnd, options.get("mix"))[1]
        pid = ax.pid_of(runner.PROCESS_PATTERN)
        base = monitor.sample(pid) if pid else None
        end = time.time() + hours * 3600
        cycle, failed = 0, 0
        pk = oracle.last_media_pk()
        while time.time() < end and not getattr(context, "stop", lambda: False)():
            cycle += 1
            project, entry = pairs[cycle % len(pairs)]
            try:
                app = recover.ensure_ready(context, (entry["id"], entry["name"]))
                faults.offline(rnd.random() < 0.3)
                done = driver.random_audition(app, rnd, context.log, take)
                context.log(f"cycle {cycle}: ok ({done['takes']} take(s), finalize {done['seconds_finalize']} s)")
            except Skip:
                raise
            except Exception as error:
                failed += 1
                recover.incident(context, f"cycle {cycle} failed: {error}")
                recover.sample_hang(context, f"soak_{cycle}")
            finally:
                faults.offline(False)
            problems_now = oracle.check(pk)
            if problems_now:
                failed += 1
                recover.incident(context, f"cycle {cycle} data check: " + "; ".join(problems_now))
            now = monitor.sample(ax.pid_of(runner.PROCESS_PATTERN) or 0)
            if base and now:
                grow = monitor.growth_problem(base["rss_mb"], now["rss_mb"], allowed_mb=2000)
                if grow:
                    failed += 1
                    recover.incident(context, f"cycle {cycle}: {grow}")
        if failed:
            raise AssertionError(f"{failed} problem(s) in {cycle} cycle(s): see incidents.txt")
        context.log(f"{cycle} cycles, no problems")
    return [("Soak: audition cycles with online/offline switches", soak)]
