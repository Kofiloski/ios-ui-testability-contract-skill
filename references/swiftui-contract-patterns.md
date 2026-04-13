# SwiftUI And UIKit Contract Patterns

Use these patterns when patching the app-side automation surface.

## Prefer Leaf Identifiers

Good:

```swift
TextField("Video URL", text: $videoURL)
    .accessibilityIdentifier("app.recipeForm.videoURL")
```

Avoid:

```swift
VStack {
    TextField("Video URL", text: $videoURL)
}
.accessibilityIdentifier("app.recipeForm.videoURL")
```

Reason:

- tests usually need the `TextField`, not the container

## Use Stable Screen Roots

Good:

```swift
List {
    formRows
}
.accessibilityIdentifier("app.recipeForm.list")
```

Reason:

- root identifiers make screen presence assertions cheap and reliable

## Segment Options Need Their Own Stable Targets

Good:

```swift
Picker("Import method", selection: $selectedMethod) {
    Text("Video")
        .tag(Method.video)
        .accessibilityIdentifier("app.recipeForm.importMethod.video")
    Text("Book")
        .tag(Method.book)
        .accessibilityIdentifier("app.recipeForm.importMethod.book")
}
```

Reason:

- segment selection is often the real interaction target
- source discovery is more reliable when IDs are literal strings

## Avoid Container IDs On Composite Rows

Be careful with:

- `List` rows
- custom cards
- `NavigationLink` wrappers
- views using combined accessibility children

If a container-level ID causes child controls to disappear or inherit that same ID in the UI tree, remove it and identify the actual child targets instead.

## Dynamic Rows Are Acceptable Only With Stable Backing IDs

Acceptable:

```swift
.accessibilityIdentifier("app.recipes.row.\(recipe.id.uuidString)")
```

Avoid:

```swift
.accessibilityIdentifier("app.recipes.row.\(recipe.name)")
```

Reason:

- names, counts, and localized strings are not stable automation keys

## Deterministic Launch Routes Matter

If the target screen is expensive or flaky to reach, prefer debug-only launch configuration such as:

- selected tab
- onboarding completion state
- seeded data mode
- direct route to a sheet or detail screen

Keep this routing generic and app-owned. It should help any automation client, not only one tool.

## UIKit Note

UIKit follows the same rule set:

- assign `view.accessibilityIdentifier` to the actual target control
- avoid placing one identifier on a broad parent view when the test needs a nested button or field
- prefer deterministic leaf targets over hierarchy-dependent traversal
