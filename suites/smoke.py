"""Smoke suite: can a tester get from launch to a session and the upload Queue, and does the local data look sane?
Needs no camera and records nothing. About two minutes."""
import json
import os

from tester import runner
from tester.runner import Skip
from . import common


def studio_is_running(context):
    app = common.app_of(context)
    names = app.names()
    context.log(f"{len(names)} named controls on screen")
    if len(names) < 3:
        raise AssertionError("this build has no test names (built before TestID.swift)")


def signed_in_and_projects_listed(context):
    app = common.app_of(context)
    if app.exists("login.signIn"):
        raise Skip("Studio is on the login screen: sign in with the test account first")
    common.go_home(app)
    rows = app.find_all(prefix="projects.row.")
    projects = {n.split(".")[2] for n in (ax_name(e) for e in rows) if len(n.split(".")) >= 3 and len(n.split(".")[2]) >= 32}
    context.log(f"{len(projects)} projects listed")
    if not projects:
        raise AssertionError("no project is listed")


def ax_name(element):
    from tester import ax
    return ax._attr(element, "AXIdentifier") or ""


def a_session_opens(context):
    app = common.app_of(context)
    # A session with scheduled talents makes the next test meaningful; STUDIO_TEST_SESSION picks another by its title. The page is
    # scrolled to find it (the list loads more pages as it goes); if it is not there the first listed session is opened.
    wanted = os.environ.get("STUDIO_TEST_SESSION", "November 04")
    try:
        session_id, title = common.open_session_by_title(app, wanted)
    except Skip:
        context.log(f"no session named like '{wanted}': opening the first listed one")
        session_id, title = common.open_session(app)
    context.log(f"opened session {session_id}: {title}")
    if not title:
        raise AssertionError("the session screen shows no title")


def session_shows_talents_and_actions(context):
    app = common.app_of(context)
    app.wait_for("session.title", timeout=10)
    talents = [n for n in app.names("session.talent.") if n.count(".") == 2]
    context.log(f"{len(talents)} talents on the session screen")
    if not talents:
        raise Skip("this session has no scheduled talents")
    if not (app.exists("session.enterAuditionMode") or app.exists("session.enterAuditionModeDisabled")):
        raise AssertionError("'Enter Audition Mode' is not on the session screen")


def queue_opens_and_counts_add_up(context):
    app = common.app_of(context)
    counts = common.open_queue(app)
    context.log(f"queue counts: {counts}")
    common.close_queue(app)
    if None in counts.values():
        raise AssertionError(f"a queue count could not be read: {counts}")
    if counts["pending"] + counts["completed"] != counts["all"]:
        raise AssertionError(f"pending {counts['pending']} + completed {counts['completed']} is not all {counts['all']}")


def connection_indicator_is_shown(context):
    app = common.app_of(context)
    if not app.exists("statusBar.connection"):
        raise AssertionError("the network indicator is not on screen")


def local_database_is_consistent(context):
    summary = runner.studio_database_summary()
    context.log("database: " + json.dumps(summary))
    test_db = next((v for k, v in summary.items() if "Test" in k), None) or next(iter(summary.values()), None)
    if not test_db or "error" in test_db:
        raise AssertionError(f"the local database could not be read: {test_db}")
    owner = test_db.get("clips_with_owner_list")
    if isinstance(owner, str):
        raise AssertionError("the database is an older version (no owner list column): run a build with model StudioApp 4")
    flagged = test_db.get("auditions_flagged_resume", 0)
    if flagged:
        context.log(f"note: {flagged} auditions are flagged 'resume'; each one holds the upload rebuild of its whole session")


TESTS = [
    ("Studio is running and has test names", studio_is_running),
    ("Signed in, projects are listed", signed_in_and_projects_listed),
    ("A session opens", a_session_opens),
    ("The session screen shows talents and Enter Audition Mode", session_shows_talents_and_actions),
    ("The upload Queue opens and its counts add up", queue_opens_and_counts_add_up),
    ("The network indicator is shown", connection_indicator_is_shown),
    ("The local database is consistent (model 4, owner lists)", local_database_is_consistent),
]
