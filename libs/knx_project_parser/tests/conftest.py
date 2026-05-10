from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
rendered = str(SRC)
if rendered not in sys.path:
    sys.path.insert(0, rendered)
