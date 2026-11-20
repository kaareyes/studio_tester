"""Explore suite: goes through sessions and auditions the way a person does - scroll the projects list, open a session, open the
upload Queue, scroll to an audition, open its file list - and checks each screen on the way. Needs no camera and records nothing.

Which sessions and auditions: the ones typed on the test page (one per line), or, when the boxes are empty, picked AT RANDOM from
what the account lists. Random choices come from a seed that is written in the log and in the report: type the same seed on the
page to run exactly the same choices again (for example to repeat a failure).
"""
import random
import time

from tester import ax
from tester.runner import Skip
from . import common

DEFAULT_ROUNDS = 3


def _name_of(element):
    return ax._attr(element, "AXIdentifier") or ""


def _scroll_page(app, notches, settle=0.6):
    """A real mouse-wheel scroll in the middle of the window (positive = towards the end of the list)."""
    app.activate()
    frame = app.window_frame()
    if frame is None:
        raise AssertionError("Studio has no window to scroll")
    x, y, width, height = frame
    for _ in range(abs(notches)):
        ax.scroll(0, 10 if notches > 0 else -10, x + width / 2, y + height * 0.55)
        time.sleep(0.08)
    time.sleep(settle)


def _scroll_to_top(app):
    _scroll_page(app, -40, settle=0.8)


# ---------------------------------------------------------------- sessions

def _sessions_on_screen(app):
    """{session id: session name} for the session rows shown now."""
    found = {}
    for element in app.find_all(prefix="sessions.row.name."):
        session_id = _name_of(element).split(".")[-1]
        if len(session_id) >= 32:
            found[session_id] = app.text(element)
    return found


def _collect_sessions(app, rnd, context, pages):
    """Scrolls the projects list a random number of pages (the list loads more as it goes) and returns every session seen."""
    common.go_home(app)
    _scroll_to_top(app)
    seen = dict(_sessions_on_screen(app))
    for _ in range(pages):
        _scroll_page(app, rnd.randint(2, 6))
        seen.update(_sessions_on_screen(app))
    context.log(f"sessions seen while scrolling {pages} page(s): {len(seen)}")
    return seen


def _open_session(app, session_id, name):
    return common.open_session_by_id(app, session_id, name)


# ---------------------------------------------------------------- auditions (in the Queue)
# Each Queue row is one container (`queue.batch.<row key>`) and the walker does not look inside containers (lists with hundreds of
# rows would take minutes): the audition name, its arrow and its files are looked up INSIDE the row.

def _rows_on_screen(app):
    """[(audition name, row container)] of the Queue rows shown now."""
    rows = []
    for element in app.find_all(prefix="queue.batch."):
        if not ax._is_container(_name_of(element)):
            continue
        names = app.find_all(identifier="queue.batch.name", within=element)
        if names and app.text(names[0]):
            rows.append((app.text(names[0]), element))
    return rows


def _toggle_row(app, row):
    """Presses the arrow of this Queue row."""
    arrows = app.find_all(identifier="queue.batch.expand", within=row)
    frame = app.frame(arrows[0]) if arrows else None
    if frame is None:
        raise AssertionError("the audition row has no expand arrow on screen")
    x, y, width, height = frame
    app.activate()
    ax.click(x + width / 2, y + height / 2)
    time.sleep(1.5)


def _find_row(app, wanted):
    """Scrolls the Queue (to the end, then back up) until a row whose audition name contains `wanted` is on screen."""
    _scroll_to_top(app)
    for direction in (1, -1):
        last = None
        for _ in range(80):
            for name, row in _rows_on_screen(app):
                if wanted.lower() in name.lower():
                    return name, row
            keys = tuple(_name_of(r) for _, r in _rows_on_screen(app))
            if keys == last:
                break                                   # the list stopped moving: its end
            last = keys
            _scroll_page(app, 3 * direction)
    raise AssertionError(f"audition '{wanted}' is not in this session's Queue (scrolled the whole list)")


def _local_media_count(audition_name=None):
    """How many media rows the local database of the Test build holds, of this audition when its name is given ('Audition 25' = the
    folder 'Audition 25/'); -1 when it cannot be read."""
    try:
        from tester import oracle
        if audition_name:
            like = "%/" + audition_name.replace(" ", "%20") + "/%"
            return int(oracle.query("select count(*) from ZDBMEDIA where ZISDELETED = 0 and ZFOLDERPATH like ?", (like,))[0][0])
        return int(oracle.query("select count(*) from ZDBMEDIA")[0][0])
    except Exception:
        return -1


def _check_audition(app, context, wanted, rnd):
    """Finds an audition in the Queue (the one named `wanted`, or a random one after random scrolling), opens its file list and checks
    that files are listed with a size. Returns the audition name, or raises Skip when the Queue of this session is empty."""
    if wanted:
        name, row = _find_row(app, wanted)
    else:
        _scroll_page(app, rnd.randint(0, 8))
        rows = _rows_on_screen(app)
        if not rows:
            _scroll_to_top(app)
            rows = _rows_on_screen(app)
        if not rows:
            raise Skip("this session's Queue has no uploaded or uploading auditions")
        name, row = rnd.choice(rows)
    context.log(f"audition: {name}")
    _toggle_row(app, row)
    files = [n for n in (_name_of(e) for e in app.find_all(prefix="queue.row.", within=row)) if n.count(".") == 2]
    sizes = [app.text(e) for e in app.find_all(identifier="queue.row.size", within=row)]
    context.log(f"files listed after opening '{name}': {len(files)}; sizes shown: {', '.join(sizes[:6])}")
    if not files and not sizes:
        if _local_media_count(name) == 0:
            # A fresh install lists completed auditions from the server, but the expanded file list is built from the local database,
            # which is empty then: nothing to check here. (Not a failure of the tester or proof of a Studio bug.)
            context.log(f"'{name}' lists no files: the local database holds no media of this audition (its completed upload is listed from the server), so there is nothing to compare")
            _toggle_row(app, row)
            return name
        raise AssertionError(f"the file list of '{name}' stayed empty after pressing its arrow although the local database holds its media")
    if any(s.strip().lower() in ("size: zero kb", "size: 0 mb") for s in sizes):
        raise AssertionError(f"a file of '{name}' shows no size: {sizes}")
    _toggle_row(app, row)                               # close it again so the next round starts from a short list
    return name


# ---------------------------------------------------------------- the suite

def _plan(context):
    """The sessions and auditions of this run: typed on the page, or random (seeded)."""
    options = context.options or {}
    seed = options.get("seed")
    try:
        seed = int(seed) if str(seed or "").strip() else random.randrange(1, 10**6)
    except ValueError:
        seed = abs(hash(seed)) % 10**6
    rnd = random.Random(seed)
    sessions = [line.strip() for line in (options.get("sessions") or "").splitlines() if line.strip()]
    auditions = [line.strip() for line in (options.get("auditions_text") or "").splitlines() if line.strip()]
    try:
        rounds = max(1, min(int(options.get("rounds") or DEFAULT_ROUNDS), 50))
    except ValueError:
        rounds = DEFAULT_ROUNDS
    if sessions:
        rounds = len(sessions)
    context.log(f"seed {seed} (type it on the page to repeat this run); rounds {rounds}; "
                f"sessions {'from the page: ' + ', '.join(sessions) if sessions else 'random'}; "
                f"auditions {'from the page: ' + ', '.join(auditions) if auditions else 'random'}")
    return rnd, seed, sessions, auditions, rounds


def build(options):
    """The tests of one run (the number of rounds depends on the page)."""
    state = {}

    def prepare(context):
        app = common.app_of(context)
        if app.exists("login.signIn"):
            raise Skip("Studio is on the login screen: sign in with the test account first")
        state["rnd"], state["seed"], state["sessions"], state["auditions"], state["rounds"] = _plan(context)
        if not state["sessions"]:
            seen = _collect_sessions(app, state["rnd"], context, pages=state["rnd"].randint(1, 4))
            if not seen:
                raise AssertionError("no session is listed on the projects screen")
            picks = list(seen.items())
            state["rnd"].shuffle(picks)
            state["picked"] = picks
        context.log(f"plan ready (seed {state['seed']})")

    def round_test(index):
        def test(context):
            if "rnd" not in state:
                raise Skip("the plan was not made (see the first test)")
            app = common.app_of(context)
            rnd = state["rnd"]
            common.close_queue(app)
            if state["sessions"]:
                wanted = state["sessions"][index]
                common.go_home(app)
                try:
                    element = app.scroll_find(prefix="sessions.row.name.", text_contains=wanted)
                except Exception:
                    raise AssertionError(f"session '{wanted}' is not on the projects screen (scrolled the whole list)")
                session_id, name = _name_of(element).split(".")[-1], app.text(element)
            else:
                picks = state["picked"]
                session_id, name = picks[index % len(picks)]
            title = _open_session(app, session_id, name)
            context.log(f"round {index + 1}: session '{name}' ({session_id}) opened; title on screen: {title}")
            talents = [n for n in app.names("session.talent.") if n.count(".") == 2]
            context.log(f"{len(talents)} talents on the session screen")
            counts = common.open_queue(app)
            context.log(f"queue counts: {counts}")
            if None in counts.values():
                raise AssertionError(f"a queue count could not be read: {counts}")
            if counts["pending"] + counts["completed"] != counts["all"]:
                raise AssertionError(f"pending {counts['pending']} + completed {counts['completed']} is not all {counts['all']}")
            auditions = state["auditions"]
            wanted_audition = auditions[index % len(auditions)] if auditions else None
            try:
                _check_audition(app, context, wanted_audition, rnd)
            finally:
                common.close_queue(app)
        return test

    rounds = len([l for l in (options.get("sessions") or "").splitlines() if l.strip()]) or \
        max(1, min(int(options.get("rounds") or DEFAULT_ROUNDS) if str(options.get("rounds") or "").isdigit() else DEFAULT_ROUNDS, 50))
    tests = [("Plan: sessions and auditions (from the page or random)", prepare)]
    for index in range(rounds):
        tests.append((f"Round {index + 1}: open a session, its Queue and an audition's files", round_test(index)))
    return tests
