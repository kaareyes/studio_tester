"""Can this Studio app be tested? Only builds made from the branch below (or newer) carry the button names (`.testID(...)`) the tester
uses to find buttons. An older build has none of them, so every click would fail. The check reads the app FILE (it does not need the
app to be open or signed in): it looks for the control names inside the app's code. A build without them gets a plain answer:
"App version not supported for testing"."""
import mmap
import os
import plistlib
import threading

SUPPORTED_BRANCH = "merge/metadata-macos-v2-into-v2-offlinemode"

# Names the tester cannot work without (all must be in the app). Only names of 16 bytes or more are used for this decision: Swift keeps a
# string literal of 15 bytes or less INSIDE the program's instructions in an optimized build (not as readable text), so a short name
# such as "login.signIn" could look missing in a good Release or archived build. Longer names are always stored as text.
# Names ending with a dot are prefixes: the app adds the id at run time.
CORE = ["sessions.row.name.", "session.enterAuditionMode", "session.talent.add.", "session.talent.slate.", "session.talent.photo.",
        "session.groupImage.photo", "capture.finalize", "capture.fullscreenStop", "statusBar.projectSelector", "queue.batch.expand",
        "alert.rightButton"]
# Newer controls: a build without them is still testable, but these features are not (shown as a note, not a block).
OPTIONAL = {"Link to talent (Queue)": "queue.linkToTalent.overlay", "Load more talents": "session.talents.loadMore",
            "Offline Sync indicator": "statusBar.offlineSyncIndicator", "Delete a take": "capture.take.delete."}

MACHO = (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf", b"\xbe\xba\xfe\xca")


def message(version=None):
    shown = f" (this app is version {version})" if version else ""
    return (f'App version not supported for testing{shown}. Testing only works with builds starting from the branch "{SUPPORTED_BRANCH}" '
            "(that build and every newer one). Older builds do not have the button names the tester needs. "
            "Install the latest Studio (macOS) - Test build from that branch and choose it again.")


def version_of(app_path):
    try:
        with open(os.path.join(app_path, "Contents", "Info.plist"), "rb") as handle:
            info = plistlib.load(handle)
        short, build = info.get("CFBundleShortVersionString", ""), info.get("CFBundleVersion", "")
        return f"{short} ({build})" if build else str(short)
    except Exception:
        return ""


def code_files(app_path):
    """The program files of the app: the main executable and any library next to it (a Debug build keeps its code in a .debug.dylib)."""
    folder = os.path.join(app_path, "Contents", "MacOS")
    found = []
    try:
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and not os.path.islink(path) and os.path.getsize(path) > 0:
                with open(path, "rb") as handle:
                    if handle.read(4) in MACHO:
                        found.append(path)
    except OSError:
        pass
    return found


def scan(app_path):
    """{name: True/False} for every name of CORE and OPTIONAL, or None when the app's code cannot be read."""
    files = code_files(app_path)
    if not files:
        return None
    wanted = list(CORE) + list(OPTIONAL.values())
    found = {name: False for name in wanted}
    for path in files:
        try:
            with open(path, "rb") as handle:
                mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
                try:
                    for name in wanted:
                        if not found[name] and mapped.find(name.encode()) >= 0:
                            found[name] = True
                finally:
                    mapped.close()
        except (OSError, ValueError):
            continue
    return found


def judge(found, version=""):
    """The answer from a scan: state 'ok' | 'unsupported' | 'unknown'."""
    result = {"state": "unknown", "version": version, "branch": SUPPORTED_BRANCH, "missing": [], "notes": [], "message": ""}
    if found is None:
        result["message"] = "Could not read this app's files, so it is not known whether it can be tested."
        return result
    missing = [name for name in CORE if not found.get(name)]
    if missing:
        result.update(state="unsupported", missing=missing, message=message(version))
        return result
    result["state"] = "ok"
    result["notes"] = [f"{feature} is not in this build (not testable)" for feature, name in OPTIONAL.items() if not found.get(name)]
    return result


def check(app_path):
    return judge(scan(app_path), version_of(app_path))


# The page asks every second: the scan (a few seconds for a big Debug build) runs once in the background and is remembered.
_cache = {}
_lock = threading.Lock()


def _signature(app_path):
    parts = []
    for path in code_files(app_path):
        stat = os.stat(path)
        parts.append((path, stat.st_size, int(stat.st_mtime)))
    return tuple(parts)


def cached(app_path, scanner=check):
    """The answer if it is known, else {'state': 'checking'} and a background scan starts. A rebuilt app (changed file) is scanned again."""
    signature = _signature(app_path)
    with _lock:
        entry = _cache.get(app_path)
        if entry and entry["signature"] == signature:
            return entry["result"] if entry["result"] is not None else {"state": "checking"}
        _cache[app_path] = {"signature": signature, "result": None}

    def work():
        result = scanner(app_path)
        with _lock:
            current = _cache.get(app_path)
            if current and current["signature"] == signature:
                current["result"] = result
    threading.Thread(target=work, daemon=True).start()
    return {"state": "checking"}
