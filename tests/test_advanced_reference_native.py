from __future__ import annotations

import platform
from pathlib import Path
import re

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.pipeline import compile_source


pytestmark = [pytest.mark.s3_contract, pytest.mark.s3_differential]


def _parse_native_result(stdout: str) -> int:
    match = re.fullmatch(r"program returned: (-?\d+)", stdout.strip())
    if match is None:
        raise ValueError(f"unexpected native result output: {stdout!r}")
    return int(match.group(1))


def _array_reference_source() -> str:
    return """fn main() -> tryte:
    mut data: tryte[3] = [10, 20, 30]
    p: &mut tryte = &mut data[1]
    *p = 90
    return data[1]
"""


def test_array_reference_lowering_uses_index_and_canonical_layout() -> None:
    assembly = compile_source(_array_reference_source(), "O0").assembly
    text = X8664Backend(register_allocation=False).generate(assembly)
    assert "cmp rax, 3" in text
    assert "rax*2" in text
    assert "array reference index" in text


def test_reborrow_lowering_preserves_address_word() -> None:
    source = """fn main() -> tryte:
    mut value: tryte = 1
    r: &mut tryte = &mut value
    s: &mut tryte = &mut *r
    *s = 7
    return *r
"""
    instructions = compile_source(source, "O1").assembly.functions[0].instructions
    assert sum(item.opcode.value == "TADDR" for item in instructions) == 1
    assert any(item.opcode.value == "TMOV" for item in instructions)


@pytest.fixture(scope="module")
def native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("advanced native reference matrix requires Linux x86-64")
    return NativeToolchain.detect()


@pytest.mark.parametrize("optimization", ["O0", "O1"])
@pytest.mark.parametrize("register_allocation", [False, True])
def test_native_array_reference_matrix(
    optimization: str,
    register_allocation: bool,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(_array_reference_source(), optimization).assembly
    executable = native_toolchain.build(
        X8664Backend(register_allocation=register_allocation).generate(program),
        tmp_path / f"array-{optimization}-{register_allocation}",
    )
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert _parse_native_result(completed.stdout) == 90
