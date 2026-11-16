"""Cameras on this Mac. The tests always use the BUILT-IN camera unless another one is chosen on purpose."""
import json
import subprocess

BUILT_IN_HINTS = ("facetime", "built-in", "builtin", "isight")
# Not real capture cameras for a test run: a phone used as a webcam (Continuity Camera) and virtual cameras.
IGNORED_HINTS = ("iphone", "ipad", "virtual", "obs", "snap camera", "desk view")


def list_cameras():
    """[{name, model, unique_id, built_in, usable}] in the order macOS reports them. Empty when none or on error."""
    try:
        out = subprocess.run(["/usr/sbin/system_profiler", "SPCameraDataType", "-json"],
                             capture_output=True, text=True, timeout=30).stdout
        items = json.loads(out or "{}").get("SPCameraDataType", [])
    except Exception:
        return []
    cameras = []
    for item in items:
        name = item.get("_name", "")
        model = item.get("spcamera_model-id", "")
        text = (name + " " + model).lower()
        cameras.append({
            "name": name,
            "model": model,
            "unique_id": item.get("spcamera_unique-id", ""),
            "built_in": any(h in text for h in BUILT_IN_HINTS),
            "usable": not any(h in text for h in IGNORED_HINTS),
        })
    return cameras


def lid_is_closed():
    """True / False, or None when it cannot be told (desktop Mac). The built-in camera does not work with the lid closed."""
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-r", "-k", "AppleClamshellState", "-d", "4"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if "AppleClamshellState" in line:
            return "Yes" in line
    return None


def choose_camera(preferred_name=None):
    """(camera or None, reason). The built-in camera is the default; `preferred_name` picks another one by name on purpose."""
    cameras = [c for c in list_cameras() if c["usable"]]
    if preferred_name:
        for camera in cameras:
            if camera["name"].lower() == preferred_name.lower():
                return camera, "chosen by name"
        return None, f"camera '{preferred_name}' is not connected"
    built_in = next((c for c in cameras if c["built_in"]), None)
    if built_in is None:
        return None, "this Mac has no built-in camera (choose an external camera on the test page)"
    if lid_is_closed():
        return None, "the built-in camera cannot be used while the lid is closed (open the lid, or choose an external camera)"
    return built_in, "built-in camera (default)"
