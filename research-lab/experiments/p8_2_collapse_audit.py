"""Small, deterministic P8.2 triage for preserved realization possibilities.

This is deliberately a structural audit of the exact production checkout. It
does not infer dynamic frequency, semantic safety, or a production target from
golden-file adjacency alone.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path


PATTERNS = (
    ("TCMP", "TBR3"),
    ("TREL", "TBR3"),
    ("TLOAD", "TSTORE"),
    ("TSTORE", "TLOAD"),
    ("TADDR", "TREFLOAD"),
    ("TREFLOAD", "TREFSTORE"),
    ("TMOV", "TMOV"),
)


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def opcode_stream(path: Path) -> list[str]:
    opcodes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        content = line.split(";", 1)[0].strip()
        if not content or content.startswith(".") or content.startswith("#"):
            continue
        opcode = content.split(None, 1)[0]
        if opcode.startswith("T"):
            opcodes.append(opcode)
    return opcodes


def audit(target: Path, expected_sha: str) -> dict[str, object]:
    actual_sha = git_head(target)
    files = sorted((target / "tests" / "golden").rglob("*.assembly.txt"))
    opcode_counts: Counter[str] = Counter()
    pattern_counts: Counter[str] = Counter()
    instruction_count = 0
    for assembly_file in files:
        stream = opcode_stream(assembly_file)
        instruction_count += len(stream)
        opcode_counts.update(stream)
        for left, right in PATTERNS:
            pattern = f"{left}->{right}"
            pattern_counts[pattern] += sum(
                1
                for before, after in zip(stream, stream[1:])
                if before == left and after == right
            )

    return {
        "target_main_sha": expected_sha,
        "target_head": actual_sha,
        "target_head_match": actual_sha == expected_sha,
        "corpus": "tests/golden/**/*.assembly.txt",
        "corpus_kind": "small_static_triage_only",
        "assembly_files": len(files),
        "instructions": instruction_count,
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "adjacent_pattern_counts": dict(sorted(pattern_counts.items())),
        "dynamic_frequency": "UNAVAILABLE",
        "semantic_safety": "NOT_INFERRED_FROM_ADJACENCY",
        "promotion": "NO_VALID_TARGET_YET",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.production_checkout, args.production_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"TARGET_HEAD={result['target_head']}")
    print(f"TARGET_HEAD_MATCH={'YES' if result['target_head_match'] else 'NO'}")
    print(f"ASSEMBLY_FILES={result['assembly_files']}")
    print(f"INSTRUCTIONS={result['instructions']}")
    print("PROMOTION=NO_VALID_TARGET_YET")
    return 0 if result["target_head_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
