"""Repository entry point for the s3bench 1.0 harness."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.s3bench.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
