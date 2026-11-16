"""Helpers shared by the suites: everything works by control name, with real waits instead of fixed delays."""
import re
import time

from tester import ax, runner
from tester.runner import Skip


def scroll_page(app, notches, settle=0.6):
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




def app_of(context):
    return context.app or context.launch()


def count_in(text):
    """'Pending, 23' or 'All Media, 1,088' -> 23 / 1088."""
    found = re.findall(r"[\d,]+", text or "")
    return int(found[-1].replace(",", "")) if found else None


def go_home(app):
    """Back to the projects list (the sidebar Home)."""
    if app.exists("queue.tab.all"):                      # the Queue is open: the Queue button in the status bar closes it
        app.press("statusBar.queue")
        app.wait_for("queue.tab.all", timeout=8, gone=True)
    if app.exists("nav.projects"):
        app.press("nav.projects")
    app.wait_for("projects.search", timeout=20)


def session_open_buttons(app):
    """[(session id, 'Open' element)] shown on the projects list now."""
    out = []
    for element in app.find_all(prefix="sessions.row."):
        from tester import ax
        name = ax._attr(element, "AXIdentifier")
        parts = name.split(".")
        if len(parts) == 3 and len(parts[2]) >= 32:          # sessions.row.<uuid>  (the Open button)
            out.append((parts[2], element))
    return out


def bring_to_middle(app, element):
    """A row found at the very top or bottom edge of the list can be under the header or cut off, and a click there is lost: scroll
    until it sits in the middle part of the window."""
    for _ in range(6):
        frame, window = app.frame(element), app.window_frame()
        if not frame or not window:
            return
        middle = frame[1] + frame[3] / 2
        top, bottom = window[1] + window[3] * 0.3, window[1] + window[3] * 0.85
        if top <= middle <= bottom:
            return
        scroll_page(app, 1 if middle > bottom else -1, settle=0.5)


def open_session_by_id(app, session_id, name):
    """Scrolls the projects list until this session's Open button is on screen, presses it, waits for the session screen.
    Tries the press twice: a click while the list is still settling after a scroll can be lost."""
    go_home(app)
    try:
        app.scroll_find(identifier="sessions.row." + session_id)
    except Exception:
        app.scroll_find(prefix="sessions.row.name.", text_contains=name)
    for attempt in (1, 2):
        button = app.wait_for("sessions.row." + session_id, timeout=10)
        bring_to_middle(app, button)
        app.press("sessions.row." + session_id)
        # The top bar can still show the PREVIOUS session's title for a moment: wait until it names this one.
        deadline = time.time() + 25
        while time.time() < deadline:
            titles = [app.text(e) for e in app.find_all(identifier="session.title")]
            if any(name.lower() in t.lower() or t.lower() in name.lower() for t in titles if t):
                return next(t for t in titles if t and (name.lower() in t.lower() or t.lower() in name.lower()))
            time.sleep(0.5)
        if attempt == 2:
            shown = ", ".join(app.text(e) for e in app.find_all(identifier="session.title")) or "nothing"
            raise AssertionError(f"pressing Open on session '{name}' did not open it (tried twice); the title shows: {shown}")
    return ""


def open_session_by_title(app, title):
    """Opens the session whose name contains `title` (for example 'November 04'), however far down the list it is: the page is
    scrolled until the session shows, and if it still does not, the projects are searched by name."""
    go_home(app)
    try:
        row = app.scroll_find(prefix="sessions.row.name.", text_contains=title)
    except Exception:
        row = None
    if row is None:
        raise Skip(f"no session named like '{title}' was found on the projects screen")
    session_id = (ax._attr(row, "AXIdentifier") or "").split(".")[-1]
    return session_id, open_session_by_id(app, session_id, app.text(row))


def open_session(app, session_id=None):
    """Presses Open on a session (the first one when none is given) and waits for its screen. Returns (id, title)."""
    go_home(app)
    buttons = session_open_buttons(app)
    if not buttons:
        raise Skip("no session is listed on the projects screen of this account")
    chosen = next((b for b in buttons if b[0] == session_id), buttons[0])
    names = app.find_all(identifier="sessions.row.name." + chosen[0])
    return chosen[0], open_session_by_id(app, chosen[0], app.text(names[0]) if names else "")


def open_queue(app):
    if not app.exists("queue.tab.all"):                  # pressing the Queue button while it is open would close it
        app.press("statusBar.queue")
    app.wait_for("queue.tab.all", timeout=15)
    return {"all": count_in(app.text(app.find("queue.tab.all"))),
            "pending": count_in(app.text(app.find("queue.tab.pending"))),
            "completed": count_in(app.text(app.find("queue.tab.completed")))}


def close_queue(app):
    if app.exists("queue.tab.all"):
        app.press("statusBar.queue")
        app.wait_for("queue.tab.all", timeout=8, gone=True)


def plan_from_options(options):
    """(random generator, seed) for a run: the seed typed on the page, or a new one. Same seed = same random choices."""
    import random
    seed = (options or {}).get("seed")
    try:
        seed = int(seed) if str(seed or "").strip() else random.randrange(1, 10**6)
    except ValueError:
        seed = abs(hash(seed)) % 10**6
    return random.Random(seed), seed
