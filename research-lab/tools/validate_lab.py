#!/usr/bin/env python3
"""Validate durable S3 research-lab structure."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ZK_ID = re.compile(r"S3-ZK-\d{4}")
FILE_REF = re.compile(r"^File:\s*`([^`]+)`\s*$", re.MULTILINE)


def find_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "research-lab" / "STATE.json").is_file():
            return candidate
    raise RuntimeError("could not locate research-lab/STATE.json")


def main() -> int:
    root = find_root(Path.cwd().resolve())
    lab = root / "research-lab"
    errors: list[str] = []

    try:
        json.loads((lab / "STATE.json").read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"STATE.json is not valid JSON: {exc}")

    index_text = (lab / "zettelkasten" / "INDEX.md").read_text(encoding="utf-8")
    indexed_ids = set(ZK_ID.findall(index_text))
    notes_dir = lab / "zettelkasten" / "notes"
    note_files: dict[str, list[Path]] = {}

    for path in sorted(notes_dir.glob("S3-ZK-*.md")):
        match = ZK_ID.search(path.name)
        if match:
            note_files.setdefault(match.group(0), []).append(path)

    for zk_id in sorted(indexed_ids):
        matches = note_files.get(zk_id, [])
        if not matches:
            errors.append(f"index references {zk_id}, but no note file exists")
        elif len(matches) > 1:
            errors.append(f"{zk_id} has duplicate note files")

    for zk_id, paths in sorted(note_files.items()):
        for path in paths:
            lines = path.read_text(encoding="utf-8").splitlines()
            first = next((line.strip() for line in lines if line.strip()), "")
            if zk_id not in first:
                errors.append(f"{path.relative_to(root)} does not identify {zk_id} in its first heading")

    experiment_text = (lab / "experiments" / "README.md").read_text(encoding="utf-8")
    for relative_name in FILE_REF.findall(experiment_text):
        path = lab / "experiments" / relative_name
        if not path.is_file():
            errors.append(f"experiment registry references missing file: {path.relative_to(root)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"LAB_CONSISTENCY=FAIL errors={len(errors)}")
        return 1

    print("LAB_CONSISTENCY=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
