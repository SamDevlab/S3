from __future__ import annotations

from dataclasses import replace
import platform
from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_native_assembly
from bootstrap.s3.diagnostics import S3Error
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_sources


_STAGE1_MODULES = (
    "selfhost/substrate/generic_lexer_state.s3",
    "selfhost/substrate/verifier_kernel.s3",
    "selfhost/substrate/output_sink.s3",
    "selfhost/compiler/stage1_compiler_v1.s3",
)


def _stage1_artifact(source: str, *, compiler_version: str = "v1") -> bytes:
    repository = Path(__file__).parents[1]
    compiler_module = f"stage1_compiler_{compiler_version}"
    module_paths = (
        *_STAGE1_MODULES[:-1],
        f"selfhost/compiler/{compiler_module}.s3",
    )
    modules = {
        path: (repository / path).read_text(encoding="utf-8")
        for path in module_paths
    }
    source_bytes = source.encode("ascii")
    main_lines = [
        "module main",
        f"from selfhost.compiler.{compiler_module} import Stage1CompileResult",
        f"from selfhost.compiler.{compiler_module} import stage1_compile",
        "fn main() -> vector<i64>:",
        f"    mut source: vector<i64> = vector_new<i64>({len(source_bytes)})",
    ]
    main_lines.extend(
        f"    discard vector_push<i64>(&mut source, {byte})"
        for byte in source_bytes
    )
    main_lines.extend(
        (
            "    mut result: Stage1CompileResult = stage1_compile(source)",
            "    mut envelope: vector<i64> = vector_new<i64>(result.output_length + 4)",
            "    discard vector_push<i64>(&mut envelope, result.status)",
            "    discard vector_push<i64>(&mut envelope, result.phase)",
            "    discard vector_push<i64>(&mut envelope, result.error_code)",
            "    discard vector_push<i64>(&mut envelope, result.output_length)",
            "    mut output_index: i64 = 0",
            "    while output_index < result.output_length:",
            "        discard vector_push<i64>(&mut envelope, vector_get<i64>(&result.output, output_index))",
            "        output_index = output_index + 1",
            "    return envelope",
        )
    )
    modules["main.s3"] = "\n".join(main_lines) + "\n"

    stage0 = compile_sources(modules, entry_module="main")
    output = execute_ir(stage0.ir)
    envelope = tuple(int(output[index]) for index in range(output.length))
    status, phase, error_code, output_length = envelope[:4]
    if status == 0:
        assert output_length == 0, f"failed Stage1 compilation emitted {output_length} bytes"
        return b""
    assert status == 1, f"Stage1 compilation failed: phase={phase}, error_code={error_code}"
    return bytes(envelope[4 : 4 + output_length])


def _reference_accepts(source: str) -> bool:
    try:
        compile_sources({"main.s3": source}, entry_module="main")
    except S3Error:
        return False
    return True


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return 2 + 3\n",
        "fn main() -> i64:\n    return 12 + 30\n",
    ),
)
def test_stage1_candidate_emits_executable_assembly_for_arithmetic(source: str) -> None:
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source)


def test_stage1_candidate_composes_two_functions_with_a_zero_argument_call() -> None:
    source = (
        "fn helper() -> i64:\n"
        "    return 37\n"
        "\n"
        "fn main() -> i64:\n"
        "    return helper()\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 37


def test_stage1_candidate_resolves_forward_function_references() -> None:
    source = (
        "fn main() -> i64:\n"
        "    return add(19, 23)\n"
        "\n"
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_lowers_typed_parameters_and_positional_call_arguments() -> None:
    source = (
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "\n"
        "fn main() -> i64:\n"
        "    return add(17, 25)\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_lowers_immutable_locals_across_function_calls() -> None:
    source = (
        "fn add(a: i64, b: i64) -> i64:\n"
        "    total: i64 = a + b\n"
        "    return total\n"
        "\n"
        "fn main() -> i64:\n"
        "    answer: i64 = add(17, 25)\n"
        "    return answer\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_composes_nested_calls_and_parenthesized_arithmetic() -> None:
    source = (
        "fn multiply(a: i64, b: i64) -> i64:\n"
        "    return (a * b)\n"
        "\n"
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "\n"
        "fn main() -> i64:\n"
        "    return add(multiply(3, 4), 2)\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes
    assert b"TMUL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 14


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return missing + 1\n",
        "fn main() -> i64:\n    value: i64 = 1\n    value: i64 = 2\n    return value\n",
        "fn add(value: i64, value: i64) -> i64:\n    return value\nfn main() -> i64:\n    return add(1, 2)\n",
        "fn add(a: i64, b: i64) -> i64:\n    return a + b\nfn main() -> i64:\n    return add(1)\n",
        "fn main() -> i64:\n    value: i64 = 1\n",
        "fn main() -> i64:\n    return 1\n    value: i64 = 2\n",
        "fn main() -> i64:\n    return true\n",
        "fn main() -> i64:\n    return (1 + 2\n",
    ),
)
def test_stage1_candidate_rejects_unsupported_or_invalid_bindings(source: str) -> None:
    assert not _reference_accepts(source)
    assert _stage1_artifact(source) == b""


def test_stage1_candidate_has_no_host_compiler_fallbacks() -> None:
    repository = Path(__file__).parents[1]
    candidate_sources = "\n".join(
        (repository / path).read_text(encoding="utf-8")
        for path in _STAGE1_MODULES
    ).casefold()
    for forbidden in (
        "bootstrap.s3",
        "compile_source(",
        "compile_program(",
        "run_source(",
        "reference_lowerer",
        "host_compiler_callback",
    ):
        assert forbidden not in candidate_sources


def test_stage1_candidate_output_is_deterministic() -> None:
    source = "fn main() -> i64:\n    return 12 + 30\n"
    assert _stage1_artifact(source) == _stage1_artifact(source)


def test_stage1_candidate_rejects_unlowered_identifier_without_artifact() -> None:
    source = "fn main() -> i64:\n    return value + 1\n"
    assert _stage1_artifact(source) == b""


@pytest.mark.parametrize(
    ("function_name", "signature"),
    (
        ("stage1_emission_value_count", "view: &vector<i64>"),
        ("stage1_emission_instruction_count", "view: &vector<i64>"),
        ("stage1_emission_value_id", "view: &vector<i64>, index: i64"),
    ),
)
def test_stage1_v2_compiles_real_reference_vector_helpers(
    function_name: str,
    signature: str,
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_text(
        encoding="utf-8"
    )
    start = raw.index(f"fn {function_name}(")
    end = raw.index("\n\n", start)
    original_function = raw[start:end]
    assert f"fn {function_name}({signature}) -> i64:" in original_function
    source = f"{original_function}\n\nfn main() -> i64:\n    return 0\n"

    artifact_bytes = _stage1_artifact(source, compiler_version="v2")
    assert artifact_bytes
    assert artifact_bytes.startswith(b".s3asm 0.7.0\n")
    assert b".param r0, reference, vector, immutable, value\n" in artifact_bytes
    assert b"TCALL r" in artifact_bytes
    if function_name == "stage1_emission_value_id":
        assert b"TADD r" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == 0


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return vector_get<f64>(1, 0)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1, 0)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1, 0, 2)\n",
        "fn read(view: &vector<i64>) -> i64:\n    return vector_get<i64>(view, 0)\n"
        "fn main() -> i64:\n    return read(1)\n",
    ),
)
def test_stage1_v2_rejects_invalid_typed_vector_calls(source: str) -> None:
    assert _stage1_artifact(source, compiler_version="v2") == b""


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_stage1_v2_real_reference_vector_helpers_execute_natively(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_text(
        encoding="utf-8"
    )
    function_names = (
        "stage1_emission_value_count",
        "stage1_emission_instruction_count",
        "stage1_emission_value_id",
    )
    source_functions = []
    for name in function_names:
        start = raw.index(f"fn {name}(")
        end = raw.index("\n\n", start)
        source_functions.append(raw[start:end])

    candidate_source = (
        "\n\n".join(source_functions)
        + "\n\nfn main() -> i64:\n    return 0\n"
    )
    candidate = parse_assembly(
        _stage1_artifact(candidate_source, compiler_version="v2").decode("ascii")
    )

    reference_source = """\
fn stage1_emission_value_count(view: &vector<i64>) -> i64:
    return 0
fn stage1_emission_instruction_count(view: &vector<i64>) -> i64:
    return 0
fn stage1_emission_value_id(view: &vector<i64>, index: i64) -> i64:
    return 0
fn main() -> i64:
    mut count_view: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut count_view, 41)
    discard vector_push<i64>(&mut count_view, 3)
    mut instruction_view: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut instruction_view, 41)
    discard vector_push<i64>(&mut instruction_view, 7)
    mut value_view: vector<i64> = vector_new<i64>(5)
    discard vector_push<i64>(&mut value_view, 41)
    discard vector_push<i64>(&mut value_view, 7)
    discard vector_push<i64>(&mut value_view, 13)
    discard vector_push<i64>(&mut value_view, 17)
    discard vector_push<i64>(&mut value_view, 99)
    return stage1_emission_value_count(&count_view) + stage1_emission_instruction_count(&instruction_view) * 100 + stage1_emission_value_id(&value_view, 1) * 10000
"""
    reference = compile_sources(
        {"main.s3": reference_source}, entry_module="main"
    )
    candidate_by_name = {
        f"__s3mod_main__{function.name}": replace(
            function, name=f"__s3mod_main__{function.name}"
        )
        for function in candidate.functions
        if function.name in function_names
    }
    assert set(candidate_by_name) == {
        f"__s3mod_main__{name}" for name in function_names
    }
    composed_functions = tuple(
        candidate_by_name.get(function.name, function)
        for function in reference.assembly.functions
    )
    composed = replace(reference.assembly, functions=composed_functions)

    native_source = generate_native_assembly(composed)
    toolchain = NativeToolchain.detect()
    executable = toolchain.build(
        native_source, tmp_path / "stage1-v2-real-helpers"
    )
    completed = toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "program returned: 990741"
    assert execute_ir(reference.ir) == 990741


def test_s3_output_sink_append_bytes_overflow_is_transactional() -> None:
    repository = Path(__file__).parents[1]
    source = """\
module main
from selfhost.substrate.output_sink import OutputSinkState
from selfhost.substrate.output_sink import output_sink_new
from selfhost.substrate.output_sink import output_sink_append
from selfhost.substrate.output_sink import output_sink_append_bytes
fn main() -> i64:
    mut sink: OutputSinkState = output_sink_new(2)
    sink = output_sink_append(sink, 65)
    mut bytes: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut bytes, 66)
    discard vector_push<i64>(&mut bytes, 67)
    sink = output_sink_append_bytes(sink, bytes)
    mut failed: i64 = 0
    match sink.failed == 1:
        -1:
            failed = 1
        0:
            discard 0
        1:
            discard 0
    return failed * 1000000 + vector_len<i64>(&sink.buffer) * 10000 + vector_get<i64>(&sink.buffer, 0)
"""
    compilation = compile_sources(
        {
            "selfhost/substrate/output_sink.s3": (
                repository / "selfhost/substrate/output_sink.s3"
            ).read_text(encoding="utf-8"),
            "main.s3": source,
        },
        entry_module="main",
    )

    assert execute_ir(compilation.ir) == 1_010_065
