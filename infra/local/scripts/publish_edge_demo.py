from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_SRC = REPO_ROOT / "libs" / "idp_demo_stack" / "src"


def main() -> int:
    if str(LIB_SRC) not in sys.path:
        sys.path.insert(0, str(LIB_SRC))

    from idp_demo_stack.cli import main as package_main

    return package_main()


if __name__ == "__main__":
    raise SystemExit(main())
