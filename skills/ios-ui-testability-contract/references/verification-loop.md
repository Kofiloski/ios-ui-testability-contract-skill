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
