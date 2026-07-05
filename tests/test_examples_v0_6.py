import sys
from pathlib import Path

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source


EXAMPLES_DIR = Path("examples")

EXPECTED_RESULTS = {
    "first.s3": 6,
    "mutable_switch.s3": 10,
    "mutable_value.s3": 15,
    "native_abi.s3": 7,
    "nested_calls.s3": 12,
    "recursive_memory.s3": 6,
    "recursive_sum.s3": 10,
    "sign.s3": -1,
    "simple_call.s3": 15,
    "static_array.s3": 13,
    "trit_array.s3": 1,
}

def _discover_examples() -> list[Path]:
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*.s3"))


@pytest.mark.parametrize("example_path", _discover_examples(), ids=lambda p: p.name)
def test_official_examples_compile_and_run_with_default(
    example_path: Path,
) -> None:
    source = example_path.read_text(encoding="utf-8")

    compilation = compile_source(source)
    assert compilation.ast
    assert compilation.ir
    assert compilation.assembly

    result = run_source(source)

    assert example_path.name in EXPECTED_RESULTS, (
        f"Missing expected result for {example_path.name}"
    )
    assert result == EXPECTED_RESULTS[example_path.name]


@pytest.mark.parametrize("example_path", _discover_examples(), ids=lambda p: p.name)
def test_official_examples_do_not_contain_obsolete_syntax(example_path: Path) -> None:
    source = example_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        text = line.split("#")[0]  # strip comments
        assert "{" not in text, f"Found obsolete '{{' at {example_path.name}:{i}"
        assert "}" not in text, f"Found obsolete '}}' at {example_path.name}:{i}"
        assert ";" not in text, f"Found obsolete ';' at {example_path.name}:{i}"
        assert "//" not in text, f"Found obsolete '//' at {example_path.name}:{i}"
        assert "switch" not in text.split(), f"Found obsolete 'switch' keyword at {example_path.name}:{i}"
        
        # historical declarations
        tokens = text.split()
        if "tryte" in tokens and ":" not in text and "->" not in text:
            # check if it looks like "tryte name = ..." or "mut tryte name = ..."
            if not text.strip().startswith("tryte["):
                pass # more complex to rule out all but simple heuristic
        
        # check specifically for historical patterns
        import re
        assert not re.search(r'\btryte\s+[a-zA-Z_]', text), f"Historical tryte declaration at {example_path.name}:{i}"
        assert not re.search(r'\btrit\s+[a-zA-Z_]', text), f"Historical trit declaration at {example_path.name}:{i}"

@pytest.mark.parametrize("example_path", _discover_examples(), ids=lambda p: p.name)
def test_official_examples_via_public_cli(example_path: Path) -> None:
    import subprocess
    
    commands = ["ast", "ir", "asm", "run"]
    
    for cmd in commands:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bootstrap.s3.cli",
                cmd,
                str(example_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI command {cmd} failed for {example_path.name}:\n"
            f"{result.stderr}"
        )


def test_default_matches_explicit_v0_6_for_official_example() -> None:
    source = (EXAMPLES_DIR / "first.s3").read_text(encoding="utf-8")
    default = compile_source(source)
    explicit = compile_source(source, mode=SyntaxMode.V0_6)

    assert default.ast == explicit.ast
    assert default.ir == explicit.ir
    assert default.assembly == explicit.assembly
    assert run_source(source) == run_source(source, mode=SyntaxMode.V0_6)

