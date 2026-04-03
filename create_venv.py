#!/usr/bin/env python3
"""
Create a Python virtual environment at ./.venv in this project directory.

Run from the project root (no PowerShell; plain cmd or any shell):
  python create_venv.py

Activate on Windows cmd.exe after creation:
  .venv\\Scripts\\activate.bat
"""

from __future__ import annotations

import sys
import venv
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    target = root / ".venv"
    if target.exists():
        print("Already exists (remove .venv first to recreate):", target, file=sys.stderr)
        return 1
    builder = venv.EnvBuilder(with_pip=True, upgrade_deps=False, symlinks=False)
    builder.create(str(target))
    print("Created virtual environment:", target)
    print("Activate (cmd.exe): .venv\\Scripts\\activate.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
