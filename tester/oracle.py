"""The data-integrity check. Reads the Test app's local database (read-only; it never writes) and says, in plain sentences, what is
wrong. Run it after every step of a stress run. It looks for the failures the Studio team cares about most: data that disappeared,
data attached to the wrong audition or session, duplicates, files marked uploaded that are not, and clips left behind.

An expectation (what the run recorded) can be passed in: {"takes": 3, "photos": 1, "slates": 1}. Without one only the general rules run.
"""
import glob
import os
import sqlite3
import urllib.parse

TEST_DB_GLOB = os.path.expanduser("~/Library/Application Support/Studio (macOS) - Test/StudioApp.sqlite")
JOURNAL_DIR = os.path.expanduser("~/Library/Application Support/com.castingapp.studio-test/PendingTakes")


def _connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)


def database_path():
    found = glob.glob(TEST_DB_GLOB)
    return found[0] if found else None


def query(sql, args=(), path=None):
    path = path or database_path()
    if not path:
        return []
    connection = _connect(path)
    try:
        return connection.execute(sql, args).fetchall()
    finally:
        connection.close()


def last_media_pk(path=None):
    """The newest clip row now. Take this before a run; pass it as `since_pk` afterwards."""
    rows = query("select ifnull(max(Z_PK),0) from ZDBMEDIA", path=path)
    return rows[0][0] if rows else 0


def local_path(folder_path):
    """ZFOLDERPATH is stored as a file URL or a path with %20; returns a normal path."""
    text = folder_path or ""
    if text.startswith("file://"):
        text = text[len("file://"):]
    return urllib.parse.unquote(text)


def media_since(since_pk=0, path=None):
    rows = query("select Z_PK, ZAUDITIOID, ZFOLDERPATH, ZISUPLOADED, ZISDELETED from ZDBMEDIA where Z_PK > ? order by Z_PK", (since_pk,), path)
    return [{"pk": r[0], "audition": r[1], "folder": r[2] or "", "uploaded": bool(r[3]), "deleted": bool(r[4])} for r in rows]


def classify(item):
    p = item["folder"]
    if p.endswith("/Snap.jpg"):
        return "talent_photo_cache"             # kept locally for the session on purpose, never uploaded
    if "/ImageAndSlate/" in p and p.endswith(".mp4"):
        return "slate"
    if "/Audition/" in p and p.endswith(".mp4"):
        return "take"
    if p.endswith(".jpg"):
        return "photo"
    return "other"


def session_folder(path):
    """'.../STUDIO APP/<project>/<session>/...' -> '<project>/<session>'."""
    parts = urllib.parse.unquote(path).split("/STUDIO APP/")[-1].split("/")
    return "/".join(parts[:2])


def check(since_pk=0, expect=None, uploaded=None, path=None, check_files=True):
    """Returns a list of problem sentences (empty = clean).

    uploaded: None = do not look at upload state; True = every clip must be uploaded (after the Queue settled);
              False = nothing may be reported uploaded yet (offline)."""
    problems = []
    items = [i for i in media_since(since_pk, path) if not i["deleted"]]
    real = [i for i in items if classify(i) != "talent_photo_cache"]
    groups = {}
    for item in real:
        groups.setdefault(item["audition"], []).append(item)

    seen = {}
    for item in real:
        if item["folder"] and item["folder"] in seen:
            problems.append(f"duplicate: the file {os.path.basename(local_path(item['folder']))} is in the database twice (rows {seen[item['folder']]} and {item['pk']})")
        seen.setdefault(item["folder"], item["pk"])

    for audition, files in groups.items():
        folders = {session_folder(f["folder"]) for f in files if f["folder"]}
        if len(folders) > 1:
            problems.append(f"wrong session: audition {str(audition)[:8]} has files in {len(folders)} session folders: {sorted(folders)}")
        if not audition:
            problems.append(f"{len(files)} clip(s) have no audition at all (rows {[f['pk'] for f in files][:5]})")
        if uploaded is True and any(not f["uploaded"] for f in files):
            problems.append(f"not uploaded: {sum(1 for f in files if not f['uploaded'])} file(s) of audition {str(audition)[:8]} are still waiting after the Queue settled")
        if uploaded is False and any(f["uploaded"] for f in files):
            problems.append(f"marked uploaded while offline: audition {str(audition)[:8]}")
        if check_files:
            for f in files:
                if f["folder"] and not f["uploaded"] and not os.path.exists(local_path(f["folder"])):
                    problems.append(f"lost file: {os.path.basename(local_path(f['folder']))} waits to upload but is not on disk")

    if expect:
        counts = {"take": 0, "slate": 0, "photo": 0}
        for item in real:
            if classify(item) in counts:
                counts[classify(item)] += 1
        for key, label in (("takes", "take"), ("slates", "slate"), ("photos", "photo")):
            if key in expect and counts[label] < expect[key]:
                problems.append(f"missing {label}s: recorded {expect[key]}, database has {counts[label]}")
            if key == "takes" and key in expect and counts[label] > expect[key]:
                problems.append(f"extra takes: recorded {expect[key]}, database has {counts[label]}")
    return problems


def journal_files():
    try:
        return sorted(f for f in os.listdir(JOURNAL_DIR) if f.endswith(".json"))
    except OSError:
        return []


def check_idle_journal():
    """When nothing is processing, no take may be waiting in the pending-take journal."""
    left = journal_files()
    return [f"pending-take journal is not empty while idle: {len(left)} take(s) still listed ({left[:3]})"] if left else []
