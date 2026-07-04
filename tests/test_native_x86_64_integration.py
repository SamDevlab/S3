from __future__ import annotations

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
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.pipeline import compile_source
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
) -> None:
    program = compile_source(source).assembly
    assert Emulator().execute(program) == expected
    completed = _run_native(program, toolchain, output)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n"


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
    _assert_differential(source, expected, native_toolchain, tmp_path / filename)


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
    )


@pytest.mark.parametrize(
    ("arity", "expected"),
    ((0, 7), (1, 1), (6, 5), (7, 6), (8, 7)),
)
def test_system_v_argument_counts(
    arity: int,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    if arity == 0:
        source = """\
fn selected() -> tryte { return 7; }
fn main() -> tryte { return selected(); }
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
    )


def test_forward_call_matches_emulator(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    _assert_differential(
        """\
fn main() -> tryte { return later(9); }
fn later(value: tryte) -> tryte { return value + 1; }
""",
        10,
        native_toolchain,
        tmp_path / "forward-call",
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
fn read(index: tryte) -> tryte {{
    tryte[3] values = [5, 6, 7];
    return values[index];
}}
fn main() -> tryte {{ return read({index_expression}); }}
""",
        expected,
        native_toolchain,
        tmp_path / f"array-{expected}-{len(index_expression)}",
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            """\
fn twice(value: tryte) -> tryte { return value + value; }
fn main() -> tryte { return twice(8) - 3; }
""",
            13,
        ),
        (
            """\
fn choose(value: tryte) -> tryte {
    mut tryte result = 0;
    switch (value <=> 0) {
        -1: { result = -3; }
        0: { result = 0; }
        1: { result = 3; }
    }
    return result;
}
fn main() -> tryte { return choose(1); }
""",
            3,
        ),
        (
            """\
fn read(index: tryte) -> tryte {
    mut tryte[3] values = [2, 4, 6];
    values[1] = values[0] + values[2];
    return values[index];
}
fn main() -> tryte { return read(1); }
""",
            8,
        ),
        (
            """\
fn main() -> tryte {
    tryte left = -100;
    tryte right = 40;
    return (left & right) | 1;
}
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
    )


@pytest.mark.parametrize(
    ("source_or_program", "category"),
    (
        ("fn main() -> tryte { return 364 + 1; }", "overflow"),
        ("fn main() -> tryte { return -364 + -1; }", "overflow"),
        (
            """\
fn read(index: tryte) -> tryte {
    tryte[2] values = [10, 20];
    return values[index];
}
fn main() -> tryte { return read(-1); }
""",
            "bounds",
        ),
        (
            """\
fn read(index: tryte) -> tryte {
    tryte[2] values = [10, 20];
    return values[index];
}
fn main() -> tryte { return read(2); }
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


def test_native_elf_has_start_and_no_dynamic_dependencies(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    program = compile_source(
        (ROOT / "examples" / "first.s3").read_text(encoding="utf-8")
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
    assert cli_main(["run-native", str(source)]) == 0
    run_output = capsys.readouterr()
    assert run_output.err == ""
    assert run_output.out == "program returned: 6\n"
