import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from tester import server, catalog


class Server(unittest.TestCase):
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
