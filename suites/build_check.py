"""The first suite: is this Studio build testable at all? Needs no camera and records nothing."""
from tester.runner import Skip

# A build without names cannot be tested by name: every other suite would fail for the wrong reason.
MINIMUM_NAMES = 3


def starts(context):
    context.launch()


def can_be_driven_by_name(context):
    app = context.app or context.launch()
    names = app.names()
    context.log(f"{len(names)} named controls on screen: {', '.join(names[:12])}")
    if len(names) < MINIMUM_NAMES:
        raise AssertionError(f"this build has {len(names)} named controls on the first screen; it was built before the test names were added")


def camera_is_available(context):
    camera = context.require_camera()
    context.log("camera: " + camera["name"])


TESTS = [
    ("Studio starts", starts),
    ("Studio can be driven by name", can_be_driven_by_name),
    ("A camera can be used", camera_is_available),
]
