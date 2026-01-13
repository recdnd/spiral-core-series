#!/usr/bin/env python3
"""
Stable entrypoint for spiral-core-series.

- Keeps README/quickstart stable across versions.
- Default target: v0.046 prototype script.
- When shipping a new version (e.g. v0.047), only update TARGET below.
"""

from __future__ import annotations

import runpy
from pathlib import Path
import sys

# Update this when a new version becomes the "latest".
TARGET = Path("versions") / "v0.046" / "spiral_core_v046_frontier-recent-k-fix.py"


def main() -> int:
    if not TARGET.exists():
        print(f"[run.py] ERROR: target script not found: {TARGET}", file=sys.stderr)
        print("[run.py] Please check repo layout or update TARGET.", file=sys.stderr)
        return 1

    runpy.run_path(str(TARGET), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

