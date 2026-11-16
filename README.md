# Studio Tester

Python regression tests that drive the Studio macOS app by themselves. No separate app, nothing to install from TestFlight.
Kept apart from the app code and from the older position-based drivers in `scripts/stress_test`.

## For testers (QA and developers)

Step-by-step guide with screenshots: [`docs/Studio_Tester_Guide.pdf`](docs/Studio_Tester_Guide.pdf) (install, start, choose a suite, read the report, troubleshooting).

1. **Every time, the same single step:** double-click `Studio Tester.command`. A Terminal window shows what it is doing, like `npm install`:
   it checks the tools folder, the packages and the permission, asks before it installs anything (Y/n), installs with visible
   progress, checks again, and then opens the test page in the browser. Nothing else to open. Safe to run again at any time.
   - If Python 3.9+ is missing, it offers to install Apple's free command line tools and waits until they are done.
   - If Accessibility is off, it opens the setting and continues by itself when you switch **Terminal** on.
   - (`Install Studio Tester.command` and `Start Studio Tester.command` only forward to this file, for older instructions.)
2. On the page: press *Collect projects from the app*, tick sessions, pick how hard, press **Start**. Watch the results; open the report at the end.
3. Keep the Terminal window open while the tests run. Do not use the Mac's mouse and keyboard during a run.
4. macOS may say it cannot verify the file the first time (it came from a download): right-click it, choose **Open**, then **Open**. Only once.

Rules: test account and test project only, never real auditions. The built-in camera is always used unless you choose
another camera on the page (the built-in camera does not work with the lid closed).

## What it needs

- macOS with Apple's command line tools (the setup opens the install window if they are missing).
- Accessibility permission for Terminal (System Settings > Privacy & Security > Accessibility).
- A Studio build that has the test names (built from a commit that includes `Shared/Utilities/TestID.swift`).

## How it works

- Studio's controls carry names (`.testID("session.enterAuditionMode")` in the app). The tests find controls by name through
  the macOS Accessibility API (`tester/ax.py`), not by screen position, and wait for real states instead of fixed delays.
- `tester/runner.py` runs a suite test by test; a failed test keeps a screenshot and the reason; a test that cannot run
  here (no camera) is reported as skipped, not failed.
- `tester/server.py` serves the page on this Mac only (`http://localhost:8765`).
- Reports: `reports/<date>_<suite>/report.html` (+ `results.json`, screenshots, Studio's console log).

## Layout

```
studio_tester/
  Install Studio Tester.command   one-time setup (double-click)
  Start Studio Tester.command     opens the test page (double-click)
  requirements.txt                Python packages the setup installs into .venv
  tester/                         ax.py (controls by name), cameras.py, setup_check.py, runner.py, report.py, server.py
  suites/                         test suites; add one to suites/__init__.py to show it on the page
  reports/                        results of every run (not committed)
```

## Adding a test

A test is a function that takes `context`:

```python
def finalize_uploads_everything(context):
    app = context.app or context.launch()
    app.press("capture.finalize")
    app.wait_for("queue.completedCount", timeout=120)
```

Raise `tester.runner.Skip("why")` when the test cannot run on this Mac. Any other exception is a failure.

## Status

Suites on the page: **Build check**, **Smoke**, **Explore**, **Realistic**, **Chaos**, **Recovery**, **Network**, **Offline load**,
**Long video**, **Soak**, **Friday scope**, **Code checks** (developers).

**Coverage:** [`COVERAGE.md`](COVERAGE.md) lists every test asset made for Studio (scripts, scenarios, fault presets, Swift test files) and where this tester covers it. The Studio rule: a new test is also put in the tester, and `python3 scripts/check_tester_coverage.py` (in the Studio repository) fails when one is missing. The unit tests of the tester itself: `.venv/bin/python -m unittest discover -s tests -t .`
(43 tests: name matching, take lengths, data-integrity check, catalog, page server, driver steps).

**What has NOT been run against the real app yet:** the Collect step and the Realistic, Chaos, Recovery, Network, Offline load,
Long video, Soak and Friday suites were written from the control names and the old position-based scripts and checked with fake-app
unit tests only. Run each once on a test project and fix what the real screen does differently before trusting a result.

## Which Studio apps can be tested

Only builds starting from the branch `merge/metadata-macos-v2-into-v2-offlinemode` (that build and every newer one) carry the button names (`.testID(...)`) the tester uses. `tester/support.py` reads the app file (main program and the `.debug.dylib` of a Debug build) and looks for the names the tester cannot work without, so it needs neither a running nor a signed-in app. Each app in the list shows *can be tested* or *not supported* with its version; an unsupported app stops the page at step 1 with **"App version not supported for testing"** and the branch, and Start and Collect refuse it. A build that lacks only newer controls stays testable and lists what is not testable. When the app gets a new control the tester needs, add its name to `CORE` (or `OPTIONAL`) in `tester/support.py`.

## Page flow

1. **This Mac:** plain OK / FIX lines, with a button that opens the right System Settings page.
2. **Projects and sessions:** press *Collect projects from the app*. The tester scrolls the projects list and opens each session
   (read only) and writes `catalog.json` (names only, not committed). Tick sessions; search forgives typos and capital letters.
   Projects without a test word in the name (qa, test, sim, stress, demo... plus your own words) are greyed out and need *use anyway*.
3. **How hard?** One of four presets (Quick, Normal, Break it, Overnight). *Advanced* has the suite, take length, mix, mode, counts,
   seed, network faults, offline-load media, camera and the test words. The page shows the estimated time and disk and blocks
   a run that does not fit on the disk or has no session ticked.
4. **Start:** a banner asks not to touch the mouse; the verdict is a big PASS or FAIL. *Run again with the same seed* repeats a run;
   *Copy report for developers* copies `results.json`.

## Take lengths

Short 30 s to 1 min, Normal 1 to 5 min, Long 25 to 50 min, Mixed = each take picks one (default 50 / 40 / 10 %). Random from the seed.

## What every stress suite checks (tester/oracle.py)

After every audition: no clip without an audition, no file twice, all files of an audition in one session folder, files waiting to
upload are still on disk, nothing marked uploaded while offline, and (after the Queue settles) everything uploaded; the pending-take
journal is empty when idle. A crash or hang keeps the evidence (crash report, `sample`) in the run folder, is written to
`incidents.txt`, and the run goes on.

## Safe stop

Whatever ends a run (finish, failure, Stop), the tester removes faults, switches simulated offline off, removes the camera label and
re-enables fault injection (`faults.reset_all`).

## Not done yet

- Pausing the run when the person moves the mouse.
- Friday scope rows 1, 2, 3, 6, 14 and 16 are listed but report "not automated yet" (they need a test agency, a person to unplug a
  camera, or another suite).
- PT-12 (another user signs in) needs a second test account.
