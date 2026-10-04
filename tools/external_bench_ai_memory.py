"""Repository entry point for the optional AI-MEMORY external benchmark adapter."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from providers.ai_memory.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
