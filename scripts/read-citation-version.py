#!/usr/bin/env python3
"""Print the release version declared in CITATION.cff."""

from __future__ import annotations

import re
import sys
from pathlib import Path


VERSION_PATTERN = re.compile(
    r"^version:\s*[\"']?([^\"'\s]+)[\"']?\s*(?:#.*)?$",
    re.MULTILINE,
)


def main() -> int:
    citation_path = Path(__file__).resolve().parents[1] / "CITATION.cff"
    match = VERSION_PATTERN.search(citation_path.read_text(encoding="utf-8"))
    if match is None:
        print("CITATION.cff is missing a valid version field", file=sys.stderr)
        return 1
    print(match.group(1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
