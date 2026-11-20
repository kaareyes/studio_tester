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
    rows = query("select Z_PK, ZAUDITIOID, ZFOLDERPATH, ZISUPLOADED, ZISDELETED, ZAUDITIONTYPE, ZGROUPTYPE, ZFILETYPE, ZNAMETAG "
                 "from ZDBMEDIA where Z_PK > ? order by Z_PK", (since_pk,), path)
    return [{"pk": r[0], "audition": r[1], "folder": r[2] or "", "uploaded": bool(r[3]), "deleted": bool(r[4]),
             "audition_type": r[5] or "", "group_type": r[6] or "", "filetype": r[7] or "", "name_tag": r[8] or ""} for r in rows]


def is_merged_group_scene(item):
    """True for the individual take of a GROUP audition whose stitched merge video exists. Studio uploads only the merged video then and
    leaves these scene clips with isUploaded=0 ON PURPOSE (found by reading the app: OfflineQueueRebuild.isIndividualGroupVideoScene,
    and seen live: 'GroupMerge-<uuid>' folder next to the scenes). They are not waiting for anything."""
    if not (item.get("audition_type") == "group" and item.get("group_type") == "audition" and item.get("filetype") == "video"):
        return False
    path = local_path(item.get("folder"))
    marker = "/STUDIO APP/"
    if marker not in path or not item.get("audition"):
        return False
    root, rest = path.split(marker, 1)
    parts = rest.split("/")
    if len(parts) < 3:
        return False
    session_dir = os.path.join(root + marker.rstrip("/"), parts[0], parts[1])
    wanted = str(item["audition"]).lower()
    try:
        for name in os.listdir(session_dir):
            if name.lower() == wanted and glob.glob(os.path.join(session_dir, name, "GroupMerge-*")):
                return True
    except OSError:
        return False
    return False


def pending_since(since_pk=0, path=None):
    """Clips that are really waiting to upload: not uploaded, not deleted, and belonging to an audition that HAS video (a take or a slate
    clip). A group image alone is the placeholder Studio makes for the NEXT audition; it uploads when that audition is finalized, so it
    must not hold up a wait or fail a check."""
    items = [i for i in media_since(since_pk, path) if not i["deleted"] and classify(i) != "talent_photo_cache"]
    with_video = {i["audition"] for i in items if classify(i) in ("take", "slate")}
    return [i for i in items if not i["uploaded"] and i["audition"] in with_video and not is_merged_group_scene(i)]


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
        has_video = any(classify(f) in ("take", "slate") for f in files)
        if uploaded is True and has_video and any(not f["uploaded"] and not is_merged_group_scene(f) for f in files):
            problems.append(f"not uploaded: {sum(1 for f in files if not f['uploaded'] and not is_merged_group_scene(f))} file(s) of audition {str(audition)[:8]} are still waiting after the Queue settled")
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
