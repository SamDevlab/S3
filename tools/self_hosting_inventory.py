from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class InventoryItem:
    path: str
    category: str
    difficulty: str
    phase: str
    requires: tuple[str, ...]


INVENTORY = (
    InventoryItem(
        "bootstrap/s3/lexer.py",
        "lexer",
        "high",
        "later",
        ("strings", "diagnostics", "source spans"),
    ),
    InventoryItem(
        "bootstrap/s3/parser.py",
        "parser",
        "very high",
        "much later",
        ("tokens", "recursive data", "diagnostics", "pattern matching"),
    ),
    InventoryItem(
        "bootstrap/s3/ast.py",
        "ast",
        "medium",
        "middle",
        ("records", "arrays", "sum types"),
    ),
    InventoryItem(
        "bootstrap/s3/diagnostics.py",
        "diagnostics",
        "high",
        "middle",
        ("records", "enums", "strings", "serialization"),
    ),
    InventoryItem(
        "bootstrap/s3/ir.py",
        "ir",
        "medium",
        "middle",
        ("records", "arrays", "enums", "deterministic serialization"),
    ),
    InventoryItem(
        "bootstrap/s3/optimizer.py",
        "optimizer",
        "very high",
        "much later",
        ("ir", "dataflow", "verification", "tests"),
    ),
    InventoryItem(
        "bootstrap/s3/assembly.py",
        "assembly",
        "medium",
        "earlier",
        ("records", "arrays", "strings", "rendering"),
    ),
    InventoryItem(
        "bootstrap/s3/codegen.py",
        "codegen",
        "high",
        "later",
        ("ir", "assembly", "diagnostics"),
    ),
    InventoryItem(
        "bootstrap/s3/emulator.py",
        "emulator",
        "very high",
        "much later",
        ("runtime state", "arrays", "structured errors"),
    ),
    InventoryItem(
        "bootstrap/s3/backends/x86_64",
        "native backend",
        "very high",
        "last",
        ("strings", "layout data", "target contracts"),
    ),
    InventoryItem(
        "bootstrap/s3/pipeline.py",
        "pipeline",
        "high",
        "later",
        ("all compiler stages", "configuration records"),
    ),
    InventoryItem(
        "bootstrap/s3/cli.py",
        "cli",
        "high",
        "later",
        ("file I/O", "arguments", "diagnostics", "host integration"),
    ),
    InventoryItem(
        "tools/golden_inspect.py",
        "golden tools",
        "low",
        "earlier",
        ("deterministic output", "file I/O", "diffing"),
    ),
)


def main() -> int:
    print("S3 self-hosting inventory")
    print()
    for item in INVENTORY:
        path = REPO_ROOT / item.path
        marker = "" if path.exists() else " (missing)"
        print(f"{item.path}{marker}")
        print(f"  category: {item.category}")
        print(f"  migration difficulty: {item.difficulty}")
        print(f"  suggested phase: {item.phase}")
        print(f"  requires: {', '.join(item.requires)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
