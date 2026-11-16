import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from tester import server, catalog


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def call(self, path, body=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()



class Server(Base):
    def setUp(self):
        server.chosen["path"] = "/Applications/Studio (macOS) - Test.app"      # a chosen Test app (the gate is tested in ChooseStudio)

    def tearDown(self):
        server.chosen["path"] = None

    def test_page_and_info(self):
        status, page = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("Collect projects from the app", page)
        status, info = self.call("/api/info")
        names = json.loads(info)["suites"]
        for key in ("smoke", "explore", "realistic", "chaos", "recovery", "network", "offline_load", "long_video", "soak", "friday"):
            self.assertIn(key, names)

    def test_estimate_needs_sessions(self):
        _, body = self.call("/api/estimate", {"suite": "chaos", "options": {}})
        self.assertTrue(json.loads(body)["blocking"])
        _, body = self.call("/api/estimate", {"suite": "smoke", "options": {}})
        self.assertFalse(json.loads(body)["blocking"])

    def test_start_refused_without_sessions(self):
        status, body = self.call("/api/start", {"build": "/x.app", "suite": "realistic", "options": {}})
        self.assertEqual(status, 400)
        self.assertIn("Tick at least one session", body)

    def test_catalog_and_search(self):
        status, body = self.call("/api/catalog")
        self.assertEqual(status, 200)
        self.assertIn("projects", json.loads(body))
        status, body = self.call("/api/search", {"q": "anything"})
        self.assertEqual(json.loads(body)["ids"] is not None, True)

    def test_unknown_path(self):
        self.assertEqual(self.call("/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()


class ReportsButton(unittest.TestCase):
    def test_page_has_the_button_and_endpoint_exists(self):
        self.assertIn("Open the reports folder", server.PAGE)
        self.assertIn("/api/open-reports", open(server.__file__).read())


class ChooseStudio(Base):
    def test_kinds(self):
        from tester import runner
        self.assertEqual(runner.kind_of("/Applications/Studio (macOS) - Test.app"), "test")
        self.assertEqual(runner.kind_of("/x/Studio (macOS) - Develop.app"), "develop")
        self.assertEqual(runner.kind_of("/x/Studio (macOS) - Staging.app"), "staging")
        self.assertEqual(runner.kind_of("/Applications/Studio (macOS).app"), "production")

    def test_apps_endpoint_and_gate(self):
        status, body = self.call("/api/apps")
        info = json.loads(body)
        self.assertEqual(status, 200)
        for key in ("running", "installed", "selected", "selected_running"):
            self.assertIn(key, info)
        server.chosen["path"] = None
        status, body = self.call("/api/start", {"suite": "smoke", "options": {}})
        self.assertEqual(status, 400)                                    # nothing chosen: nothing starts
        self.assertIn("Choose a Studio app", body)

    def test_select_unknown_app_refused(self):
        status, body = self.call("/api/select-app", {"path": "/tmp/evil.app"})
        self.assertEqual(status, 400)
        self.assertIsNone(server.chosen["path"])

    def test_cannot_change_the_app_during_a_run(self):
        class Busy:
            finished = None
        server.current["run"] = Busy()
        try:
            status, body = self.call("/api/select-app", {"path": "/Applications/Studio (macOS) - Test.app"})
            self.assertEqual(status, 409)
            self.assertIn("test is running", body)
            self.assertIsNone(server.chosen["path"])
        finally:
            server.current["run"] = None

    def test_production_only_read_only_suites(self):
        server.chosen["path"] = "/Applications/Studio (macOS).app"
        try:
            self.assertIsNone(server.suite_problem("smoke"))
            self.assertIsNone(server.suite_problem("explore"))
            for suite in ("realistic", "chaos", "recovery", "network", "soak", "long_video", "offline_load", "friday"):
                self.assertIn("Test build", server.suite_problem(suite))
            server.chosen["path"] = "/Applications/Studio (macOS) - Test.app"
            self.assertIsNone(server.suite_problem("chaos"))
        finally:
            server.chosen["path"] = None

    def test_watchdog_decision(self):
        from tester import runner
        self.assertTrue(runner.should_reopen(True, False, False, 12))
        self.assertFalse(runner.should_reopen(True, False, False, 3))
        self.assertFalse(runner.should_reopen(True, False, True, 60))
        self.assertFalse(runner.should_reopen(False, False, False, 60))
        self.assertFalse(runner.should_reopen(True, True, False, 60))


class TargetPid(unittest.TestCase):
    def test_pid_of_follows_the_chosen_app(self):
        from tester import ax
        procs = [(11, "/Applications/Studio (macOS).app/Contents/MacOS/Studio (macOS)"),
                 (22, "/Applications/Studio (macOS) - Test.app/Contents/MacOS/Studio (macOS) - Test")]
        old_target = ax.TARGET_PATH
        original = ax._studio_processes
        ax._studio_processes = lambda pattern: procs
        try:
            ax.TARGET_PATH = None
            self.assertEqual(ax.pid_of("x"), 11)
            ax.TARGET_PATH = "/Applications/Studio (macOS) - Test.app"
            self.assertEqual(ax.pid_of("x"), 22)
            ax.TARGET_PATH = "/Applications/Studio (macOS) - Develop.app"
            self.assertIsNone(ax.pid_of("x"))
            self.assertEqual(ax.list_apps("x"), [(11, "/Applications/Studio (macOS).app"), (22, "/Applications/Studio (macOS) - Test.app")])
        finally:
            ax._studio_processes, ax.TARGET_PATH = original, old_target


class Ports(unittest.TestCase):
    def test_running_tester_is_replaced(self):
        calls = {"n": 0}
        def make(port):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("in use")                    # the old tester still holds the port
            return "server"
        kind, srv, port = server.bind_or_reuse(8765, make_server=make, probe=lambda p: True, stopper=lambda p: True)
        self.assertEqual((kind, srv, port), ("replaced", "server", 8765))

    def test_tester_with_a_test_running_is_left_alone(self):
        def busy(port):
            raise OSError("in use")
        kind, srv, port = server.bind_or_reuse(8765, make_server=busy, probe=lambda p: True, stopper=lambda p: False)
        self.assertEqual((kind, srv, port), ("existing", None, 8765))

    def test_other_program_on_the_port_moves_to_the_next_one(self):
        def make(port):
            if port == 8765:
                raise OSError("in use")
            return "server-%d" % port
        kind, srv, port = server.bind_or_reuse(8765, make_server=make, probe=lambda p: False, stopper=lambda p: self.fail("must not kill"))
        self.assertEqual((kind, srv, port), ("new", "server-8766", 8766))

    def test_no_free_port_is_a_clear_error(self):
        def busy(port):
            raise OSError("in use")
        with self.assertRaises(OSError):
            server.bind_or_reuse(8765, make_server=busy, probe=lambda p: False, tries=3)

    def test_stopper_kills_only_an_idle_tester_process(self):
        sent = []
        state = {"alive": True}
        def pids(port): return [101, 202] if state["alive"] else []
        def kill(pid, sig): sent.append((pid, sig)); state["alive"] = False
        ok = server.stop_running_tester(8765, pids=pids, is_tester=lambda p: p == 101, busy=lambda port: False, kill=kill, wait=lambda s: None)
        self.assertTrue(ok)
        self.assertEqual([p for p, _ in sent], [101])          # pid 202 is not a tester: never touched
        sent.clear()
        self.assertFalse(server.stop_running_tester(8765, pids=lambda p: [101], is_tester=lambda p: True, busy=lambda port: True, kill=kill, wait=lambda s: None))
        self.assertEqual(sent, [])                              # a test is running in it: not killed
        self.assertFalse(server.stop_running_tester(8765, pids=lambda p: [303], is_tester=lambda p: False, busy=lambda port: False, kill=kill, wait=lambda s: None))
        self.assertEqual(sent, [])

    def test_work_in_progress(self):
        import json as j
        class R:
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return j.dumps(self.data).encode()
        def opener(state, collect):
            def f(url, timeout):
                if url.endswith("/api/state"): return R(state)
                if collect is None: raise OSError("404")
                return R(collect)
            return f
        self.assertTrue(server.work_in_progress(1, opener=opener({"suite": "x", "finished": None}, {"running": False})))
        self.assertFalse(server.work_in_progress(1, opener=opener({"suite": "x", "finished": "t"}, {"running": False})))
        self.assertFalse(server.work_in_progress(1, opener=opener({}, {"running": False})))
        self.assertTrue(server.work_in_progress(1, opener=opener({}, {"running": True})))
        self.assertFalse(server.work_in_progress(1, opener=opener({}, None)))               # older tester without Collect
        def down(url, timeout): raise OSError("refused")
        self.assertTrue(server.work_in_progress(1, opener=down))                            # unreadable: leave it alone

    def test_identifies_a_studio_tester_page(self):
        class Page:
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n): return self.data
        self.assertTrue(server.is_studio_tester(1, opener=lambda url, timeout: Page(b"<title>Studio Tester</title>")))
        self.assertFalse(server.is_studio_tester(1, opener=lambda url, timeout: Page(b"<html>other</html>")))
        def down(url, timeout): raise OSError("refused")
        self.assertFalse(server.is_studio_tester(1, opener=down))


class CollectLimit(unittest.TestCase):
    def test_page_offers_the_project_choices_and_sends_the_limit(self):
        for text in ("First 10 projects", "First 20 projects", "All projects (slow)", "limit:$('limit').value"):
            self.assertIn(text, server.PAGE)
        self.assertIn("fetch('/api/update/apply',{method:'POST',body:'{}'})", server.PAGE)      # the Update call is not touched by the limit


class UpdateButton(unittest.TestCase):
    def test_update_button_is_always_in_the_page_and_checks_on_click(self):
        self.assertIn('id="updBtn"', server.PAGE)
        self.assertIn('onclick="updateClick()"', server.PAGE)
        self.assertIn("async function updateClick()", server.PAGE)
        self.assertIn("You have the latest version", server.PAGE)         # said when there is nothing newer
        self.assertIn("fetch('/api/update/apply',{method:'POST',body:'{}'})", server.PAGE)
