"""The catalog: every project, session and talent the Collect step found in the app. Saved in catalog.json (names only, no media,
no passwords) and shown on the test page, where QA ticks what to test. Nothing leaves this Mac."""
import datetime
import json
import os

from . import matcher, runner

PATH = os.path.join(runner.ROOT, "catalog.json")
SETTINGS = os.path.join(runner.ROOT, "settings.json")
# A project whose name has one of these words is a test project. Anything else is greyed out on the page (real customer data).
DEFAULT_TEST_WORDS = ["qa", "test", "tester", "testing", "sim", "stress", "demo", "sandbox"]


def empty():
    return {"collected_at": None, "complete": False, "projects": []}


def load(path=None):
    path = path or PATH                  # read at call time, so a test can point PATH at a temporary file
    try:
        with open(path) as handle:
            data = json.load(handle)
        data.setdefault("projects", [])
        return data
    except (OSError, ValueError):
        return empty()


def save(data, path=None):
    path = path or PATH
    data["collected_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(data, handle, indent=1)
    os.replace(temporary, path)          # the page never reads a half-written file


def load_settings(path=SETTINGS):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_settings(values, path=SETTINGS):
    with open(path, "w") as handle:
        json.dump(values, handle, indent=1)


def test_words(path=SETTINGS):
    extra = load_settings(path).get("test_words") or []
    return sorted({matcher.normalize(w) for w in DEFAULT_TEST_WORDS + list(extra) if matcher.normalize(w)})


def protect_enabled(path=None):
    """The optional 'Protect real projects' switch (Advanced). Off by default: the Test build uses the test environment, so every project
    in it is test data and can be used."""
    return bool(load_settings(path or SETTINGS).get("protect_projects", False))


def is_test_project(name, words=None):
    wanted = set(words if words is not None else test_words())
    return any(t in wanted for t in matcher.tokens(name))


def decorate(data, words=None):
    """The catalog for the page: every project gets `is_test` and `usable_sessions` (sessions with scheduled talents). Without the
    'Protect real projects' switch every project counts as usable; with it (or when `words` is given) only projects with a test word."""
    protect = words is not None or protect_enabled()
    words = words if words is not None else test_words()
    projects = []
    for project in data.get("projects", []):
        sessions = []
        for session in project.get("sessions", []):
            talents = session.get("talents", [])
            sessions.append(dict(session, usable=bool(talents) or not session.get("talents_read", False)))
        is_test = (not protect) or is_test_project(project.get("name", ""), words)
        projects.append(dict(project, sessions=sessions, is_test=is_test))
    return dict(data, projects=projects, test_words=words, protected=protect)


def flatten(data):
    """[(project, session)] pairs."""
    return [(p, s) for p in data.get("projects", []) for s in p.get("sessions", [])]


def resolve_selection(data, selected_sessions, allow_real=()):
    """Turns ticked session ids into [(project, session)], keeping the order ticked. Returns (pairs, problems).
    A session of a non-test project is refused unless its project id is in `allow_real` (the extra confirm on the page)."""
    index = {s["id"]: (p, s) for p, s in flatten(data)}
    words = test_words()
    protect = protect_enabled()
    pairs, problems = [], []
    for session_id in selected_sessions:
        if session_id not in index:
            problems.append(f"session {session_id} is not in the catalog any more (collect again)")
            continue
        project, session = index[session_id]
        if protect and not is_test_project(project["name"], words) and project["id"] not in set(allow_real):
            problems.append(f"'{project['name']}' is not a test project: not used (confirm it on the page to allow it)")
            continue
        pairs.append((project, session))
    return pairs, problems


def pick_random(data, count, rnd, only_test=True):
    """`count` random usable sessions (as ids), for the 'random N sessions' button."""
    words = test_words()
    protect = protect_enabled()
    pool = [s["id"] for p, s in flatten(data)
            if (not (only_test and protect) or is_test_project(p["name"], words)) and (s.get("talents") or not s.get("talents_read"))]
    rnd.shuffle(pool)
    return pool[:count]


def find_session(data, query):
    """Fuzzy: a session by typed name (optionally 'project / session'). Same result shape as matcher.find."""
    pairs = flatten(data)
    if "/" in query:
        project_part, session_part = [x.strip() for x in query.split("/", 1)]
        narrowed = [(p, s) for p, s in pairs if matcher.score(project_part, p["name"]) >= matcher.MIN_SCORE]
        pairs = narrowed or pairs
        query = session_part
    return matcher.find(query, pairs, key=lambda pair: pair[1]["name"])
