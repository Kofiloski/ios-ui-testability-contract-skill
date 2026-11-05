# Verification Loop

Use the smallest loop that proves the contract is fixed.

## Discover Existing Helpers

Check whether the repo already has app-local automation helpers:

```bash
rg -n "run-ai-ui-scenario|local-ai-ui-check|ScenarioRunnerUITests|planner-context" .
```

If present, prefer those repo-local helpers over inventing a new loop.

## Minimal Verification

1. Run an inspect pass for the target screen.
2. Confirm the UI tree exposes the intended identifier on the expected element type.
3. Run one focused scenario on the exact failure path.
4. Run `git diff --check`.

## When The Repo Uses ios-ai-ui-check

Prefer this shape:

- inspect the current UI with the repo's local helper or runner
- fix the app-side contract
- rerun inspect
- rerun one focused scenario rather than the broadest prompt set first

Useful artifacts to inspect:

- `summary.md`
- `xcodebuild-ui-test.log`
- failure screenshot
- before-planning screenshot
- captured UI tree JSON
- checked-in scenario JSON

## Focused Scenario Guidance

A focused scenario should only include the critical path:

- deterministic launch
- shortest navigation to the target screen
- one or two assertions that prove the contract is correct
- optional type or tap action if that interaction was the original failure

Do not verify unrelated flows while confirming an accessibility-contract fix.

## Native Xcode Simulator exploration

When Xcode 27 or later exposes native Simulator tools to the session, use them to build/launch the app, reach the failing screen, send supported touch input, and capture the observed state. Discover the actual tool schemas first and select the intended scheme and Simulator explicitly. Reuse existing app launch/data setup. If native tools are unavailable, continue with the repo's inspect/replay helpers.

Coordinates and visual labels can help reproduce a visible issue, but they do not prove identifier uniqueness, element type, or XCTest query resolution. Obtain that evidence from the failing tool's inspect output or a focused XCTest query. After patching, rerun the original failing automation path. Report native observations separately from the replay result, including any inspection or replay that could not run.

## Diagnostics when the cause is unclear

Correlate diagnostics with the same app revision, installed build, Simulator UDID, launch/data setup, locale, and timestamped reproduction. Use existing test logs first; collect an app-filtered console excerpt around the failed action only when it helps distinguish the remaining causes. An empty log query does not prove a method was not called. Report service-access failures as tooling gaps instead of resetting the Simulator.

Trace the actual source flow before reading saved state. Resolve the current app container with `xcrun simctl get_app_container <UDID> <bundle-id> data`; inspect only the relevant preferences, file, or database record. Read a consistent SQLite backup or copy made after writers stop, preserving matching WAL/SHM files when needed. Keep raw state out of planner/upload directories, redact shared evidence, and never edit the live store to make a test pass. A visible success message does not prove persistence or a backend result.

Use Xcode's view debugger or a focused LLDB inspection to explain underlying state when necessary. UIKit view dumps and SwiftUI runtime observations cannot establish what XCUITest exposes. Debugger pauses or injected hooks can change behavior; label that evidence, then verify the original path without the hooks. Do not force an identifier, invoke an action directly, or override a return value and report the automation contract repaired.

A labeled element can expose the same type as a nested interactive control while its own center is not a working tap target. Inspect the actual children, bounds, values, and hit points before changing app code. If the hierarchy exposes one intended nested control, scope the original automation query to that control and verify its behavior. A passing scoped query can identify a scenario-targeting problem; the outer type alone does not prove an app defect. Preserve the failed query and its artifacts alongside the corrected replay.

These diagnostics require no Simulator jailbreak or new injection dependency. Prefer available native tools; optional device instrumentation needs an explicitly scoped request and compatible tooling. The completion standard remains a correct identifier/type through the failing automation client and a successful focused replay.
