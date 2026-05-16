#!/usr/bin/env python3
"""
Draft planner-context guidance from source-discovered automation hooks.

This produces a starter section for `.github/ai-ui/planner-context.md`. It is a
draft, not truth: maintainers still need to replace guesses with exact values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


from . import inventory_accessibility_ids
from . import inventory_launch_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft planner-context markdown from launch and accessibility inventories."
    )
    parser.add_argument("path", help="Repo root or source directory to scan.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of markdown.",
    )
    parser.add_argument(
        "--max-identifiers",
        type=int,
        default=16,
        help="Maximum number of literal identifiers to include in the markdown draft.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. When omitted, the result is printed to stdout.",
    )
    return parser.parse_args()


def build_markdown(
    *,
    launch_report: dict[str, object],
    accessibility_report: dict[str, object],
    max_identifiers: int,
) -> str:
    environment_keys: list[str] = launch_report["environment_keys"]  # type: ignore[assignment]
    launch_arguments: list[str] = launch_report["launch_arguments"]  # type: ignore[assignment]
    url_schemes: list[dict[str, object]] = launch_report["url_schemes"]  # type: ignore[assignment]
    route_hints: list[dict[str, object]] = launch_report["route_hints"]  # type: ignore[assignment]
    identifiers: dict[str, list[dict[str, object]]] = accessibility_report["identifiers"]  # type: ignore[assignment]
    review_needed_dynamic: list[dict[str, object]] = accessibility_report["review_needed_dynamic"]  # type: ignore[assignment]

    identifier_names = list(identifiers.keys())[:max_identifiers]

    lines = [
        "## Preferred deterministic launch",
        "",
        "Replace guesses below with exact key-value pairs or routes that are confirmed to work in this repo.",
        "",
        "- Candidate automation environment keys discovered in source:",
    ]

    if environment_keys:
        lines.extend(f"  - `{key}`: document the exact value if the planner should use it." for key in environment_keys)
    else:
        lines.append("  - none found")

    lines.append("- Candidate launch arguments discovered in source:")
    if launch_arguments:
        lines.extend(f"  - `{argument}`" for argument in launch_arguments)
    else:
        lines.append("  - none found")

    lines.append("- Candidate URL schemes:")
    if url_schemes:
        lines.extend(f"  - `{entry['scheme']}`" for entry in url_schemes[:8])
    else:
        lines.append("  - none found")

    lines.append("- Candidate route hooks to inspect:")
    if route_hints:
        lines.extend(
            f"  - `{entry['file']}:{entry['line']}`"
            for entry in route_hints[:8]
        )
    else:
        lines.append("  - none found")

    lines.extend(
        [
            "",
            "## Preferred flow",
            "",
            "- Stable literal accessibility identifiers discovered in source:",
        ]
    )

    if identifier_names:
        lines.extend(f"  - `{identifier}`" for identifier in identifier_names)
    else:
        lines.append("  - none found")

    lines.extend(
        [
            "- Prefer a short deterministic path that starts from a known route or launch state.",
            "- Prefer literal root identifiers, primary input fields, and final assertions over conditional-state targets.",
            "",
            "## Review before relying on AI planning",
            "",
        ]
    )

    if review_needed_dynamic:
        lines.append("- Review these dynamic identifiers before the planner depends on them:")
        for entry in review_needed_dynamic[:8]:
            identifier = entry.get("identifier") or entry["source"]
            lines.append(f"  - `{identifier}`")
    else:
        lines.append("- No obvious review-needed dynamic identifiers were found.")

    lines.append(
        "- Replace this draft with exact launch settings, stable route guidance, and the specific identifiers the repo wants to expose as automation API."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser().resolve()
    launch_report = inventory_launch_contract.collect(root)
    accessibility_report = inventory_accessibility_ids.collect(root)
    markdown = build_markdown(
        launch_report=launch_report,
        accessibility_report=accessibility_report,
        max_identifiers=args.max_identifiers,
    )

    if args.json:
        output = json.dumps(
            {
                "launch": launch_report,
                "accessibility": accessibility_report,
                "markdown": markdown,
            },
            indent=2,
            sort_keys=True,
        )
    else:
        output = markdown

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="" if not args.json else "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
