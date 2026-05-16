#!/usr/bin/env python3
"""
Heuristic first-pass triage for iOS UI automation failures.

The goal is not perfect diagnosis. The goal is to turn a summary, scenario, and
UI tree into an evidence-based starting bucket before code changes begin.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT_CAUSE_BUCKETS = (
    "app contract",
    "scenario contract",
    "launch determinism",
    "backend or network dependency",
    "mixed cause",
)

STATE_DEPENDENT_TOKENS = (
    "empty",
    "sheet",
    "modal",
    "draft",
    "processing",
    "paywall",
    "placeholder",
)

UI_TREE_ID_PATTERN = re.compile(r"identifier:\s*'([^']+)'")
UI_TREE_LABEL_PATTERN = re.compile(r"label:\s*'([^']+)'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Triage an iOS UI automation failure into a likely root-cause bucket."
    )
    parser.add_argument("--summary", type=Path, required=True, help="Path to summary.md or failure text.")
    parser.add_argument("--ui-tree", type=Path, help="Path to captured UI tree JSON.")
    parser.add_argument("--scenario", type=Path, help="Path to scenario JSON.")
    parser.add_argument(
        "--planner-validation-error",
        type=Path,
        help="Optional planner-validation-error.txt path.",
    )
    parser.add_argument(
        "--report-mode",
        choices=("triage", "patch-plan", "full"),
        default="triage",
        help="Choose whether to print the triage report, a fix-oriented patch plan, or both.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text output.")
    return parser.parse_args()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists() or path.is_dir():
        return ""
    return path.read_text(encoding="utf-8")


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists() or path.is_dir():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def collect_ui_tree_identifiers(path: Path | None) -> set[str]:
    payload = read_json(path)
    hierarchy_description = payload.get("hierarchyDescription") or ""
    return set(UI_TREE_ID_PATTERN.findall(hierarchy_description))


def collect_ui_tree_labels(path: Path | None) -> set[str]:
    payload = read_json(path)
    hierarchy_description = payload.get("hierarchyDescription") or ""
    return set(UI_TREE_LABEL_PATTERN.findall(hierarchy_description))


def collect_scenario_ids(path: Path | None) -> list[str]:
    payload = read_json(path)
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return []
    ids: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("id")
        if isinstance(step_id, str) and step_id:
            ids.append(step_id)
    return ids


def is_state_dependent(identifier: str) -> bool:
    lowered = identifier.lower()
    return any(token in lowered for token in STATE_DEPENDENT_TOKENS)


def classify(
    summary_text: str,
    scenario_ids: list[str],
    ui_tree_ids: set[str],
    *,
    planner_validation_error_text: str = "",
) -> dict[str, object]:
    combined_text = "\n".join(
        part for part in (summary_text, planner_validation_error_text) if part
    )
    lowered = combined_text.lower()
    scores = {bucket: 0 for bucket in ROOT_CAUSE_BUCKETS}
    evidence: list[str] = []

    missing_ids = [identifier for identifier in scenario_ids if identifier not in ui_tree_ids]
    visible_ids = [identifier for identifier in scenario_ids if identifier in ui_tree_ids]
    state_dependent_missing = [identifier for identifier in missing_ids if is_state_dependent(identifier)]

    if any(
        token in lowered
        for token in (
            "planner validation",
            "unknown id",
            "unknown identifier",
            "conditional-state",
            "conditional state",
            "scenario resolution failed before runner execution",
            "planner generated",
            "checked-in scenario",
        )
    ):
        scores["scenario contract"] += 3
        evidence.append("summary points at planner or scenario validation failure")

    if planner_validation_error_text.strip():
        scores["scenario contract"] += 2
        evidence.append("planner-validation-error artifact points at a scenario contract failure")

    if state_dependent_missing:
        scores["scenario contract"] += 2
        evidence.append(
            "scenario targets state-dependent identifiers that were not present in the captured UI tree"
        )

    if any(
        token in lowered
        for token in (
            "boot",
            "simulator",
            "launch",
            "startup",
            "inspect",
            "deep link",
            "deeplink",
        )
    ):
        scores["launch determinism"] += 2
        evidence.append("summary mentions startup, inspect, or simulator launch behavior")

    if scenario_ids and not visible_ids and ui_tree_ids:
        scores["launch determinism"] += 2
        evidence.append("none of the scenario identifiers were visible in the captured UI tree")

    if any(
        token in lowered
        for token in (
            "not hittable",
            "multiple matches",
            "statictext",
            "textfield",
            "button",
            "wrong element type",
            "container",
        )
    ):
        scores["app contract"] += 3
        evidence.append("summary suggests the UI exposes the wrong element type or target")

    if visible_ids and missing_ids:
        scores["app contract"] += 1
        scores["scenario contract"] += 1
        evidence.append("some scenario identifiers resolve in the UI tree while others do not")

    if any(
        token in lowered
        for token in (
            "network",
            "backend",
            "server",
            "api",
            "ocr",
            "openai",
            "job",
            "request failed",
            "processing",
        )
    ):
        scores["backend or network dependency"] += 3
        evidence.append("summary mentions a backend, network, OCR, or AI dependency")

    ranked = sorted(
        ((score, bucket) for bucket, score in scores.items() if bucket != "mixed cause"),
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        bucket = "mixed cause"
    else:
        best_score, best_bucket = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0
        if best_score < 2 or best_score - second_score <= 1:
            bucket = "mixed cause"
        else:
            bucket = best_bucket

    confidence = "low"
    if bucket != "mixed cause":
        confidence = "medium"
        if ranked and len(ranked) > 1 and ranked[0][0] - ranked[1][0] >= 3:
            confidence = "high"

    next_steps = {
        "app contract": [
            "inspect the source view and move or add the identifier on the leaf interactive control",
            "rerun one inspect pass and confirm the target resolves as the right element type",
        ],
        "scenario contract": [
            "tighten the checked-in scenario or planner context to use only visible or documented identifiers",
            "remove conditional-state identifiers unless launch setup guarantees that state",
        ],
        "launch determinism": [
            "add or document launch arguments, environment, deep links, or seeded state that force the intended screen",
            "rerun the inspect path before replaying the scenario",
        ],
        "backend or network dependency": [
            "narrow assertions to deterministic UI state or add mocks and seeded data",
            "avoid treating a backend dependency as an accessibility-identifier problem",
        ],
        "mixed cause": [
            "inspect the decisive log line, the UI tree, and the source view before patching code",
            "separate app contract issues from launch setup or backend dependencies first",
        ],
    }[bucket]
    patch_plan = build_patch_plan(
        bucket=bucket,
        visible_ids=visible_ids,
        missing_ids=missing_ids,
        state_dependent_missing=state_dependent_missing,
        planner_validation_error_present=bool(planner_validation_error_text.strip()),
    )

    return {
        "bucket": bucket,
        "confidence": confidence,
        "evidence": evidence,
        "planner_validation_error_present": bool(planner_validation_error_text.strip()),
        "scenario_ids": scenario_ids,
        "visible_scenario_ids": visible_ids,
        "missing_scenario_ids": missing_ids,
        "state_dependent_missing_ids": state_dependent_missing,
        "next_steps": next_steps,
        "patch_plan": patch_plan,
    }


def build_patch_plan(
    *,
    bucket: str,
    visible_ids: list[str],
    missing_ids: list[str],
    state_dependent_missing: list[str],
    planner_validation_error_present: bool,
) -> list[str]:
    leading_missing = missing_ids[:3]
    leading_visible = visible_ids[:3]
    leading_state_dependent = state_dependent_missing[:3]

    if bucket == "app contract":
        patch_plan = [
            "Inspect the source view that owns the failing target and move or add the identifier on the leaf interactive control instead of the surrounding container.",
            "If a broad parent identifier shares a prefix with child controls, narrow or remove the parent identifier so XCTest resolves the intended element type.",
        ]
        if leading_missing:
            patch_plan.append(
                f"Audit these likely app-side targets first: {', '.join(leading_missing)}."
            )
        if leading_visible:
            patch_plan.append(
                f"Use these already-visible identifiers as nearby contract anchors while patching: {', '.join(leading_visible)}."
            )
        return patch_plan

    if bucket == "scenario contract":
        patch_plan = [
            "Rewrite the checked-in scenario or planner context so it only targets identifiers that are visible in the captured UI tree or explicitly documented as deterministic automation API.",
            "Remove conditional-state identifiers from the main path unless launch setup guarantees that state.",
        ]
        if planner_validation_error_present:
            patch_plan.append(
                "Treat planner-validation-error.txt as the first edit target and fix the contract mismatch before tuning prompts."
            )
        if leading_missing:
            patch_plan.append(
                f"Replace or document these missing scenario identifiers first: {', '.join(leading_missing)}."
            )
        if leading_state_dependent:
            patch_plan.append(
                f"Move these state-dependent identifiers behind deterministic launch setup or remove them from the happy path: {', '.join(leading_state_dependent)}."
            )
        return patch_plan

    if bucket == "launch determinism":
        patch_plan = [
            "Add or document exact launch arguments, environment values, deep links, or seeded fixtures that land the app on the intended screen deterministically.",
            "Update planner context and any checked-in smoke scenario so the launch contract is explicit and reusable.",
        ]
        if leading_missing:
            patch_plan.append(
                f"Do not patch UI identifiers first for these targets until the screen is reachable deterministically: {', '.join(leading_missing)}."
            )
        return patch_plan

    if bucket == "backend or network dependency":
        return [
            "Narrow the scenario to deterministic UI assertions and stop treating backend completion as an accessibility-contract problem.",
            "If the user-visible outcome must remain in scope, add mocks or seeded data and document that contract in planner context or test setup.",
        ]

    return [
        "Capture one more decisive inspect pass, then separate app-contract fixes from launch or backend dependencies before editing code.",
        "Patch the smallest stable automation surface first: deterministic launch route, literal identifiers on leaf controls, then scenario or planner guidance.",
    ]


def print_text_report(report: dict[str, object], ui_tree_labels: set[str]) -> None:
    print(f"Bucket: {report['bucket']}")
    print(f"Confidence: {report['confidence']}")

    evidence = report["evidence"]
    if evidence:
        print("\nEvidence")
        for entry in evidence:
            print(f"  - {entry}")

    missing_ids = report["missing_scenario_ids"]
    if missing_ids:
        print("\nMissing scenario ids")
        for identifier in missing_ids:
            print(f"  - {identifier}")

    visible_ids = report["visible_scenario_ids"]
    if visible_ids:
        print("\nVisible scenario ids")
        for identifier in visible_ids:
            print(f"  - {identifier}")

    if ui_tree_labels:
        print("\nObserved UI labels")
        for label in sorted(ui_tree_labels)[:12]:
            print(f"  - {label}")

    print("\nNext steps")
    for step in report["next_steps"]:
        print(f"  - {step}")


def print_patch_plan(report: dict[str, object]) -> None:
    print("Patch plan")
    for step in report["patch_plan"]:
        print(f"  - {step}")


def main() -> int:
    args = parse_args()
    summary_text = read_text(args.summary)
    planner_validation_error_text = read_text(args.planner_validation_error)
    scenario_ids = collect_scenario_ids(args.scenario)
    ui_tree_ids = collect_ui_tree_identifiers(args.ui_tree)
    ui_tree_labels = collect_ui_tree_labels(args.ui_tree)

    report = classify(
        summary_text,
        scenario_ids,
        ui_tree_ids,
        planner_validation_error_text=planner_validation_error_text,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if args.report_mode in {"triage", "full"}:
            print_text_report(report, ui_tree_labels)
        if args.report_mode == "full":
            print("")
        if args.report_mode in {"patch-plan", "full"}:
            print_patch_plan(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
