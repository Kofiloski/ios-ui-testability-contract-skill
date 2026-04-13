# Artifact Contract

Use this file to keep the workflow evidence-based and repeatable.

## Preferred Inputs

Gather these before changing code:

- failing test output or `summary.md`
- the decisive failure line from the UI test log
- failure screenshot or recording
- captured UI tree JSON, if available
- checked-in scenario JSON, planner context, or repo-local runner input
- source view and nearby launch-routing code

If some artifacts are missing, say so explicitly instead of guessing.

## Expected Outputs

A good fix should usually leave behind:

- a minimal app-side code change that improves the automation contract
- updated scenario JSON or planner context when the contract changed
- one inspect artifact proving the identifier is now exposed on the intended element type
- one focused replay proving the original failure path now passes
- a short explanation of the root-cause bucket

## Root-Cause Buckets

Use one of these labels when summarizing the issue:

- app contract
- scenario contract
- launch determinism
- backend or network dependency
- mixed cause

## Done Criteria

The work is done when:

1. the correct target exists in the UI tree with the right identifier
2. the exact failure path has been replayed successfully
3. the surrounding contract consumers have been updated if needed
4. the diff is clean
