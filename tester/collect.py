"""Collect step: reads every project, session and scheduled talent the signed-in account shows, the way a person would (scroll the
projects list, open each session). Read only: it records nothing and changes nothing. The result goes to catalog.json.
It can be stopped; what was found so far is kept (the catalog is marked incomplete)."""
import time

from . import ax, catalog
from suites import common


def assign_sessions(elements):
    """`elements`: [{'kind': 'project'|'session', 'id', 'name', 'y'}] seen on one screen. A session belongs to the project row
    just above it on the screen (the list is grouped by project). Returns {project_id: {'name', 'sessions': {id: name}}}, with the
    project id None / name '(project not shown)' for sessions seen before any project row."""
    out = {}
    current = None
    for element in sorted(elements, key=lambda e: e["y"]):
        if element["kind"] == "project":
            current = element["id"]
            out.setdefault(current, {"name": element["name"], "sessions": {}})
        else:
            key = current
            out.setdefault(key, {"name": "(project not shown)" if key is None else out[key]["name"], "sessions": {}})
            out[key]["sessions"][element["id"]] = element["name"]
    return out


def _on_screen(app):
    elements = []
    for element in app.find_all(prefix="projects.row."):
        name = ax._attr(element, "AXIdentifier") or ""
        parts = name.split(".")
        frame = app.frame(element)
        if len(parts) == 3 and len(parts[2]) >= 32 and frame and app.text(element):
            elements.append({"kind": "project", "id": parts[2], "name": app.text(element), "y": frame[1]})
    for element in app.find_all(prefix="sessions.row.name."):
        session_id = (ax._attr(element, "AXIdentifier") or "").split(".")[-1]
        frame = app.frame(element)
        if len(session_id) >= 32 and frame:
            elements.append({"kind": "session", "id": session_id, "name": app.text(element), "y": frame[1]})
    return elements


def _merge(projects, found):
    for project_id, info in found.items():
        entry = projects.setdefault(project_id, {"id": project_id or "unknown", "name": info["name"], "sessions": {}})
        if info["name"] and not entry["name"].startswith("("):
            entry["name"] = info["name"]
        entry["sessions"].update(info["sessions"])


def read_talents(app):
    """Names of the talents scheduled in the open session."""
    talents = {}
    for element in app.find_all(prefix="session.talent."):
        parts = (ax._attr(element, "AXIdentifier") or "").split(".")
        if len(parts) == 3 and len(parts[2]) >= 32 and app.text(element):          # session.talent.<id>
            talents[parts[2]] = app.text(element).strip()
    return [{"id": i, "name": n} for i, n in talents.items()]


def run(app, log, progress=None, stop=lambda: False, read_sessions=True, max_scrolls=400):
    """Returns the catalog dict (also saved). `progress(text)` is shown on the page."""
    progress = progress or (lambda text: None)
    projects = {}
    common.go_home(app)
    common.scroll_page(app, -40, settle=0.8)
    same = 0
    for step in range(max_scrolls):
        if stop():
            break
        before = sum(len(p["sessions"]) for p in projects.values())
        _merge(projects, assign_sessions(_on_screen(app)))
        after = sum(len(p["sessions"]) for p in projects.values())
        progress(f"Scanning the projects list: {len(projects)} projects, {after} sessions found")
        same = same + 1 if after == before else 0
        if same >= 6 and step > 2:                  # nothing new for six scrolls: the end of the list
            break
        common.scroll_page(app, 4, settle=0.7)
    complete = same >= 6 and not stop()
    log(f"list scanned: {len(projects)} projects, {sum(len(p['sessions']) for p in projects.values())} sessions")

    data = {"complete": complete, "projects": []}
    todo = [(pid, p, sid, name) for pid, p in projects.items() for sid, name in p["sessions"].items()]
    sessions_done = {}
    for number, (pid, project, sid, name) in enumerate(todo, 1):
        entry = {"id": sid, "name": name, "talents": [], "talents_read": False}
        if read_sessions and not stop():
            progress(f"Reading talents: session {number} of {len(todo)} ({name})")
            try:
                common.open_session_by_id(app, sid, name)
                entry["talents"] = read_talents(app)
                entry["talents_read"] = True
            except Exception as error:                # a session that cannot be opened stays listed, marked unread
                log(f"could not read the talents of '{name}': {error}")
            finally:
                try:
                    common.go_home(app)
                except Exception:
                    pass
        elif stop():
            complete = False
        sessions_done.setdefault(pid, []).append(entry)
    for pid, project in projects.items():
        data["projects"].append({"id": project["id"], "name": project["name"], "sessions": sessions_done.get(pid, [])})
    data["complete"] = complete and all(s.get("talents_read") for p in data["projects"] for s in p["sessions"]) if read_sessions else complete
    catalog.save(data)
    return data
