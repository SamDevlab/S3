from __future__ import annotations

import json
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


TEXT_BUILDER_PATH = Path("examples/self_hosting/assembly_renderer_text_builder.s3")
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}
FIXTURE_ENTRYPOINTS = {
    "first": {
        "validate": "validate_first_builder",
        "commands": "validate_first_builder_commands",
        "counts": "validate_first_builder_counts",
        "signature": "validate_first_builder_signature",
        "chunk": "first_builder_logical_byte_chunk_count",
        "remainder": "first_builder_logical_byte_remainder",
        "builder_signature": "first_builder_signature",
    },
    "simple_call": {
        "validate": "validate_simple_call_builder",
        "commands": "validate_simple_call_builder_commands",
        "counts": "validate_simple_call_builder_counts",
        "signature": "validate_simple_call_builder_signature",
        "chunk": "simple_call_builder_logical_byte_chunk_count",
        "remainder": "simple_call_builder_logical_byte_remainder",
        "builder_signature": "simple_call_builder_signature",
    },
    "sign": {
        "validate": "validate_sign_builder",
        "commands": "validate_sign_builder_commands",
        "counts": "validate_sign_builder_counts",
        "signature": "validate_sign_builder_signature",
        "chunk": "sign_builder_logical_byte_chunk_count",
        "remainder": "sign_builder_logical_byte_remainder",
        "builder_signature": "sign_builder_signature",
    },
}


def _source() -> str:
    return TEXT_BUILDER_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly, entry=entry
    )


def _metrics(path: Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    logical_bytes = len(
        path.read_bytes().decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    )
    stripped = [line.strip() for line in lines]
    instructions = sum(bool(line) and not line.startswith(".") for line in stripped)
    token_writes = sum(bool(line) for line in stripped)
    indentation_writes = sum(line.startswith("    ") for line in lines)
    return {
        "lines": len(lines),
        "bytes": logical_bytes,
        "newlines": len(lines),
        "metadata": instructions,
        "tokens": token_writes,
        "indentation": indentation_writes,
    }


def test_renderer_text_builder_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert TEXT_BUILDER_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn text_builder_model_self_check() -> tryte:" in source
    assert "fn expected_builder_command_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert "fn validate_byte_count_mismatch_probe() -> trit:" in source


def test_renderer_text_builder_model_compiles_and_executes() -> None:
    source = _source()
    compilation = compile_source(source)
    names = {function.name for function in compilation.ast.functions}

    assert {
        "main",
        "text_builder_model_self_check",
        "validate_all_fixture_builders",
        "validate_builder_line_consistency",
        "validate_builder_buffer_consistency",
        "validate_total_builder_signature",
        "validate_invalid_fixture_probe",
        "validate_unknown_command_probe",
        "validate_unknown_state_probe",
        "validate_invalid_index_probe",
        "validate_invalid_builder_transition_probe",
        "validate_byte_count_mismatch_probe",
        "validate_signature_mismatch_probe",
    } <= names
    assert run_source(source) == 0
    assert run_source(source, entry="text_builder_model_self_check") == 0
    assert _execute(compilation, "validate_all_fixture_builders") == 1


def test_renderer_text_builder_model_matches_current_fixture_metrics() -> None:
    compilation = compile_source(_source())
    expected = {name: _metrics(path) for name, path in GOLDEN_PATHS.items()}

    assert expected == {
        "first": {"lines": 18, "bytes": 441, "newlines": 18, "metadata": 7, "tokens": 17, "indentation": 13},
        "simple_call": {"lines": 21, "bytes": 448, "newlines": 21, "metadata": 6, "tokens": 19, "indentation": 12},
        "sign": {"lines": 36, "bytes": 946, "newlines": 36, "metadata": 14, "tokens": 34, "indentation": 24},
    }
    expected_signatures = {"first": 87, "simple_call": 96, "sign": 172}
    for name, entrypoints in FIXTURE_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoints["validate"]) == 1
        assert _execute(compilation, entrypoints["commands"]) == 1
        assert _execute(compilation, entrypoints["counts"]) == 1
        assert _execute(compilation, entrypoints["signature"]) == 1
        logical_bytes = (
            _execute(compilation, entrypoints["chunk"]) * 300
            + _execute(compilation, entrypoints["remainder"])
        )
        assert logical_bytes == expected[name]["bytes"]
        assert _execute(compilation, entrypoints["builder_signature"]) == expected_signatures[name]


def test_renderer_text_builder_model_validates_totals_and_negative_probes() -> None:
    compilation = compile_source(_source())

    assert _execute(compilation, "total_line_count") == 75
    assert _execute(compilation, "total_command_count") == 108
    assert _execute(compilation, "total_newline_count") == 75
    assert _execute(compilation, "total_indentation_write_count") == 49
    assert _execute(compilation, "total_token_write_count") == 70
    assert _execute(compilation, "total_source_metadata_write_count") == 27
    assert _execute(compilation, "total_logical_byte_chunk_count") == 5
    assert _execute(compilation, "total_logical_byte_remainder") == 335
    assert _execute(compilation, "total_builder_signature") == 355
    assert _execute(compilation, "expected_total_builder_signature") == 355
    for entry in (
        "validate_invalid_fixture_probe",
        "validate_unknown_command_probe",
        "validate_unknown_state_probe",
        "validate_invalid_index_probe",
        "validate_invalid_builder_transition_probe",
        "validate_byte_count_mismatch_probe",
        "validate_signature_mismatch_probe",
    ):
        assert _execute(compilation, entry) == 1


def test_renderer_text_builder_model_is_registered_without_output_contract_changes() -> None:
    program = find_program(TEXT_BUILDER_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0
    actual_outputs = json.loads(
        Path("tests/golden/assembly_renderer_candidate_actual_outputs.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(
        output["source"] != TEXT_BUILDER_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
