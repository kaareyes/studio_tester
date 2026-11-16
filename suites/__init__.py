"""Test suites. Each suite is (title, description, tests); `tests` is a list of (test name, function(context)) or a function of the page
options that builds that list. Add a suite here to show it on the page. `needs` says what the page must ask for."""
from . import build_check, chaos, explore, friday, long_video, network, offline_load, realistic, recovery, smoke, soak

SUITES = {
    "build_check": ("Build check (1 min)", "Starts the chosen Studio build and checks that it can be driven by name.", build_check.TESTS),
    "smoke": ("Smoke (2 min)", "Launch to session to upload Queue by control name, plus local database checks. No camera needed.", smoke.TESTS),
    "explore": ("Explore sessions and auditions (3-10 min)", "Scrolls the projects list, opens sessions, opens the Queue, scrolls to auditions and opens their file lists. No camera needed. The seed in the report repeats a run.", explore.build),
    "realistic": ("Realistic: like a casting user", "Random auditions in the sessions you tick: 1-3 talents, photos, slates, group image, 1-4 takes, Back, rating. After every audition the data is checked, and at the end every file must be uploaded.", realistic.build),
    "chaos": ("Chaos: tries to break it", "A careless user: flaky network during takes, button spam, add/remove talents, app killed mid-take, camera switched mid-take, half-built auditions. Crashes and hangs are saved as evidence and the run goes on. The seed repeats a run.", chaos.build),
    "recovery": ("Recovery: crashes at exact points", "Crashes the app right after Stop, after export, after the database save, and kills it during processing; checks the take comes back exactly once and uploads.", recovery.build),
    "network": ("Network faults", "One audition per network fault (upload cut, response lost, slow, server down, timeout): after the fault is removed everything must upload once.", network.build),
    "offline_load": ("Offline load (100+ auditions)", "Generates many offline auditions, goes online and checks that every one syncs once. Needs a small test photo and video.", offline_load.build),
    "long_video": ("Long video (25-50 min takes)", "Realistic auditions with 25-50 minute takes; memory must return near the start and uploads must finish. Takes hours.", long_video.build),
    "soak": ("Soak (hours)", "Audition cycles for hours with online/offline switches; watches memory, CPU and open files.", soak.build),
    "friday": ("Friday scope", "One test per row of the weekly stress scope; rows that cannot be automated yet say so.", friday.build),
}
# Suites that record video need a camera and the ticked sessions.
RECORDING = {"realistic", "chaos", "recovery", "network", "offline_load", "long_video", "soak", "friday"}
