# Fix XCUITest “Element Not Found” Failures in SwiftUI and UIKit

[![CI](https://github.com/Kofiloski/ios-ui-testability-contract-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/Kofiloski/ios-ui-testability-contract-skill/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/Kofiloski/ios-ui-testability-contract-skill)](https://github.com/Kofiloski/ios-ui-testability-contract-skill/releases/latest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Turn XCUITest’s “element not found,” wrong-element, and flaky-navigation failures into the smallest SwiftUI/UIKit accessibility or launch-route fix with a local zero-dependency scanner and an installable agent skill.

**Local by default:** the CLI reads Swift, Objective-C, plist, and explicitly supplied failure artifacts from disk. It has no runtime dependencies, makes no network requests, does not upload source code, and fails closed on missing or malformed inputs.

## See the Problem in 60 Seconds

This view puts an identifier on a container while the test needs the nested `TextField`:

```swift
VStack {
    Text("Add Recipe")
    TextField("Video URL", text: $url)
        .textFieldStyle(.roundedBorder)
}
.accessibilityIdentifier("sample.recipeForm")
```

Run the scanner against the checked-in example:

```bash
ios-ui-testability ids examples/broken-swiftui-contract
```

It reports the concrete risk:

```text
Identifiers: 1
Likely parent-container assignments: 1

Likely parent-container assignments
  RecipeFormView.swift:12  sample.recipeForm
```

The smallest safe contract change is to identify the interactive control itself:

```swift
VStack {
    Text("Add Recipe")
    TextField("Video URL", text: $url)
        .textFieldStyle(.roundedBorder)
        .accessibilityIdentifier("sample.recipeForm.videoURL")
}
```

That static finding is evidence to inspect the runtime accessibility tree, not a claim that the test is already fixed. The skill then checks the resolved `XCUIElement` type and reruns the exact failing path. See the [captured demo and its limits](examples/container-identifier-demo.md).

## Copy-Paste Quick Start

Install the CLI from the latest published package release and scan an iOS repository:

```bash
pipx install "git+https://github.com/Kofiloski/ios-ui-testability-contract-skill.git@v0.4.0"
ios-ui-testability ids /path/to/your-ios-repo
```

Install the agent skill for Codex at user scope from the immutable release:

```bash
gh skill install Kofiloski/ios-ui-testability-contract-skill \
  ios-ui-testability-contract@v0.4.0 \
  --agent codex \
  --scope user
```

Then give the agent the actual failure evidence:

```text
Use $ios-ui-testability-contract to diagnose why XCUITest cannot find
app.recipeForm.videoURL. Inspect the failure log and UI tree, patch the
smallest app-side contract issue, and rerun the focused test.
```

The skill follows the open Agent Skills layout under [`skills/ios-ui-testability-contract/`](skills/ios-ui-testability-contract/). GitHub CLI can also install it for other supported coding agents; keep the requested agent and scope explicit. A root `SKILL.md` compatibility entry point remains for older direct-clone installations, while new installs should use the nested package.

## Problems It Is Built to Fix

- a control is visible but XCUITest reports that it does not exist
- an identifier resolves to `Other` or `StaticText` instead of the expected `Button` or `TextField`
- an identifier on a `VStack`, row, card, or other container collides with or hides child controls
- identifiers are duplicated, generated from unstable data, or stale in a checked-in scenario
- onboarding, seeded state, modal order, or navigation makes a screen unreachable deterministically
- a UI assertion is really waiting on an uncontrolled backend or network result

It is not a general VoiceOver, Dynamic Type, or accessibility-conformance audit. It repairs the app-side automation surface used by XCUITest, AXe, `ios-ai-ui-check`, and other clients built on the iOS accessibility tree.

## Agent Workflow

The installed skill tells an agent to:

1. inspect the decisive test log, screenshot or recording, UI tree, scenario, and source view
2. classify the failure as app contract, scenario contract, launch determinism, backend dependency, or mixed cause
3. patch the smallest app-side accessibility or routing surface
4. update checked-in scenarios or planner context when their contract changed
5. prove the target resolves as the intended element type and replay the exact failing path

Example prompts:

- `Use $ios-ui-testability-contract to diagnose why XCUITest cannot find app.recipeForm.videoURL and patch the app-side contract.`
- `Use $ios-ui-testability-contract to inspect this failing ios-ai-ui-check artifact bundle and fix the app-side automation surface.`
- `Use $ios-ui-testability-contract to make this SwiftUI sheet reachable through deterministic launch state.`
- `Use $ios-ui-testability-contract to inspect this artifact bundle and give me a patch plan before editing code.`

The canonical instructions are in [`SKILL.md`](skills/ios-ui-testability-contract/SKILL.md). References are loaded only for the failure pattern being handled.

## CLI Commands

The Python package exposes one `ios-ui-testability` command with four focused subcommands:

| Command | Purpose |
| --- | --- |
| `ids PATH` | Inventory literal identifiers, duplicates, dynamic assignments, and likely parent-container risks in Swift and Objective-C. |
| `launch PATH` | Inventory launch arguments, automation environment keys, URL schemes, and likely deterministic route hooks. |
| `triage ...` | Compare a failure summary, UI tree, scenario, and optional planner validation error to classify the likely root cause. |
| `draft-context PATH` | Draft planner-context guidance from discovered launch hooks and stable identifiers. |

Triage the included artifact bundle:

```bash
ios-ui-testability triage \
  --summary tests/fixtures/sample_failure_bundle/summary.md \
  --ui-tree tests/fixtures/sample_failure_bundle/ui-tree.json \
  --scenario tests/fixtures/sample_failure_bundle/scenario.json \
  --planner-validation-error tests/fixtures/sample_failure_bundle/planner-validation-error.txt \
  --report-mode full
```

Example excerpt:

```text
Bucket: scenario contract
Confidence: high

Patch plan:
- Remove or update stale scenario identifiers that are missing from the UI tree.
- Prefer stable app-side identifiers such as sample.recipeForm.submit for replayable controls.
```

Repository inventories use root-relative paths, do not follow symbolic links, and report skipped links. Launch inventories also report unreadable or malformed plist files. Commented code and code-like examples inside Swift raw or multiline strings are excluded from identifier findings.

## Install and Versioning

The CLI package and the agent skill are related but independent:

- install the CLI when you want deterministic local inventory and triage commands
- install the skill when you want an agent to interpret evidence, edit the app, and verify the repair
- install both for the shortest end-to-end workflow

For a source checkout:

```bash
python3 -m pip install .
ios-ui-testability --help
```

Published tags match the Python package version exactly: package version `X.Y.Z` is tagged `vX.Y.Z`. Prefer an exact tag when reproducibility matters. See [REMOTE_INSTALL.md](REMOTE_INSTALL.md) for install details and [PUBLISHING.md](PUBLISHING.md) for the maintainer release flow.

## Companion iOS Quality Projects

- [`ios-ai-ui-check`](https://github.com/Kofiloski/ios-ai-ui-check) runs planned iOS Simulator UI scenarios and produces the artifacts this skill can diagnose.
- [`app-store-review-risk`](https://github.com/Kofiloski/app-store-review-risk) scans iOS projects for App Store review risks before submission.

Together they cover runtime UI validation, app-side testability repair, and release-policy risk without coupling application code to one automation provider.

## Development

Run the complete local check:

```bash
./scripts/check-skill.sh
```

CI installs the wheel-backed package on Python 3.10, 3.12, and 3.13, then checks package, runtime, and CLI version agreement. The repository also validates the distributable Agent Skills layout with GitHub CLI before release work.

Machine-readable project navigation is available in [`llms.txt`](llms.txt). Citation metadata is in [`CITATION.cff`](CITATION.cff). The project is available under the [MIT License](LICENSE).
