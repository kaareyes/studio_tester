"""One start for everything. Run by the system Python (standard library only) from `Studio Tester.command`:
checks what is missing, asks, installs with visible progress (like `npm install`), checks again, then starts the tester.

Steps: 1 tools folder (.venv)  2 packages  3 check the packages work  4 permission + this Mac  5 start the page.
It is safe to run again at any time: whatever is already fine is skipped."""
import hashlib
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv")
VENV_PYTHON = os.path.join(VENV, "bin", "python")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")
STAMP = os.path.join(VENV, ".requirements.sha256")
MIN_PYTHON = (3, 9)
TOTAL = 5


def say(text=""):
    print(text, flush=True)


def step(number, text):
    say(f"\n[{number}/{TOTAL}] {text}")


def ok(text):
    say("  OK   " + text)


def problem(text):
    say("  FIX  " + text)


def ask(question, default=True, answer=None):
    """Yes/no in the Terminal. Enter = the default. Without a keyboard (no terminal) the default is used."""
    suffix = " [Y/n] " if default else " [y/N] "
    if answer is None:
        if not sys.stdin or not sys.stdin.isatty():
            return default
        try:
            answer = input("  ? " + question + suffix)
        except EOFError:
            return default
    answer = answer.strip().lower()
    return default if not answer else answer.startswith("y")


def requirements_hash(path=REQUIREMENTS):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def packages_current(stamp=STAMP, path=REQUIREMENTS):
    try:
        with open(stamp) as handle:
            return handle.read().strip() == requirements_hash(path) != ""
    except OSError:
        return False


def venv_works(python=VENV_PYTHON, runner=subprocess.run):
    if not os.path.exists(python):
        return False
    try:
        result = runner([python, "-c", "import sys; print(sys.version_info[:2] >= %r)" % (MIN_PYTHON,)], capture_output=True, text=True, timeout=30)
    except Exception:
        return False
    return result.returncode == 0 and "True" in result.stdout


def internet(url="https://pypi.org/simple/pip/", opener=urllib.request.urlopen):
    try:
        opener(url, timeout=8).close()
        return True
    except Exception:
        return False


def make_venv(runner=subprocess.run):
    return runner([sys.executable, "-m", "venv", VENV]).returncode == 0


def install_packages(runner=subprocess.run):
    """pip output stays visible, so the person sees it working."""
    runner([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    code = runner([VENV_PYTHON, "-m", "pip", "install", "-r", REQUIREMENTS, "--disable-pip-version-check"]).returncode
    if code == 0:
        with open(STAMP, "w") as handle:
            handle.write(requirements_hash())
    return code == 0


def packages_import(runner=subprocess.run):
    result = runner([VENV_PYTHON, "-c", "import tester.ax, tester.server, suites; print('ok')"], capture_output=True, text=True, cwd=ROOT, timeout=120)
    return result.returncode == 0, (result.stderr or "").strip()[-300:]


def accessibility_on(runner=subprocess.run):
    result = runner([VENV_PYTHON, "-c", "from tester import ax; print(ax.trusted())"], capture_output=True, text=True, cwd=ROOT, timeout=60)
    return "True" in result.stdout


def wait_until(check, seconds, every=3, show=None, clock=time.time, sleep=time.sleep):
    """Polls `check` until it is true or the time is up. Returns True/False."""
    end = clock() + seconds
    while True:
        if check():
            return True
        if clock() >= end:
            return False
        if show:
            show()
        sleep(every)


def main():
    os.chdir(ROOT)
    say("=" * 46)
    say(" Studio Tester: checking this Mac, then starting")
    say("=" * 46)

    step(1, "Tools folder")
    if venv_works():
        ok("already set up")
    else:
        say("  Creating the tools folder (once)...")
        if os.path.isdir(VENV):
            import shutil
            shutil.rmtree(VENV, ignore_errors=True)       # a broken or old one is rebuilt
        if not make_venv() or not venv_works():
            problem("Could not create the tools folder. Send a screenshot of this window to the developers.")
            return 1
        ok("created")

    step(2, "Packages (the test tools)")
    if packages_current():
        ok("all installed")
    else:
        while not internet():
            problem("No internet connection. The packages are downloaded once (about 1 minute).")
            if not ask("Connect to the internet, then press Enter to try again. Try again?", True):
                return 1
            time.sleep(1)
        say("  Installing (you will see the progress):")
        if not install_packages():
            problem("The installation failed (see the lines above).")
            if not ask("Try once more?", True) or not install_packages():
                problem("Still failing. Send a screenshot of this window to the developers.")
                return 1
        ok("installed")

    step(3, "Checking that everything works")
    works, detail = packages_import()
    if not works:
        problem("Something is not right: " + detail)
        if ask("Repair it now (reinstall the packages)?", True):
            if os.path.exists(STAMP):
                os.remove(STAMP)
            if install_packages():
                works, detail = packages_import()
    if not works:
        problem("Could not repair it. Send a screenshot of this window to the developers.")
        return 1
    ok("the tester loads")

    step(4, "Permission and this Mac")
    if accessibility_on():
        ok("Accessibility permission is on (the tester can press Studio's buttons)")
    elif os.environ.get("STUDIO_TESTER_NO_PROMPTS"):
        problem("Accessibility permission is off (skipped waiting: automated run).")
    else:
        problem("Accessibility permission is off. The tester needs it to press Studio's buttons.")
        say("       In the window that opens: switch ON 'Terminal' (the tester app that is running this). I continue by myself.")
        if ask("Open that setting now?", True):
            subprocess.run(["/usr/bin/open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
            if wait_until(accessibility_on, 300, show=lambda: say("       waiting for the switch... (up to 5 minutes)")):
                ok("Accessibility permission is on")
            else:
                problem("Still off. The page will open, but the tests cannot press buttons until it is on. Run this again after switching it on.")
    run = subprocess.run([VENV_PYTHON, "-m", "tester.setup_check"], cwd=ROOT)
    if run.returncode != 0:
        say("  (The lines marked FIX above are not blockers for opening the page; fix them before running tests.)")

    step(5, "Starting")
    say("  The test page opens in your browser. Keep this window open while you test. Close it to stop.\n")
    os.execv(VENV_PYTHON, [VENV_PYTHON, "-m", "tester.server"])


if __name__ == "__main__":
    sys.exit(main())
