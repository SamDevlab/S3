from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "tests" / "golden" / "assembly_renderer_subset_manifest.json"


@dataclass(frozen=True, slots=True)
class AssemblyRendererFixture:
    example: str
    golden: str


FIXTURES = (
    AssemblyRendererFixture(
        "examples/first.s3",
        "tests/golden/inspect/first.assembly.txt",
    ),
    AssemblyRendererFixture(
        "examples/simple_call.s3",
        "tests/golden/inspect/simple_call.assembly.txt",
    ),
    AssemblyRendererFixture(
        "examples/sign.s3",
        "tests/golden/inspect/sign.assembly.txt",
    ),
)


def _scan_golden(path: Path) -> tuple[set[str], set[str], set[str]]:
    directives: set[str] = set()
    opcodes: set[str] = set()
    assembly_versions: set[str] = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        first_token = stripped.split(maxsplit=1)[0]
        if first_token.startswith("."):
            directives.add(first_token)
            if first_token == ".s3asm":
                parts = stripped.split()
                if len(parts) >= 2:
                    assembly_versions.add(parts[1])
            continue

        if first_token.startswith("T"):
            opcodes.add(first_token)

    return directives, opcodes, assembly_versions


def build_manifest() -> dict[str, object]:
    directives: set[str] = set()
    opcodes: set[str] = set()
    assembly_versions: set[str] = set()

    for fixture in FIXTURES:
        fixture_directives, fixture_opcodes, fixture_versions = _scan_golden(
            REPO_ROOT / fixture.golden
        )
        directives.update(fixture_directives)
        opcodes.update(fixture_opcodes)
        assembly_versions.update(fixture_versions)

    if len(assembly_versions) != 1:
        raise RuntimeError("expected exactly one assembly format version")

    return {
        "assembly_format_version": next(iter(assembly_versions)),
        "directives": sorted(directives),
        "fixtures": [
            {
                "example": fixture.example,
                "golden": fixture.golden,
            }
            for fixture in FIXTURES
        ],
        "manifest_format_version": "1.0.0",
        "opcodes": sorted(opcodes),
        "source": "tests/golden/inspect/*.assembly.txt",
    }


def render_manifest(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def write_manifest() -> None:
    MANIFEST_PATH.write_text(
        render_manifest(build_manifest()),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    write_manifest()
    print("assembly renderer subset manifest generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
