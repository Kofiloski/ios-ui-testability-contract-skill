# Failure Patterns

Use this file to classify common iOS UI automation contract failures before patching code.
If you want the helper to turn a classified failure into a short first-edit checklist, run `scripts/triage_ui_contract_failure.py --report-mode patch-plan` against the artifact bundle.

## Missing Identifier

Symptoms:

- screenshot shows the control
- test log says the element does not exist
- UI tree contains the control but without a stable identifier

Preferred fix:

- add a literal accessibility identifier to the actual target control

## Identifier Collision

Symptoms:

- multiple controls resolve from the same identifier
- a visible `TextField` or `Button` appears in the UI tree under a parent identifier
- the runner taps or types into the wrong node

Preferred fix:

- remove or narrow the container identifier
- keep identifiers on the leaf targets that tests actually interact with

Common SwiftUI trap:

- a `List` row, card wrapper, or other container gets `.accessibilityIdentifier(...)`, and child controls inherit or collapse under that same identifier

## Wrong Element Type

Symptoms:

- the identifier exists
- the test still cannot tap or type reliably
- the resolved node is `StaticText`, `Other`, or another noninteractive type

Preferred fix:

- move the identifier to the interactive control
- if needed, expose separate identifiers for a visible label and the input or button behind it

## Unstable Identifier

Symptoms:

- IDs include generated text, counts, transient values, or layout-dependent names
- tests pass only with one dataset or one language

Preferred fix:

- use deterministic literal identifiers for primary actions and inputs
- reserve dynamic identifiers for repeated rows backed by stable model IDs
- keep screen roots, primary CTA buttons, inputs, and asserted targets on literal stable identifiers

## Unreachable Screen

Symptoms:

- the UI contract may be correct, but the test cannot reach the screen reliably
- setup depends on onboarding, seeded data, modal order, or deep navigation

Preferred fix:

- add or tighten debug automation launch state
- add a deterministic route into the specific screen or sheet

## False UI Problem

Symptoms:

- the element is present and interactable
- the assertion actually depends on network completion, server jobs, OCR, or AI output

Preferred fix:

- narrow the scenario to deterministic UI assertions
- only assert backend completion when the repo documents mocks or seeded deterministic behavior
