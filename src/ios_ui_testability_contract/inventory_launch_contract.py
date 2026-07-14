#!/usr/bin/env python3
"""
Inventory likely launch-determinism hooks in an iOS repo.

This stays regex-based on purpose. It is meant to surface likely automation
entry points quickly, not to fully parse every routing abstraction.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import sys
from pathlib import Path

from ._paths import display_path, iter_regular_files, resolve_scan_root


SOURCE_SUFFIXES = {".swift", ".m", ".mm", ".h"}
PLIST_SUFFIXES = {".plist"}
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

ENV_KEY_PATTERN = re.compile(r'"([A-Z][A-Z0-9_]{3,})"')
LAUNCH_ARGUMENT_PATTERN = re.compile(r'"(-{1,2}[A-Za-z][A-Za-z0-9_-]*)"')
ROUTE_HINT_PATTERN = re.compile(
    r"onOpenURL|handlesExternalEvents|openURL|deeplink|deep link|deep-link|route",
    re.IGNORECASE,
)
AUTOMATION_HINT_PATTERN = re.compile(
    r"automation|ui[_ -]?test|seed|mock|fixture|debug.*route|test.*route",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory launch and routing hooks in an iOS codebase."
    )
    parser.add_argument("path", help="Repo root or source directory to scan.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text output.",
    )
    return parser.parse_args()


def iter_files(
    root: Path,
    suffixes: set[str],
    *,
    skipped_symlinks: list[str] | None = None,
) -> list[Path]:
    return iter_regular_files(
        root,
        suffixes,
        EXCLUDED_PARTS,
        skipped_symlinks=skipped_symlinks,
    )


def collect_url_schemes(
    root: Path,
    *,
    skipped_symlinks: list[str] | None = None,
    skipped_plists: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    schemes: list[dict[str, object]] = []

    for path in iter_files(root, PLIST_SUFFIXES, skipped_symlinks=skipped_symlinks):
        try:
            with path.open("rb") as handle:
                payload = plistlib.load(handle)
        except OSError:
            if skipped_plists is not None:
                skipped_plists.append(
                    {
                        "file": display_path(path, root),
                        "reason": "unreadable plist",
                    }
                )
            continue
        except (plistlib.InvalidFileException, ValueError, TypeError, OverflowError):
            if skipped_plists is not None:
                skipped_plists.append(
                    {
                        "file": display_path(path, root),
                        "reason": "malformed plist",
                    }
                )
            continue

        if not isinstance(payload, dict):
            continue

        url_types = payload.get("CFBundleURLTypes")
        if not isinstance(url_types, list):
            continue

        for entry in url_types:
            if not isinstance(entry, dict):
                continue
            url_schemes = entry.get("CFBundleURLSchemes")
            if not isinstance(url_schemes, list):
                continue
            for scheme in url_schemes:
                if not isinstance(scheme, str):
                    continue
                schemes.append({"scheme": scheme, "file": display_path(path, root)})

    return schemes


def collect(root: Path) -> dict[str, object]:
    root = resolve_scan_root(root)
    environment_keys: set[str] = set()
    launch_arguments: set[str] = set()
    route_hints: list[dict[str, object]] = []
    automation_hints: list[dict[str, object]] = []
    skipped_symlinks: list[str] = []
    skipped_plists: list[dict[str, str]] = []

    env_tokens = ("AUTOMATION", "UITEST", "UI_TEST", "TESTING", "ROUTE", "SEED", "MOCK")

    for path in iter_files(root, SOURCE_SUFFIXES, skipped_symlinks=skipped_symlinks):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")

        for line_number, line in enumerate(text.splitlines(), start=1):
            for key in ENV_KEY_PATTERN.findall(line):
                if any(token in key for token in env_tokens):
                    environment_keys.add(key)

            for argument in LAUNCH_ARGUMENT_PATTERN.findall(line):
                launch_arguments.add(argument)

            if ROUTE_HINT_PATTERN.search(line):
                route_hints.append(
                    {
                        "file": display_path(path, root),
                        "line": line_number,
                        "source": line.strip(),
                    }
                )

            if AUTOMATION_HINT_PATTERN.search(line):
                automation_hints.append(
                    {
                        "file": display_path(path, root),
                        "line": line_number,
                        "source": line.strip(),
                    }
                )

    return {
        "environment_keys": sorted(environment_keys),
        "launch_arguments": sorted(launch_arguments),
        "url_schemes": collect_url_schemes(
            root,
            skipped_symlinks=skipped_symlinks,
            skipped_plists=skipped_plists,
        ),
        "route_hints": route_hints,
        "automation_hints": automation_hints,
        "skipped_symlinks": sorted(dict.fromkeys(skipped_symlinks)),
        "skipped_plists": sorted(
            skipped_plists,
            key=lambda item: (item["file"], item["reason"]),
        ),
    }


def print_text_report(report: dict[str, object]) -> None:
    environment_keys: list[str] = report["environment_keys"]  # type: ignore[assignment]
    launch_arguments: list[str] = report["launch_arguments"]  # type: ignore[assignment]
    url_schemes: list[dict[str, object]] = report["url_schemes"]  # type: ignore[assignment]
    route_hints: list[dict[str, object]] = report["route_hints"]  # type: ignore[assignment]
    automation_hints: list[dict[str, object]] = report["automation_hints"]  # type: ignore[assignment]
    skipped_symlinks: list[str] = report["skipped_symlinks"]  # type: ignore[assignment]
    skipped_plists: list[dict[str, str]] = report["skipped_plists"]  # type: ignore[assignment]

    print(f"Environment keys: {len(environment_keys)}")
    print(f"Launch arguments: {len(launch_arguments)}")
    print(f"URL schemes: {len(url_schemes)}")
    print(f"Route hints: {len(route_hints)}")
    print(f"Automation hints: {len(automation_hints)}")
    print(f"Skipped symbolic links: {len(skipped_symlinks)}")
    print(f"Skipped plist files: {len(skipped_plists)}")

    if environment_keys:
        print("\nEnvironment keys")
        for key in environment_keys:
            print(f"  {key}")

    if launch_arguments:
        print("\nLaunch arguments")
        for argument in launch_arguments:
            print(f"  {argument}")

    if url_schemes:
        print("\nURL schemes")
        for entry in url_schemes:
            print(f"  {entry['scheme']}  {entry['file']}")

    if route_hints:
        print("\nRoute hints")
        for entry in route_hints:
            print(f"  {entry['file']}:{entry['line']}  {entry['source']}")

    if automation_hints:
        print("\nAutomation hints")
        for entry in automation_hints:
            print(f"  {entry['file']}:{entry['line']}  {entry['source']}")

    if skipped_symlinks:
        print("\nSkipped symbolic links")
        for path in skipped_symlinks[:8]:
            print(f"  {path}")
        if len(skipped_symlinks) > 8:
            print(f"  ... and {len(skipped_symlinks) - 8} more")

    if skipped_plists:
        print("\nSkipped plist files")
        for entry in skipped_plists[:8]:
            print(f"  {entry['file']}  {entry['reason']}")
        if len(skipped_plists) > 8:
            print(f"  ... and {len(skipped_plists) - 8} more")


def main() -> int:
    args = parse_args()
    try:
        report = collect(Path(args.path))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
