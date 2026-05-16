#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from ios_ui_testability_contract.inventory_launch_contract import *  # noqa: E402,F401,F403
from ios_ui_testability_contract.inventory_launch_contract import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
