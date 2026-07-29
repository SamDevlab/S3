from __future__ import annotations

import json
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


PIPELINE_PATH = Path("examples/self_hosting/assembly_renderer_pipeline.s3")
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}
EVENT_SIGNATURES = {"first": 81, "simple_call": 94, "sign": 170}
WRITER_SIGNATURES = {"first": 70, "simple_call": 81, "sign": 126}
BUFFER_SIGNATURES = {"first": 86, "simple_call": 101, "sign": 168}
FIXTURE_ENTRYPOINTS = {
    "first": {
        "pipeline": "validate_first_pipeline",
        "event_line": "validate_first_event_write_line_consistency",
        "writer_buffer": "validate_first_writer_buffer_consistency",
        "signature": "validate_first_pipeline_signature",
    },
    "simple_call": {
        "pipeline": "validate_simple_call_pipeline",
        "event_line": "validate_simple_call_event_write_line_consistency",
        "writer_buffer": "validate_simple_call_writer_buffer_consistency",
        "signature": "validate_simple_call_pipeline_signature",
    },
    "sign": {
        "pipeline": "validate_sign_pipeline",
        "event_line": "validate_sign_event_write_line_consistency",
        "writer_buffer": "validate_sign_writer_buffer_consistency",
        "signature": "validate_sign_pipeline_signature",
    },
}


def _source() -> str:
    return PIPELINE_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly, entry=entry
    )


def _metrics(path: Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    stripped = [line.strip() for line in lines]
    directives = sum(line.startswith(".") for line in stripped)
    instructions = sum(bool(line) and not line.startswith(".") for line in stripped)
    blanks = sum(not line for line in stripped)
    return {
        "lines": len(lines),
        "directives": directives,
        "instructions": instructions,
        "blanks": blanks,
    }


def test_renderer_pipeline_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert PIPELINE_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn pipeline_model_self_check() -> tryte:" in source
    assert "fn validate_pipeline_stage_sequence() -> trit:" in source
    assert "fn validate_fixture_pipeline(fixture: tryte) -> trit:" in source
    assert "fn validate_buffer_overflow_probe() -> trit:" in source


def test_renderer_pipeline_model_compiles_executes_and_exposes_model_api() -> None:
    source = _source()
    compilation = compile_source(source)
    names = {function.name for function in compilation.ast.functions}

    assert {
        "main",
        "pipeline_model_self_check",
        "validate_all_fixture_pipelines",
        "validate_event_write_line_consistency",
        "validate_writer_buffer_consistency",
        "validate_total_pipeline_signature",
        "validate_invalid_fixture_probe",
        "validate_unknown_stage_probe",
        "validate_unknown_result_probe",
        "validate_count_mismatch_probe",
        "validate_signature_mismatch_probe",
        "validate_buffer_overflow_probe",
        "validate_invalid_stage_transition_probe",
        "validate_invalid_final_state_probe",
    } <= names
    assert run_source(source) == 0
    assert run_source(source, entry="pipeline_model_self_check") == 0
    assert _execute(compilation, "validate_pipeline_stage_sequence") == 1
    assert _execute(compilation, "validate_all_fixture_pipelines") == 1


def test_renderer_pipeline_model_matches_current_fixture_pipeline_metrics() -> None:
    compilation = compile_source(_source())
    expected = {name: _metrics(path) for name, path in GOLDEN_PATHS.items()}

    assert expected == {
        "first": {"lines": 16, "directives": 9, "instructions": 6, "blanks": 1},
        "simple_call": {
            "lines": 21,
            "directives": 13,
            "instructions": 6,
            "blanks": 2,
        },
        "sign": {"lines": 32, "directives": 18, "instructions": 12, "blanks": 2},
    }
    expected_pipeline_signatures = {
        name: EVENT_SIGNATURES[name]
        + WRITER_SIGNATURES[name]
        - BUFFER_SIGNATURES[name]
        + metrics["lines"] * 3
        for name, metrics in expected.items()
    }
    assert expected_pipeline_signatures == {
        "first": 113,
        "simple_call": 137,
        "sign": 224,
    }
    for name, entrypoints in FIXTURE_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoints["pipeline"]) == 1
        assert _execute(compilation, entrypoints["event_line"]) == 1
        assert _execute(compilation, entrypoints["writer_buffer"]) == 1
        assert _execute(compilation, entrypoints["signature"]) == 1
        assert _execute(compilation, f"pipeline_{name}_probe") == 0


def test_renderer_pipeline_model_validates_totals_and_negative_probes() -> None:
    compilation = compile_source(_source())

    assert _execute(compilation, "total_event_count") == 69
    assert _execute(compilation, "total_write_count") == 69
    assert _execute(compilation, "total_line_advance_count") == 69
    assert _execute(compilation, "total_buffer_capacity") == 69
    assert _execute(compilation, "total_buffer_cursor") == 69
    assert _execute(compilation, "total_directive_count") == 40
    assert _execute(compilation, "total_instruction_count") == 24
    assert _execute(compilation, "total_blank_count") == 5
    assert _execute(compilation, "total_event_signature") == 318
    assert _execute(compilation, "total_writer_signature") == 259
    assert _execute(compilation, "total_buffer_signature") == 328
    assert _execute(compilation, "expected_total_pipeline_signature") == 220
    assert _execute(compilation, "modeled_total_pipeline_signature") == 220
    assert _execute(compilation, "pipeline_counts_probe") == 0
    assert _execute(compilation, "pipeline_signature_probe") == 0
    for entry in (
        "validate_invalid_fixture_probe",
        "validate_unknown_stage_probe",
        "validate_unknown_result_probe",
        "validate_invalid_event_probe",
        "validate_count_mismatch_probe",
        "validate_signature_mismatch_probe",
        "validate_buffer_overflow_probe",
        "validate_invalid_stage_transition_probe",
        "validate_invalid_final_state_probe",
    ):
        assert _execute(compilation, entry) == 1


def test_renderer_pipeline_model_is_registered_without_output_contract_changes() -> None:
    program = find_program(PIPELINE_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0
    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != PIPELINE_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
