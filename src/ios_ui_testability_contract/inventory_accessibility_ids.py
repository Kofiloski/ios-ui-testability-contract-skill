#!/usr/bin/env python3
"""
Inventory literal accessibility identifiers in Swift/ObjC sources.

This script is intentionally regex-based and dependency-light. It is meant for
fast contract audits, not full syntax-aware parsing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path


LITERAL_PATTERNS = (
    re.compile(r"\.accessibilityIdentifier\(\s*\"([^\"]+)\"\s*\)"),
    re.compile(r"\baccessibilityIdentifier\s*=\s*@?\"([^\"]+)\""),
)

LIKELY_DYNAMIC_PATTERNS = (
    re.compile(r"\.accessibilityIdentifier\("),
    re.compile(r"\baccessibilityIdentifier\s*="),
)

SOURCE_SUFFIXES = {".swift", ".m", ".mm", ".h"}
EXCLUDED_PARTS = {
    ".build",
    ".derivedData",
    ".git",
    ".swiftpm",
    "Build",
    "Carthage",
    "DerivedData",
    "Pods",
    "SourcePackages",
    "build",
    "node_modules",
    "vendor",
    "xcuserdata",
}
CRITICAL_DYNAMIC_TOKENS = (
    "screen",
    "root",
    "form",
    "field",
    "input",
    "button",
    "cta",
    "modal",
    "sheet",
    "paywall",
    "empty",
    "placeholder",
)
LIKELY_REPEATED_ITEM_TOKENS = ("row", "cell", "item", "card")
CONTAINER_CONTEXT_TOKENS = (
    "VStack",
    "HStack",
    "ZStack",
    "Group",
    "Section",
    "List",
    "Form",
    "ScrollView",
    "LazyVStack",
    "LazyHStack",
    "NavigationStack",
    "NavigationView",
    "TabView",
    "UIStackView",
    "UIView",
    "UICollectionView",
    "UITableView",
)
INTERACTIVE_CONTEXT_TOKENS = (
    "Button(",
    "NavigationLink(",
    "TextField(",
    "SecureField(",
    "TextEditor(",
    "Toggle(",
    "Picker(",
    "Stepper(",
    "Slider(",
    "Link(",
    "UIButton",
    "UITextField",
    "UITextView",
    "UISwitch",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory accessibility identifiers in an iOS codebase."
    )
    parser.add_argument("path", help="Repo root or source directory to scan.")
    parser.add_argument(
        "--duplicates-only",
        action="store_true",
        help="Print only identifiers that appear more than once.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text output.",
    )
    return parser.parse_args()


def iter_source_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix in SOURCE_SUFFIXES else []
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_PARTS]
        base_path = Path(current_root)
        for filename in filenames:
            path = base_path / filename
            if path.suffix in SOURCE_SUFFIXES:
                files.append(path)
    return sorted(files)


def nearby_context(lines: list[str], line_number: int, *, radius: int = 2) -> str:
    start = max(0, line_number - 1 - radius)
    end = min(len(lines), line_number + radius)
    window = [line.strip() for line in lines[start:end] if line.strip()]
    return " ".join(window)


def is_likely_parent_container_assignment(*, lines: list[str], line_number: int) -> bool:
    context = nearby_context(lines, line_number)
    has_container = any(token in context for token in CONTAINER_CONTEXT_TOKENS)
    has_interactive = any(token in context for token in INTERACTIVE_CONTEXT_TOKENS)
    return has_container and not has_interactive


def build_parent_container_collisions(
    *,
    occurrences: dict[str, list[dict[str, object]]],
    likely_parent_container_assignments: list[dict[str, object]],
) -> list[dict[str, object]]:
    collisions: list[dict[str, object]] = []
    seen_identifiers: set[str] = set()

    for entry in likely_parent_container_assignments:
        identifier = entry.get("identifier")
        if not isinstance(identifier, str) or not identifier or identifier in seen_identifiers:
            continue
        seen_identifiers.add(identifier)

        duplicate_count = len(occurrences.get(identifier, []))
        child_identifiers = sorted(
            other_identifier
            for other_identifier in occurrences
            if other_identifier.startswith(f"{identifier}.")
        )
        if duplicate_count <= 1 and not child_identifiers:
            continue

        collisions.append(
            {
                "identifier": identifier,
                "file": entry["file"],
                "line": entry["line"],
                "source": entry["source"],
                "duplicate_count": duplicate_count,
                "child_identifiers": child_identifiers,
            }
        )

    return collisions


def classify_dynamic_entry(*, identifier: str | None, source: str) -> str:
    lowered_identifier = (identifier or "").lower()
    lowered_source = source.lower()

    if any(token in lowered_source for token in (" ? ", ":", "??", "step ==", "if ")):
        return "review_needed"
    if any(token in lowered_identifier for token in CRITICAL_DYNAMIC_TOKENS):
        return "review_needed"
    if any(token in lowered_source for token in ("empty", "modal", "sheet", "paywall")):
        return "review_needed"
    if any(token in lowered_identifier for token in LIKELY_REPEATED_ITEM_TOKENS):
        return "acceptable"
    if any(token in lowered_source for token in ("foreach", "list", "row", "cell", "item")):
        return "acceptable"
    if identifier and "\\(" in identifier:
        return "acceptable"
    return "review_needed"


def collect(root: Path) -> dict[str, object]:
    occurrences: dict[str, list[dict[str, object]]] = defaultdict(list)
    interpolated: list[dict[str, object]] = []
    likely_dynamic: list[dict[str, object]] = []
    acceptable_dynamic: list[dict[str, object]] = []
    review_needed_dynamic: list[dict[str, object]] = []
    likely_parent_container_assignments: list[dict[str, object]] = []

    for path in iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")

        matched_lines: set[int] = set()
        lines = text.splitlines()

        for line_number, line in enumerate(lines, start=1):
            line_had_literal = False
            for pattern in LITERAL_PATTERNS:
                for match in pattern.finditer(line):
                    identifier = match.group(1)
                    if "\\(" in identifier:
                        entry = {
                            "identifier": identifier,
                            "file": str(path),
                            "line": line_number,
                            "source": line.strip(),
                            "classification": classify_dynamic_entry(
                                identifier=identifier,
                                source=line.strip(),
                            ),
                        }
                        interpolated.append(entry)
                        if entry["classification"] == "acceptable":
                            acceptable_dynamic.append(entry)
                        else:
                            review_needed_dynamic.append(entry)
                        line_had_literal = True
                        matched_lines.add(line_number)
                        continue
                    occurrences[identifier].append(
                        {
                            "file": str(path),
                            "line": line_number,
                            "source": line.strip(),
                        }
                    )
                    if is_likely_parent_container_assignment(lines=lines, line_number=line_number):
                        likely_parent_container_assignments.append(
                            {
                                "identifier": identifier,
                                "file": str(path),
                                "line": line_number,
                                "source": line.strip(),
                            }
                        )
                    line_had_literal = True
                    matched_lines.add(line_number)

            if line_had_literal:
                continue

            if any(pattern.search(line) for pattern in LIKELY_DYNAMIC_PATTERNS):
                entry = {
                    "file": str(path),
                    "line": line_number,
                    "source": line.strip(),
                    "classification": classify_dynamic_entry(
                        identifier=None,
                        source=line.strip(),
                    ),
                }
                likely_dynamic.append(entry)
                if entry["classification"] == "acceptable":
                    acceptable_dynamic.append(entry)
                else:
                    review_needed_dynamic.append(entry)
                if is_likely_parent_container_assignment(lines=lines, line_number=line_number):
                    likely_parent_container_assignments.append(
                        {
                            "identifier": None,
                            "file": str(path),
                            "line": line_number,
                            "source": line.strip(),
                        }
                    )

    duplicates = {
        identifier: entries
        for identifier, entries in sorted(occurrences.items())
        if len(entries) > 1
    }
    likely_parent_container_collisions = build_parent_container_collisions(
        occurrences=occurrences,
        likely_parent_container_assignments=likely_parent_container_assignments,
    )

    return {
        "identifiers": dict(sorted(occurrences.items())),
        "duplicates": duplicates,
        "interpolated": interpolated,
        "likely_dynamic": likely_dynamic,
        "acceptable_dynamic": acceptable_dynamic,
        "review_needed_dynamic": review_needed_dynamic,
        "likely_parent_container_assignments": likely_parent_container_assignments,
        "likely_parent_container_collisions": likely_parent_container_collisions,
    }


def print_text_report(report: dict[str, object], duplicates_only: bool) -> None:
    identifiers: dict[str, list[dict[str, object]]] = report["identifiers"]  # type: ignore[assignment]
    duplicates: dict[str, list[dict[str, object]]] = report["duplicates"]  # type: ignore[assignment]
    interpolated: list[dict[str, object]] = report["interpolated"]  # type: ignore[assignment]
    likely_dynamic: list[dict[str, object]] = report["likely_dynamic"]  # type: ignore[assignment]
    acceptable_dynamic: list[dict[str, object]] = report["acceptable_dynamic"]  # type: ignore[assignment]
    review_needed_dynamic: list[dict[str, object]] = report["review_needed_dynamic"]  # type: ignore[assignment]
    likely_parent_container_assignments: list[dict[str, object]] = report["likely_parent_container_assignments"]  # type: ignore[assignment]
    likely_parent_container_collisions: list[dict[str, object]] = report["likely_parent_container_collisions"]  # type: ignore[assignment]

    target = duplicates if duplicates_only else identifiers
    print(f"Identifiers: {len(identifiers)}")
    print(f"Duplicate literals: {len(duplicates)}")
    print(f"Interpolated assignments: {len(interpolated)}")
    print(f"Likely non-literal assignments: {len(likely_dynamic)}")
    print(f"Acceptable dynamic assignments: {len(acceptable_dynamic)}")
    print(f"Review-needed dynamic assignments: {len(review_needed_dynamic)}")
    print(f"Likely parent-container assignments: {len(likely_parent_container_assignments)}")
    print(f"Likely parent-container collisions: {len(likely_parent_container_collisions)}")

    if not target:
        if duplicates_only:
            print("\nNo duplicate literal identifiers found.")
        else:
            print("\nNo literal identifiers found.")
        if not interpolated and not likely_dynamic:
            return

    if target:
        print("")
        for identifier, entries in target.items():
            print(identifier)
            for entry in entries:
                relative = entry["file"]
                print(f"  {relative}:{entry['line']}")

    if interpolated:
        print("\nInterpolated assignments")
        for entry in interpolated:
            print(
                f"  {entry['file']}:{entry['line']}  {entry['identifier']}  [{entry['classification']}]"
            )

    if likely_dynamic and not duplicates_only:
        print("\nLikely non-literal assignments")
        for entry in likely_dynamic:
            print(
                f"  {entry['file']}:{entry['line']}  {entry['source']}  [{entry['classification']}]"
            )

    if review_needed_dynamic and not duplicates_only:
        print("\nReview-needed dynamic assignments")
        for entry in review_needed_dynamic:
            location = f"{entry['file']}:{entry['line']}"
            identifier = entry.get("identifier")
            detail = identifier if identifier else entry["source"]
            print(f"  {location}  {detail}")

    if likely_parent_container_assignments and not duplicates_only:
        print("\nLikely parent-container assignments")
        for entry in likely_parent_container_assignments:
            detail = entry.get("identifier") or entry["source"]
            print(f"  {entry['file']}:{entry['line']}  {detail}")

    if likely_parent_container_collisions and not duplicates_only:
        print("\nLikely parent-container collisions")
        for entry in likely_parent_container_collisions:
            identifier = entry["identifier"]
            child_identifiers = ", ".join(entry["child_identifiers"]) or "duplicate literal only"
            print(f"  {entry['file']}:{entry['line']}  {identifier}  ->  {child_identifiers}")


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser().resolve()
    report = collect(root)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report, args.duplicates_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
