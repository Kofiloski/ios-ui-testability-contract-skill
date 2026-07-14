#!/usr/bin/env python3
"""
Inventory literal accessibility identifiers in Swift/ObjC sources.

This script is intentionally regex-based and dependency-light. It is meant for
fast contract audits, not full syntax-aware parsing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ._paths import display_path, iter_regular_files, resolve_scan_root


LIKELY_DYNAMIC_PATTERNS = (
    re.compile(r"\.accessibilityIdentifier\("),
    re.compile(r"\baccessibilityIdentifier\s*="),
    re.compile(r"\bsetAccessibilityIdentifier\s*:"),
)
OBJC_SETTER_DECLARATION_PATTERN = re.compile(
    r"^\s*[-+]\s*\([^)]*\)\s*setAccessibilityIdentifier\s*:"
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
    "Button",
    "NavigationLink",
    "TextField",
    "SecureField",
    "TextEditor",
    "Toggle",
    "Picker",
    "Stepper",
    "Slider",
    "Link",
    "UIButton",
    "UITextField",
    "UITextView",
    "UISwitch",
)
INTERPOLATION_EXPRESSION_PATTERN = re.compile(r"\\#*\((.*?)\)")
STABLE_MODEL_ID_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.(?:id|identifier|uuid)(?:\.uuidString)?"
    r"|[A-Za-z_][A-Za-z0-9_]*ID\.uuidString)",
    re.IGNORECASE,
)
UNSTABLE_DYNAMIC_PATTERN = re.compile(
    r"(?:^|[.\s(])(?:count|description|hashvalue|index|localized|name|offset|title)(?:$|[.\s)])",
    re.IGNORECASE,
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


def iter_source_files(
    root: Path,
    *,
    skipped_symlinks: list[str] | None = None,
) -> list[Path]:
    return iter_regular_files(
        root,
        SOURCE_SUFFIXES,
        EXCLUDED_PARTS,
        skipped_symlinks=skipped_symlinks,
    )


def without_string_literals(source: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', source)


@dataclass(frozen=True)
class SourceString:
    start: int
    content_start: int
    content_end: int
    end: int
    hash_count: int
    quote_count: int
    interpolation_spans: tuple[tuple[int, int], ...]


def string_delimiter_at(source: str, index: int) -> tuple[int, int, int] | None:
    cursor = index
    while cursor < len(source) and source[cursor] == "#":
        cursor += 1
    if cursor >= len(source) or source[cursor] != '"':
        return None
    quote_count = 3 if source.startswith('"""', cursor) else 1
    return cursor - index, quote_count, cursor


def skip_block_comment(source: str, index: int) -> int:
    depth = 1
    cursor = index + 2
    while cursor < len(source) and depth:
        if source.startswith("/*", cursor):
            depth += 1
            cursor += 2
        elif source.startswith("*/", cursor):
            depth -= 1
            cursor += 2
        else:
            cursor += 1
    return cursor


def extended_regex_hash_count_at(source: str, index: int) -> int | None:
    cursor = index
    while cursor < len(source) and source[cursor] == "#":
        cursor += 1
    hash_count = cursor - index
    if hash_count == 0 or cursor >= len(source) or source[cursor] != "/":
        return None
    return hash_count


def scan_extended_regex(source: str, start: int) -> int:
    hash_count = extended_regex_hash_count_at(source, start)
    if hash_count is None:
        raise ValueError(f"expected extended regex delimiter at offset {start}")
    cursor = start + hash_count + 1
    close_delimiter = "/" + ("#" * hash_count)
    interpolation_delimiter = "\\" + ("#" * hash_count) + "("

    while cursor < len(source):
        if source.startswith(close_delimiter, cursor):
            return cursor + len(close_delimiter)
        if source.startswith(interpolation_delimiter, cursor):
            cursor = skip_interpolation(source, cursor + len(interpolation_delimiter))
            continue
        if source[cursor] == "\\":
            cursor += min(2, len(source) - cursor)
            continue
        cursor += 1
    return len(source)


def scan_string(source: str, start: int) -> SourceString:
    delimiter = string_delimiter_at(source, start)
    if delimiter is None:
        raise ValueError(f"expected string delimiter at offset {start}")
    hash_count, quote_count, quote_start = delimiter
    content_start = quote_start + quote_count
    close_delimiter = ('"' * quote_count) + ('#' * hash_count)
    interpolation_delimiter = "\\" + ("#" * hash_count) + "("
    escape_delimiter = "\\" + ("#" * hash_count)
    interpolation_spans: list[tuple[int, int]] = []
    cursor = content_start

    while cursor < len(source):
        if source.startswith(close_delimiter, cursor):
            return SourceString(
                start=start,
                content_start=content_start,
                content_end=cursor,
                end=cursor + len(close_delimiter),
                hash_count=hash_count,
                quote_count=quote_count,
                interpolation_spans=tuple(interpolation_spans),
            )
        if source.startswith(interpolation_delimiter, cursor):
            expression_start = cursor + len(interpolation_delimiter)
            interpolation_end = skip_interpolation(source, expression_start)
            expression_end = (
                interpolation_end - 1
                if interpolation_end > expression_start
                and source[interpolation_end - 1] == ")"
                else interpolation_end
            )
            interpolation_spans.append((expression_start, expression_end))
            cursor = interpolation_end
            continue
        if source.startswith(escape_delimiter, cursor):
            escaped_start = cursor + len(escape_delimiter)
            if escaped_start < len(source):
                escaped_length = (
                    quote_count
                    if source.startswith('"' * quote_count, escaped_start)
                    else 1
                )
                cursor = min(len(source), escaped_start + escaped_length)
                continue
        if source[cursor] == "\\":
            cursor += 1
            continue
        cursor += 1

    return SourceString(
        start=start,
        content_start=content_start,
        content_end=len(source),
        end=len(source),
        hash_count=hash_count,
        quote_count=quote_count,
        interpolation_spans=tuple(interpolation_spans),
    )


def skip_interpolation(source: str, index: int) -> int:
    depth = 1
    cursor = index
    while cursor < len(source) and depth:
        if source.startswith("//", cursor):
            newline = source.find("\n", cursor + 2)
            cursor = len(source) if newline < 0 else newline + 1
            continue
        if source.startswith("/*", cursor):
            cursor = skip_block_comment(source, cursor)
            continue
        delimiter = string_delimiter_at(source, cursor)
        if delimiter is not None:
            cursor = scan_string(source, cursor).end
            continue
        if extended_regex_hash_count_at(source, cursor) is not None:
            cursor = scan_extended_regex(source, cursor)
            continue
        if source[cursor] == "(":
            depth += 1
        elif source[cursor] == ")":
            depth -= 1
        cursor += 1
    return cursor


def mask_range(mask: list[str], source: str, start: int, end: int) -> None:
    for index in range(start, end):
        if source[index] != "\n":
            mask[index] = " "


def lex_source(source: str) -> tuple[str, list[SourceString]]:
    """Return a code-only mask and source string tokens with offsets preserved."""
    mask = list(source)
    strings: list[SourceString] = []
    cursor = 0

    while cursor < len(source):
        if source.startswith("//", cursor):
            newline = source.find("\n", cursor + 2)
            end = len(source) if newline < 0 else newline
            mask_range(mask, source, cursor, end)
            cursor = end
            continue
        if source.startswith("/*", cursor):
            end = skip_block_comment(source, cursor)
            mask_range(mask, source, cursor, end)
            cursor = end
            continue
        delimiter = string_delimiter_at(source, cursor)
        if delimiter is not None:
            token = scan_string(source, cursor)
            strings.append(token)
            mask_range(mask, source, token.start, token.end)
            cursor = token.end
            continue
        if extended_regex_hash_count_at(source, cursor) is not None:
            end = scan_extended_regex(source, cursor)
            mask_range(mask, source, cursor, end)
            cursor = end
            continue
        cursor += 1

    return "".join(mask), strings


def literal_identifier_calls(
    source: str,
    code_mask: str,
    strings: list[SourceString],
) -> list[tuple[int, int, SourceString]]:
    calls: list[tuple[int, int, SourceString]] = []
    swift_prefix = re.compile(r"\.accessibilityIdentifier\(\s*$")
    assignment_prefix = re.compile(r"\baccessibilityIdentifier\s*=\s*@?\s*$")
    objc_setter_prefix = re.compile(r"\bsetAccessibilityIdentifier\s*:\s*@?\s*$")

    for token in strings:
        prefix = code_mask[: token.start]
        swift_match = swift_prefix.search(prefix)
        assignment_match = assignment_prefix.search(prefix)
        if swift_match:
            close_match = re.match(r"\s*\)", code_mask[token.end :])
            if close_match:
                calls.append(
                    (
                        swift_match.start(),
                        token.end + close_match.end(),
                        token,
                    )
                )
            continue

        if assignment_match:
            line_end = code_mask.find("\n", token.end)
            if line_end < 0:
                line_end = len(code_mask)
            trailing_code = code_mask[token.end : line_end].strip()
            if trailing_code in {"", ";"}:
                calls.append((assignment_match.start(), token.end, token))
            continue

        setter_match = objc_setter_prefix.search(prefix)
        if setter_match:
            close_match = re.match(r"\s*\]", code_mask[token.end :])
            if close_match:
                calls.append(
                    (
                        setter_match.start(),
                        token.end + close_match.end(),
                        token,
                    )
                )

    return calls


def line_number_at(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def source_excerpt(source: str, start: int, end: int) -> str:
    return " ".join(source[start:end].split())


def contains_ternary_expression(
    *,
    identifier: str | None,
    source: str,
    interpolation_expressions: list[str] | None = None,
) -> bool:
    candidates = interpolation_expressions
    if candidates is None:
        candidates = (
            INTERPOLATION_EXPRESSION_PATTERN.findall(identifier)
            if identifier
            else [without_string_literals(source.split("//", 1)[0])]
        )
    return any(
        re.search(r"(?<!\?)\?(?!\?)", candidate) and ":" in candidate
        for candidate in candidates
    )


def direct_dynamic_expression(source: str) -> str | None:
    call = re.search(
        r"\.accessibilityIdentifier\(\s*([^()\s][^()]*)\s*\)",
        source,
    )
    if call:
        return call.group(1).strip()
    assignment = re.search(r"\baccessibilityIdentifier\s*=\s*([^;]+)", source)
    if assignment:
        return assignment.group(1).strip()
    setter = re.search(r"\bsetAccessibilityIdentifier\s*:\s*([^\]]+)\]", source)
    if setter:
        return setter.group(1).strip()
    return None


def contains_context_token(source: str, tokens: tuple[str, ...]) -> bool:
    return any(
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])",
            source,
        )
        for token in tokens
    )


def has_identifier_token(source: str, tokens: tuple[str, ...]) -> bool:
    lowered = source.lower()
    return any(
        re.search(
            rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])",
            lowered,
        )
        for token in tokens
    )


def is_inside_foreach(lines: list[str], line_number: int) -> bool:
    depth = 0
    for index in range(line_number - 2, max(-1, line_number - 82), -1):
        source = without_string_literals(lines[index])
        depth += source.count("}") - source.count("{")
        if contains_context_token(source, ("ForEach",)) and depth < 0:
            return True
    return False


def preceding_swiftui_expression(lines: list[str], line_number: int) -> str:
    current = without_string_literals(lines[line_number - 1]).strip()
    if ".accessibilityIdentifier" in current:
        inline_target = current.split(".accessibilityIdentifier", 1)[0].strip()
        if inline_target and inline_target != "}":
            return inline_target

    index = line_number - 2
    while index >= 0:
        source = without_string_literals(lines[index]).strip()
        if not source or source.startswith("//") or source.startswith("."):
            index -= 1
            continue
        if "}" not in source:
            return source

        depth = 0
        for cursor in range(index, -1, -1):
            candidate = without_string_literals(lines[cursor]).strip()
            depth += candidate.count("}") - candidate.count("{")
            if depth <= 0 and "{" in candidate:
                return candidate
        return source
    return ""


def is_likely_parent_container_assignment(*, lines: list[str], line_number: int) -> bool:
    line = lines[line_number - 1]
    if ".accessibilityIdentifier(" in line:
        context = preceding_swiftui_expression(lines, line_number)
    else:
        start = max(0, line_number - 6)
        context = " ".join(without_string_literals(item) for item in lines[start:line_number])
    has_container = contains_context_token(context, CONTAINER_CONTEXT_TOKENS)
    has_interactive = contains_context_token(context, INTERACTIVE_CONTEXT_TOKENS)
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


def classify_dynamic_entry(
    *,
    identifier: str | None,
    source: str,
    repeated_context: bool = False,
    interpolation_expressions: list[str] | None = None,
) -> str:
    lowered_identifier = (identifier or "").lower()
    lowered_source = source.lower()

    if contains_ternary_expression(
        identifier=identifier,
        source=source,
        interpolation_expressions=interpolation_expressions,
    ):
        return "review_needed"
    if any(token in lowered_source for token in ("??", "step ==", "if ")):
        return "review_needed"
    if has_identifier_token(lowered_identifier, CRITICAL_DYNAMIC_TOKENS):
        return "review_needed"
    if any(token in lowered_source for token in ("empty", "modal", "sheet", "paywall")):
        return "review_needed"
    expressions = interpolation_expressions
    if expressions is None:
        expressions = (
            INTERPOLATION_EXPRESSION_PATTERN.findall(identifier)
            if identifier
            else []
        )
    direct_expression = direct_dynamic_expression(source) if not expressions else None
    dynamic_source = " ".join(expressions) if expressions else (direct_expression or source)
    if UNSTABLE_DYNAMIC_PATTERN.search(dynamic_source):
        return "review_needed"
    is_repeated_target = repeated_context or has_identifier_token(
        f"{lowered_identifier} {lowered_source}",
        LIKELY_REPEATED_ITEM_TOKENS,
    )
    every_expression_is_stable = bool(expressions) and all(
        STABLE_MODEL_ID_PATTERN.fullmatch(expression.strip())
        for expression in expressions
    )
    direct_expression_is_stable = bool(direct_expression) and bool(
        STABLE_MODEL_ID_PATTERN.fullmatch(direct_expression)
    )
    if is_repeated_target and (
        every_expression_is_stable or direct_expression_is_stable
    ):
        return "acceptable"
    return "review_needed"


def collect(root: Path) -> dict[str, object]:
    root = resolve_scan_root(root)
    occurrences: dict[str, list[dict[str, object]]] = defaultdict(list)
    interpolated: list[dict[str, object]] = []
    likely_dynamic: list[dict[str, object]] = []
    acceptable_dynamic: list[dict[str, object]] = []
    review_needed_dynamic: list[dict[str, object]] = []
    likely_parent_container_assignments: list[dict[str, object]] = []
    skipped_symlinks: list[str] = []

    for path in iter_source_files(root, skipped_symlinks=skipped_symlinks):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")

        scan_text, source_strings = lex_source(text)
        lines = scan_text.splitlines()
        original_lines = text.splitlines()
        literal_start_lines: set[int] = set()

        for start, end, token in literal_identifier_calls(
            text,
            scan_text,
            source_strings,
        ):
            identifier = text[token.content_start : token.content_end]
            interpolation_expressions = [
                text[expression_start:expression_end]
                for expression_start, expression_end in token.interpolation_spans
            ]
            line_number = line_number_at(scan_text, start)
            literal_start_lines.add(line_number)
            excerpt = source_excerpt(text, start, end)
            if interpolation_expressions:
                entry = {
                    "identifier": identifier,
                    "file": display_path(path, root),
                    "line": line_number,
                    "source": excerpt,
                    "classification": classify_dynamic_entry(
                        identifier=identifier,
                        source=excerpt,
                        repeated_context=is_inside_foreach(lines, line_number),
                        interpolation_expressions=interpolation_expressions,
                    ),
                }
                interpolated.append(entry)
                if entry["classification"] == "acceptable":
                    acceptable_dynamic.append(entry)
                else:
                    review_needed_dynamic.append(entry)
                continue
            occurrences[identifier].append(
                {
                    "file": display_path(path, root),
                    "line": line_number,
                    "source": excerpt,
                }
            )
            if is_likely_parent_container_assignment(lines=lines, line_number=line_number):
                likely_parent_container_assignments.append(
                    {
                        "identifier": identifier,
                        "file": display_path(path, root),
                        "line": line_number,
                        "source": excerpt,
                    }
                )

        for line_number, line in enumerate(lines, start=1):
            if line_number in literal_start_lines:
                continue
            if any(pattern.search(line) for pattern in LIKELY_DYNAMIC_PATTERNS):
                original_line = (
                    original_lines[line_number - 1].strip()
                    if line_number <= len(original_lines)
                    else line.strip()
                )
                if OBJC_SETTER_DECLARATION_PATTERN.search(original_line):
                    continue
                entry = {
                    "file": display_path(path, root),
                    "line": line_number,
                    "source": original_line,
                    "classification": classify_dynamic_entry(
                        identifier=None,
                        source=original_line,
                        repeated_context=is_inside_foreach(lines, line_number),
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
                            "file": display_path(path, root),
                            "line": line_number,
                            "source": original_line,
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
        "skipped_symlinks": sorted(dict.fromkeys(skipped_symlinks)),
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
    skipped_symlinks: list[str] = report["skipped_symlinks"]  # type: ignore[assignment]

    target = duplicates if duplicates_only else identifiers
    print(f"Identifiers: {len(identifiers)}")
    print(f"Duplicate literals: {len(duplicates)}")
    print(f"Interpolated assignments: {len(interpolated)}")
    print(f"Likely non-literal assignments: {len(likely_dynamic)}")
    print(f"Acceptable dynamic assignments: {len(acceptable_dynamic)}")
    print(f"Review-needed dynamic assignments: {len(review_needed_dynamic)}")
    print(f"Likely parent-container assignments: {len(likely_parent_container_assignments)}")
    print(f"Likely parent-container collisions: {len(likely_parent_container_collisions)}")
    print(f"Skipped symbolic links: {len(skipped_symlinks)}")

    if not target:
        if duplicates_only:
            print("\nNo duplicate literal identifiers found.")
        else:
            print("\nNo literal identifiers found.")
    if target:
        print("")
        for identifier, entries in target.items():
            print(identifier)
            for entry in entries:
                relative = entry["file"]
                print(f"  {relative}:{entry['line']}")

    if interpolated and not duplicates_only:
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

    if skipped_symlinks:
        print("\nSkipped symbolic links")
        for path in skipped_symlinks[:8]:
            print(f"  {path}")
        if len(skipped_symlinks) > 8:
            print(f"  ... and {len(skipped_symlinks) - 8} more")


def main() -> int:
    args = parse_args()
    try:
        report = collect(Path(args.path))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        output = (
            {
                "duplicates": report["duplicates"],
                "skipped_symlinks": report["skipped_symlinks"],
            }
            if args.duplicates_only
            else report
        )
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print_text_report(report, args.duplicates_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
