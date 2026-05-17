# iOS UI Testability Contract

A focused agent skill for diagnosing and fixing iOS UI automation contract failures in SwiftUI and UIKit.

This skill is for cases where `XCUITest`, `AXe`, or `ios-ai-ui-check` cannot find the intended element, resolves the wrong element, or cannot reach a screen deterministically even though the product UI itself appears correct.

## Agent Usage

Use this skill when an AI agent needs to repair the app-side testability contract for an iOS UI automation failure, especially missing or duplicate `accessibilityIdentifier` values, wrong `XCUIElement` types, container collisions, unstable identifiers, unreachable screens, or incomplete launch routing.

Prompt examples:

- `Use $ios-ui-testability-contract to diagnose why XCUITest cannot find app.recipeForm.videoURL and patch the app-side contract.`
- `Use $ios-ui-testability-contract to inspect this failing ios-ai-ui-check artifact bundle and fix the app-side automation surface.`
- `Use $ios-ui-testability-contract to make this SwiftUI sheet reachable and testable through deterministic launch state.`
- `Use $ios-ui-testability-contract to inspect this artifact bundle and give me a patch plan before editing code.`

Agents should read `SKILL.md` first, inspect the failure artifact or UI tree before editing prompts, and load `references/` only for the failure pattern being fixed.

## What It Does

- inspects failing UI automation artifacts before touching prompts
- classifies failures like missing identifiers, container collisions, wrong element types, unstable IDs, and nondeterministic launch paths
- patches the smallest app-side automation contract needed
- updates checked-in scenario or planner context when the contract changes
- verifies the fix with an inspect pass and one focused replay

## What It Does Not Do

- general accessibility compliance review
- VoiceOver or Dynamic Type audits
- visual UI redesign
- backend mocking or full end-to-end workflow design unless needed to make the screen deterministic

## Install

For the reusable CLI:

```bash
python -m pip install .
ios-ui-testability --help
```

For Codex-style skills, copy or symlink this folder into your skills directory:

```bash
git clone https://github.com/Kofiloski/ios-ui-testability-contract-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ios-ui-testability-contract"
```

This folder is structured as a standalone skill repository. Keep `SKILL.md`, `README.md`, `references/`, `scripts/`, and `tests/` together and tag releases from that root.
See [PUBLISHING.md](PUBLISHING.md) for the minimal standalone-repo release flow.
See [REMOTE_INSTALL.md](REMOTE_INSTALL.md) for the remote-repo install contract and pinning guidance.
This standalone-repo shape now also includes an MIT `LICENSE` plus GitHub Actions workflows for CI and manual releases.

Before publishing or updating the standalone repo, run:

```bash
./scripts/check-skill.sh
```

The same skill check now runs automatically on every branch push and pull request through `.github/workflows/ci.yml`.

## Example Helper Usage

Patch-plan mode from the sample fixture bundle:

```bash
ios-ui-testability triage \
  --summary tests/fixtures/sample_failure_bundle/summary.md \
  --ui-tree tests/fixtures/sample_failure_bundle/ui-tree.json \
  --scenario tests/fixtures/sample_failure_bundle/scenario.json \
  --planner-validation-error tests/fixtures/sample_failure_bundle/planner-validation-error.txt \
  --report-mode full
```

The old script paths remain available for compatibility:

```bash
python3 scripts/triage_ui_contract_failure.py --help
```

CLI subcommands:

- `ios-ui-testability ids`
  Inventory literal accessibility identifiers, duplicates, likely dynamic assignments, and likely parent-container collisions.
- `ios-ui-testability launch`
  Inventory launch arguments, automation environment keys, URL schemes, and route hints.
- `ios-ui-testability triage`
  Classify an artifact bundle into a likely root-cause bucket and optional patch plan.
- `ios-ui-testability draft-context`
  Draft `.github/ai-ui/planner-context.md` guidance from discovered launch hooks and stable identifiers.

## Repository Contents

- `pyproject.toml`
  Python package metadata and the `ios-ui-testability` console command.
- `src/ios_ui_testability_contract/`
  The reusable CLI and helper implementation.
- `SKILL.md`
  The actual skill instructions and workflow.
- `references/`
  Failure patterns, SwiftUI/UIKit contract patterns, artifact expectations, and the verification loop.
- `scripts/inventory_accessibility_ids.py`
  A lightweight helper for inventorying literal accessibility identifiers, duplicate literals, and likely non-literal assignments.
- `scripts/inventory_launch_contract.py`
  A lightweight helper for surfacing launch arguments, automation environment keys, URL schemes, and route hints.
- `scripts/triage_ui_contract_failure.py`
  A first-pass triage helper that turns `summary.md`, a scenario file, a UI tree, and optional `planner-validation-error.txt` into a likely root-cause bucket. It can also emit a short fix-oriented patch plan.
- `scripts/draft_planner_context.py`
  A starter generator for planner-context sections based on discovered launch hooks, route hints, and stable identifiers. It can print to stdout or write directly to a target file with `--output`.
- `scripts/check-skill.sh`
  A tiny self-check runner for `compileall` plus the fixture tests, useful when the skill is published as its own repo.
- `tests/`
  Tiny fixture-style tests for the helper scripts so the skill can be evolved with less guesswork.
- `examples/`
  Small sample broken-contract source files you can use to understand the kinds of app-side issues this skill is meant to fix.
- `tests/fixtures/sample_failure_bundle/`
  A tiny example artifact bundle you can use to exercise the triage helper and inspect the expected inputs.

## Suggested Workflow

1. Start from the failing artifact, screenshot, log, or local repro.
2. Confirm whether the issue is app contract, scenario contract, launch determinism, or a non-UI dependency.
3. Patch the smallest app-side surface that fixes the contract.
4. Update checked-in automation artifacts if the contract changed.
5. Verify with inspect plus one focused replay.
