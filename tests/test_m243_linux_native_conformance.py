from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_source


pytestmark = [pytest.mark.s3_native, pytest.mark.s3_differential]


ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("M2.43 conformance requires Linux x86-64")
    return NativeToolchain.detect()


def _reference_source() -> str:
    return """fn update(values: &mut tryte[3]) -> tryte:
    values[1] = values[0] + values[2]
    return values[1]
fn main() -> tryte:
    mut values: tryte[3] = [10, 20, 30]
    return update(&mut values)
"""


def _stack_and_call_source() -> str:
    return """fn select(
    a: tryte, b: tryte, c: tryte, d: tryte,
    e: tryte, f: tryte, g: tryte, h: tryte
) -> tryte:
    return h
fn descend(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return 0
        0:
            return 0
        1:
            return descend(value - 1)
fn main() -> tryte:
    return select(0, 1, 2, 3, 4, 5, descend(3), 7)
"""


def _tmov_source() -> str:
    return """fn main() -> tryte:
    mut value: tryte = 1
    r: &mut tryte = &mut value
    s: &mut tryte = &mut *r
    *s = 7
    return *r
"""


@pytest.mark.parametrize(
    ("label", "source", "expected"),
    (
        ("first", (ROOT / "examples" / "first.s3").read_text(encoding="utf-8"), 6),
        ("abi", (ROOT / "examples" / "native_abi.s3").read_text(encoding="utf-8"), 7),
        ("recursive", (ROOT / "examples" / "recursive_sum.s3").read_text(encoding="utf-8"), 10),
        ("reference-memory", _reference_source(), 40),
        ("stack-call", _stack_and_call_source(), 7),
        ("tmov-reference", _tmov_source(), 7),
    ),
)
@pytest.mark.parametrize("optimization", ["O0", "O1"])
@pytest.mark.parametrize("register_allocation", [False, True])
def test_linux_native_o0_o1_conformance_matrix(
    label: str,
    source: str,
    expected: int,
    optimization: str,
    register_allocation: bool,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(source, optimization).assembly
    assert Emulator().execute(program) == expected
    assembly = X8664Backend(
        register_allocation=register_allocation,
        experimental_mode="off",
    ).generate(program)
    executable = native_toolchain.build(
        assembly,
        tmp_path / f"{label}-{optimization}-{register_allocation}",
    )
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n"


def test_native_conformance_keeps_tmov_and_compact_ea_off(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(_tmov_source(), "O1").assembly
    assert any(item.opcode.value == "TMOV" for item in program.functions[0].instructions)
    assembly = X8664Backend(
        register_allocation=True,
        experimental_mode="off",
    ).generate(program)
    executable = native_toolchain.build(assembly, tmp_path / "tmov-compact-ea-off")
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 7\n"
    assert completed.stderr == ""
