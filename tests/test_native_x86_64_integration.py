from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
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
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ternary import TernaryWidth, tritwise_max, tritwise_min
from tools.benchmark_native import (
    NativeBuildRequest,
    NativeSamplingPlan,
    build_native_artifact,
    execute_native_artifact,
    run_native_sampling_case,
    validate_native_execution,
)


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
    ("source_or_program", "category"),
    (
        ("fn main() -> tryte:\n    return 364 + 1\n", "overflow"),
        ("fn main() -> tryte:\n    return -364 + -1\n", "overflow"),
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
        ("fn main() -> tryte:\n    return 364 + 1\n", "overflow"),
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


@pytest.mark.parametrize(
    "optimization",
    (OptimizationLevel.O0, OptimizationLevel.O1),
    ids=lambda level: level.value,
)
def test_e3_native_sampling_reuses_one_minimal_elf_for_o0_and_o1(
    optimization: OptimizationLevel,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    del native_toolchain
    manifest = json.loads(
        (ROOT / "benchmarks" / "manifest.json").read_text(encoding="utf-8")
    )
    workload = next(
        item for item in manifest["workloads"] if item["id"] == "minimal"
    )
    source_path = ROOT / "benchmarks" / workload["file"]
    output_path = tmp_path / f"minimal-{optimization.value}"
    build_calls = []
    build_process_calls = []
    built_snapshots = []

    def build_runner(command, **kwargs):
        build_process_calls.append((command, kwargs))
        return subprocess.run(command, **kwargs)

    request = NativeBuildRequest(
        workload_id=workload["id"],
        source_path=source_path,
        optimization=optimization,
        expected_return=workload["expected_return"],
        output_path=output_path,
        max_instructions=workload["max_instructions"],
        max_frames=workload["max_frames"],
        source_syntax="0.6",
    )

    def builder(build_request: NativeBuildRequest):
        build_calls.append(build_request)
        artifact = build_native_artifact(
            build_request,
            process_runner=build_runner,
            python_executable=sys.executable,
        )
        artifact_path = artifact.executable_path
        artifact_bytes = artifact_path.read_bytes()
        built_snapshots.append(
            (
                artifact_path,
                artifact_bytes,
                artifact_path.stat().st_mtime_ns,
                artifact_path.stat().st_size,
                hashlib.sha256(artifact_bytes).hexdigest(),
            )
        )
        return artifact

    execution_calls = []
    execution_results = []

    def execution_runner(command, **kwargs):
        execution_calls.append((command, kwargs))
        return subprocess.run(command, **kwargs)

    def executor(artifact, *, timeout):
        execution = execute_native_artifact(
            artifact,
            timeout=timeout,
            process_runner=execution_runner,
        )
        execution_results.append((artifact, execution))
        return execution

    validation_calls = []

    def validator(execution, expected_return):
        validation = validate_native_execution(execution, expected_return)
        validation_calls.append((execution, expected_return, validation))
        return validation

    result = run_native_sampling_case(
        request,
        NativeSamplingPlan(warmups=1, runs=3, timeout=10.0),
        builder=builder,
        executor=executor,
        validator=validator,
    )

    assert build_calls == [request]
    assert len(build_process_calls) == 1
    assert len(built_snapshots) == 1
    original_path, original_bytes, original_mtime, original_size, original_sha = (
        built_snapshots[0]
    )
    assert result.artifact.executable_path == output_path.resolve()
    assert result.artifact.executable_path == original_path
    assert result.artifact.executable_path.is_file()
    assert result.artifact.size_bytes == original_size
    assert result.artifact.size_bytes == len(original_bytes)
    assert result.artifact.size_bytes > 0
    assert result.artifact.sha256 == original_sha
    assert original_sha == hashlib.sha256(original_bytes).hexdigest()

    assert len(execution_calls) == 5
    assert len(execution_results) == 5
    assert len(validation_calls) == 5
    assert all(artifact is result.artifact for artifact, _ in execution_results)
    assert all(
        command == [str(result.artifact.executable_path)]
        for command, _ in execution_calls
    )
    assert all(kwargs["timeout"] == 10.0 for _, kwargs in execution_calls)

    for _, execution in execution_results:
        assert execution.returncode == 0
        assert execution.stderr == ""
        assert not execution.timed_out

    assert all(
        validation.valid and validation.require_valid() == workload["expected_return"]
        for _, _, validation in validation_calls
    )
    assert result.actual_return == workload["expected_return"]
    assert result.warmups == 1
    assert result.runs == 3
    assert result.total_execution_count == 5
    assert len(result.samples_ns) == 3
    assert all(isinstance(sample, int) for sample in result.samples_ns)
    assert all(sample >= 0 for sample in result.samples_ns)
    assert result.statistics.sample_count == 3
    assert result.statistics.unit == "ns"
    assert result.statistics.minimum in result.samples_ns
    assert result.statistics.maximum in result.samples_ns
    assert result.statistics.minimum == min(result.samples_ns)
    assert result.statistics.maximum == max(result.samples_ns)
    assert result.statistics.median == sorted(result.samples_ns)[1]
    assert result.statistics.p95 == max(result.samples_ns)

    current_bytes = result.artifact.executable_path.read_bytes()
    assert current_bytes == original_bytes
    assert result.artifact.executable_path.stat().st_mtime_ns == original_mtime
    assert result.artifact.executable_path.stat().st_size == original_size
    assert hashlib.sha256(current_bytes).hexdigest() == original_sha


def test_public_elf_execution_runner_measures_minimal_o0_o1(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    del native_toolchain
    native_temp = tmp_path / "native-runner-temp"
    native_temp.mkdir()
    env = os.environ.copy()
    env.update({
        "TMPDIR": str(native_temp),
        "TMP": str(native_temp),
        "TEMP": str(native_temp),
    })
    command = [
        sys.executable,
        str(ROOT / "tools" / "benchmark.py"),
        "--mode",
        "elf-execution",
        "--optimization",
        "both",
        "--workload",
        "minimal",
        "--warmups",
        "1",
        "--runs",
        "3",
        "--timeout-seconds",
        "10.0",
        "--format",
        "json",
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert "traceback" not in completed.stdout.lower()
    assert "traceback" not in completed.stderr.lower()
    assert str(ROOT) not in completed.stdout
    assert str(native_temp) not in completed.stdout
    username = env.get("USERNAME") or env.get("USER")
    if username:
        assert username not in completed.stdout

    payload = json.loads(completed.stdout)
    assert payload["benchmark_format_version"] == "1.2.0"
    assert payload["configuration"]["mode"] == "elf-execution"
    assert payload["metadata"]["mode"] == "elf-execution"
    assert len(payload["results"]) == 1

    grouped_result = payload["results"][0]
    assert grouped_result["workload"] == "minimal"
    assert grouped_result["status"] == "passed"
    cases = [grouped_result["O0"], grouped_result["O1"]]
    assert [case["opt_level"] for case in cases] == ["O0", "O1"]

    for case in cases:
        assert case["workload"] == "minimal"
        assert case["mode"] == "elf-execution"
        assert case["status"] == "passed"
        validation = case["functional_validation"]
        assert validation["mode"] == "elf-execution"
        assert validation["status"] == "passed"
        assert validation["expected_return"] == 0
        assert validation["actual_return"] == 0

        artifact = case["metrics"]["native_artifact"]
        assert artifact["artifact_kind"] == "elf-linux-x86-64"
        assert artifact["size_bytes"] > 0
        assert len(artifact["sha256"]) == 64
        assert all(character in "0123456789abcdef" for character in artifact["sha256"])

        execution = case["metrics"]["execution"]
        assert execution["build_count"] == 1
        assert execution["preflight_count"] == 1
        assert execution["warmups"] == 1
        assert execution["runs"] == 3
        assert execution["total_execution_count"] == 5

        timing = case["timing"]
        assert timing["unit"] == "ns"
        samples = timing["samples_ns"]
        assert len(samples) == 3
        assert all(isinstance(sample, int) for sample in samples)
        assert all(sample >= 0 for sample in samples)

        statistics = timing["elf_execution"]
        ordered_samples = sorted(samples)
        expected_p95 = ordered_samples[math.ceil(0.95 * len(samples)) - 1]
        assert statistics["sample_count"] == 3
        assert statistics["minimum"] == min(samples)
        assert statistics["maximum"] == max(samples)
        assert statistics["mean"] == pytest.approx(sum(samples) / len(samples))
        assert statistics["median"] == ordered_samples[1]
        assert statistics["p95"] == expected_p95

    assert native_temp.exists()
    assert list(native_temp.glob("s3-benchmark-elf-*")) == []
    assert not any(native_temp.rglob("*.s"))
    assert not any(path.is_file() for path in native_temp.rglob("*"))
