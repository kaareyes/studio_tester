"""Find and use Studio's controls by NAME (the accessibility identifier set in the app with `.testID(...)`), never by screen
position. Needs the Accessibility permission for the app that runs Python (Terminal)."""
import re
import subprocess
import time

from ApplicationServices import (
    AXIsProcessTrusted, AXUIElementCopyAttributeValue, AXUIElementCreateApplication, AXUIElementPerformAction,
    AXValueGetValue, kAXValueCGPointType, kAXValueCGSizeType,
)
import Quartz

from . import control

MAX_DEPTH = 40
# Studio's rule: `screen.control[.more]`, e.g. `session.enterAuditionMode`, `queue.row.status`, `session.talent.<id>`.
STUDIO_NAME = re.compile(r"^(?!com\.|org\.|NS|_)[a-z][A-Za-z0-9]*(\.[A-Za-z0-9_-]+)+$")


class ControlNotFound(Exception):
    pass


def trusted():
    return bool(AXIsProcessTrusted())


TARGET_PATH = None      # the Studio app chosen on the page (path of the .app); None = the first Studio found


def _studio_processes(process_pattern):
    """[(pid, command)] of running Studio apps (not the `script` wrapper the tester starts them with)."""
    out = subprocess.run(["/usr/bin/pgrep", "-fl", "^/.*" + process_pattern + "[^/]*$"], capture_output=True, text=True).stdout.splitlines()
    found = []
    for line in out:
        pid, _, command = line.partition(" ")
        if not pid.isdigit():
            continue                       # the continuation line of a multi-line command of some other program
        if not command.startswith(("/usr/bin/script", "script ")):
            found.append((int(pid), command))
    return found


def app_path_of(command):
    return command.split(".app/")[0] + ".app" if ".app/" in command else None


def list_apps(process_pattern):
    """[(pid, app path)] of every Studio running now (Test, Develop, Staging, Production...)."""
    return [(pid, app_path_of(command)) for pid, command in _studio_processes(process_pattern) if app_path_of(command)]


def pid_of(process_pattern):
    """The process id of the running Studio (the chosen app when one is chosen), or None."""
    # Only a process whose command line STARTS with the app's path: the `script` wrapper that the tester (or a person) used to start
    # Studio also contains the path, but it has no windows, so its accessibility tree is empty.
    for pid, command in _studio_processes(process_pattern):
        if TARGET_PATH is None or command.startswith(TARGET_PATH + "/"):
            return pid
    return None


def _attr(element, name):
    error, value = AXUIElementCopyAttributeValue(element, name, None)
    return value if error == 0 else None


# Rows and cards are listed as ONE element each and their insides are not walked unless asked (`within=card`): a list with hundreds of
# rows has tens of thousands of accessibility nodes, and walking all of them takes minutes.
PRUNE_PREFIXES = ("syncTalent.card.", "queue.batch.", "queue.offline.row.", "queue.failedTake.", "sessions.row.menu.", "offlineSync.row.")
PRUNE_EXACT_PREFIX_ALLOW = ("queue.batch.name", "queue.batch.talentCount", "queue.batch.fileCount", "queue.batch.size", "queue.batch.status",
                            "queue.batch.percent", "queue.batch.progress", "queue.batch.retry", "queue.batch.expand", "queue.batch.syncedFromOffline",
                            "queue.batch.completedCount", "queue.batch.failedCount", "queue.batch.renderWarning")


def _is_container(identifier):
    """A row or card container (named with an id after the prefix) whose insides are skipped while walking."""
    if not identifier or not identifier.startswith(PRUNE_PREFIXES):
        return False
    return not identifier.startswith(PRUNE_EXACT_PREFIX_ALLOW)


def _walk(element, depth=0, prune=True):
    yield element
    if depth >= MAX_DEPTH:
        return
    if prune and _is_container(_attr(element, "AXIdentifier")):
        return
    for child in _attr(element, "AXChildren") or []:
        yield from _walk(child, depth + 1, prune)


class App:
    def __init__(self, pid):
        self.pid = pid
        self.root = AXUIElementCreateApplication(pid)

    # --- finding

    def find_all(self, identifier=None, prefix=None, within=None):
        """Every element whose name equals `identifier` or starts with `prefix`. Inside a row or card (`within`) everything is searched."""
        found = []
        for element in (_walk(within, prune=False) if within is not None else _walk(self.root)):
            name = _attr(element, "AXIdentifier")
            if not name:
                continue
            if (identifier and name == identifier) or (prefix and name.startswith(prefix)):
                found.append(element)
        # A pop-up: SwiftUI gives EVERY part of it the container's name `alert.dialog` (the X, icon, title, message and buttons), so the
        # names alert.title / alert.message / alert.okButton / alert.leftButton / alert.rightButton / alert.closeButton are worked out
        # from the parts (role, text, position). Found live: without this no pop-up could ever be read or answered.
        if not found and within is None and identifier and identifier.startswith("alert.") and identifier != "alert.dialog":
            found = self._alert_part(identifier)
        return found

    def native_sheet(self):
        """A native macOS sheet over Studio's window (for example 'Stop Recording?'), which is not one of the app's named controls and
        blocks every click behind it. Returns {'title', 'message', 'buttons': [(text, element)]} or None."""
        for window in _attr(self.root, "AXWindows") or []:
            for child in _attr(window, "AXChildren") or []:
                if _attr(child, "AXRole") != "AXSheet":
                    continue
                texts, buttons = [], []
                for part in _attr(child, "AXChildren") or []:
                    role = _attr(part, "AXRole")
                    if role == "AXStaticText":
                        texts.append(self.text(part))
                    elif role == "AXButton":
                        buttons.append((self.text(part), part))
                return {"title": texts[0] if texts else "", "message": texts[1] if len(texts) > 1 else "", "buttons": buttons}
        return None

    def press_element(self, element):
        """A real click in the middle of one element (used for parts that have no name of their own)."""
        frame = self.stable_frame(element)
        if frame is None or frame[2] <= 0:
            raise ControlNotFound("cannot press an element without a frame")
        self.activate()
        x, y, width, height = frame
        self.make_sure_studio_is_on_top(x + width / 2, y + height / 2)
        click(x + width / 2, y + height / 2)

    def _alert_part(self, identifier):
        parts = self.find_all(identifier="alert.dialog")
        if not parts:
            return []
        texts = [e for e in parts if _attr(e, "AXRole") == "AXStaticText"]
        buttons = [e for e in parts if _attr(e, "AXRole") == "AXButton"]
        close = [e for e in buttons if self.text(e).strip().lower() == "close"]
        others = sorted((e for e in buttons if e not in close), key=lambda e: (self.frame(e) or (0, 0))[0])
        if identifier.startswith("alert.button."):
            wanted = identifier[len("alert.button."):].replace("_", " ").lower()      # by the words on the button: its place (left or right) differs per pop-up
            return [e for e in buttons if self.text(e).strip().lower() == wanted][:1]
        if identifier == "alert.title":
            return texts[:1]
        if identifier == "alert.message":
            return texts[1:2]
        if identifier == "alert.closeButton":
            return close[:1]
        if identifier == "alert.okButton":
            return others if len(others) == 1 else []
        if identifier == "alert.leftButton":
            return others[:1] if len(others) >= 2 else []
        if identifier == "alert.rightButton":
            return others[-1:] if len(others) >= 2 else []
        return []

    def find(self, identifier, within=None):
        found = self.find_all(identifier=identifier, within=within)
        if not found:
            raise ControlNotFound(identifier)
        return found[0]

    def exists(self, identifier, within=None):
        return bool(self.find_all(identifier=identifier, within=within))

    def wait_for(self, identifier, timeout=15.0, within=None, gone=False):
        """Waits until the control is there (or, with gone=True, until it is no longer there). Returns the element or None."""
        from . import activity, patience
        wait = patience.Patience(timeout, lambda: patience.process_tree_cpu(self.pid), extend=10.0, cap=timeout * 2)   # a busy Studio gets up to 3x
        activity.set(f"waiting for the control '{identifier}' to {'disappear' if gone else 'appear'} on Studio's screen")
        while True:
            found = self.find_all(identifier=identifier, within=within)
            if gone and not found:
                return None
            if not gone and found:
                return found[0]
            if wait.expired():
                raise ControlNotFound(("still shown: " if gone else "not shown: ") + identifier)
            time.sleep(0.25)

    def names(self, prefix=""):
        """Every Studio test name on screen now (for the build check and for failure reports). macOS and SwiftUI give their own
        identifiers to menus and windows; only names that follow Studio's rule `screen.control` are returned."""
        found = {n for n in (_attr(e, "AXIdentifier") for e in _walk(self.root)) if n and STUDIO_NAME.match(n) and n.startswith(prefix)}
        return sorted(found)

    # --- reading

    @staticmethod
    def text(element):
        """What the control shows: its value, else its title, else its description."""
        for name in ("AXValue", "AXTitle", "AXDescription"):
            value = _attr(element, name)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def enabled(element):
        value = _attr(element, "AXEnabled")
        return True if value is None else bool(value)

    @staticmethod
    def frame(element):
        position, size = _attr(element, "AXPosition"), _attr(element, "AXSize")
        if position is None or size is None:
            return None
        ok_p, point = AXValueGetValue(position, kAXValueCGPointType, None)
        ok_s, extent = AXValueGetValue(size, kAXValueCGSizeType, None)
        if not (ok_p and ok_s):
            return None
        return point.x, point.y, extent.width, extent.height

    def stable_frame(self, element, tries=8, pause=0.15):
        """The frame of a control once it stopped moving (the window being dragged, a list still scrolling, an animation): two reads in
        a row must agree. Returns the last frame read when it never settles."""
        last = None
        for _ in range(tries):
            current = self.frame(element)
            if current is not None and current == last:
                return current
            last = current
            time.sleep(pause)
        return last

    def scroll_into_view(self, element, tries=10):
        """A row of a list that is scrolled out of Studio's window still has a frame, but a click there would land in another app (found
        live: talent rows below the fold). The list under it is scrolled, like a person does, until the element sits inside the window."""
        for _ in range(tries):
            frame, window = self.frame(element), self.window_frame()
            if not frame or not window or frame[2] <= 0:
                return
            cx, cy = frame[0] + frame[2] / 2, frame[1] + frame[3] / 2
            margin_y = window[3] * 0.08
            if window[0] < cx < window[0] + window[2] and window[1] + margin_y < cy < window[1] + window[3] - margin_y:
                return
            x = min(max(cx, window[0] + 30), window[0] + window[2] - 30)
            y = window[1] + window[3] / 2
            self.activate()
            scroll(0, 12 if cy > window[1] + window[3] / 2 else -12, x, y)
            time.sleep(0.6)

    def make_sure_studio_is_on_top(self, x, y, tries=4):
        """A click lands on whatever window is on top at that point. When another app covers Studio there (a window opened, Studio went to
        the back after a relaunch), Studio is raised again and the check repeated; when it still does not work the step is reported as
        a screen failure (it is retried) and NEVER clicks into the other app."""
        owner = None
        for _ in range(tries):
            owner = window_owner_at(x, y)
            if owner is None or owner[0] == self.pid:
                return
            self.activate()
            time.sleep(0.4)
        raise ControlNotFound(f"another window covers Studio where the click would land ({owner[1]}): not clicked")

    # --- acting

    # --- finding rows that are not on screen (lists draw only the rows in view)

    def activate(self):
        """Brings Studio to the front, so scrolls and clicks land on it and not on a window that covers it."""
        from ApplicationServices import AXUIElementSetAttributeValue
        AXUIElementSetAttributeValue(self.root, "AXFrontmost", True)
        time.sleep(0.6)

    def window_frame(self):
        """(x, y, width, height) of Studio's main window, or None."""
        windows = _attr(self.root, "AXWindows") or []
        for window in windows:
            frame = self.frame(window)
            if frame and frame[2] > 400:
                return frame
        return None

    def scroll_find(self, identifier=None, prefix=None, text_contains=None, max_scrolls=150, step=10, settle=0.7):
        """Scrolls the page (to the end, then back to the top) until a control with this name, or a named control whose text
        contains `text_contains`, is on screen. Returns the element or raises ControlNotFound. This is what a person does when a
        session or an audition is not in view: it works however long the list is."""
        def look():
            for element in self.find_all(identifier=identifier, prefix=prefix):
                if text_contains is None or text_contains.lower() in (self.text(element) or "").lower():
                    return element
            return None
        found = look()
        if found is not None:
            return found
        self.activate()
        frame = self.window_frame()
        if frame is None:
            raise ControlNotFound("no window to scroll")
        x, y, width, height = frame
        cx, cy = x + width / 2, y + height * 0.55
        for _ in range(40):                       # start from the top, like a person who looks through a list from the beginning
            scroll(0, -60, cx, cy)
            time.sleep(0.05)
        time.sleep(0.5)
        found = look()
        if found is not None:
            return found
        for direction in (1, -1):                 # first towards the end, then all the way back up
            seen_same = 0
            last = None
            for _ in range(max_scrolls):
                scroll(0, direction * step, cx, cy)
                time.sleep(settle)
                found = look()
                if found is not None:
                    return found
                names = tuple(self.names())
                seen_same = seen_same + 1 if names == last else 0
                last = names
                if seen_same >= 6:                # the list stopped growing and moving (pages load a moment after a scroll): the end
                    break
        raise ControlNotFound(f"not found after scrolling: {identifier or prefix} {text_contains or ''}".strip())

    def press_scrolling(self, identifier, timeout=15.0, **kwargs):
        """Like press, but scrolls the page to find the control first."""
        self.scroll_find(identifier=identifier, **kwargs)
        self.press(identifier, timeout=timeout)

    def type_text(self, identifier, text, clear=True, timeout=15.0):
        """Clicks a text field by name and types into it with key events (clears it first by default)."""
        self.activate()
        element = self.wait_for(identifier, timeout=timeout)
        frame = self.frame(element)
        if frame is None:
            raise ControlNotFound("no frame: " + identifier)
        x, y, width, height = frame
        click(x + min(width / 2, 60), y + height / 2)
        time.sleep(0.4)
        if clear:
            for down in (True, False):                  # select all, delete
                event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)   # keycode 0 = 'a'
                Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            for down in (True, False):
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateKeyboardEvent(None, 51, down))   # delete
            time.sleep(0.2)
        type_keys(text)

    def set_text(self, identifier, text, timeout=15.0):
        """Types into a text field by name (sets its value, the same as typing it)."""
        from ApplicationServices import AXUIElementSetAttributeValue
        element = self.wait_for(identifier, timeout=timeout)
        AXUIElementPerformAction(element, "AXRaise")
        if AXUIElementSetAttributeValue(element, "AXValue", text) != 0:
            raise ControlNotFound("cannot type into: " + identifier)

    def press(self, identifier, within=None, timeout=15.0):
        """Presses a control by name the way a person does: a real click in the middle of it. (The accessibility 'press' reports
        success on views that are tapped through a gesture without doing anything, so it is only the fallback when the control
        has no frame.)"""
        element = self.wait_for(identifier, timeout=timeout, within=within)
        if not self.enabled(element):
            # A control is greyed out while Studio is busy (merging a take, saving, finalizing): wait like a person, longer while Studio works
            from . import activity, patience
            wait = patience.for_studio(timeout, cap=timeout * 2, extend=10)
            activity.set(f"waiting for '{identifier}' to become enabled")
            try:
                while not self.enabled(element):
                    if wait.expired():
                        raise ControlNotFound("disabled: " + identifier)
                    time.sleep(0.5)
                    element = self.wait_for(identifier, timeout=5, within=within)
            finally:
                activity.clear()
        self.scroll_into_view(element)
        frame = self.stable_frame(element)
        if frame is not None and frame[2] > 0 and frame[3] > 0:
            self.activate()
            x, y, width, height = frame
            self.make_sure_studio_is_on_top(x + width / 2, y + height / 2)
            click(x + width / 2, y + height / 2)
            return
        if AXUIElementPerformAction(element, "AXPress") != 0:
            raise ControlNotFound("cannot press: " + identifier)


def type_keys(text, delay=0.03):
    """Types text with real key events (what a person does): works in SwiftUI fields where setting the value would not reach the app."""
    control.checkpoint()
    for char in text:
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
            Quartz.CGEventKeyboardSetUnicodeString(event, len(char), char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(delay)


def scroll(dx, dy, x, y):
    """A real mouse-wheel scroll at a point (positive dy scrolls the content up, i.e. towards the end of a list)."""
    control.checkpoint()
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft))
    event = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 2, int(-dy), int(-dx))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def window_owner_at(x, y):
    """(pid, app name) of the topmost normal window at a screen point, or None. The window list is ordered front to back."""
    try:
        windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID)
    except Exception:
        return None
    for window in windows or []:
        if window.get("kCGWindowLayer", 0) != 0:
            continue
        bounds = window.get("kCGWindowBounds") or {}
        if bounds.get("X", 0) <= x <= bounds.get("X", 0) + bounds.get("Width", 0) and bounds.get("Y", 0) <= y <= bounds.get("Y", 0) + bounds.get("Height", 0):
            return window.get("kCGWindowOwnerPID"), window.get("kCGWindowOwnerName")
    return None


POINTER_MOVED = 0          # how many times somebody moved the mouse away while the tester was about to click (shown in the run log)


def pointer_is_at(x, y, tolerance=4):
    location = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return abs(location.x - x) <= tolerance and abs(location.y - y) <= tolerance


def click(x, y):
    global POINTER_MOVED
    control.checkpoint()
    # Move there first, like a hand does: SwiftUI buttons inside scrolling lists ignore a press that was never preceded by the pointer
    # arriving (no hover), so a bare down/up could be lost. If the pointer is not where it was put (a person touched the mouse), it is
    # put there again: the click is never sent from somewhere else.
    for attempt in range(4):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft))
        time.sleep(0.2)
        if pointer_is_at(x, y):
            break
        POINTER_MOVED += 1
    for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        event = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.05)
