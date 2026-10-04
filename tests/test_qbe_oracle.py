from __future__ import annotations

from dataclasses import replace
import platform
import shutil
import subprocess

import pytest

from bootstrap.s3.ir import IRModule, IROpcode
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.verifier import IRVerificationError
from tools.qbe_oracle import QBETranslationError, translate_verified_ir


SCALAR_PROGRAMS = {
    "constant": """\
fn main() -> i64:
    return 42
""",
    "compare_branch": """\
fn classify(value: i64) -> i64:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
fn main() -> i64:
    return classify(2)
""",
    "nested_call": """\
fn identity(value: i64) -> i64:
    return value
fn forward(value: i64) -> i64:
    return identity(value)
fn main() -> i64:
    return forward(7)
""",
    "f64_identity": """\
fn identity(value: f64) -> f64:
    return value
fn main() -> i64:
    return 0
""",
    "f64_compare": """\
fn classify(value: f64) -> i64:
    match value <=> 0.0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
fn main() -> i64:
    return classify(1.5)
""",
}


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("name", tuple(SCALAR_PROGRAMS))
def test_qbe_oracle_emits_deterministic_verified_scalar_il(name: str, optimization) -> None:
    program = compile_source(SCALAR_PROGRAMS[name], optimization=optimization).ir
    assert program is not None

    first = translate_verified_ir(program)
    second = translate_verified_ir(program)

    assert first == second
    assert "function " in first
    assert "QBE oracle; generated from verified S3 IR" in first
    assert "export function l $main()" in first


def test_qbe_oracle_preserves_compare_branch_and_scalar_call_shapes() -> None:
    program = compile_source(SCALAR_PROGRAMS["compare_branch"]).ir
    assert program is not None
    text = translate_verified_ir(program)

    assert "csltl" in text
    assert "csgtl" in text
    assert "phi @" in text
    assert "ceql" in text
    assert "jnz" in text
    assert "call $classify(l" in text


def test_qbe_oracle_emits_f64_comparisons_without_integer_coercion() -> None:
    program = compile_source(SCALAR_PROGRAMS["f64_compare"]).ir
    assert program is not None
    text = translate_verified_ir(program)
    assert "cltd" in text
    assert "cgtd" in text
    assert "csltl" not in text


@pytest.mark.parametrize(
    "source,reason",
    [
        (
            """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    return i64_vector_len(&values)
""",
            "outside QBE oracle V1",
        ),
        (
            """\
record Pair:
    value: i64
fn read(pair: &Pair) -> i64:
    return pair.value
fn main() -> i64:
    mut pair: Pair = Pair(value=1)
    return read(&pair)
""",
            "non-scalar ABI parameter",
        ),
        (
            """\
fn main() -> i64:
    mut value: i64 = 1
    value = value + 1
    return value
""",
            "outside QBE oracle V1",
        ),
        (
            """\
fn main() -> tryte:
    return 1
""",
            "result type tryte",
        ),
        (
            """\
fn main() -> trit:
    return -1
""",
            "result type trit",
        ),
        (
            """\
fn read(value: &i64) -> i64:
    return 0
fn main() -> i64:
    mut value: i64 = 1
    return read(&value)
""",
            "non-scalar ABI parameter",
        ),
    ],
)
def test_qbe_oracle_rejects_ir_outside_the_scalar_subset(
    source: str, reason: str
) -> None:
    program = compile_source(source).ir
    assert program is not None
    with pytest.raises(QBETranslationError, match=reason):
        translate_verified_ir(program)


def test_qbe_oracle_verifies_ir_before_translation() -> None:
    program = compile_source(SCALAR_PROGRAMS["constant"]).ir
    assert program is not None
    function = program.functions[0]
    block = function.blocks[0]
    constant = next(item for item in block.instructions if item.opcode is IROpcode.CONST)
    bad_constant = replace(constant, immediate=1 << 100)
    bad_instructions = tuple(
        bad_constant if item is constant else item for item in block.instructions
    )
    bad_function = replace(
        function,
        blocks=(replace(block, instructions=bad_instructions), *function.blocks[1:]),
    )
    bad_program = IRModule((bad_function, *program.functions[1:]), program.static_strings)

    with pytest.raises(IRVerificationError):
        translate_verified_ir(bad_program)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("name", tuple(SCALAR_PROGRAMS))
def test_qbe_native_scalar_differential_when_linux_toolchain_exists(
    name, optimization, tmp_path
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_source(
        SCALAR_PROGRAMS[name], optimization=optimization
    )
    program = compilation.ir
    assert program is not None
    il_path = tmp_path / f"{name}-{optimization.value}.ssa"
    assembly_path = tmp_path / f"{name}-{optimization.value}.s"
    executable_path = tmp_path / f"{name}-{optimization.value}"
    s3_assembly_path = tmp_path / f"{name}-{optimization.value}-s3.s"
    s3_executable_path = tmp_path / f"{name}-{optimization.value}-s3"
    il_path.write_text(translate_verified_ir(program), encoding="utf-8")
    subprocess.run([qbe, "-o", str(assembly_path), str(il_path)], check=True, capture_output=True)
    subprocess.run([cc, "-no-pie", str(assembly_path), "-o", str(executable_path)], check=True, capture_output=True)
    native = subprocess.run([str(executable_path)], check=False, capture_output=True)
    s3_assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(s3_assembly_path), "-o", str(s3_executable_path)],
        check=True,
        capture_output=True,
    )
    s3_native = subprocess.run(
        [str(s3_executable_path)], check=False, capture_output=True, text=True
    )

    result = execute_ir(program)
    assert isinstance(result, int)
    assert execute_assembly(compilation.assembly) == result
    assert native.returncode == (result & 0xFF)
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert f"program returned: {result}" in s3_native.stdout
