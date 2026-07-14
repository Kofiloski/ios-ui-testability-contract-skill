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
import sys
from pathlib import Path
from typing import Any

from ._paths import read_required_text


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
UI_IDENTIFIER_KEYS = {"accessibilityid", "accessibilityidentifier", "identifier"}
UI_LABEL_KEYS = {"label", "title"}
SCENARIO_IDENTIFIER_KEYS = {
    "accessibilityid",
    "accessibilityidentifier",
    "id",
    "identifier",
    "targetid",
}
SCENARIO_LABEL_KEYS = {"accessibilitylabel", "label"}
SCENARIO_SELECTOR_CONTAINER_KEYS = {
    "element",
    "find",
    "query",
    "selector",
    "target",
    "waitfor",
}
SCENARIO_DIRECT_SELECTOR_STRING_KEYS = {
    "element",
    "find",
    "query",
    "selector",
    "target",
    "waitfor",
}
SCENARIO_SELECTOR_STRATEGY_KEYS = {"by", "kind", "strategy", "type", "using"}
SCENARIO_SELECTOR_NAME_KEYS = {"name"}
SCENARIO_SELECTOR_VALUE_KEYS = {"value"}
SCENARIO_IDENTIFIER_STRATEGIES = {
    "accessibilityid",
    "accessibilityidentifier",
    "id",
    "identifier",
}
SCENARIO_LABEL_STRATEGIES = {"accessibilitylabel", "label"}
SCENARIO_PAYLOAD_HINT_KEYS = {
    "assert",
    "assertion",
    "expected",
    "expectedtext",
    "input",
    "payload",
    "text",
}
SCENARIO_PAYLOAD_CONTAINER_KEYS = SCENARIO_PAYLOAD_HINT_KEYS


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


def read_text(
    path: Path | None,
    *,
    label: str = "text artifact",
    allow_empty: bool = True,
) -> str:
    if path is None:
        return ""
    return read_required_text(path, label=label, allow_empty=allow_empty)


def read_json(path: Path | None, *, label: str = "JSON artifact") -> Any:
    if path is None:
        return {}
    text = read_required_text(path, label=label, allow_empty=False)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{label} is not valid JSON at line {error.lineno}, column {error.colno}: {path}: {error.msg}"
        ) from None


def normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def collect_string_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        append_unique(values, value)
    elif isinstance(value, dict):
        for child in value.values():
            for child_value in collect_string_values(child):
                append_unique(values, child_value)
    elif isinstance(value, list):
        for child in value:
            for child_value in collect_string_values(child):
                append_unique(values, child_value)
    return values


def collect_pattern_matches(value: Any, pattern: re.Pattern[str]) -> set[str]:
    matches: set[str] = set()
    if isinstance(value, str):
        matches.update(pattern.findall(value))
    elif isinstance(value, dict):
        for child in value.values():
            matches.update(collect_pattern_matches(child, pattern))
    elif isinstance(value, list):
        for child in value:
            matches.update(collect_pattern_matches(child, pattern))
    return matches


def collect_keyed_strings(value: Any, keys: set[str]) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if normalized_key(key) in keys:
                values.update(collect_string_values(child))
            values.update(collect_keyed_strings(child, keys))
    elif isinstance(value, list):
        for child in value:
            values.update(collect_keyed_strings(child, keys))
    return {item for item in values if item}


def collect_ui_tree_identifiers(path: Path | None) -> set[str]:
    payload = read_json(path, label="UI tree")
    if path is not None and not isinstance(payload, (dict, list)):
        raise ValueError(f"UI tree JSON root must be an object or array: {path}")
    identifiers = collect_pattern_matches(payload, UI_TREE_ID_PATTERN)
    identifiers.update(collect_keyed_strings(payload, UI_IDENTIFIER_KEYS))
    return identifiers


def collect_ui_tree_labels(path: Path | None) -> set[str]:
    payload = read_json(path, label="UI tree")
    if path is not None and not isinstance(payload, (dict, list)):
        raise ValueError(f"UI tree JSON root must be an object or array: {path}")
    labels = collect_pattern_matches(payload, UI_TREE_LABEL_PATTERN)
    labels.update(collect_keyed_strings(payload, UI_LABEL_KEYS))
    return labels


def collect_scenario_steps(path: Path | None) -> list[Any]:
    if path is None:
        return []
    payload = read_json(path, label="scenario")
    steps = payload.get("steps") if isinstance(payload, dict) else payload
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"scenario JSON must contain a non-empty `steps` array: {path}")
    if not all(isinstance(step, dict) for step in steps):
        raise ValueError(f"every scenario step must be an object: {path}")
    return steps


def collect_scenario_ids(path: Path | None) -> list[str]:
    ids: list[str] = []
    for step in collect_scenario_steps(path):
        collect_scenario_identifiers(step, ids, top_level=True)
    return ids


def collect_scenario_labels(path: Path | None) -> list[str]:
    labels: list[str] = []
    for step in collect_scenario_steps(path):
        collect_scenario_label_values(step, labels, top_level=True)
    return labels


def selector_uses_identifier_strategy(value: dict[Any, Any]) -> bool:
    for key, child in value.items():
        if normalized_key(key) in SCENARIO_SELECTOR_STRATEGY_KEYS:
            if isinstance(child, str) and normalized_key(child) in SCENARIO_IDENTIFIER_STRATEGIES:
                return True
    return False


def selector_uses_label_strategy(value: dict[Any, Any]) -> bool:
    for key, child in value.items():
        if normalized_key(key) in SCENARIO_SELECTOR_STRATEGY_KEYS:
            if isinstance(child, str) and normalized_key(child) in SCENARIO_LABEL_STRATEGIES:
                return True
    return False


def selector_value_key_is_locator(value: dict[Any, Any]) -> bool:
    keys = {normalized_key(key) for key in value}
    if keys & SCENARIO_SELECTOR_NAME_KEYS:
        return False
    return True


def mapping_has_identifier_locator(value: dict[Any, Any]) -> bool:
    for key, child in value.items():
        if normalized_key(key) in SCENARIO_IDENTIFIER_KEYS and collect_string_values(child):
            return True
    if not selector_uses_identifier_strategy(value):
        return False
    for key, child in value.items():
        if normalized_key(key) in (
            SCENARIO_SELECTOR_NAME_KEYS | SCENARIO_SELECTOR_VALUE_KEYS
        ) and collect_string_values(child):
            return True
    return False


def collect_scenario_label_values(
    value: Any,
    labels: list[str],
    *,
    selector_context: bool = False,
    top_level: bool = False,
) -> None:
    if isinstance(value, dict):
        collect_direct_labels = selector_context or top_level
        selector_value_is_label = collect_direct_labels and selector_uses_label_strategy(value)
        identifier_takes_precedence = (
            collect_direct_labels and mapping_has_identifier_locator(value)
        )
        has_selector_name = any(
            normalized_key(key) in SCENARIO_SELECTOR_NAME_KEYS
            and bool(collect_string_values(child))
            for key, child in value.items()
        )
        has_direct_label = any(
            normalized_key(key) in SCENARIO_LABEL_KEYS
            and bool(collect_string_values(child))
            for key, child in value.items()
        )
        for key, child in value.items():
            key_name = normalized_key(key)
            if collect_direct_labels and key_name in SCENARIO_LABEL_KEYS:
                if not identifier_takes_precedence:
                    for item in collect_string_values(child):
                        append_unique(labels, item)
                continue
            if selector_value_is_label and key_name in SCENARIO_SELECTOR_NAME_KEYS:
                for item in collect_string_values(child):
                    append_unique(labels, item)
                continue
            if (
                selector_value_is_label
                and key_name in SCENARIO_SELECTOR_VALUE_KEYS
                and not has_selector_name
                and not has_direct_label
            ):
                for item in collect_string_values(child):
                    append_unique(labels, item)
                continue
            if key_name in SCENARIO_PAYLOAD_CONTAINER_KEYS:
                continue
            if key_name in SCENARIO_SELECTOR_CONTAINER_KEYS:
                if not isinstance(child, str):
                    collect_scenario_label_values(child, labels, selector_context=True)
                continue
            collect_scenario_label_values(child, labels)
    elif isinstance(value, list):
        for child in value:
            collect_scenario_label_values(child, labels, selector_context=selector_context)


def collect_scenario_identifiers(
    value: Any,
    ids: list[str],
    *,
    selector_context: bool = False,
    top_level: bool = False,
) -> None:
    if isinstance(value, dict):
        collect_direct_ids = selector_context or top_level
        selector_value_is_identifier = collect_direct_ids and selector_uses_identifier_strategy(value)
        for key, child in value.items():
            key_name = normalized_key(key)
            if collect_direct_ids and key_name in SCENARIO_IDENTIFIER_KEYS:
                for item in collect_string_values(child):
                    append_unique(ids, item)
                continue
            if selector_value_is_identifier and key_name in SCENARIO_SELECTOR_NAME_KEYS:
                for item in collect_string_values(child):
                    append_unique(ids, item)
                continue
            if selector_value_is_identifier and key_name in SCENARIO_SELECTOR_VALUE_KEYS:
                if selector_value_key_is_locator(value):
                    for item in collect_string_values(child):
                        append_unique(ids, item)
                continue
            if key_name in SCENARIO_PAYLOAD_CONTAINER_KEYS:
                continue
            if key_name in SCENARIO_SELECTOR_CONTAINER_KEYS:
                if isinstance(child, str):
                    if key_name in SCENARIO_DIRECT_SELECTOR_STRING_KEYS:
                        append_unique(ids, child)
                else:
                    collect_scenario_identifiers(child, ids, selector_context=True)
                continue
            collect_scenario_identifiers(child, ids)
    elif isinstance(value, list):
        for child in value:
            collect_scenario_identifiers(child, ids, selector_context=selector_context)


def is_state_dependent(identifier: str) -> bool:
    lowered = identifier.lower()
    return any(token in lowered for token in STATE_DEPENDENT_TOKENS)


CLAUSE_SPLIT_PATTERN = re.compile(
    r"[.!?;\n]+|\b(?:but|however|whereas|yet)\b"
)
FAILURE_STATE_PATTERN = re.compile(
    r"\b(?:crash(?:ed|es|ing)?|error(?:ed)?|fail(?:ed|ing|s|ure)?|hang(?:s|ing)?|"
    r"offline|refused|stuck|timed? ?out|timeout|unavailable|unreachable|"
    r"unsuccessful(?:ly)?|wrong screen)\b"
    r"|\b(?:(?:http|status)\s+5\d\d|returned\s+5\d\d)\b"
)
NEGATED_FAILURE_PATTERN = re.compile(
    r"\b(?:(?:did|does|do|was|were|is|are|has|have)\s+not|"
    r"(?:didn|doesn|wasn|weren|isn|aren|hasn|haven)['’]t|never)\s+"
    r"(?:(?!(?:after|and|before|but|later|then|yet)\b)\w+\s+){0,2}"
    r"(?:crash(?:ed|es|ing)?|error(?:ed)?|fail(?:ed|ing|s|ure)?|"
    r"hang(?:s|ing)?|offline|refused|stuck|timed? ?out|timeout|unavailable|"
    r"unreachable|unsuccessful(?:ly)?)\b"
)
NO_FAILURE_PATTERN = re.compile(
    r"\b(?:without|no|(?:had|has|have|with)\s+no)\s+"
    r"(?:(?!(?:after|and|before|but|later|then|yet)\b)\w+\s+){0,4}"
    r"(?:crash(?:ed|es|ing)?|error(?:ed)?|fail(?:ed|ing|s|ure)?|hang(?:s|ing)?|"
    r"offline|refused|stuck|timed? ?out|timeout|unavailable|unreachable|"
    r"unsuccessful(?:ly)?|(?:(?:http|status)\s+5\d\d)|(?:returned\s+5\d\d))\b"
)
NEGATED_SUCCESS_PATTERN = re.compile(
    r"\b(?:(?:did|does|do|was|were|is|are|has|have)\s+not|"
    r"(?:didn|doesn|wasn|weren|isn|aren|hasn|haven)['’]t|never)\s+"
    r"(?:(?!(?:after|and|before|but|later|then|yet)\b)\w+\s+){0,2}"
    r"(?:complete(?:d)?|ready|respond(?:ed)?|succeed(?:ed)?|"
    r"successful(?:ly)?)\b"
)
DIRECT_FAILURE_PREFIX_PATTERN = re.compile(
    r"\b(?:can(?:not|['’]t)|could(?: not|n['’]t)|did(?: not|n['’]t)|"
    r"does(?: not|n['’]t)|do not|won['’]t|unable to|"
    r"failed to|failure to)\s+(?:(?:open|reach|start|trigger)\s+)?$"
)
PARENTHETICAL_COMMA_PATTERN = re.compile(
    r",\s*(?P<aside>(?:(?:after|although|at|because|before|despite|during|eventually|"
    r"following|initially|on|once|surprisingly|unexpectedly|upon|when|which|while|who)\b)"
    r"[^,\n]{0,96}),"
)


def spans_covering(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [match.span() for match in pattern.finditer(text)]


def span_is_covered(span: tuple[int, int], covers: list[tuple[int, int]]) -> bool:
    return any(start <= span[0] and span[1] <= end for start, end in covers)


def without_parenthetical_commas(text: str) -> str:
    normalized = text
    outer_app_pattern = re.compile(r"\b(?:app|application|it|process)\s*$")
    active_launch_aside_pattern = re.compile(
        r"\b(?:(?:at|during|on|upon)\s+(?:app\s+)?(?:boot|launch|routing|startup)|"
        r"when\s+(?:\w+\s+){0,3}launched|while\s+(?:\w+\s+){0,3}launching)\b"
    )
    while True:
        match = PARENTHETICAL_COMMA_PATTERN.search(normalized)
        if match is None:
            break
        prefix = normalized[max(0, match.start() - 64) : match.start()]
        replacement = (
            " launch "
            if outer_app_pattern.search(prefix)
            and active_launch_aside_pattern.search(match.group("aside"))
            else " "
        )
        normalized = normalized[: match.start()] + replacement + normalized[match.end() :]
    return normalized


def parenthetical_asides(text: str) -> list[str]:
    return [match.group("aside") for match in PARENTHETICAL_COMMA_PATTERN.finditer(text)]


def fragment_has_failure(
    fragment: str,
    *,
    unrelated_pattern: re.Pattern[str],
    inability_verbs: str,
    predicate_position: str,
    negation_context: str | None = None,
    fragment_offset: int = 0,
) -> bool:
    negation_source = fragment if negation_context is None else negation_context
    negated_failures = spans_covering(NEGATED_FAILURE_PATTERN, negation_source)
    negated_failures.extend(spans_covering(NO_FAILURE_PATTERN, negation_source))
    inability_pattern = re.compile(
        rf"\b(?:can(?:not|['’]t)|could(?: not|n['’]t)|won['’]t|unable to)\s+"
        rf"(?:\w+\s+){{0,2}}(?:{inability_verbs})\b"
    )

    def has_unrelated_subject(match: re.Match[str]) -> bool:
        before = fragment[: match.start()]
        if unrelated_pattern.search(before):
            return True
        if predicate_position in {"before_subject", "standalone"}:
            return bool(unrelated_pattern.search(fragment[match.end() :]))
        return False

    for failure in NEGATED_SUCCESS_PATTERN.finditer(fragment):
        if not has_unrelated_subject(failure):
            return True

    for failure in inability_pattern.finditer(fragment):
        if not has_unrelated_subject(failure):
            return True

    for failure in FAILURE_STATE_PATTERN.finditer(fragment):
        failure_span = (
            fragment_offset + failure.start(),
            fragment_offset + failure.end(),
        )
        if span_is_covered(failure_span, negated_failures):
            continue
        if has_unrelated_subject(failure):
            continue
        return True

    return False


def subject_has_failure(
    clause: str,
    *,
    subject_pattern: re.Pattern[str],
    unrelated_pattern: re.Pattern[str],
    inability_verbs: str,
    scope_routing_with_prefix: bool = False,
) -> bool:
    negated_clause_failures = spans_covering(NEGATED_FAILURE_PATTERN, clause)
    negated_clause_failures.extend(spans_covering(NO_FAILURE_PATTERN, clause))
    for subject in subject_pattern.finditer(clause):
        prefix_start = max(0, subject.start() - 96)
        prefix = clause[prefix_start : subject.start()]
        direct_prefix = DIRECT_FAILURE_PREFIX_PATTERN.search(prefix)
        if direct_prefix and not unrelated_pattern.search(prefix[: direct_prefix.start()]):
            direct_failures = list(
                FAILURE_STATE_PATTERN.finditer(
                    prefix[direct_prefix.start() : direct_prefix.end()]
                )
            )
            direct_failure_offset = prefix_start + direct_prefix.start()
            if not direct_failures or any(
                not span_is_covered(
                    (
                        direct_failure_offset + failure.start(),
                        direct_failure_offset + failure.end(),
                    ),
                    negated_clause_failures,
                )
                for failure in direct_failures
            ):
                return True

        if fragment_has_failure(
            prefix,
            unrelated_pattern=unrelated_pattern,
            inability_verbs=inability_verbs,
            predicate_position="before_subject",
            negation_context=clause,
            fragment_offset=prefix_start,
        ):
            return True

        if (
            scope_routing_with_prefix
            and subject.group(0).strip() == "routing"
            and unrelated_pattern.search(prefix)
        ):
            continue

        tail_end = min(len(clause), subject.end() + 128)
        tail = clause[subject.end() : tail_end]

        if fragment_has_failure(
            tail,
            unrelated_pattern=unrelated_pattern,
            inability_verbs=inability_verbs,
            predicate_position="after_subject",
            negation_context=clause,
            fragment_offset=subject.end(),
        ):
            return True

    return False


def summary_points_at_launch_failure(text: str) -> bool:
    subject_pattern = re.compile(
        r"\b(?:boot|deep[ -]?link|inspect|launch|simulator|startup|routing|"
        r"(?:automation|launch|test)\s+rout(?:e|ing))\b"
    )
    backend_pattern = re.compile(
        r"\b(?:api|backend|job|network|ocr|openai|processing|request|server)\b"
    )
    unrelated_pattern = re.compile(
        backend_pattern.pattern + r"|\b(?:assertion|button|scenario|ui test)\b"
    )
    introductory_launch_pattern = re.compile(
        r"^\s*(?:at|during|on|upon)\s+(?:app\s+)?(?:boot|launch|startup)\s*$"
    )
    if any(
        subject_has_failure(
            aside,
            subject_pattern=subject_pattern,
            unrelated_pattern=unrelated_pattern,
            inability_verbs=r"boot|complete|launch|load|open|route|start|succeed|become ready",
            scope_routing_with_prefix=True,
        )
        for aside in parenthetical_asides(text)
    ):
        return True
    text = without_parenthetical_commas(text)
    clauses = [
        clause.strip()
        for clause in CLAUSE_SPLIT_PATTERN.split(text)
        if clause.strip()
    ]

    for index, clause in enumerate(clauses):
        if subject_has_failure(
            clause,
            subject_pattern=subject_pattern,
            unrelated_pattern=unrelated_pattern,
            inability_verbs=r"boot|complete|launch|load|open|route|start|succeed|become ready",
            scope_routing_with_prefix=True,
        ):
            return True
        if (
            index > 0
            and introductory_launch_pattern.match(clauses[index - 1])
            and fragment_has_failure(
                clause,
                unrelated_pattern=unrelated_pattern,
                inability_verbs=(
                    r"boot|complete|launch|load|open|route|start|succeed|become ready"
                ),
                predicate_position="standalone",
            )
        ):
            return True
    return False


def summary_points_at_backend_failure(text: str) -> bool:
    backend_pattern = re.compile(
        r"\b(?:api|backend|job|network|ocr|openai|processing|request|server)\b"
    )
    launch_pattern = re.compile(
        r"\b(?:boot|deep[ -]?link|inspect|launch|simulator|startup|"
        r"(?:automation|launch|test)\s+rout(?:e|ing))\b"
    )
    if any(
        subject_has_failure(
            aside,
            subject_pattern=backend_pattern,
            unrelated_pattern=launch_pattern,
            inability_verbs=r"complete|connect|process|reach|respond|return",
        )
        for aside in parenthetical_asides(text)
    ):
        return True
    text = without_parenthetical_commas(text)
    return any(
        subject_has_failure(
            clause,
            subject_pattern=backend_pattern,
            unrelated_pattern=launch_pattern,
            inability_verbs=r"complete|connect|process|reach|respond|return",
        )
        for clause in CLAUSE_SPLIT_PATTERN.split(text)
    )


def classify(
    summary_text: str,
    scenario_ids: list[str],
    ui_tree_ids: set[str],
    *,
    planner_validation_error_text: str = "",
    scenario_labels: list[str] | None = None,
    ui_tree_labels: set[str] | None = None,
) -> dict[str, object]:
    combined_text = "\n".join(
        part for part in (summary_text, planner_validation_error_text) if part
    )
    lowered = combined_text.lower()
    scores = {bucket: 0 for bucket in ROOT_CAUSE_BUCKETS}
    evidence: list[str] = []
    scenario_labels = scenario_labels or []
    ui_tree_labels = ui_tree_labels or set()

    missing_ids = [identifier for identifier in scenario_ids if identifier not in ui_tree_ids]
    visible_ids = [identifier for identifier in scenario_ids if identifier in ui_tree_ids]
    missing_labels = [label for label in scenario_labels if label not in ui_tree_labels]
    visible_labels = [label for label in scenario_labels if label in ui_tree_labels]
    state_dependent_missing = [identifier for identifier in missing_ids if is_state_dependent(identifier)]
    state_dependent_missing_labels = [label for label in missing_labels if is_state_dependent(label)]

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

    if state_dependent_missing or state_dependent_missing_labels:
        scores["scenario contract"] += 2
        evidence.append(
            "scenario targets state-dependent identifiers or labels that were not present in the captured UI tree"
        )

    if summary_points_at_launch_failure(lowered):
        scores["launch determinism"] += 2
        evidence.append("summary points at a startup, inspect, simulator, or route failure")

    if (
        (scenario_ids or scenario_labels)
        and not (visible_ids or visible_labels)
        and (ui_tree_ids or ui_tree_labels)
    ):
        scores["launch determinism"] += 2
        evidence.append("none of the scenario identifiers or labels were visible in the captured UI tree")

    if re.search(
        r"\b(?:cannot (?:tap|type)|container collision|multiple matches|not hittable|resolved as (?:button|other|static ?text|text ?field)|wrong element type)\b|\bstatic ?text\b",
        lowered,
    ):
        scores["app contract"] += 3
        evidence.append("summary suggests the UI exposes the wrong element type or target")

    if (visible_ids or visible_labels) and (missing_ids or missing_labels):
        scores["app contract"] += 1
        scores["scenario contract"] += 1
        evidence.append("some scenario targets resolve in the UI tree while others do not")

    if summary_points_at_backend_failure(lowered):
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
        visible_labels=visible_labels,
        missing_labels=missing_labels,
        state_dependent_missing_labels=state_dependent_missing_labels,
    )

    return {
        "bucket": bucket,
        "confidence": confidence,
        "evidence": evidence,
        "planner_validation_error_present": bool(planner_validation_error_text.strip()),
        "scenario_ids": scenario_ids,
        "scenario_labels": scenario_labels,
        "visible_scenario_ids": visible_ids,
        "missing_scenario_ids": missing_ids,
        "state_dependent_missing_ids": state_dependent_missing,
        "visible_scenario_labels": visible_labels,
        "missing_scenario_labels": missing_labels,
        "state_dependent_missing_labels": state_dependent_missing_labels,
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
    visible_labels: list[str] | None = None,
    missing_labels: list[str] | None = None,
    state_dependent_missing_labels: list[str] | None = None,
) -> list[str]:
    visible_labels = visible_labels or []
    missing_labels = missing_labels or []
    state_dependent_missing_labels = state_dependent_missing_labels or []
    leading_missing = [
        *missing_ids,
        *(f"label: {label}" for label in missing_labels),
    ][:3]
    leading_visible = [
        *visible_ids,
        *(f"label: {label}" for label in visible_labels),
    ][:3]
    leading_state_dependent = [
        *state_dependent_missing,
        *(f"label: {label}" for label in state_dependent_missing_labels),
    ][:3]

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
            "Rewrite the checked-in scenario or planner context so it only targets identifiers or labels that are visible in the captured UI tree or explicitly documented as deterministic automation API.",
            "Remove conditional-state identifiers or labels from the main path unless launch setup guarantees that state.",
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

    missing_labels = report["missing_scenario_labels"]
    if missing_labels:
        print("\nMissing scenario labels")
        for label in missing_labels:
            print(f"  - {label}")

    visible_labels = report["visible_scenario_labels"]
    if visible_labels:
        print("\nVisible scenario labels")
        for label in visible_labels:
            print(f"  - {label}")

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
    try:
        summary_text = read_text(
            args.summary,
            label="summary",
            allow_empty=False,
        )
        planner_validation_error_text = read_text(
            args.planner_validation_error,
            label="planner validation error",
        )
        scenario_ids = collect_scenario_ids(args.scenario)
        scenario_labels = collect_scenario_labels(args.scenario)
        ui_tree_ids = collect_ui_tree_identifiers(args.ui_tree)
        ui_tree_labels = collect_ui_tree_labels(args.ui_tree)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report = classify(
        summary_text,
        scenario_ids,
        ui_tree_ids,
        planner_validation_error_text=planner_validation_error_text,
        scenario_labels=scenario_labels,
        ui_tree_labels=ui_tree_labels,
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
