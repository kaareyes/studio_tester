"""The test page. Runs on this Mac only (http://localhost:8765): pick the Studio build and a suite, press Start, watch, open the report."""
import datetime
import glob
import json
import os
import random
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ax, cameras, catalog, collect, control, matcher, profiles, runner, setup_check, share, updater

PORT = int(os.environ.get("STUDIO_TESTER_PORT", "8765"))     # a different port lets a second copy run side by side (tests)
sys.path.insert(0, runner.ROOT)
import suites  # noqa: E402

current = {"run": None}
OPTION_KEYS = ("picked", "allow_real", "auditions", "rounds", "hours", "profile", "mix", "mode", "seed", "presets", "sample_image",
               "sample_video", "sessions", "auditions_text")


class CollectJob:
    """The Collect button: opens the app (if needed) and reads every project, session and talent. Read only."""

    def __init__(self):
        self.running = False
        self.text = ""
        self.stop = False
        self.just_done = False

    def start(self, build_path, limit=0):
        self.running, self.stop, self.just_done = True, False, False
        self.text = "Starting..."
        threading.Thread(target=self._run, args=(build_path, limit), daemon=True).start()

    def _run(self, build_path, limit=0):
        try:
            run_dir = os.path.join(runner.REPORTS, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_collect")
            os.makedirs(run_dir, exist_ok=True)
            context = runner.Context(build_path, None, run_dir, lambda t: None)
            app = context.launch()
            if app.exists("login.signIn"):
                self.text = "Studio is on the login screen. Sign in with the test account in Studio, then press Collect again."
                return
            data = collect.run(app, context.log, progress=lambda t: setattr(self, "text", t), stop=lambda: self.stop, project_limit=limit)
            count = sum(len(p["sessions"]) for p in data["projects"])
            scope = f"the first {limit} projects" if limit else "all projects"
            self.text = f"Collected {len(data['projects'])} projects and {count} sessions ({scope})." + ("" if data["complete"] else " The list is not complete (stopped or some sessions could not be read).")
            self.just_done = True
        except Exception as error:
            self.text = f"Could not collect: {error}. Is Studio installed and open? Is the test account signed in?"
        finally:
            self.running = False


collect_job = CollectJob()


def estimate_text(suite, options):
    """(text, problem sentence or None, blocking) for the page: how long, how much disk, and what is missing."""
    problem = suite_problem(suite)
    if problem:
        return "", problem, True
    try:
        picked = json.loads(options.get("picked") or "[]")
    except ValueError:
        picked = []
    profile = options.get("profile") or "mixed"
    mix = options.get("mix")
    try:
        per = int(options.get("auditions") or 3)
        rounds = int(options.get("rounds") or 20)
        hours = float(options.get("hours") or 2)
    except ValueError:
        return "", "A count on the page is not a number.", True
    needs_sessions = suite in suites.RECORDING
    if needs_sessions and not picked:
        return "", "Tick at least one session first (collect the projects, then tick sessions).", True
    if suite in ("realistic", "long_video"):
        takes = len(picked) * per * 2.2
        e = profiles.estimate(takes, "long" if suite == "long_video" and profile not in ("long", "mixed") else profile, mix)
    elif suite in ("chaos", "network", "recovery", "friday"):
        e = profiles.estimate(rounds if suite == "chaos" else 12, "short", mix)
    elif suite == "soak":
        e = {"seconds": int(hours * 3600), "disk_mb": int(hours * 3600 * 0.55 * 0.5)}
    elif suite == "offline_load":
        e = {"seconds": 3600, "disk_mb": 2000}
    else:
        return "Takes a few minutes. Nothing is recorded.", None, False
    text = f"About <b>{profiles.describe(e['seconds'])}</b> and <b>{e['disk_mb'] / 1024:.1f} GB</b> of disk (free: {profiles.free_disk_mb() / 1024:.0f} GB). {len(picked)} session(s) ticked."
    problem = profiles.disk_problem(max(1, e["disk_mb"] // 1000), "short") if e["disk_mb"] + 5000 > profiles.free_disk_mb() else None
    return text, problem, bool(problem)

from .page import PAGE  # noqa: E402  (the page lives in page.py)


KIND_LABEL = {"test": "Test", "develop": "Develop", "staging": "Staging", "production": "Production"}
READ_ONLY_SUITES = {"build_check", "smoke", "explore", "checks"}      # these only look; every other suite records and needs the Test build's test tools
chosen = {"path": None}


def app_row(path, pid=None):
    kind = runner.kind_of(path)
    return {"path": path, "name": os.path.basename(path)[:-4], "kind": kind, "label": KIND_LABEL[kind], "pid": pid}


def apps_info():
    """What the page lists first: the Studio apps running now, the installed ones that are not open, and the one chosen."""
    running = [app_row(path, pid) for pid, path in ax.list_apps(runner.PROCESS_PATTERN)]
    running_paths = {r["path"] for r in running}
    installed = [app_row(p) for p in find_builds() if p not in running_paths]
    seen, unique = set(), []
    for row in installed:                         # one row per app name (several copies of one build are not a choice)
        if row["name"] not in seen and row["name"] not in {r["name"] for r in running}:
            seen.add(row["name"])
            unique.append(row)
    path = chosen["path"]
    return {"running": running, "installed": unique[:8], "selected": path,
            "selected_row": app_row(path) if path else None,
            "selected_running": bool(path and path in running_paths)}


def select_app(path):
    """Remembers the chosen Studio and points every driver at it. Returns an error sentence or None."""
    info = apps_info()
    known = {r["path"] for r in info["running"] + info["installed"]}
    if path not in known:
        return "That Studio app is not running and was not found on this Mac."
    chosen["path"] = path
    ax.TARGET_PATH = path
    return None


def classify_login(exists):
    """What the chosen Studio shows: 'login' (the sign-in screen), 'signed_in' (projects, a session or Audition Mode) or 'unknown'.
    `exists(name)` says whether a named control is on screen."""
    if exists("login.signIn") or exists("login.email"):
        return "login"
    if any(exists(n) for n in ("nav.projects", "projects.search", "session.title", "capture.record", "queue.tab.all")):
        return "signed_in"
    return "unknown"


_login_cache = {"at": 0.0, "path": None, "value": None}


def login_info(max_age=2.0):
    """{'state': 'none'|'closed'|'login'|'signed_in'|'unknown', 'detail': sentence} for the chosen Studio (cached for a moment: the page asks often)."""
    path = chosen["path"]
    if not path:
        return {"state": "none", "detail": "No Studio app is chosen yet."}
    if _login_cache["path"] == path and time.time() - _login_cache["at"] < max_age and _login_cache["value"]:
        return _login_cache["value"]
    pid = ax.pid_of(runner.PROCESS_PATTERN)
    if pid is None:
        value = {"state": "closed", "detail": "The chosen Studio is not open."}
    else:
        try:
            if not ax.trusted():
                value = {"state": "unknown", "detail": "Accessibility permission is off, so the tester cannot see Studio's screen."}
            else:
                app = ax.App(pid)
                value = {"state": classify_login(app.exists), "detail": ""}
        except Exception as error:
            value = {"state": "unknown", "detail": f"Could not read Studio's screen ({type(error).__name__})."}
    _login_cache.update(at=time.time(), path=path, value=value)
    return value


def suite_problem(suite):
    """A plain sentence when the chosen app cannot run this suite, else None."""
    path = chosen["path"]
    if not path:
        return "Choose a Studio app first (step 1)."
    kind = runner.kind_of(path)
    if suite not in READ_ONLY_SUITES and kind != "test":
        return (f"This test records auditions and needs the Test build's test tools. You chose Studio ({KIND_LABEL[kind]}). "
                "Choose 'Studio (macOS) - Test' in step 1, or pick Smoke or Explore, which only look.")
    return None


def find_builds():
    """Studio .app builds on this Mac, newest first: Xcode's DerivedData, /Applications, and the folders the team uses."""
    patterns = ["~/Library/Developer/Xcode/DerivedData/*/Build/Products/*/Studio*.app", "/Applications/Studio*.app",
                "/private/tmp/claude-501/*/Build/Products/*/Studio*.app", "~/Desktop/Studio*.app", "~/Downloads/Studio*.app"]
    found = []
    for pattern in patterns:
        found += glob.glob(os.path.expanduser(pattern))
    return sorted(set(found), key=lambda path: os.path.getmtime(path), reverse=True)


LOCAL_NAMES = ("localhost", "127.0.0.1")


def request_allowed(host_header, origin_header):
    """Only this Mac's own page may talk to the tester. A website open in the same browser could otherwise send requests to
    localhost:8765 (start a test, quit the tester); a rebinding attack uses a foreign Host. Both are refused."""
    def hostname(value):
        value = (value or "").strip().lower()
        if "://" in value:
            value = value.split("://", 1)[1]
        return value.split("/")[0].rsplit(":", 1)[0] if not value.startswith("[") else value
    if hostname(host_header) not in LOCAL_NAMES:
        return False
    if origin_header and hostname(origin_header) not in LOCAL_NAMES:        # Origin is sent by browsers on cross-site requests
        return False
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def forbidden(self):
        self.send("This request does not come from the Studio Tester page.", "text/plain", 403)

    def send(self, body, kind="application/json", code=200):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not request_allowed(self.headers.get("Host"), self.headers.get("Origin")):
            return self.forbidden()
        if self.path == "/":
            return self.send(PAGE, "text/html; charset=utf-8")
        if self.path == "/api/info":
            return self.send(json.dumps({"builds": find_builds(), "cameras": cameras.list_cameras(),
                                         "suites": {key: [value[0], value[1]] for key, value in suites.SUITES.items()},
                                         "setup": setup_check.checks(), "words_extra": catalog.load_settings().get("test_words", [])}))
        if self.path == "/guide.pdf":
            guide = os.path.join(runner.ROOT, "docs", "Studio_Tester_Guide.pdf")
            if os.path.isfile(guide):
                with open(guide, "rb") as handle:
                    return self.send(handle.read(), "application/pdf")
            return self.send("The PDF guide is not in this install.", "text/plain", 404)
        if self.path == "/api/login-state":
            return self.send(json.dumps(login_info()))
        if self.path == "/api/apps":
            return self.send(json.dumps(apps_info()))
        if self.path == "/api/update":
            return self.send(json.dumps(updater.check(catalog.load_settings().get("update_repo"))))
        if self.path == "/api/catalog":
            return self.send(json.dumps(catalog.decorate(catalog.load())))
        if self.path == "/api/collect-state":
            flag = collect_job.just_done
            collect_job.just_done = False
            return self.send(json.dumps({"running": collect_job.running, "text": collect_job.text, "just_done": flag}))
        if self.path == "/api/state":
            return self.send(json.dumps(current["run"].state() if current["run"] else {}))
        if self.path.startswith("/reports/"):
            path = os.path.normpath(os.path.join(runner.ROOT, self.path.lstrip("/")))
            if path.startswith(runner.REPORTS) and os.path.isfile(path):
                kind = "text/html; charset=utf-8" if path.endswith(".html") else ("image/png" if path.endswith(".png") else "text/plain")
                with open(path, "rb") as handle:
                    return self.send(handle.read(), kind)
        self.send("not found", "text/plain", 404)

    def do_POST(self):
        if not request_allowed(self.headers.get("Host"), self.headers.get("Origin")):
            return self.forbidden()
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/start":
            run = current["run"]
            if run and not run.finished:
                return self.send(json.dumps({"error": "a run is already in progress"}), code=409)
            suite = suites.SUITES.get(body.get("suite"))
            body["build"] = chosen["path"]
            if not suite or not body.get("build"):
                return self.send(json.dumps({"error": "Choose a Studio app first (step 1)."}), code=400)
            options = {key: str(value)[:20000] for key, value in (body.get("options") or {}).items() if key in OPTION_KEYS}
            _, problem, blocking = estimate_text(body["suite"], options)
            if blocking:
                return self.send(json.dumps({"error": problem}), code=400)
            try:
                new_run = runner.Run(body["suite"], suite[2], body["build"], body.get("camera") or None, options)
            except Exception as error:
                return self.send(json.dumps({"error": f"This suite could not be prepared: {error}"}), code=400)
            current["run"] = new_run
            new_run.start()
            return self.send("{}")
        if self.path == "/api/update/apply":
            busy = lambda: bool(collect_job.running or (current["run"] and not current["run"].finished))
            result = updater.apply(catalog.load_settings().get("update_repo"), busy=busy)
            if result["ok"]:
                def restart_soon():
                    if result.get("packages_changed"):
                        updater.install_packages()
                    updater.restart()
                threading.Timer(2.0, restart_soon).start()
            return self.send(json.dumps(result))
        if self.path == "/api/collect":
            if collect_job.running or (current["run"] and not current["run"].finished):
                return self.send(json.dumps({"error": "something is already running"}), code=409)
            build = chosen["path"]
            if not build:
                return self.send(json.dumps({"error": "Choose a Studio app first (step 1)."}), code=400)
            try:
                limit = max(0, min(int(body.get("limit") or 0), 1000))
            except (TypeError, ValueError):
                limit = 0
            collect_job.start(build, limit)
            return self.send("{}")
        if self.path == "/api/collect-stop":
            collect_job.stop = True
            return self.send("{}")
        if self.path == "/api/estimate":
            text, problem, blocking = estimate_text(body.get("suite", ""), body.get("options") or {})
            return self.send(json.dumps({"text": text, "problem": problem, "blocking": blocking}))
        if self.path == "/api/random":
            data = catalog.load()
            return self.send(json.dumps({"ids": catalog.pick_random(data, int(body.get("count") or 5), random.Random())}))
        if self.path == "/api/search":
            data = catalog.load()
            query = str(body.get("q") or "")
            ids = []
            for project, session in catalog.flatten(data):
                text = project["name"] + " " + session["name"]
                if matcher.normalize(query) in matcher.normalize(text) or matcher.score(query, text) >= matcher.MIN_SCORE or matcher.score(query, session["name"]) >= matcher.MIN_SCORE:
                    ids.append(session["id"])
            return self.send(json.dumps({"ids": ids}))
        if self.path == "/api/settings":
            words = [str(w)[:40] for w in (body.get("test_words") or [])][:50]
            values = catalog.load_settings()
            values["test_words"] = words
            catalog.save_settings(values)
            return self.send("{}")
        if self.path == "/api/select-app":
            if collect_job.running or (current["run"] and not current["run"].finished):
                # the drivers follow the chosen app: changing it in the middle of a run would make the run drive another Studio
                return self.send(json.dumps({"error": "A test is running. Wait until it finishes (or press Stop) before choosing another Studio app."}), code=409)
            error = select_app(body.get("path") or "")
            return self.send(json.dumps({"error": error}), code=400 if error else 200)
        if self.path == "/api/focus-app":
            if chosen["path"]:
                subprocess.run(["/usr/bin/open", chosen["path"]])           # brings the chosen Studio to the front
            return self.send("{}")
        if self.path == "/api/open-app":
            path = body.get("path") or ""
            if path in {r["path"] for r in apps_info()["installed"]}:
                subprocess.run(["/usr/bin/open", path])
            return self.send("{}")
        if self.path == "/api/open-reports":
            visible = share.shared_dir()                                  # the visible Reports folder when the program is hidden
            folder = visible if visible and os.path.isdir(visible) else runner.REPORTS
            os.makedirs(folder, exist_ok=True)
            subprocess.run(["/usr/bin/open", folder])
            return self.send("{}")
        if self.path == "/api/reveal-report":
            path = share.zip_for(str(body.get("folder") or ""))
            if path:
                share.reveal(path)
                return self.send(json.dumps({"path": path}))
            folder = os.path.join(runner.REPORTS, os.path.basename(str(body.get("folder") or "")))      # no shared zip: show the run folder
            if os.path.isdir(folder):
                share.reveal(folder)
            return self.send(json.dumps({"path": folder}))
        if self.path == "/api/fix":
            target = {"accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                      "camera": "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"}.get(body.get("what"))
            if target:
                subprocess.run(["/usr/bin/open", target])
            return self.send("{}")
        if self.path == "/api/quit":
            busy = bool(current["run"] and not current["run"].finished) or collect_job.running
            threading.Thread(target=quit_sequence, daemon=True).start()
            return self.send(json.dumps({"quitting": True, "was_busy": busy}))
        if self.path in ("/api/stop", "/api/cancel"):
            if current["run"]:
                current["run"].stop_requested = True
                control.cancel()                          # takes effect at the next click or wait, not at the end of the step
            return self.send("{}")
        if self.path == "/api/pause":
            ok = control.pause("paused from the page")
            return self.send(json.dumps({"paused": ok}))
        if self.path == "/api/resume":
            return self.send(json.dumps({"resumed": control.resume()}))
        self.send("not found", "text/plain", 404)


def is_studio_tester(port, opener=None):
    """True when what answers on this port is a Studio Tester page (this or an older version)."""
    import urllib.request
    try:
        with (opener or urllib.request.urlopen)(f"http://127.0.0.1:{port}/", timeout=3) as response:
            return b"Studio Tester" in response.read(20000)
    except Exception:
        return False


def listening_pids(port):
    out = subprocess.run(["/usr/sbin/lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if p.isdigit()]


def is_tester_process(pid):
    command = subprocess.run(["/bin/ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
    return "tester.server" in command or "tester/server.py" in command


def work_in_progress(port, opener=None):
    """True when the tester on this port is running a test or collecting (it must not be killed then), or cannot be read at all."""
    import urllib.request
    opener = opener or urllib.request.urlopen

    def get(path):
        with opener(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
            return json.loads(response.read() or b"{}")
    try:
        state = get("/api/state")
    except Exception:
        return True                       # cannot tell: leave it alone
    try:
        collecting = get("/api/collect-state").get("running")
    except Exception:
        collecting = False                # an older tester has no Collect
    return bool(collecting or (state.get("suite") and not state.get("finished")))


def stop_running_tester(port, pids=listening_pids, is_tester=is_tester_process, busy=work_in_progress, kill=os.kill, wait=time.sleep):
    """Closes the Studio Tester that is already running on `port`, so this start replaces it. Returns True when it was closed,
    False when it was left alone (a test is running in it, or it is not a tester process)."""
    found = [p for p in pids(port) if is_tester(p)]
    if not found or busy(port):
        return False
    for pid in found:
        try:
            kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(10):
        wait(0.5)
        if not [p for p in pids(port) if is_tester(p)]:
            break
    else:
        for pid in found:
            try:
                kill(pid, signal.SIGKILL)
            except OSError:
                pass
        wait(1)
    try:
        from . import faults
        faults.reset_all()               # the old tester may have left faults on (offline mode, camera label)
    except Exception:
        pass
    return True


def bind_or_reuse(preferred, make_server=None, probe=None, stopper=None, tries=10):
    """Opens the page server. Returns ('new', server, port). When a Studio Tester already runs on the port it is closed and replaced
    (('replaced' is reported by main through the stopper); if a test is running in it, it is left alone: ('existing', None, port).
    When another program uses the port, the next free port is used."""
    make_server = make_server or (lambda port: ThreadingHTTPServer(("127.0.0.1", port), Handler))
    probe = probe or is_studio_tester
    stopper = stopper or stop_running_tester
    for port in range(preferred, preferred + tries):
        try:
            return "new", make_server(port), port
        except OSError:
            if not probe(port):
                continue
            if stopper(port):
                for _ in range(10):
                    try:
                        return "replaced", make_server(port), port
                    except OSError:
                        time.sleep(0.5)
            return "existing", None, port
    raise OSError(f"no free port between {preferred} and {preferred + tries - 1}")


_running = {"server": None}      # the HTTP server of this program (set in main), so Quit can stop it


def shutdown_process():
    """Ends the tester program: the server loop is stopped (the program then ends by itself). A timer makes sure it really exits, even if
    something keeps it alive. (A signal like Ctrl+C is not used: a program started in the background ignores it.)"""
    threading.Timer(4.0, lambda: os._exit(0)).start()
    server = _running["server"]
    if server is not None:
        server.shutdown()


def quit_sequence(wait_seconds=20):
    """Quit Studio Tester from the page: a running test or Collect is cancelled first (so Studio is left normal and the report is
    made), then the program ends. Runs in its own thread, after the page got its answer."""
    time.sleep(0.5)
    collect_job.stop = True
    run = current["run"]
    if run and not run.finished:
        run.stop_requested = True
        control.cancel()
        for _ in range(int(wait_seconds * 2)):
            if run.finished:
                break
            time.sleep(0.5)
    print("\nStudio Tester was closed from its page. You can close this Terminal window.\nTo use it again: double-click Studio Tester.command.", flush=True)
    shutdown_process()


def esc_pause(port):
    """Esc was held during a run: pause it, make a sound and bring the page to the front, where Continue / Cancel testing wait."""
    if control.pause("Esc held"):
        subprocess.Popen(["/usr/bin/afplay", "/System/Library/Sounds/Funk.aiff"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        webbrowser.open(f"http://localhost:{port}")


def main():
    try:
        kind, server, port = bind_or_reuse(PORT)
    except OSError as error:
        print(f"Studio Tester could not start: {error}. Close other programs that use these ports, or restart the Mac.")
        sys.exit(1)
    url = f"http://localhost:{port}"
    if kind == "existing":
        print(f"Another Studio Tester is running a test right now, so I left it alone. Its page is open: {url}\n"
              "To restart it: press Stop on that page (or wait until the test finishes), then open Studio Tester.command again.")
        webbrowser.open(url)
        return
    if kind == "replaced":
        print("A Studio Tester was already running. I closed it and started a fresh one.")
    if port != PORT:
        print(f"(Port {PORT} is used by another program, so the tester uses {port}.)")
    print(f"Studio Tester is running. The page: {url}\nKeep this window open while testing. Close it to stop.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    control.start_esc_watcher(lambda: bool(current["run"] and not current["run"].finished), lambda: esc_pause(port))
    _running["server"] = server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
