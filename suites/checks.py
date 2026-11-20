"""Code checks suite (for developers: needs the Studio repository on this Mac). Runs the checks that are not about clicking in the app:
the GraphQL schema drift check and the Swift unit tests of the offline package. On a QA Mac that only has the tester these are skipped
with a plain sentence, never passed silently. The repository is found next to the tester (a working copy), through the STUDIO_REPO
environment variable, or through "studio_repo" in settings.json."""
import os
import shutil
import subprocess
import tempfile
import time

from tester import catalog, control, runner
from tester.runner import Skip


def repo_root():
    candidates = [os.environ.get("STUDIO_REPO"), catalog.load_settings().get("studio_repo"), os.path.dirname(runner.ROOT)]
    for path in candidates:
        if path and os.path.exists(os.path.join(path, "Studio.xcodeproj")):
            return path
    return None


def _need_repo():
    root = repo_root()
    if not root:
        raise Skip("the Studio repository is not on this Mac (set STUDIO_REPO or studio_repo in settings.json): developers run this suite")
    return root


def _spawn(command, cwd, out):
    return subprocess.Popen(command, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, text=True)


def _run(context, command, cwd, timeout):
    """Runs a command and returns (exit code, last lines of its output). The wait can be cancelled (Cancel testing / Quit): the child is
    stopped, never left running."""
    context.log("running: " + " ".join(command))
    with tempfile.TemporaryFile("w+") as out:                 # a file, not a pipe: a long `swift test` must never block on a full pipe
        process = _spawn(command, cwd, out)
        began = time.time()
        try:
            while process.poll() is None:
                control.checkpoint()                          # pause holds here; cancel raises StopRun
                if time.time() - began > timeout:
                    raise AssertionError(f"timed out after {timeout} s: " + " ".join(command))
                time.sleep(0.5)
        except BaseException:
            if process.poll() is None:
                process.kill()
            raise
        out.seek(0)
        tail = out.read().strip().splitlines()[-25:]
    for line in tail[-8:]:
        context.log("  " + line)
    return process.returncode, "\n".join(tail)


def schema_drift(context):
    """scripts/check_schema_drift.py: the vendored GraphQL schema against the live backend (removed fields are a crash risk)."""
    root = _need_repo()
    code, tail = _run(context, ["/usr/bin/python3", "scripts/check_schema_drift.py"], root, 300)
    if code == 1 and "RESULT: FAIL" not in tail:
        # exit 1 is also what Python returns for an uncaught error. The live endpoint refusing the introspection request (403/401, no auth
        # token) is a check that could not run: shown as skipped with the reason, never a pass and never a "drift" finding.
        if "HTTP 403" in tail or "HTTP 401" in tail or "403 Forbidden" in tail:
            raise Skip("the schema drift check could not run: the live backend refused the introspection request (HTTP 403). Set "
                       "SCHEMA_DRIFT_AUTH_TOKEN to run it. Nothing was compared: this is neither a pass nor a drift.")
        raise AssertionError("the schema drift check could not run (the live backend could not be read): " + tail[-400:])
    if code == 1:
        raise AssertionError("the GraphQL schema drifted (a type or field was removed): " + tail[-400:])
    if code != 0:
        raise AssertionError(f"the schema drift check could not run (exit {code}): " + tail[-400:])


def offline_package_tests(context):
    """OfflineModeTests: the Swift package with the offline rules, sync, queue, media identity and migration tests."""
    root = _need_repo()
    if not shutil.which("swift"):
        raise Skip("the `swift` tool is not installed on this Mac")
    code, tail = _run(context, ["swift", "test"], os.path.join(root, "OfflineModeTests"), 3000)
    if code != 0:
        raise AssertionError("Swift unit tests failed: " + tail[-600:])


TESTS = [
    ("GraphQL schema drift (scripts/check_schema_drift.py)", schema_drift),
    ("Offline package unit tests (swift test, OfflineModeTests)", offline_package_tests),
]
