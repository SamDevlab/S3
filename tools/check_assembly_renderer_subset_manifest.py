from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.generate_assembly_renderer_subset_manifest import (  # noqa: E402
    MANIFEST_PATH,
    build_manifest,
    render_manifest,
)


STALE_MESSAGE = (
    "assembly renderer subset manifest is stale; run:\n"
    "python tools/generate_assembly_renderer_subset_manifest.py"
)


def _is_current() -> bool:
    expected_manifest = build_manifest()
    expected_text = render_manifest(expected_manifest)

    try:
        actual_text = MANIFEST_PATH.read_text(encoding="utf-8")
        actual_manifest = json.loads(actual_text)
    except (FileNotFoundError, json.JSONDecodeError):
        return False

    return actual_manifest == expected_manifest and actual_text == expected_text


def main() -> int:
    if _is_current():
        print("assembly renderer subset manifest: ok")
        return 0

    print(STALE_MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
