# Studio Tester coverage

The Studio rule: **every test script, scenario, fault preset and test file made for Studio is also in the Studio Tester**, so the tester is never behind. This list says, for each one, where the tester covers it. `python3 scripts/check_tester_coverage.py` fails when a Studio test asset is missing here (the review runs it).

Statuses: **ported** (the tester runs it), **replaced** (superseded by a better tester part), **planned** (not driven yet: the next piece of work), **manual** (needs a person or a second account).
A ported row is written from the code and unit tests; it still needs its first run on the real app (see the README).

Summary: 1 manual, 29 planned, 60 ported, 4 replaced (94 test assets).

| Asset | Kind | Status | Where the tester covers it |
|---|---|---|---|
| `check_schema_drift.py` | script | ported | Checks suite (`suites/checks.py`, developers' Macs with the repository) |
| `stress_test/click.swift` | script | replaced | `tester/ax.py` (real clicks by control name) |
| `stress_test/clk.sh` | script | replaced | `tester/ax.py` (real clicks by control name) |
| `stress_test/shot.sh` | script | replaced | `tester/runner.py` takes screenshots on every failure |
| `stress_test/stress.py` | script | replaced | Realistic suite (`suites/realistic.py`): the position-based driver is superseded by control names |
| `stress_test/stress_real.py` | script | ported | Realistic suite (`suites/realistic.py`): talents, photo/slate, group image, 1-4 takes, camera switch, Back, rating |
| `stress_test/time_finalize.py` | script | ported | `driver.finalize()` measures the Finalize time; it is logged in every Realistic/Soak audition |
| `stress_test/verify_all.py` | script | ported | `tester/oracle.py` runs after every audition and at the end of every stress suite |
| `stress_test/verify_real.py` | script | ported | `tester/oracle.py` (offline check after the Queue settles) |
| `pending_take_recovery/run_scenario.py` | script | ported | Recovery suite (`suites/recovery.py`), see the PT rows |
| `fault_injection/fault.sh` | script | ported | `tester/faults.py` (offline, presets, camera label and switch, events) |
| `attach-exact-lost-response.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `attach-lost-response.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `crash-at-first-media-post.json` | fault preset | planned | Recovery: crash during the first media upload (not driven yet) |
| `crash-take-after-export.json` | fault preset | ported | Recovery PT-03 |
| `crash-take-after-save.json` | fault preset | ported | Recovery PT-04 |
| `crash-take-after-stop.json` | fault preset | ported | Recovery PT-01 / PT-11 / PT-13 / PT-16 |
| `intermittent-seed-42.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `media-lost-response.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `rest-slow-3s.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `s3-cut-at-50.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `s3-cut-at-90.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `s3-lost-response.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `s3-slow.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `server-down.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `sync-lost-after-checkIn.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-createFlag.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-createRole.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-createSchedule.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-createSession.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-createTalent.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-lost-after-roleIds.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-checkIn.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-createFlag.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-createRole.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-createSchedule.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-createSession.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-createTalent.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `sync-quit-before-roleIds.json` | fault preset | planned | Offline sync suite (needs offline-created talents and the Syncing Talent flow; not driven yet) |
| `timeout-then-recover.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `wifi-up-no-internet.json` | fault preset | ported | Network suite (default set, `suites/network.py`) |
| `PT-01` | scenario | ported | Recovery suite (`crash-take-after-stop.json`) |
| `PT-02` | scenario | ported | Recovery suite (timed kill 1 s after Stop) |
| `PT-03` | scenario | ported | Recovery suite (`crash-take-after-export.json`) |
| `PT-04` | scenario | ported | Recovery suite (`crash-take-after-save.json`) |
| `PT-05` | scenario | ported | Recovery suite (normal run, journal must end empty) |
| `PT-06` | scenario | ported | Recovery suite (delete while processing) |
| `PT-07` | scenario | ported | Recovery suite (3 takes, kill) |
| `PT-08` | scenario | ported | Recovery suite (slate take) |
| `PT-09` | scenario | ported | Recovery suite (group take) |
| `PT-10` | scenario | ported | Recovery suite (fast-track Finalize then next audition) |
| `PT-11` | scenario | ported | Recovery suite (offline crash and reopen) |
| `PT-12` | scenario | manual | needs a second test account |
| `PT-13` | scenario | ported | Recovery suite (stay on the projects list after the relaunch) |
| `PT-14` | scenario | planned | needs `chmod 000` on the raw audio of a take while the app runs |
| `PT-15` | scenario | planned | needs the PT-07 setup, then recording inside the reopened session |
| `PT-16` | scenario | ported | Recovery suite (corrupt `broken.json` next to a valid entry) |
| `PT-17` | scenario | planned | needs the Production app running next to the Test app |
| `RF-01` | scenario | planned | needs a Browse trim and a render failure (`chmod`) before Finalize |
| `StudioTests/CaptureSafeStartTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/FaultInjectionTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/OfflineAssetSafetyTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/OfflineAuthTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/OfflineLinkRulesTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/OfflineStudioStoreTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/OfflineSyncTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/SlateTrimHistoryTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/SlateTrimUploadPolicyTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `StudioTests/UploadTalentResolverTests.swift` | Swift test | planned | Checks suite: `xcodebuild test` of the Studio scheme (needs an Xcode build; not driven yet) |
| `Tests/OfflineCDTests/CoreDataRecordingSourceTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineCDTests/ModelMigrationTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineCDTests/StoreMigrationGuardTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/CaptureSafeStartTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/ClipOwnerResolverTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/FaultInjectionTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/LargeUploadPolicyTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/MediaIdentityTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineAgencyDirectoryTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineAgencyPagerTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineAssetSafetyTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineAuthTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineCreatedRolesTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineErrorGateTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineInitialTalentCacheTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineMatchRulesTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineQueueRetryTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineQueueRowsTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineRepresentationTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineStudioStoreTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/OfflineSyncTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/QueueRowSessionTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/ResumeFlagGateTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/TalentBackupCodecTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
| `Tests/OfflineTests/UploadTalentResolverTests.swift` | Swift test | ported | Checks suite: `swift test` in OfflineModeTests (developers' Macs) |
