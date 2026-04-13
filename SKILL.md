---
name: ios-ui-testability-contract
description: Diagnose and fix iOS UI automation contract failures in SwiftUI or UIKit by improving accessibility identifiers, element exposure, deterministic launch routes, and repo-local scenario or planner context. Use when XCUITest, AXe, or ios-ai-ui-check cannot find the intended element, finds the wrong element, interacts with a container instead of a child control, or cannot reach a screen deterministically.
---

# iOS UI Testability Contract

Use this skill to repair the app-side automation surface. Keep `XCUITest`, `AXe`, or `ios-ai-ui-check` as the detector; use this skill to make the UI expose stable, testable targets.

## Non-Negotiable Rules

- Inspect the actual failure artifacts before changing prompts or scenarios.
- Patch the app-side contract first when the UI tree proves the app is exposing the wrong target.
- Put identifiers on the intended interactive control, not on broad containers, unless the container itself is the target.
- Keep identifiers stable and literal when possible.
- Do not turn a backend or network problem into a fake UI-accessibility fix.
- Verify with a focused replay of the exact failure path before calling the work done.

## Start Here

1. Inspect the failure before changing prompts.
2. Classify the contract problem.
3. Patch the smallest app-side surface that fixes it.
4. Update checked-in scenarios or planner context if the contract changed.
5. Verify with an inspect pass and one focused scenario.

Open these references as needed:

- `references/failure-patterns.md`
  Use when the failure mode is unclear or you need to classify it quickly.
- `references/swiftui-contract-patterns.md`
  Use when patching SwiftUI or UIKit views and choosing where identifiers belong.
- `references/artifact-contract.md`
  Use when deciding what evidence to gather and what outputs a completed fix should leave behind.
- `references/verification-loop.md`
  Use when deciding how to reproduce, inspect, and verify the fix.

Optional helper:

- `scripts/inventory_accessibility_ids.py`
  Use when you need a quick inventory of literal accessibility identifiers, duplicate literals, likely non-literal identifier assignments, or likely parent-container collisions in a repo.
- `scripts/inventory_launch_contract.py`
  Use when you need a quick inventory of launch arguments, automation environment keys, URL schemes, and likely routing hooks before blaming the UI tree.
- `scripts/triage_ui_contract_failure.py`
  Use when you have `summary.md`, a UI tree, a scenario file, and optionally `planner-validation-error.txt` and want a fast first-pass root-cause bucket before patching code. Use `--report-mode patch-plan` or `--report-mode full` when you want the helper to suggest the first contract edits instead of just classifying the failure.
- `scripts/draft_planner_context.py`
  Use when bootstrapping or tightening `.github/ai-ui/planner-context.md` from the repo's discovered launch hooks and stable identifiers. Pass `--output` when you want it to write the draft directly into a file.

## Inspect First

Inspect in this order:

- `summary.md` or the failing test output
- the decisive failure line in the UI test log
- failure screenshot or video
- captured UI tree, if available
- checked-in scenario JSON or failing UI test steps
- the source view and nearby launch-routing code

Do not start by tuning prompts. First prove whether the app is exposing the correct automation contract.

## Classify The Failure

Map the issue to one of these buckets:

- Missing identifier
  The intended element exists visually but has no stable automation handle.
- Identifier collision
  A parent container identifier is swallowing child controls, or multiple elements share the same identifier.
- Wrong element type
  The identifier resolves, but XCTest finds a static label or container when the test needs a `Button`, `TextField`, or similar control.
- Unstable identifier
  The identifier depends on generated text, dynamic layout, or incidental state.
- Unreachable screen
  The app has no deterministic launch route or seeded state to reach the screen reliably.
- False UI problem
  The test is really asserting a backend or network-dependent outcome instead of a deterministic UI contract.

## Fix Rules

Apply these rules consistently:

- Put identifiers on the actual interactive target, not broad containers, unless the container itself is the intended target.
- Prefer literal stable identifiers in source when source discovery or planner context depends on them.
- Expose one stable root identifier per screen or flow, then stable identifiers for primary controls within it.
- Reserve dynamic identifiers for repeated rows or cells backed by stable model IDs. Keep screen roots, primary CTAs, input fields, and asserted targets literal and stable.
- Add deterministic launch routes or automation state only when the screen cannot be reached reliably through normal setup.
- Keep the app generic. Do not make the UI contract depend on one specific testing tool.
- Narrow or remove backend-dependent assertions unless the repo documents deterministic mocks or seeded state.

## Update The Contract Surface

When the app-side contract changes, update the nearby artifacts that consume it:

- checked-in scenario JSON used for smoke coverage
- planner context or repo automation docs
- UI test helper comments or fixtures, if the contract became more precise

Do not rename or broaden identifiers casually. Stable IDs become part of the repo's automation API.

## Artifact Contract

Treat these as the preferred inputs:

- failing `summary.md`, test output, or CI comment
- UI test log with the decisive failure line
- failure screenshot or video
- captured UI tree, if available
- checked-in scenario JSON or repo-local runner input
- source view plus any nearby launch-routing or seeding code

Leave behind these outputs when possible:

- the smallest app-side contract patch that fixes the issue
- updated checked-in scenario or planner context if the contract changed
- one inspect artifact or UI tree proving the target now resolves correctly
- one focused replay proving the original path now passes
- a brief explanation of whether the root cause was app contract, scenario contract, launch determinism, or a non-UI dependency

## Verification Standard

A fix is not complete until you have:

1. verified the UI tree exposes the intended identifier on the correct element type
2. rerun one focused scenario on the exact failure path
3. checked diff hygiene with `git diff --check`

If the repo includes app-local helpers from `ios-ai-ui-check`, prefer those helpers for inspect and replay. Otherwise use the smallest direct `xcodebuild` UI test that covers the failure.
