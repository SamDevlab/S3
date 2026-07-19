from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


LINE_SEQUENCES_PATH = Path(
    "examples/self_hosting/assembly_renderer_line_sequences.s3"
)
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}
ACTUAL_OUTPUT_PATHS = {
    "first": Path("tests/golden/assembly_renderer_candidate_actual/first.assembly.txt"),
    "simple_call": Path(
        "tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt"
    ),
    "sign": Path("tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt"),
}
METRIC_ENTRYPOINTS = {
    "line_count": {
        "first": "first_line_count",
        "simple_call": "simple_call_line_count",
        "sign": "sign_line_count",
    },
    "blueprint_count": {
        "first": "first_blueprint_count",
        "simple_call": "simple_call_blueprint_count",
        "sign": "sign_blueprint_count",
    },
    "transition_count": {
        "first": "first_transition_count",
        "simple_call": "simple_call_transition_count",
        "sign": "sign_transition_count",
    },
    "function_count": {
        "first": "first_function_count",
        "simple_call": "simple_call_function_count",
        "sign": "sign_function_count",
    },
    "function_boundary_count": {
        "first": "first_function_boundary_count",
        "simple_call": "simple_call_function_boundary_count",
        "sign": "sign_function_boundary_count",
    },
    "instruction_run_count": {
        "first": "first_instruction_run_count",
        "simple_call": "simple_call_instruction_run_count",
        "sign": "sign_instruction_run_count",
    },
    "longest_instruction_run_count": {
        "first": "first_longest_instruction_run_count",
        "simple_call": "simple_call_longest_instruction_run_count",
        "sign": "sign_longest_instruction_run_count",
    },
    "blank_line_count": {
        "first": "first_blank_line_count",
        "simple_call": "simple_call_blank_line_count",
        "sign": "sign_blank_line_count",
    },
    "memory_line_count": {
        "first": "first_memory_line_count",
        "simple_call": "simple_call_memory_line_count",
        "sign": "sign_memory_line_count",
    },
    "instruction_blueprint_count": {
        "first": "first_instruction_blueprint_count",
        "simple_call": "simple_call_instruction_blueprint_count",
        "sign": "sign_instruction_blueprint_count",
    },
    "directive_blueprint_count": {
        "first": "first_directive_blueprint_count",
        "simple_call": "simple_call_directive_blueprint_count",
        "sign": "sign_directive_blueprint_count",
    },
    "directives_before_first_label_count": {
        "first": "first_directives_before_first_label_count",
        "simple_call": "simple_call_directives_before_first_label_count",
        "sign": "sign_directives_before_first_label_count",
    },
    "first_label_index": {
        "first": "first_first_label_index",
        "simple_call": "simple_call_first_label_index",
        "sign": "sign_first_label_index",
    },
    "sequence_signature": {
        "first": "first_sequence_signature",
        "simple_call": "simple_call_sequence_signature",
        "sign": "sign_sequence_signature",
    },
}
FUNCTION_BOUNDARY_ENTRYPOINTS = {
    "first": (
        ("first_function_0_start_index", "first_function_0_end_index"),
    ),
    "simple_call": (
        ("simple_call_function_0_start_index", "simple_call_function_0_end_index"),
        ("simple_call_function_1_start_index", "simple_call_function_1_end_index"),
    ),
    "sign": (
        ("sign_function_0_start_index", "sign_function_0_end_index"),
        ("sign_function_1_start_index", "sign_function_1_end_index"),
    ),
}
BLUEPRINT_S3ASM_HEADER = 0
BLUEPRINT_FUNCTION_HEADER = 1
BLUEPRINT_PARAM = 2
BLUEPRINT_REGISTER = 3
BLUEPRINT_MEMORY = 4
BLUEPRINT_LABEL = 5
BLUEPRINT_INSTRUCTION = 6
BLUEPRINT_INSTRUCTION_WITH_SOURCE = 7
BLUEPRINT_END = 8
BLUEPRINT_BLANK_LINE = 9


def _source() -> str:
    return LINE_SEQUENCES_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator().execute(compilation.assembly, entry=entry)


def _line_blueprint(line: str) -> int:
    stripped = line.strip()
    if not stripped:
        return BLUEPRINT_BLANK_LINE
    if stripped.startswith(".s3asm "):
        return BLUEPRINT_S3ASM_HEADER
    if stripped.startswith(".function "):
        return BLUEPRINT_FUNCTION_HEADER
    if stripped.startswith(".param "):
        return BLUEPRINT_PARAM
    if stripped.startswith(".register "):
        return BLUEPRINT_REGISTER
    if stripped.startswith(".memory "):
        return BLUEPRINT_MEMORY
    if stripped.startswith(".label "):
        return BLUEPRINT_LABEL
    if stripped == ".end":
        return BLUEPRINT_END
    if "; source=" in line:
        return BLUEPRINT_INSTRUCTION_WITH_SOURCE
    return BLUEPRINT_INSTRUCTION


def _derive_line_sequence_metrics(path: Path) -> dict[str, object]:
    sequence = tuple(
        _line_blueprint(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    transitions = tuple(zip(sequence, sequence[1:]))
    first_label_index = sequence.index(BLUEPRINT_LABEL)

    instruction_runs = []
    current_instruction_run = 0
    for blueprint in sequence:
        if blueprint in {BLUEPRINT_INSTRUCTION, BLUEPRINT_INSTRUCTION_WITH_SOURCE}:
            current_instruction_run += 1
            continue
        if current_instruction_run:
            instruction_runs.append(current_instruction_run)
        current_instruction_run = 0
    if current_instruction_run:
        instruction_runs.append(current_instruction_run)

    directive_blueprints = {
        BLUEPRINT_S3ASM_HEADER,
        BLUEPRINT_FUNCTION_HEADER,
        BLUEPRINT_PARAM,
        BLUEPRINT_REGISTER,
        BLUEPRINT_MEMORY,
        BLUEPRINT_LABEL,
        BLUEPRINT_END,
    }
    return {
        "sequence": sequence,
        "transitions": transitions,
        "line_count": len(sequence),
        "blueprint_count": len(sequence),
        "transition_count": len(transitions),
        "function_count": sequence.count(BLUEPRINT_FUNCTION_HEADER),
        "function_boundary_count": (
            sequence.count(BLUEPRINT_FUNCTION_HEADER)
            + sequence.count(BLUEPRINT_END)
        ),
        "function_start_indices": tuple(
            index
            for index, blueprint in enumerate(sequence)
            if blueprint == BLUEPRINT_FUNCTION_HEADER
        ),
        "function_end_indices": tuple(
            index for index, blueprint in enumerate(sequence) if blueprint == BLUEPRINT_END
        ),
        "instruction_run_count": len(instruction_runs),
        "longest_instruction_run_count": max(instruction_runs),
        "blank_line_count": sequence.count(BLUEPRINT_BLANK_LINE),
        "memory_line_count": sequence.count(BLUEPRINT_MEMORY),
        "instruction_blueprint_count": sequence.count(BLUEPRINT_INSTRUCTION)
        + sequence.count(BLUEPRINT_INSTRUCTION_WITH_SOURCE),
        "directive_blueprint_count": sum(
            1 for blueprint in sequence if blueprint in directive_blueprints
        ),
        "directives_before_first_label_count": sum(
            1
            for blueprint in sequence[:first_label_index]
            if blueprint in directive_blueprints
            and blueprint != BLUEPRINT_S3ASM_HEADER
        ),
        "first_label_index": first_label_index,
        "sequence_signature": sum(sequence) - len(sequence),
    }


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_line_sequence_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert LINE_SEQUENCES_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn line_sequence_model_self_check() -> tryte:" in source
    assert "fn expected_blueprint_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert "fn validate_fixture_line_sequences(fixture: tryte) -> trit:" in source
    assert "fn is_valid_blueprint_transition(left: tryte, right: tryte) -> trit:" in source


def test_renderer_line_sequence_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "line_sequence_model_self_check" in names
    assert "validate_total_line_sequences" in names
    assert "line_sequences_invalid_transition_probe" in names
    assert "first_blueprint_0" in names
    assert "simple_call_blueprint_20" in names
    assert "sign_blueprint_35" in names


def test_renderer_line_sequence_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="line_sequence_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_sequences") == 1


def test_renderer_line_sequence_model_sequences_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_line_sequence_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["sequence"] == (
        0,
        9,
        1,
        3,
        3,
        3,
        3,
        3,
        3,
        5,
        7,
        7,
        7,
        7,
        7,
        7,
        7,
        8,
    )
    assert expected["simple_call"]["sequence"] == (
        0,
        9,
        1,
        2,
        2,
        3,
        5,
        7,
        7,
        8,
        9,
        1,
        3,
        3,
        3,
        5,
        7,
        7,
        7,
        7,
        8,
    )
    assert expected["sign"]["sequence"] == (
        0,
        9,
        1,
        2,
        3,
        3,
        3,
        3,
        3,
        3,
        5,
        7,
        7,
        7,
        5,
        7,
        7,
        7,
        5,
        7,
        7,
        5,
        7,
        7,
        8,
        9,
        1,
        3,
        3,
        3,
        5,
        7,
        7,
        7,
        7,
        8,
    )

    for fixture, metrics in expected.items():
        for index, blueprint in enumerate(metrics["sequence"]):
            assert _execute(compilation, f"{fixture}_blueprint_{index}") == blueprint


def test_renderer_line_sequence_model_metrics_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_line_sequence_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["transition_count"] == 17
    assert expected["simple_call"]["transition_count"] == 20
    assert expected["sign"]["transition_count"] == 35
    assert expected["first"]["sequence_signature"] == 72
    assert expected["simple_call"]["sequence_signature"] == 83
    assert expected["sign"]["sequence_signature"] == 152

    for metric_name, by_fixture in METRIC_ENTRYPOINTS.items():
        for fixture, entrypoint in by_fixture.items():
            assert _execute(compilation, entrypoint) == expected[fixture][metric_name]


def test_renderer_line_sequence_model_function_boundaries_match_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_line_sequence_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["function_start_indices"] == (2,)
    assert expected["first"]["function_end_indices"] == (17,)
    assert expected["simple_call"]["function_start_indices"] == (2, 11)
    assert expected["simple_call"]["function_end_indices"] == (9, 20)
    assert expected["sign"]["function_start_indices"] == (2, 26)
    assert expected["sign"]["function_end_indices"] == (24, 35)

    for fixture, entrypoint_pairs in FUNCTION_BOUNDARY_ENTRYPOINTS.items():
        starts = expected[fixture]["function_start_indices"]
        ends = expected[fixture]["function_end_indices"]
        for function_index, (start_entry, end_entry) in enumerate(entrypoint_pairs):
            assert _execute(compilation, start_entry) == starts[function_index]
            assert _execute(compilation, end_entry) == ends[function_index]


def test_renderer_line_sequence_model_totals_match_current_goldens() -> None:
    compilation = compile_source(_source())
    metrics = [
        _derive_line_sequence_metrics(path)
        for path in GOLDEN_PATHS.values()
    ]

    assert _execute(compilation, "total_line_count") == sum(
        metric["line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_blueprint_count") == sum(
        metric["blueprint_count"] for metric in metrics
    )
    assert _execute(compilation, "total_transition_count") == sum(
        metric["transition_count"] for metric in metrics
    )
    assert _execute(compilation, "total_function_boundary_count") == sum(
        metric["function_boundary_count"] for metric in metrics
    )
    assert _execute(compilation, "total_instruction_blueprint_count") == sum(
        metric["instruction_blueprint_count"] for metric in metrics
    )
    assert _execute(compilation, "total_directive_blueprint_count") == sum(
        metric["directive_blueprint_count"] for metric in metrics
    )
    assert _execute(compilation, "total_blank_blueprint_count") == sum(
        metric["blank_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_sequence_signature") == sum(
        metric["sequence_signature"] for metric in metrics
    )
    assert _execute(compilation, "line_sequences_totals_probe") == 0


def test_renderer_line_sequence_model_executes_sequence_and_transition_probes() -> None:
    compilation = compile_source(_source())

    assert _execute(compilation, "validate_first_sequence") == 1
    assert _execute(compilation, "validate_simple_call_sequence") == 1
    assert _execute(compilation, "validate_sign_sequence") == 1
    assert _execute(compilation, "validate_first_transitions") == 1
    assert _execute(compilation, "validate_simple_call_transitions") == 1
    assert _execute(compilation, "validate_sign_transitions") == 1
    assert _execute(compilation, "line_sequences_first_probe") == 0
    assert _execute(compilation, "line_sequences_simple_call_probe") == 0
    assert _execute(compilation, "line_sequences_sign_probe") == 0
    assert _execute(compilation, "line_sequences_unknown_fixture_probe") == 0
    assert _execute(compilation, "line_sequences_invalid_index_probe") == 0
    assert _execute(compilation, "line_sequences_unknown_blueprint_probe") == 0
    assert _execute(compilation, "line_sequences_invalid_transition_probe") == 0
    assert _execute(compilation, "line_sequences_transition_probe") == 0
    assert _execute(compilation, "line_sequences_signature_probe") == 0


def test_renderer_line_sequence_model_is_registered_for_hosted_check() -> None:
    program = find_program(LINE_SEQUENCES_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_line_sequence_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "examples/self_hosting/assembly_renderer_line_sequences.s3"
        in completed.stdout
    )
    assert "s3 program check: checked 21 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 18 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_line_sequence_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_sequences.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_sequences.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != LINE_SEQUENCES_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
