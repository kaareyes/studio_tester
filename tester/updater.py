"""Update button: brings this folder up to the latest published version, in place. Needs no git and no GitHub account: it downloads the
zip of the public repo's `release` branch over HTTPS, replaces only the code, keeps the tester's own data, checks that the new code
starts, and puts the old code back if it does not.

Kept on update: catalog.json, settings.json, reports/, .venv, .update_backup. Replaced: the CODE_PATHS below."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from . import runner

ROOT = runner.ROOT
DEFAULT_REPO = "kaareyes/studio_tester"
BRANCH = "release"                     # QA follows this branch; main is work in progress and never reaches them
CODE_PATHS = ["tester", "suites", "tests", "docs", "NAMES.md", "README.md", "requirements.txt", "VERSION",
              "Studio Tester.command", "Install Studio Tester.command", "Start Studio Tester.command", "install.sh"]
KEEP = {"catalog.json", "settings.json", "reports", ".venv", ".update_backup", "release.json"}
BACKUPS = os.path.join(ROOT, ".update_backup")
TIMEOUT = 20


def local_version(root=None):
    try:
        with open(os.path.join(root or ROOT, "VERSION")) as handle:
            return handle.read().strip() or "0"
    except OSError:
        return "0"


def version_tuple(text):
    parts = []
    for piece in str(text).strip().lstrip("v").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def newer(remote, local):
    return version_tuple(remote) > version_tuple(local)


def urls(repo=None, branch=BRANCH):
    repo = repo or DEFAULT_REPO
    return {"info": f"https://raw.githubusercontent.com/{repo}/{branch}/release.json",
            "zip": f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"}


def fetch(url, timeout=TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": "studio-tester-updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check(repo=None, root=None, fetcher=fetch, branch=BRANCH):
    """What the page shows. Never raises: a failure becomes a plain sentence."""
    here = local_version(root)
    result = {"current": here, "latest": None, "available": False, "notes": "", "min_build": "", "error": None}
    try:
        info = json.loads(fetcher(urls(repo, branch)["info"]).decode())
        result.update(latest=str(info.get("version", "")), notes=str(info.get("notes", ""))[:2000], min_build=str(info.get("min_build", "")))
        result["available"] = bool(result["latest"]) and newer(result["latest"], here)
    except Exception as error:
        result["error"] = f"Could not check for updates ({type(error).__name__}). Is this Mac online?"
    return result


def _safe_members(archive):
    """The zip from GitHub holds one top folder (<repo>-<branch>/). Returns (top, members) and refuses paths that escape."""
    names = [n for n in archive.namelist() if n and not n.endswith("/")]
    if not names:
        raise ValueError("the downloaded update is empty")
    top = names[0].split("/")[0]
    members = []
    for name in names:
        if not name.startswith(top + "/"):
            raise ValueError("the downloaded update has an unexpected layout")
        relative = name[len(top) + 1:]
        if relative.startswith(("/", "..")) or ".." in relative.split("/") or os.path.isabs(relative):
            raise ValueError("the downloaded update has an unsafe path: " + relative)
        members.append((name, relative))
    return members


def _code_files(members):
    wanted = []
    for name, relative in members:
        first = relative.split("/")[0]
        if first in CODE_PATHS and first not in KEEP:
            wanted.append((name, relative))
    return wanted


def self_test(root):
    """Does the NEW code start? Imports the page server and every suite in a fresh process."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import tester.server, suites; "
            "print(len(suites.SUITES), 'suites')")
    result = subprocess.run([sys.executable, "-c", code, root], capture_output=True, text=True, timeout=120, cwd=root)
    return result.returncode == 0, (result.stderr or result.stdout).strip()[-400:]


def apply(repo=None, root=None, fetcher=fetch, test=self_test, branch=BRANCH, busy=lambda: False):
    """Downloads and installs the latest version into `root`. Returns {'ok', 'version', 'message'}. Rolls back on any failure."""
    root = root or ROOT
    if busy():
        return {"ok": False, "version": local_version(root), "message": "A test is running. Wait until it finishes, then update."}
    old_version = local_version(root)
    try:
        archive = zipfile.ZipFile(io.BytesIO(fetcher(urls(repo, branch)["zip"], timeout=120)))
    except Exception as error:
        return {"ok": False, "version": old_version, "message": f"Download failed ({type(error).__name__}). Nothing was changed."}
    try:
        files = _code_files(_safe_members(archive))
        if not any(rel == "VERSION" for _, rel in files) or not any(rel.startswith("tester/") for _, rel in files):
            raise ValueError("the downloaded update does not look like the Studio Tester")
    except Exception as error:
        return {"ok": False, "version": old_version, "message": f"The update was refused: {error}. Nothing was changed."}

    backup = os.path.join(root, ".update_backup", f"{old_version}-{int(time.time())}")
    os.makedirs(backup, exist_ok=True)
    touched = []
    try:
        for first in CODE_PATHS:
            source = os.path.join(root, first)
            if os.path.exists(source):
                target = os.path.join(backup, first)
                (shutil.copytree if os.path.isdir(source) else shutil.copy2)(source, target)
        # Code folders that the new version owns are replaced as a whole (a file removed upstream must disappear here too).
        for first in {rel.split("/")[0] for _, rel in files}:
            path = os.path.join(root, first)
            if os.path.isdir(path):
                shutil.rmtree(path)
        for name, relative in files:
            destination = os.path.join(root, relative)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(name) as source, open(destination, "wb") as target:
                shutil.copyfileobj(source, target)
            if relative.endswith(".command"):
                os.chmod(destination, 0o755)
            touched.append(relative)
        ok, detail = test(root)
        if not ok:
            raise RuntimeError("the new version does not start: " + detail)
    except Exception as error:
        _restore(backup, root)
        return {"ok": False, "version": local_version(root), "message": f"The update failed and the old version was put back ({error})."}
    _prune_backups(root)
    new_version = local_version(root)
    return {"ok": True, "version": new_version, "message": f"Updated {old_version} to {new_version}. The tester restarts now.",
            "packages_changed": _requirements_changed(backup, root)}


def _restore(backup, root):
    for first in CODE_PATHS:
        saved = os.path.join(backup, first)
        target = os.path.join(root, first)
        if os.path.exists(saved):
            if os.path.isdir(target):
                shutil.rmtree(target)
            elif os.path.exists(target):
                os.remove(target)
            (shutil.copytree if os.path.isdir(saved) else shutil.copy2)(saved, target)


def _requirements_changed(backup, root):
    try:
        with open(os.path.join(backup, "requirements.txt")) as old, open(os.path.join(root, "requirements.txt")) as new:
            return old.read() != new.read()
    except OSError:
        return False


def _prune_backups(root, keep=3):
    folder = os.path.join(root, ".update_backup")
    try:
        old = sorted(os.listdir(folder))[:-keep]
        for name in old:
            shutil.rmtree(os.path.join(folder, name), ignore_errors=True)
    except OSError:
        pass


def install_packages(root=None):
    """Runs pip for a changed requirements.txt (inside the tester's own .venv)."""
    root = root or ROOT
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", os.path.join(root, "requirements.txt")], capture_output=True, timeout=600)


def restart():
    """Replaces this process with a fresh one running the new code (the same command that started it)."""
    os.execv(sys.executable, [sys.executable, "-m", "tester.server"])
