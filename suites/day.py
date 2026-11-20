"""A real audition day (the default template): the way a casting day really goes, in one run.

  1. a normal audition (online)
  2. the internet drops in the middle of a take and comes back
  3. a long audition (3 talents, 4 takes of 1-5 minutes)
  4. an audition recorded with no internet at all
  5. the internet is back: everything recorded offline syncs, nothing is lost or doubled
  6. a few more auditions, each one randomly normal / dropping internet / offline (the seed repeats the run)
  7. at the end every clip is checked: uploaded exactly once, on disk, in the right session

Steps 2-4 come in a random order (seeded). Options: picked (sessions), seed, extra (how many random auditions at step 6, default 3)."""
from tester import faults, oracle, profiles
from tester.runner import Skip
from . import common, realistic
from .common import plan_from_options

TEMPLATE = [
    ("Normal audition (online)", {"mode": "online", "profile": "short", "talents": 1}),
    ("Internet drops in the middle of a take and comes back", {"mode": "online", "profile": "short", "flaky": True, "takes": 2}),
    ("Long audition: 3 talents, 4 takes of 1-5 minutes", {"mode": "online", "profile": "normal", "talents": 3, "takes": 4}),
    ("Audition with no internet at all", {"mode": "offline", "profile": "short", "takes": 2}),
]
RANDOM_KINDS = [
    ("online", {"mode": "online", "profile": "short"}),
    ("internet drops", {"mode": "online", "profile": "short", "flaky": True, "takes": 2}),
    ("offline", {"mode": "offline", "profile": "short"}),
]


def build(options):
    rnd, seed = plan_from_options(options)
    pairs, problems = realistic._sessions(options)
    state = {"rnd": rnd, "pk": None, "expected": {"takes": 0, "photos": 0, "slates": 0}}
    extra = max(0, min(int(options.get("extra") or 3), 50))
    tests = []

    def prepare(context):
        app = common.app_of(context)
        if app.exists("login.signIn"):
            raise Skip("Studio is on the login screen: sign in with the test account first")
        for sentence in problems:
            context.log("NOT USED: " + sentence)
        if not pairs:
            raise Skip("no session was chosen (or none can be used): pick sessions on the page")
        context.log(f"audition day, seed {seed}: {len(TEMPLATE)} template auditions + {extra} random ones in {len(pairs)} session(s)")
        reason = profiles.disk_problem(len(TEMPLATE) + extra, "normal", None)
        if reason:
            raise Skip(reason)
        faults.reset_events()
        faults.label("T-#", 1)
        state["pk"] = oracle.last_media_pk()
    tests.append(("Prepare: seed, sessions, disk, camera label", prepare))

    def session_for(index):
        return pairs[index % len(pairs)] if pairs else ({"name": "?"}, {"id": "", "name": "?"})

    order = [0] + rnd.sample([1, 2, 3], 3)                     # the normal audition first, then the three special ones in random order
    number = 0
    for step in order:
        name, plan = TEMPLATE[step]
        number += 1
        tests.append((f"{number}. {name}", realistic.audition_test(session_for(number - 1), number, options, state, plan=plan)))
        if plan.get("mode") == "offline":
            tests.append((f"{number}b. Internet is back: offline recordings sync", realistic.settle_test(options, state)))
    for n in range(extra):
        kind, plan = rnd.choice(RANDOM_KINDS)
        number += 1
        tests.append((f"{number}. Random audition ({kind})", realistic.audition_test(session_for(number - 1), number, options, state, plan=plan)))
    tests.append(("Final check: everything uploaded once, on disk, in the right session", realistic.settle_test(options, state)))
    return tests
