"""Checks that this Mac is ready for the tests and says what to fix in plain words. Exit code 0 = ready."""
import os
import sys

from . import cameras


def checks():
    """[(ok, text)] in display order."""
    results = []
    try:
        from . import ax
        if ax.trusted():
            results.append((True, "Accessibility permission is on (the tests can press Studio's buttons)."))
        else:
            results.append((False, "Accessibility permission is off. Open System Settings > Privacy & Security > Accessibility "
                                   "and switch ON 'Terminal'. Then run this setup again."))
    except Exception as error:
        results.append((False, f"The test tools are not installed correctly ({type(error).__name__}). Run the setup again."))
    found = cameras.list_cameras()
    if not found:
        results.append((False, "No camera was found. Connect a camera (or open the lid) and run this setup again."))
    else:
        names = ", ".join(c["name"] + (" (built-in)" if c["built_in"] else "") + ("" if c["usable"] else " (not used)") for c in found)
        results.append((True, "Cameras found: " + names))
        camera, reason = cameras.choose_camera()
        if camera:
            results.append((True, f"Camera for the tests: {camera['name']} - {reason}."))
        else:
            others = [c["name"] for c in found if c["usable"] and not c["built_in"]]
            if others:
                # Not a blocker: the tester can choose the other camera on the test page. The default stays the built-in one.
                results.append((True, f"The built-in camera cannot be used right now ({reason}). "
                                      f"On the test page you can choose: {', '.join(others)}."))
            else:
                results.append((False, "No camera can be used right now: " + reason + "."))
    home = os.path.expanduser("~")
    free_gb = os.statvfs(home).f_bavail * os.statvfs(home).f_frsize / 1e9
    results.append((free_gb >= 10, f"Free disk space: {free_gb:.0f} GB" + ("" if free_gb >= 10 else " (the tests record video: free at least 10 GB)")))
    return results


def main():
    ready = True
    for ok, text in checks():
        print(("  OK   " if ok else "  FIX  ") + text)
        ready = ready and ok
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
