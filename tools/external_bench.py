"""Repository entry point for S3 external benchmarks."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
