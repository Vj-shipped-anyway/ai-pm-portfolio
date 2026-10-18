"""Puts ../src on the path so the tests import the package without an install."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
