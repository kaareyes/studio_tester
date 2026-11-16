"""A shareable copy of every report. The program lives in a hidden folder (`.studio_tester`), so the run folders under it are hard to find.
After each run the tester also writes ONE zip per run into a visible `Reports` folder next to `Studio Tester.command`: send that file as it is."""
import os
import re
import subprocess
import zipfile

from . import runner


def shared_dir(root=None):
    """<install folder>/Reports when the program is in a hidden folder (a normal install); None for a plain working copy (its reports/
    folder is already visible)."""
    root = os.path.abspath(root or runner.ROOT)
    if os.path.basename(root).startswith("."):
        return os.path.join(os.path.dirname(root), "Reports")
    return None


def make_copy(run_dir, dest_dir=None):
    """Zips everything in one run folder (report.html, results.json, screenshots, logs, incidents, crash reports) into
    <dest_dir>/<run folder name>.zip. Returns the zip path, or None when there is nowhere visible to put it."""
    dest_dir = dest_dir or shared_dir()
    if not dest_dir or not os.path.isdir(run_dir):
        return None
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(run_dir.rstrip("/"))
    path = os.path.join(dest_dir, name + ".zip")
    temporary = path + ".part"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for base, _, files in os.walk(run_dir):
            for file_name in files:
                full = os.path.join(base, file_name)
                archive.write(full, os.path.join(name, os.path.relpath(full, run_dir)))
    os.replace(temporary, path)          # never a half-written zip in the visible folder
    return path


def zip_for(folder, dest_dir=None):
    """The shared zip of a run folder name, or None (also refuses names that could point outside the folder)."""
    dest_dir = dest_dir or shared_dir()
    if not dest_dir or not re.fullmatch(r"[0-9A-Za-z_.\-]+", folder or ""):
        return None
    path = os.path.join(dest_dir, folder + ".zip")
    return path if os.path.isfile(path) else None


def reveal(path):
    """Shows a file (or folder) selected in Finder."""
    subprocess.run(["/usr/bin/open", "-R", path])
