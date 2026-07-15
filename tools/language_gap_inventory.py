from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Gap:
    priority: str
    name: str
    unlocks: tuple[str, ...]


GAPS = (
    Gap("P0", "strings", ("Assembly renderer", "diagnostic formatter")),
    Gap("P0", "arrays or vectors", ("IR normalizer", "small static checker")),
    Gap("P0", "reusable helpers", ("all early components",)),
    Gap("P0", "program tests", ("Python-vs-S3 comparison",)),
    Gap("P1", "records or structs", ("AST", "IR", "Assembly", "diagnostics")),
    Gap("P1", "enums or sum types", ("token kinds", "opcodes", "diagnostics")),
    Gap("P1", "pattern matching", ("lowering", "verifier", "parser subsets")),
    Gap("P1", "modules and imports", ("multi-file components",)),
    Gap("P1", "structural comparison", ("comparison harnesses",)),
    Gap("P1", "deterministic serialization", ("golden comparisons",)),
    Gap("P1", "structured diagnostics", ("diagnostic compatibility",)),
    Gap("P1", "maps or lookup tables", ("semantic analysis", "verifiers")),
    Gap("P2", "controlled file I/O", ("future S3 tooling",)),
    Gap("P2", "host tool boundary", ("broader tool integration",)),
)


def main() -> int:
    print("S3 language gap inventory")
    for priority in ("P0", "P1", "P2"):
        print()
        print(f"{priority}:")
        for gap in GAPS:
            if gap.priority != priority:
                continue
            print(f"  {gap.name}")
            print(f"    unlocks: {', '.join(gap.unlocks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
