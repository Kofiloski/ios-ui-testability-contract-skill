from __future__ import annotations

import sys
from collections.abc import Sequence
from types import ModuleType

from . import __version__
from . import draft_planner_context
from . import inventory_accessibility_ids
from . import inventory_launch_contract
from . import triage_ui_contract_failure


COMMANDS: dict[str, tuple[str, ModuleType]] = {
    "ids": (
        "Inventory literal accessibility identifiers and likely identifier contract risks.",
        inventory_accessibility_ids,
    ),
    "launch": (
        "Inventory launch arguments, automation environment keys, URL schemes, and route hints.",
        inventory_launch_contract,
    ),
    "triage": (
        "Classify a failure artifact bundle into a likely UI automation contract root-cause bucket.",
        triage_ui_contract_failure,
    ),
    "draft-context": (
        "Draft planner-context markdown from discovered launch hooks and stable identifiers.",
        draft_planner_context,
    ),
}


def print_help() -> None:
    print("usage: ios-ui-testability <command> [options]")
    print("")
    print("CLI helpers for the iOS UI Testability Contract skill.")
    print("")
    print("commands:")
    for command, (description, _) in COMMANDS.items():
        print(f"  {command:<13} {description}")
    print("")
    print("examples:")
    print("  ios-ui-testability ids /path/to/app")
    print("  ios-ui-testability launch /path/to/app --json")
    print("  ios-ui-testability triage --summary summary.md --ui-tree ui-tree.json --scenario scenario.json")
    print("  ios-ui-testability draft-context /path/to/app --output .github/ai-ui/planner-context.md")
    print("")
    print("Run `ios-ui-testability <command> --help` for command-specific options.")


def run_command(command: str, module: ModuleType, argv: Sequence[str]) -> int:
    original_argv = sys.argv
    try:
        sys.argv = [f"ios-ui-testability {command}", *argv]
        return int(module.main())
    finally:
        sys.argv = original_argv


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"-h", "--help"}:
        print_help()
        return 0

    if args[0] == "--version":
        print(__version__)
        return 0

    command = args[0]
    try:
        _, module = COMMANDS[command]
    except KeyError:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Run `ios-ui-testability --help` for available commands.", file=sys.stderr)
        return 2

    return run_command(command, module, args[1:])
