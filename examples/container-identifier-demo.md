# Container Identifier Demo

This is a reproducible static-analysis demo built from the checked-in [`RecipeFormView.swift`](broken-swiftui-contract/RecipeFormView.swift) fixture. It does not pretend to be a Simulator recording or a completed XCUITest run.

## Failure Shape

The sample places `sample.recipeForm` on a `VStack` even though UI automation needs to type into the nested `TextField`:

```swift
VStack {
    Text("Add Recipe")
    TextField("Video URL", text: $url)
        .textFieldStyle(.roundedBorder)
}
.accessibilityIdentifier("sample.recipeForm")
```

This is a common source of runtime accessibility-tree surprises: a query can resolve a container or inherited identifier instead of the interactive control the test expects.

## Reproduce the Finding

From the repository root, install the package and run:

```bash
python3 -m pip install .
ios-ui-testability ids examples/broken-swiftui-contract
```

The following output was captured from version 0.4.0 against the checked-in fixture:

```text
Identifiers: 1
Duplicate literals: 0
Interpolated assignments: 0
Likely non-literal assignments: 0
Acceptable dynamic assignments: 0
Review-needed dynamic assignments: 0
Likely parent-container assignments: 1
Likely parent-container collisions: 0
Skipped symbolic links: 0

sample.recipeForm
  RecipeFormView.swift:12

Likely parent-container assignments
  RecipeFormView.swift:12  sample.recipeForm
```

The scanner calls this a **likely** parent-container assignment. Static source alone cannot prove how SwiftUI will expose the element in the runtime accessibility tree.

## Candidate Contract Repair

If the UI tree confirms that the test needs the text field, put a stable identifier on that leaf control and remove the broad container identifier:

```swift
VStack {
    Text("Add Recipe")
    TextField("Video URL", text: $url)
        .textFieldStyle(.roundedBorder)
        .accessibilityIdentifier("sample.recipeForm.videoURL")
}
```

## Evidence Still Required

Do not call the repair complete from this source diff alone. The agent workflow requires:

1. inspect the captured UI tree and confirm `sample.recipeForm.videoURL` resolves as a `TextField`
2. replay the exact test that originally failed to find or type into the field
3. keep the patch only when that focused replay passes

This separation is deliberate: the CLI surfaces likely contract risks, while the [`ios-ui-testability-contract`](../skills/ios-ui-testability-contract/SKILL.md) skill combines source findings with runtime evidence and performs the repair workflow.
