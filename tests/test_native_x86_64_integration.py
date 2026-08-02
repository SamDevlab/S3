from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyProgram, parse_assembly
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.ternary import TernaryWidth, tritwise_max, tritwise_min


ROOT = Path(__file__).parents[1]
NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def _program(source_or_program: str | AssemblyProgram) -> AssemblyProgram:
    if isinstance(source_or_program, AssemblyProgram):
        return source_or_program
    return compile_source(source_or_program).assembly


def _run_native(
    program: AssemblyProgram,
    toolchain: NativeToolchain,
    output: Path,
) -> subprocess.CompletedProcess[str]:
    assembly = generate_native_assembly(program)
    executable = toolchain.build(assembly, output)
    return toolchain.run(executable)


def _assert_differential(
    source: str,
    expected: int,
    toolchain: NativeToolchain,
    output: Path,
    optimization: str = "O0",
    *,
    mode: SyntaxMode | None = None,
) -> None:
    if mode is not None:
        program = compile_source(source, optimization, mode=mode).assembly
    else:
        program = compile_source(source, optimization).assembly
    assert Emulator().execute(program) == expected
    completed = _run_native(program, toolchain, output)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n"


def _assert_o0_o1_native_equivalence(
    source: str,
    expected: int,
    toolchain: NativeToolchain,
    output: Path,
) -> None:
    for level in ("O0", "O1"):
        _assert_differential(
            source,
            expected,
            toolchain,
            output / level.lower(),
            optimization=level,
            mode=SyntaxMode.V0_6,
        )


def _assert_o0_o1_native_sources_equivalence(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    expected: int,
    toolchain: NativeToolchain,
    output: Path,
    *,
    entry_module: str = "main",
) -> None:
    for level in ("O0", "O1"):
        program = compile_sources(
            sources,
            level,
            entry_module=entry_module,
            mode=SyntaxMode.V0_6,
        ).assembly
        assert Emulator().execute(program) == expected
        completed = _run_native(program, toolchain, output / level.lower())
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == f"program returned: {expected}\n"


def _assert_o0_o1_emulator_equivalence(source: str, expected: int) -> None:
    for level in ("O0", "O1"):
        program = compile_source(source, level, mode=SyntaxMode.V0_6).assembly
        assert Emulator().execute(program) == expected


def test_o0_o1_native_fixed_array_boundaries(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    source = (
        "fn rotate(values: tryte[8]) -> tryte[8]:\n"
        "    output: tryte[8] = values\n"
        "    return output\n"
        "fn main() -> tryte:\n"
        "    values: tryte[8] = [1, 2, 3, 4, 5, 6, 7, 8]\n"
        "    result: tryte[8] = rotate(values)\n"
        "    return result[0] + result[7]\n"
    )

    _assert_o0_o1_native_equivalence(
        source,
        9,
        native_toolchain,
        tmp_path / "fixed-array-boundaries",
    )


def _assert_o0_o1_emulator_sources_equivalence(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    expected: int,
    *,
    entry_module: str = "main",
) -> None:
    for level in ("O0", "O1"):
        program = compile_sources(
            sources,
            level,
            entry_module=entry_module,
            mode=SyntaxMode.V0_6,
        ).assembly
        assert Emulator().execute(program) == expected


def _assert_o0_o1_semantic_error(
    source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    for level in ("O0", "O1"):
        with pytest.raises(SemanticError) as captured:
            compile_source(source, level, mode=SyntaxMode.V0_6)

        diagnostic = diagnostic_from_exception(captured.value)
        assert diagnostic.phase is DiagnosticPhase.SEMANTIC
        assert diagnostic.category is DiagnosticCategory.SEMANTIC
        assert diagnostic.code is code
        assert message in diagnostic.message


def _assert_o0_o1_semantic_sources_error(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    message: str,
    code: DiagnosticCode,
    *,
    entry_module: str = "main",
) -> None:
    for level in ("O0", "O1"):
        with pytest.raises(SemanticError) as captured:
            compile_sources(
                sources,
                level,
                entry_module=entry_module,
                mode=SyntaxMode.V0_6,
            )

        diagnostic = diagnostic_from_exception(captured.value)
        assert diagnostic.phase is DiagnosticPhase.SEMANTIC
        assert diagnostic.category is DiagnosticCategory.SEMANTIC
        assert diagnostic.code is code
        assert message in diagnostic.message


def _assert_o0_o1_native_error_category(
    source: str,
    diagnostic_category: str,
    native_fragment: str,
    toolchain: NativeToolchain,
    output: Path,
    *,
    max_frames: int = 1024,
    max_instructions: int = 100_000,
) -> None:
    for level in ("O0", "O1"):
        program = compile_source(source, level, mode=SyntaxMode.V0_6).assembly
        with pytest.raises(EmulatorError) as captured:
            Emulator(
                max_frames=max_frames,
                max_instructions=max_instructions,
            ).execute(program)
        diagnostic = diagnostic_from_exception(captured.value)
        assert diagnostic.category.value == diagnostic_category

        native = generate_native_assembly(
            program,
            max_frames=max_frames,
            max_instructions=max_instructions,
        )
        executable = toolchain.build(native, output / level.lower())
        completed = toolchain.run(executable)
        assert completed.returncode != 0
        assert completed.returncode not in {-11, 139}
        assert completed.stdout == ""
        assert native_fragment in completed.stderr.lower()


@pytest.mark.parametrize(
    ("filename", "expected"),
    (
        ("first.s3", 6),
        ("simple_call.s3", 15),
        ("nested_calls.s3", 12),
        ("sign.s3", -1),
        ("recursive_sum.s3", 10),
        ("mutable_value.s3", 15),
        ("mutable_switch.s3", 10),
        ("static_array.s3", 13),
        ("trit_array.s3", 1),
        ("recursive_memory.s3", 6),
        ("native_abi.s3", 7),
    ),
)
def test_all_examples_match_emulator(
    filename: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    for level in ("O0", "O1"):
        _assert_differential(
            source,
            expected,
            native_toolchain,
            tmp_path / f"{filename}-{level}",
            level,
        )


@pytest.mark.parametrize(
    "order",
    (
        ("entry", "before", "after"),
        ("before", "entry", "after"),
        ("before", "after", "entry"),
    ),
)
def test_native_execution_starts_at_entry_regardless_of_block_order(
    order: tuple[str, ...],
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    blocks = {
        "before": ".label before\n    TCONST r0, 99\n    TRET r0\n",
        "entry": ".label entry\n    TCONST r0, 6\n    TRET r0\n",
        "after": ".label after\n    TCONST r0, 77\n    TRET r0\n",
    }
    program = parse_assembly(
        ".function main -> tryte\n"
        "    .register r0, tryte\n"
        + "".join(blocks[label] for label in order)
        + ".end\n"
    )
    assert Emulator().execute(program) == 6
    completed = _run_native(
        program,
        native_toolchain,
        tmp_path / f"entry-{'-'.join(order)}",
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == "program returned: 6\n"


RECURSIVE_DEPTH_SOURCE = """\
fn descend(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return 0
        0:
            return 0
        1:
            return descend(value - 1)
fn main() -> tryte:
    return descend(3)
"""


@pytest.mark.parametrize("max_frames", (5, 8))
def test_native_recursion_within_frame_limit(
    max_frames: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(RECURSIVE_DEPTH_SOURCE, mode=SyntaxMode.V0_6).assembly
    assert Emulator(max_frames=max_frames).execute(program) == 0
    executable = native_toolchain.build(
        generate_native_assembly(program, max_frames=max_frames),
        tmp_path / f"frames-{max_frames}",
    )
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 0\n"
    assert completed.stderr == ""


def test_native_recursion_above_frame_limit_is_controlled(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(RECURSIVE_DEPTH_SOURCE, mode=SyntaxMode.V0_6).assembly
    with pytest.raises(EmulatorError, match="frame limit 4 exceeded"):
        Emulator(max_frames=4).execute(program)
    executable = native_toolchain.build(
        generate_native_assembly(program, max_frames=4),
        tmp_path / "frames-overflow",
    )
    completed = native_toolchain.run(executable)
    assert completed.returncode != 0
    assert completed.returncode not in {-11, 139}
    assert completed.stdout == ""
    assert "frame limit" in completed.stderr.lower()
    assert "function 'descend'" in completed.stderr
    assert "block entry, ENTER" in completed.stderr
    assert "depth 5 exceeds limit 4" in completed.stderr


@pytest.mark.parametrize("value", (-364, -1, 0, 1, 364))
def test_constant_boundaries(
    value: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        f"fn main() -> tryte {{ return {value}; }}",
        value,
        native_toolchain,
        tmp_path / f"constant-{value}",
        mode=SyntaxMode.V0_5,
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    (
        ("10 + 4", 14),
        ("-10", -10),
        ("10 - 4", 6),
        ("-10 <=> 4", -1),
        ("4 <=> 4", 0),
        ("10 <=> 4", 1),
    ),
)
def test_scalar_arithmetic_and_comparison(
    expression: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    return_type = "trit" if "<=>" in expression else "tryte"
    _assert_differential(
        f"fn main() -> {return_type} {{ return {expression}; }}",
        expected,
        native_toolchain,
        tmp_path / f"scalar-{expression.replace(' ', '_').replace('<=>', 'cmp')}",
        mode=SyntaxMode.V0_5,
    )


@pytest.mark.parametrize(
    ("argument", "expected"),
    ((-7, -1), (0, 0), (7, 1)),
)
def test_each_ternary_branch(
    argument: int,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        f"""\
fn sign(value: tryte) -> trit {{
    switch (value <=> 0) {{
        -1: {{ return -1; }}
        0: {{ return 0; }}
        1: {{ return 1; }}
    }}
}}
fn main() -> trit {{ return sign({argument}); }}
""",
        expected,
        native_toolchain,
        tmp_path / f"branch-{argument}",
        mode=SyntaxMode.V0_5,
    )


def test_native_enum_payload_scalar_and_match_binding_o0_o1(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        "enum Result:\n"
        "    Empty\n"
        "    Ok(value: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "fn main() -> tryte:\n"
        "    return inspect(Result.Ok(value=7))\n",
        7,
        native_toolchain,
        tmp_path / "enum-payload-scalar",
    )


def test_native_structured_result_error_record_o0_o1(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        "record Error:\n"
        "    code: tryte\n"
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(error: Error)\n"
        "fn handle(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(error):\n"
        "            return error.code\n"
        "fn main() -> tryte:\n"
        "    result: Result = Result.Err(error=Error(code=5))\n"
        "    return handle(result)\n",
        5,
        native_toolchain,
        tmp_path / "structured-result-error",
    )


@pytest.mark.parametrize(
    ("left", "right"),
    (
        (-364, -364),
        (-364, 364),
        (-243, 242),
        (-100, 100),
        (-10, 4),
        (-2, -1),
        (-1, 0),
        (0, 1),
        (1, 2),
        (40, 121),
        (363, 364),
        (364, -364),
    ),
)
@pytest.mark.parametrize(
    ("operator", "model"),
    (("&", tritwise_min), ("|", tritwise_max)),
)
def test_tryte_tritwise_helpers_match_reference(
    left: int,
    right: int,
    operator: str,
    model,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    expected = model(left, right, TernaryWidth.TRYTE)
    _assert_differential(
        f"fn main() -> tryte {{ return {left} {operator} {right}; }}",
        expected,
        native_toolchain,
        tmp_path / f"tritwise-{left}-{right}-{ord(operator)}",
        mode=SyntaxMode.V0_5,
    )


@pytest.mark.parametrize(
    ("left", "right", "operator", "expected"),
    (
        (-1, 1, "&", -1),
        (-1, 1, "|", 1),
        (0, 1, "&", 0),
        (-1, 0, "|", 0),
    ),
)
def test_trit_minimum_and_maximum(
    left: int,
    right: int,
    operator: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        f"""\
fn main() -> trit {{
    trit left = {left};
    trit right = {right};
    return left {operator} right;
}}
""",
        expected,
        native_toolchain,
        tmp_path / f"trit-{left}-{right}-{ord(operator)}",
        mode=SyntaxMode.V0_5,
    )


@pytest.mark.parametrize(
    ("arity", "expected"),
    ((0, 7), (1, 0), (6, 5), (7, 6), (8, 7)),
)
def test_system_v_argument_counts(
    arity: int,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    if arity == 0:
        source = """\
fn selected() -> tryte {
    return 7;
}
fn main() -> tryte {
    return selected();
}
"""
    else:
        parameters = ", ".join(f"a{i}: tryte" for i in range(arity))
        arguments = ", ".join(str(i) for i in range(arity))
        source = f"""\
fn selected({parameters}) -> tryte {{ return a{arity - 1}; }}
fn main() -> tryte {{ return selected({arguments}); }}
"""
    _assert_differential(
        source,
        expected,
        native_toolchain,
        tmp_path / f"arity-{arity}",
        mode=SyntaxMode.V0_5,
    )


def test_forward_call_matches_emulator(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        """\
fn main() -> tryte:
    return later(9)
fn later(value: tryte) -> tryte:
    return value + 1
""",
        10,
        native_toolchain,
        tmp_path / "forward-call",
        mode=SyntaxMode.V0_6,
    )


@pytest.mark.parametrize(
    ("index_expression", "expected"),
    (("0", 5), ("2", 7), ("1 + 1", 7)),
)
def test_tryte_array_first_last_and_calculated_indices(
    index_expression: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        f"""\
fn read(index: tryte) -> tryte:
    values: tryte[3] = [5, 6, 7]
    return values[index]
fn main() -> tryte:
    return read({index_expression})
""",
        expected,
        native_toolchain,
        tmp_path / f"array-{expected}-{len(index_expression)}",
        mode=SyntaxMode.V0_6,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            """\
fn twice(value: tryte) -> tryte:
    return value + value
fn main() -> tryte:
    return twice(8) - 3
""",
            13,
        ),
        (
            """\
fn choose(value: tryte) -> tryte:
    mut result: tryte = 0
    match value <=> 0:
        -1:
            result = -3
        0:
            result = 0
        1:
            result = 3
    return result
fn main() -> tryte:
    return choose(1)
""",
            3,
        ),
        (
            """\
fn read(index: tryte) -> tryte:
    mut values: tryte[3] = [2, 4, 6]
    values[1] = values[0] + values[2]
    return values[index]
fn main() -> tryte:
    return read(1)
""",
            8,
        ),
        (
            """\
fn main() -> tryte:
    mut values: tryte[3] = [0, 0, 0]
    mut i: tryte = 0
    values[i] = 5
    i = 1
    values[i] = 7
    return values[0]
""",
            5,
        ),
        (
            """\
fn main() -> tryte:
    left: tryte = -100
    right: tryte = 40
    return (left & right) | 1
""",
            tritwise_max(
                tritwise_min(-100, 40, TernaryWidth.TRYTE),
                1,
                TernaryWidth.TRYTE,
            ),
        ),
    ),
)
def test_deterministic_differential_corpus(
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    case = sum(ord(character) for character in source)
    _assert_differential(
        source,
        expected,
        native_toolchain,
        tmp_path / f"corpus-{case}",
        mode=SyntaxMode.V0_6,
    )


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    (
        (
            "trit-return",
            """\
fn main() -> trit:
    mut value: trit = -1
    return value
""",
            -1,
        ),
        (
            "source-subtraction",
            """\
fn main() -> tryte:
    mut left: tryte = 10
    mut right: tryte = 4
    return left - right
""",
            6,
        ),
        (
            "tritwise-minimum",
            """\
fn main() -> tryte:
    mut left: tryte = -100
    mut right: tryte = 40
    return left & right
""",
            -100,
        ),
        (
            "nested-call",
            """\
fn add_one(value: tryte) -> tryte:
    return value + 1
fn add_two(value: tryte) -> tryte:
    return add_one(add_one(value))
fn main() -> tryte:
    return add_two(8)
""",
            10,
        ),
        (
            "recursion",
            """\
fn sum_to(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return 0
        0:
            return 0
        1:
            return value + sum_to(value - 1)
fn main() -> tryte:
    return sum_to(4)
""",
            10,
        ),
        (
            "diamond-join",
            """\
fn choose(value: tryte) -> tryte:
    mut result: tryte = 0
    match value <=> 0:
        -1:
            result = 3
        0:
            result = 5
        else:
            result = 7
    return result
fn main() -> tryte:
    return choose(1)
""",
            7,
        ),
        (
            "while-loop",
            """\
fn main() -> tryte:
    mut i: tryte = 0
    mut total: tryte = 0
    while i < 3:
        total = total + 2
        i = i + 1
    return total
""",
            6,
        ),
        (
            "for-loop",
            """\
fn main() -> tryte:
    mut total: tryte = 0
    for i: tryte in range(0, 4):
        total = total + i
    return total
""",
            6,
        ),
        (
            "mutable-array-dynamic-index",
            """\
fn read(index: tryte) -> tryte:
    mut values: tryte[3] = [2, 4, 6]
    values[index] = values[index] + 1
    return values[index]
fn main() -> tryte:
    return read(1)
""",
            5,
        ),
        (
            "consecutive-stores",
            """\
fn main() -> tryte:
    mut value: tryte = 1
    value = 2
    value = 3
    return value
""",
            3,
        ),
        (
            "memory-in-loop",
            """\
fn main() -> tryte:
    mut i: tryte = 0
    mut values: tryte[3] = [0, 0, 0]
    while i < 3:
        values[i] = i + 1
        i = i + 1
    return values[0] + values[1] + values[2]
""",
            6,
        ),
        (
            "critical-edge-phi",
            """\
fn choose(value: tryte) -> tryte:
    mut result: tryte = 0
    match value <=> 0:
        -1:
            result = 3
        0:
            result = 5
        else:
            result = 7
    return result + 1
fn seed() -> tryte:
    return -1
fn main() -> tryte:
    return choose(seed())
""",
            4,
        ),
    ),
)
def test_o0_o1_native_differential_matrix_successes(
    name: str,
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        source,
        expected,
        native_toolchain,
        tmp_path / f"matrix-{name}",
    )


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    (
        (
            "simple-import",
            {
                "main.s3": (
                    "module main\n"
                    "from math import inc\n"
                    "fn main() -> tryte:\n"
                    "    return inc(8)\n"
                ),
                "math.s3": (
                    "module math\n"
                    "export fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            },
            9,
        ),
        (
            "transitive-alias-import",
            {
                "main.s3": (
                    "module main\n"
                    "from app.logic import compute as answer\n"
                    "fn main() -> tryte:\n"
                    "    return answer(3)\n"
                ),
                "app/logic.s3": (
                    "module app.logic\n"
                    "from math import inc\n"
                    "export fn compute(value: tryte) -> tryte:\n"
                    "    return inc(value) + inc(1)\n"
                ),
                "math.s3": (
                    "module math\n"
                    "export fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            },
            6,
        ),
    ),
)
def test_o0_o1_native_multi_module_compilation(
    name: str,
    sources: dict[str, str],
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        sources,
        expected,
        native_toolchain,
        tmp_path / f"modules-{name}",
    )


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    (
        (
            "record-parameter",
            """\
record Pair:
    left: tryte
    right: tryte
fn sum(pair: Pair) -> tryte:
    return pair.left + pair.right
fn main() -> tryte:
    return sum(Pair(left=4, right=6))
""",
            10,
        ),
        (
            "single-field-record-return",
            """\
record Box:
    value: tryte
fn make() -> Box:
    return Box(value=8)
fn main() -> tryte:
    return make().value
""",
            8,
        ),
        (
            "enum-match",
            """\
enum Opcode:
    Add
    Subtract
    Minimum
    Maximum
fn main() -> tryte:
    value: Opcode = Opcode.Maximum
    match value:
        Opcode.Add:
            return 0
        Opcode.Subtract:
            return 1
        Opcode.Minimum:
            return 2
        Opcode.Maximum:
            return 3
""",
            3,
        ),
    ),
)
def test_o0_o1_native_composite_types(
    name: str,
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        source,
        expected,
        native_toolchain,
        tmp_path / f"composite-{name}",
    )


def test_o0_o1_native_imported_module_composite_types(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from logic import classify\n"
            "fn main() -> tryte:\n"
            "    return classify(2)\n"
        ),
        "logic.s3": (
            "module logic\n"
            "enum Kind:\n"
            "    Small\n"
            "    Large\n"
            "record Classified:\n"
            "    kind: Kind\n"
            "    value: tryte\n"
            "export fn classify(value: tryte) -> tryte:\n"
            "    item: Classified = Classified(kind=Kind.Large, value=value)\n"
            "    match item.kind:\n"
            "        Kind.Small:\n"
            "            return -1\n"
            "        Kind.Large:\n"
            "            return item.value\n"
        ),
    }

    _assert_o0_o1_native_sources_equivalence(
        sources,
        2,
        native_toolchain,
        tmp_path / "composite-module",
    )


IMPORTED_NOMINAL_NATIVE_CASES = (
        (
            "single-field-record-return",
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import Point\n"
                    "from geometry import make\n"
                    "from consumer import x_of\n"
                    "fn main() -> tryte:\n"
                    "    point: Point = make()\n"
                    "    return x_of(point)\n"
                ),
                "geometry.s3": (
                    "module geometry\n"
                    "export record Point:\n"
                    "    x: tryte\n"
                    "export fn make() -> Point:\n"
                    "    return Point(x=7)\n"
                ),
                "consumer.s3": (
                    "module consumer\n"
                    "from geometry import Point\n"
                    "export fn x_of(point: Point) -> tryte:\n"
                    "    return point.x\n"
                ),
            },
            7,
        ),
        (
            "qualified-record-constructor",
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import marker\n"
                    "fn main() -> tryte:\n"
                    "    point: geometry.Point = geometry.Point(x=5)\n"
                    "    return point.x\n"
                ),
                "geometry.s3": (
                    "module geometry\n"
                    "export record Point:\n"
                    "    x: tryte\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
            5,
        ),
        (
            "enum-value-flow",
            {
                "main.s3": (
                    "module main\n"
                    "from signs import Sign\n"
                    "from signs import positive\n"
                    "from consumer import score\n"
                    "fn main() -> tryte:\n"
                    "    value: Sign = positive()\n"
                    "    return score(value)\n"
                ),
                "signs.s3": (
                    "module signs\n"
                    "export enum Sign:\n"
                    "    Negative\n"
                    "    Zero\n"
                    "    Positive\n"
                    "export fn positive() -> Sign:\n"
                    "    return Sign.Positive\n"
                ),
                "consumer.s3": (
                    "module consumer\n"
                    "from signs import Sign\n"
                    "export fn score(value: Sign) -> tryte:\n"
                    "    match value:\n"
                    "        Sign.Negative:\n"
                    "            return -1\n"
                    "        Sign.Zero:\n"
                    "            return 0\n"
                    "        Sign.Positive:\n"
                    "            return 1\n"
                ),
            },
            1,
        ),
        (
            "imported-record-fields",
            {
                "main.s3": (
                    "module main\n"
                    "from model import Flag\n"
                    "from model import Sign\n"
                    "from consumer import score\n"
                    "fn main() -> tryte:\n"
                    "    flag: Flag = Flag(active=-1, amount=8, sign=Sign.Positive)\n"
                    "    return score(flag)\n"
                ),
                "model.s3": (
                    "module model\n"
                    "export enum Sign:\n"
                    "    Negative\n"
                    "    Positive\n"
                    "export record Flag:\n"
                    "    active: trit\n"
                    "    amount: tryte\n"
                    "    sign: Sign\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
                "consumer.s3": (
                    "module consumer\n"
                    "from model import Flag\n"
                    "from model import Sign\n"
                    "export fn score(flag: Flag) -> tryte:\n"
                    "    match flag.sign:\n"
                    "        Sign.Negative:\n"
                    "            return 0\n"
                    "        Sign.Positive:\n"
                    "            return flag.amount\n"
                ),
            },
            8,
        ),
        (
            "multifield-record-source-order",
            (
                (
                    "sink.s3",
                    "module sink\n"
                    "from model import Packet\n"
                    "from model import Sign\n"
                    "export fn score(packet: Packet) -> tryte:\n"
                    "    match packet.sign:\n"
                    "        Sign.Negative:\n"
                    "            return 0\n"
                    "        Sign.Positive:\n"
                    "            return packet.zeta\n",
                ),
                (
                    "hop.s3",
                    "module hop\n"
                    "from model import Packet\n"
                    "from sink import score\n"
                    "export fn relay(packet: Packet) -> tryte:\n"
                    "    return score(packet)\n",
                ),
                (
                    "model.s3",
                    "module model\n"
                    "export enum Sign:\n"
                    "    Negative\n"
                    "    Positive\n"
                    "export record Packet:\n"
                    "    zeta: tryte\n"
                    "    flag: trit\n"
                    "    sign: Sign\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n",
                ),
                (
                    "main.s3",
                    "module main\n"
                    "from model import Packet\n"
                    "from model import Sign\n"
                    "from hop import relay\n"
                    "fn main() -> tryte:\n"
                    "    packet: Packet = Packet(zeta=11, flag=-1, sign=Sign.Positive)\n"
                    "    return relay(packet)\n",
                ),
            ),
            11,
        ),
)


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    IMPORTED_NOMINAL_NATIVE_CASES,
)
def test_imported_nominal_native_corpus_matches_emulator_o0_o1(
    name: str,
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    expected: int,
    tmp_path: Path,
) -> None:
    del name, tmp_path
    for level in ("O0", "O1"):
        program = compile_sources(
            sources,
            level,
            entry_module="main",
            mode=SyntaxMode.V0_6,
        ).assembly
        assert Emulator().execute(program) == expected


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    IMPORTED_NOMINAL_NATIVE_CASES,
)
def test_o0_o1_native_imported_nominal_types(
    name: str,
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        sources,
        expected,
        native_toolchain,
        tmp_path / f"imported-nominal-{name}",
    )


LOCAL_NESTED_NATIVE_SOURCE = """\
enum Sign:
    Negative
    Positive
record Leaf:
    third: trit
    fourth: tryte
record Middle:
    second: Leaf
    first: tryte
record Wrapper:
    middle: Middle
record Outer:
    suffix: tryte
    inner: Wrapper
    prefix: trit
    sign: Sign
fn score(value: Outer) -> tryte:
    local: Outer = value
    copy: Outer = local
    mut total: tryte = 0
    while copy.prefix:
        match copy.inner.middle.second.third:
            -1:
                match copy.sign:
                    Sign.Negative:
                        return 0
                    Sign.Positive:
                        total = copy.inner.middle.second.fourth
                        total = total + copy.inner.middle.first
                        total = total + copy.suffix
                        return total
            0:
                return 1
            else:
                return 2
    return 0
fn main() -> tryte:
    item: Outer = Outer(sign=Sign.Positive, prefix=-1, inner=Wrapper(middle=Middle(first=3, second=Leaf(fourth=7, third=-1))), suffix=2)
    return score(item)
"""


SINGLE_LEAF_NESTED_RETURN_SOURCE = """\
record Leaf:
    value: tryte
record Box:
    leaf: Leaf
fn make() -> Box:
    return Box(leaf=Leaf(value=5))
fn take(box: Box) -> tryte:
    return box.leaf.value
fn main() -> tryte:
    return take(make())
"""


STATIC_TEXT_NESTED_RECORD_SOURCE = """\
record Label:
    text: string
record Packet:
    flag: trit
    label: Label
fn pick(packet: Packet) -> string:
    return packet.label.text
fn main() -> tryte:
    packet: Packet = Packet(label=Label(text="hello"), flag=-1)
    selected: string = pick(packet)
    return len("hello")
"""


NESTED_RECORD_NATIVE_SOURCE_CASES = (
    ("local-nested-records", LOCAL_NESTED_NATIVE_SOURCE, 12),
    ("single-leaf-nested-return", SINGLE_LEAF_NESTED_RETURN_SOURCE, 5),
    ("static-text-nested-record", STATIC_TEXT_NESTED_RECORD_SOURCE, 5),
)


NESTED_RECORD_NATIVE_MODULE_SOURCES = (
    (
        "main.s3",
        "module main\n"
        "from geometry import Leaf\n"
        "from model import Inner\n"
        "from model import Outer\n"
        "from consumer import score\n"
        "fn main() -> tryte:\n"
        "    value: Outer = model.Outer(tail=4, inner=model.Inner(leaf=geometry.Leaf(value=6)), flag=-1)\n"
        "    return consumer.score(value)\n",
    ),
    (
        "model.s3",
        "module model\n"
        "from geometry import Leaf\n"
        "export record Inner:\n"
        "    leaf: Leaf\n"
        "export record Outer:\n"
        "    tail: tryte\n"
        "    inner: Inner\n"
        "    flag: trit\n"
        "export fn marker() -> tryte:\n"
        "    return 0\n",
    ),
    (
        "geometry.s3",
        "module geometry\n"
        "export record Leaf:\n"
        "    value: tryte\n"
        "export fn marker() -> tryte:\n"
        "    return 0\n",
    ),
    (
        "consumer.s3",
        "module consumer\n"
        "from model import Outer\n"
        "export fn score(value: Outer) -> tryte:\n"
        "    while value.flag:\n"
        "        return value.inner.leaf.value + value.tail\n"
        "    return 0\n",
    ),
)


NESTED_RECORD_NATIVE_MODULE_ORDER_CASES = (
    ("main-model-geometry-consumer", NESTED_RECORD_NATIVE_MODULE_SOURCES),
    (
        "consumer-main-model-geometry",
        (
            NESTED_RECORD_NATIVE_MODULE_SOURCES[3],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[0],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[1],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[2],
        ),
    ),
    (
        "model-geometry-consumer-main",
        (
            NESTED_RECORD_NATIVE_MODULE_SOURCES[1],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[2],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[3],
            NESTED_RECORD_NATIVE_MODULE_SOURCES[0],
        ),
    ),
)


STATIC_TEXT_NESTED_RECORD_MODULE_SOURCES = (
    (
        "main.s3",
        "module main\n"
        "from model import Label\n"
        "from model import Packet\n"
        "from consumer import pick\n"
        "fn main() -> tryte:\n"
        "    packet: Packet = model.Packet(label=model.Label(text=\"hello\"), flag=-1)\n"
        "    selected: string = consumer.pick(packet)\n"
        "    return len(\"hello\")\n",
    ),
    (
        "model.s3",
        "module model\n"
        "export record Label:\n"
        "    text: string\n"
        "export record Packet:\n"
        "    label: Label\n"
        "    flag: trit\n"
        "export fn marker() -> tryte:\n"
        "    return 0\n",
    ),
    (
        "consumer.s3",
        "module consumer\n"
        "from model import Packet\n"
        "export fn pick(packet: Packet) -> string:\n"
        "    return packet.label.text\n",
    ),
)


NESTED_RECORD_TEXT_NATIVE_MODULE_CASES = (
    ("static-text-record-module", STATIC_TEXT_NESTED_RECORD_MODULE_SOURCES, 5),
)


AGGREGATE_RESULT_NATIVE_SOURCE_CASES = (
    (
        "local-multileaf-return",
        """\
record Leaf:
    left: tryte
    right: tryte
record Box:
    leaf: Leaf
fn make() -> Box:
    return Box(leaf=Leaf(left=1, right=2))
fn main() -> tryte:
    box: Box = make()
    return box.leaf.left + box.leaf.right
""",
        3,
    ),
    (
        "branch-multileaf-return",
        """\
record Pair:
    left: tryte
    right: tryte
fn choose(flag: trit) -> Pair:
    while flag:
        return Pair(left=1, right=2)
    return Pair(left=3, right=4)
fn main() -> tryte:
    pair: Pair = choose(0)
    return pair.left + pair.right
""",
        7,
    ),
    (
        "indirect-multileaf-return",
        """\
record Pair:
    left: tryte
    right: tryte
record Holder:
    pair: Pair
fn make_holder() -> Holder:
    return Holder(pair=Pair(left=1, right=2))
fn main() -> tryte:
    holder: Holder = make_holder()
    return holder.pair.left + holder.pair.right
""",
        3,
    ),
    (
        "recursive-multileaf-return",
        """\
record Pair:
    left: tryte
    right: tryte
fn climb(count: tryte) -> Pair:
    match count <=> 0:
        -1:
            return Pair(left=0, right=0)
        0:
            return Pair(left=1, right=1)
        1:
            previous: Pair = climb(count - 1)
            return Pair(left=previous.left + 1, right=previous.right + 2)
fn main() -> tryte:
    pair: Pair = climb(3)
    return pair.left + pair.right
""",
        11,
    ),
)


IMPORTED_AGGREGATE_RESULT_NATIVE_SOURCES = (
    (
        "main.s3",
        "module main\n"
        "from geometry import Pair\n"
        "from geometry import make\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = make()\n"
        "    return pair.left + pair.right\n",
    ),
    (
        "geometry.s3",
        "module geometry\n"
        "export record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "export fn make() -> Pair:\n"
        "    return Pair(left=1, right=2)\n",
    ),
)


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    NESTED_RECORD_NATIVE_SOURCE_CASES,
)
def test_nested_record_native_sources_match_emulator_o0_o1(
    name: str,
    source: str,
    expected: int,
) -> None:
    del name
    _assert_o0_o1_emulator_equivalence(source, expected)


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    NESTED_RECORD_NATIVE_SOURCE_CASES,
)
def test_o0_o1_native_nested_record_sources(
    name: str,
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        source,
        expected,
        native_toolchain,
        tmp_path / f"nested-record-{name}",
    )


@pytest.mark.parametrize(
    ("name", "sources"),
    NESTED_RECORD_NATIVE_MODULE_ORDER_CASES,
)
def test_nested_record_native_modules_match_emulator_o0_o1(
    name: str,
    sources: tuple[tuple[str, str], ...],
) -> None:
    del name
    _assert_o0_o1_emulator_sources_equivalence(sources, 10)


@pytest.mark.parametrize(
    ("name", "sources"),
    NESTED_RECORD_NATIVE_MODULE_ORDER_CASES,
)
def test_o0_o1_native_nested_record_modules(
    name: str,
    sources: tuple[tuple[str, str], ...],
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        sources,
        10,
        native_toolchain,
        tmp_path / f"nested-record-modules-{name}",
    )


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    NESTED_RECORD_TEXT_NATIVE_MODULE_CASES,
)
def test_nested_record_static_text_modules_match_emulator_o0_o1(
    name: str,
    sources: tuple[tuple[str, str], ...],
    expected: int,
) -> None:
    del name
    _assert_o0_o1_emulator_sources_equivalence(sources, expected)


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    NESTED_RECORD_TEXT_NATIVE_MODULE_CASES,
)
def test_o0_o1_native_nested_record_static_text_modules(
    name: str,
    sources: tuple[tuple[str, str], ...],
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        sources,
        expected,
        native_toolchain,
        tmp_path / f"nested-record-text-modules-{name}",
    )


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    AGGREGATE_RESULT_NATIVE_SOURCE_CASES,
)
def test_aggregate_result_native_sources_match_emulator_o0_o1(
    name: str,
    source: str,
    expected: int,
) -> None:
    del name
    _assert_o0_o1_emulator_equivalence(source, expected)


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    AGGREGATE_RESULT_NATIVE_SOURCE_CASES,
)
def test_o0_o1_native_aggregate_result_sources(
    name: str,
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_equivalence(
        source,
        expected,
        native_toolchain,
        tmp_path / f"aggregate-result-{name}",
    )


def test_imported_aggregate_result_native_sources_match_emulator_o0_o1() -> None:
    _assert_o0_o1_emulator_sources_equivalence(
        IMPORTED_AGGREGATE_RESULT_NATIVE_SOURCES,
        3,
    )


def test_o0_o1_native_imported_aggregate_result_sources(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        IMPORTED_AGGREGATE_RESULT_NATIVE_SOURCES,
        3,
        native_toolchain,
        tmp_path / "imported-aggregate-result",
    )


@pytest.mark.parametrize(
    ("name", "source", "message", "code"),
    (
        (
            "self-cycle",
            "record Node:\n"
            "    next: Node\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: Node -> Node",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "two-node-cycle",
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: A -> B -> A",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "three-node-cycle",
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    c: C\n"
            "record C:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: A -> B -> C -> A",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "missing-nested-type",
            "record Outer:\n"
            "    inner: Missing\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "unknown type 'Missing'",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "same-shape-mismatch",
            "record Left:\n"
            "    value: tryte\n"
            "record Right:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    left: Left\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(left=Right(value=1))\n"
            "    return 0\n",
            "nominal literal 'Right' has type Right; expected Left",
            DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
        ),
        (
            "missing-field",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "    flag: trit\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(flag=-1)\n"
            "    return 0\n",
            "record 'Outer' literal is missing field(s): inner",
            DiagnosticCode.RECORD_FIELD_MISSING,
        ),
        (
            "extra-field",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1), extra=2)\n"
            "    return 0\n",
            "record 'Outer' has no field 'extra'",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "field-type-mismatch",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=1)\n"
            "    return 0\n",
            "field 'inner' has type tryte; expected Inner",
            DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
        ),
        (
            "invalid-member",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1))\n"
            "    return item.inner.missing\n",
            "record 'Inner' has no field 'missing'",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "member-after-scalar",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1))\n"
            "    return item.inner.value.missing\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "array-of-records",
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    values: Inner[1] = [Inner(value=1)]\n"
            "    return 0\n",
            "arrays of nominal types are not supported",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
    ),
)
def test_nested_record_native_semantic_rejections_stay_before_backend(
    name: str,
    source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    del name
    _assert_o0_o1_semantic_error(source, message, code)


@pytest.mark.parametrize(
    ("name", "sources", "message", "code"),
    (
        (
            "private-nested-type",
            {
                "main.s3": (
                    "module main\n"
                    "from model import Inner\n"
                    "record Outer:\n"
                    "    inner: Inner\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "model.s3": (
                    "module model\n"
                    "record Inner:\n"
                    "    value: tryte\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
            "type 'Inner' in module 'model' is private",
            DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        ),
        (
            "missing-module",
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import Leaf\n"
                    "record Outer:\n"
                    "    leaf: Leaf\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
            },
            "module 'geometry' was not found",
            DiagnosticCode.MODULE_NOT_FOUND,
        ),
        (
            "cross-module-cycle",
            {
                "main.s3": (
                    "module main\n"
                    "from graph import B\n"
                    "export record A:\n"
                    "    b: B\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "graph.s3": (
                    "module graph\n"
                    "from main import A\n"
                    "export record B:\n"
                    "    a: A\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
            "module import cycle: graph -> main -> graph",
            DiagnosticCode.MODULE_CYCLE,
        ),
        (
            "imported-same-name-same-shape-mismatch",
            {
                "main.s3": (
                    "module main\n"
                    "from left import Point\n"
                    "from left import make\n"
                    "from right import consume\n"
                    "fn main() -> tryte:\n"
                    "    point: Point = make()\n"
                    "    return consume(point)\n"
                ),
                "left.s3": (
                    "module left\n"
                    "export record Point:\n"
                    "    value: tryte\n"
                    "export fn make() -> Point:\n"
                    "    return Point(value=1)\n"
                ),
                "right.s3": (
                    "module right\n"
                    "export record Point:\n"
                    "    value: tryte\n"
                    "export fn consume(point: Point) -> tryte:\n"
                    "    return point.value\n"
                ),
            },
            "variable 'point' has type __s3mod_left__type_Point; expected __s3mod_right__type_Point",
            DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
        ),
    ),
)
def test_nested_record_native_module_semantic_rejections_stay_before_backend(
    name: str,
    sources: dict[str, str],
    message: str,
    code: DiagnosticCode,
) -> None:
    del name
    _assert_o0_o1_semantic_sources_error(sources, message, code)


@pytest.mark.parametrize(
    ("name", "sources", "expected"),
    (
        (
            "qualified-call-and-arguments",
            {
                "main.s3": (
                    "module main\n"
                    "from math import inc\n"
                    "from math import one\n"
                    "fn main() -> tryte:\n"
                    "    return math.inc(math.one())\n"
                ),
                "math.s3": (
                    "module math\n"
                    "export fn one() -> tryte:\n"
                    "    return 1\n"
                    "export fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            },
            2,
        ),
        (
            "qualified-enum-match",
            {
                "main.s3": (
                    "module main\n"
                    "from signlib import classify\n"
                    "from signlib import positive\n"
                    "fn main() -> tryte:\n"
                    "    match signlib.positive():\n"
                    "        signlib.Sign.Negative:\n"
                    "            return -1\n"
                    "        signlib.Sign.Zero:\n"
                    "            return 0\n"
                    "        signlib.Sign.Positive:\n"
                    "            return signlib.classify(signlib.Sign.Positive)\n"
                ),
                "signlib.s3": (
                    "module signlib\n"
                    "export enum Sign:\n"
                    "    Negative\n"
                    "    Zero\n"
                    "    Positive\n"
                    "export fn positive() -> Sign:\n"
                    "    return Sign.Positive\n"
                    "export fn classify(value: Sign) -> tryte:\n"
                    "    match value:\n"
                    "        Sign.Negative:\n"
                    "            return -5\n"
                    "        Sign.Zero:\n"
                    "            return 0\n"
                    "        Sign.Positive:\n"
                    "            return 5\n"
                ),
            },
            5,
        ),
        (
            "record-fields-branch-and-loop",
            {
                "main.s3": (
                    "module main\n"
                    "enum Sign:\n"
                    "    Negative\n"
                    "    Zero\n"
                    "    Positive\n"
                    "record Tagged:\n"
                    "    flag: trit\n"
                    "    sign: Sign\n"
                    "    value: tryte\n"
                    "fn score(item: Tagged) -> tryte:\n"
                    "    while item.flag:\n"
                    "        return -9\n"
                    "    match item.sign:\n"
                    "        Sign.Negative:\n"
                    "            return -1\n"
                    "        Sign.Zero:\n"
                    "            return 0\n"
                    "        Sign.Positive:\n"
                    "            return item.value\n"
                    "fn main() -> tryte:\n"
                    "    item: Tagged = Tagged(flag=0, sign=Sign.Positive, value=11)\n"
                    "    return score(item)\n"
                ),
            },
            11,
        ),
        (
            "qualified-record-return-member",
            {
                "main.s3": (
                    "module main\n"
                    "from maker import make\n"
                    "fn main() -> tryte:\n"
                    "    return maker.make().value\n"
                ),
                "maker.s3": (
                    "module maker\n"
                    "record Box:\n"
                    "    value: tryte\n"
                    "export fn make() -> Box:\n"
                    "    return Box(value=7)\n"
                ),
            },
            7,
        ),
    ),
)
def test_o0_o1_native_qualified_postfix_composition(
    name: str,
    sources: dict[str, str],
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_sources_equivalence(
        sources,
        expected,
        native_toolchain,
        tmp_path / f"qualified-postfix-{name}",
    )


@pytest.mark.parametrize(
    (
        "name",
        "source",
        "diagnostic_category",
        "native_fragment",
        "max_frames",
        "max_instructions",
    ),
    (
        (
            "overflow",
            """\
fn main() -> tryte:
    mut value: tryte = 364
    return value + 1
""",
            "overflow",
            "overflow",
            1024,
            100_000,
        ),
        (
            "bounds",
            """\
fn read(index: tryte) -> tryte:
    values: tryte[2] = [10, 20]
    return values[index]
fn main() -> tryte:
    return read(2)
""",
            "bounds",
            "bounds",
            1024,
            100_000,
        ),
        (
            "frame-limit",
            RECURSIVE_DEPTH_SOURCE.replace("return descend(3)", "return descend(10)"),
            "frame-limit",
            "frame limit",
            4,
            100_000,
        ),
        (
            "instruction-limit",
            RECURSIVE_DEPTH_SOURCE,
            "instruction-limit",
            "instruction limit",
            1024,
            5,
        ),
    ),
)
def test_o0_o1_native_differential_matrix_errors(
    name: str,
    source: str,
    diagnostic_category: str,
    native_fragment: str,
    max_frames: int,
    max_instructions: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_o0_o1_native_error_category(
        source,
        diagnostic_category,
        native_fragment,
        native_toolchain,
        tmp_path / f"matrix-error-{name}",
        max_frames=max_frames,
        max_instructions=max_instructions,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            """\
fn choose(value: tryte) -> tryte:
    mut result: tryte = 0
    match value <=> 0:
        -1:
            result = 3
        0:
            result = 5
        else:
            result = 7
    return result
fn seed() -> tryte:
    return 1
fn main() -> tryte:
    return choose(seed())
""",
            7,
        ),
        (
            """\
fn pair(value: tryte) -> tryte:
    mut a: tryte = 0
    mut b: tryte = 0
    match value <=> 0:
        -1:
            a = 1
            b = 2
        0:
            a = 3
            b = 4
        else:
            a = 5
            b = 6
    return a + b
fn seed() -> tryte:
    return -1
fn main() -> tryte:
    return pair(seed())
""",
            3,
        ),
        (
            """\
fn main() -> tryte:
    mut i: tryte = 0
    mut total: tryte = 0
    while i <=> 3:
        total = total + 2
        i = i + 1
    return total
""",
            6,
        ),
    ),
)
def test_native_o1_phi_lowering_cases(
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    case = sum(ord(character) for character in source)
    _assert_differential(
        source,
        expected,
        native_toolchain,
        tmp_path / f"o1-phi-{case}",
        optimization="O1",
        mode=SyntaxMode.V0_6,
    )


@pytest.mark.parametrize(
    ("source_or_program", "category"),
    (
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 364\n"
            "    return value + 1\n",
            "overflow",
        ),
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = -364\n"
            "    return value + -1\n",
            "overflow",
        ),
        (
            """\
fn read(index: tryte) -> tryte:
    values: tryte[2] = [10, 20]
    return values[index]
fn main() -> tryte:
    return read(-1)
""",
            "bounds",
        ),
        (
            """\
fn read(index: tryte) -> tryte:
    values: tryte[2] = [10, 20]
    return values[index]
fn main() -> tryte:
    return read(2)
""",
            "bounds",
        ),
        (
            parse_assembly(
                """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0
    TRET r1
.end
"""
            ),
            "uninitialized memory",
        ),
        (
            parse_assembly(
                """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, immutable
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TCONST r2, 2
    TSTORE m0, r0, r1
    TSTORE m0, r0, r2
    TRET r2
.end
"""
            ),
            "immutable memory",
        ),
    ),
)
def test_runtime_failures_are_controlled(
    source_or_program: str | AssemblyProgram,
    category: str,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = _program(source_or_program)
    with pytest.raises(EmulatorError):
        Emulator().execute(program)
    completed = _run_native(program, native_toolchain, tmp_path / "failure")
    assert completed.returncode != 0
    assert completed.returncode not in {-11, 139}
    assert completed.stdout == ""
    assert category in completed.stderr.lower()


def test_native_bounds_diagnostic_contains_context_and_dynamic_value(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(
        """\
fn read(index: tryte) -> tryte:
    values: tryte[2] = [10, 20]
    return values[index]
fn main() -> tryte:
    return read(-1)
""",
        mode=SyntaxMode.V0_6,
    ).assembly
    completed = _run_native(program, native_toolchain, tmp_path / "bounds-context")
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "runtime error [bounds] in function 'read'" in completed.stderr
    assert "block entry, TLOAD" in completed.stderr
    assert "source 3:" in completed.stderr
    assert "index -1 outside [0, 2)" in completed.stderr


def test_native_unknown_source_diagnostic_is_explicit(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0
    TRET r1
.end
"""
    )
    completed = _run_native(program, native_toolchain, tmp_path / "unknown-source")
    assert completed.returncode != 0
    assert "runtime error [uninitialized memory] in function 'main'" in (
        completed.stderr
    )
    assert "source unknown" in completed.stderr
    assert "block entry, TLOAD, assembly line 7" in completed.stderr
    assert "index 0 is uninitialized in m0" in completed.stderr


def test_native_elf_has_start_and_no_dynamic_dependencies(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(
        (ROOT / "examples" / "first.s3").read_text(encoding="utf-8"),
        mode=SyntaxMode.V0_6,
    ).assembly
    executable = native_toolchain.build(
        generate_native_assembly(program),
        tmp_path / "first",
        keep_assembly=tmp_path / "first.s",
    )
    file_tool = shutil.which("file")
    readelf = shutil.which("readelf")
    if NATIVE_REQUIRED:
        assert file_tool is not None, "file is required by the native CI job"
        assert readelf is not None, "readelf is required by the native CI job"
    if file_tool is None or readelf is None:
        pytest.skip("file/readelf are unavailable")
    file_output = subprocess.run(
        [file_tool, str(executable)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "ELF 64-bit" in file_output
    assert "x86-64" in file_output
    symbols = subprocess.run(
        [readelf, "-sW", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "_start" in symbols
    dynamic = subprocess.run(
        [readelf, "-dW", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "NEEDED" not in dynamic
    assembly = (tmp_path / "first.s").read_text(encoding="utf-8")
    assert "TSUB" not in assembly
    assert "python" not in assembly.lower()
    assert platform.machine().lower() in {"x86_64", "amd64"}


def test_same_toolchain_build_is_byte_reproducible(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(
        (ROOT / "examples" / "recursive_memory.s3").read_text(
            encoding="utf-8"
        ),
        "O1",
        mode=SyntaxMode.V0_6,
    ).assembly
    native = generate_native_assembly(program)
    first = native_toolchain.build(native, tmp_path / "one" / "program")
    second = native_toolchain.build(native, tmp_path / "two" / "program")
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()
    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(
        second_bytes
    ).hexdigest()




    for executable in (first, second):
        completed = native_toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: 6\n"

    readelf = shutil.which("readelf")
    if NATIVE_REQUIRED:
        assert readelf is not None, "readelf is required by the native CI job"
    if readelf is None:
        pytest.skip("readelf is unavailable")
    notes = subprocess.run(
        [readelf, "-nW", str(first)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "Build ID" not in notes
    header = subprocess.run(
        [readelf, "-hW", str(first)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "ELF64" in header
    assert "Advanced Micro Devices X86-64" in header


@pytest.mark.parametrize(
    ("source", "category"),
    (
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 364\n"
            "    return value + 1\n",
            "overflow",
        ),
        (
            """\
fn read(index: tryte) -> tryte:
    values: tryte[1] = [1]
    return values[index]
fn main() -> tryte:
    return read(1)
""",
            "bounds",
        ),
    ),
)
def test_o0_o1_native_errors_preserve_category(
    source: str,
    category: str,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    messages: list[str] = []
    for level in ("O0", "O1"):
        program = compile_source(source, level, mode=SyntaxMode.V0_6).assembly
        with pytest.raises(EmulatorError, match=category):
            Emulator().execute(program)
        completed = _run_native(
            program,
            native_toolchain,
            tmp_path / f"error-{category}-{level}",
        )
        assert completed.returncode != 0
        assert category in completed.stderr.lower()
        messages.append(completed.stderr)
    assert all(category in message for message in messages)


def test_build_and_run_native_cli_commands(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del native_toolchain
    source = ROOT / "examples" / "first.s3"
    executable = tmp_path / "first"
    assembly = tmp_path / "first.s"
    assert cli_main(
        [
            "--source-syntax", "0.6",
            "build",
            str(source),
            "-o",
            str(executable),
            "--keep-assembly",
            str(assembly),
        ]
    ) == 0
    build_output = capsys.readouterr()
    assert build_output.err == ""
    assert executable.is_file()
    assert assembly.is_file()
    assert cli_main(["--source-syntax", "0.6", "run-native", str(source)]) == 0
    run_output = capsys.readouterr()
    assert run_output.err == ""
    assert run_output.out == "program returned: 6\n"
