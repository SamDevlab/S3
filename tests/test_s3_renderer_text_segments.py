from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


TEXT_SEGMENTS_PATH = Path("examples/self_hosting/assembly_renderer_text_segments.s3")
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
    "segment_count": {
        "first": "first_segment_count",
        "simple_call": "simple_call_segment_count",
        "sign": "sign_segment_count",
    },
    "directive_segment_count": {
        "first": "first_directive_segment_count",
        "simple_call": "simple_call_directive_segment_count",
        "sign": "sign_directive_segment_count",
    },
    "function_segment_count": {
        "first": "first_function_segment_count",
        "simple_call": "simple_call_function_segment_count",
        "sign": "sign_function_segment_count",
    },
    "param_segment_count": {
        "first": "first_param_segment_count",
        "simple_call": "simple_call_param_segment_count",
        "sign": "sign_param_segment_count",
    },
    "register_segment_count": {
        "first": "first_register_segment_count",
        "simple_call": "simple_call_register_segment_count",
        "sign": "sign_register_segment_count",
    },
    "memory_segment_count": {
        "first": "first_memory_segment_count",
        "simple_call": "simple_call_memory_segment_count",
        "sign": "sign_memory_segment_count",
    },
    "label_segment_count": {
        "first": "first_label_segment_count",
        "simple_call": "simple_call_label_segment_count",
        "sign": "sign_label_segment_count",
    },
    "instruction_segment_count": {
        "first": "first_instruction_segment_count",
        "simple_call": "simple_call_instruction_segment_count",
        "sign": "sign_instruction_segment_count",
    },
    "blank_line_segment_count": {
        "first": "first_blank_line_segment_count",
        "simple_call": "simple_call_blank_line_segment_count",
        "sign": "sign_blank_line_segment_count",
    },
    "source_segment_count": {
        "first": "first_source_segment_count",
        "simple_call": "simple_call_source_segment_count",
        "sign": "sign_source_segment_count",
    },
    "end_segment_count": {
        "first": "first_end_segment_count",
        "simple_call": "simple_call_end_segment_count",
        "sign": "sign_end_segment_count",
    },
}


def _source() -> str:
    return TEXT_SEGMENTS_PATH.read_text(encoding="utf-8")


def _derive_segment_metrics(path: Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    metrics = {
        "line_count": len(lines),
        "directive_segment_count": 0,
        "function_segment_count": 0,
        "param_segment_count": 0,
        "register_segment_count": 0,
        "memory_segment_count": 0,
        "label_segment_count": 0,
        "instruction_segment_count": 0,
        "blank_line_segment_count": 0,
        "source_segment_count": 0,
        "end_segment_count": 0,
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            metrics["blank_line_segment_count"] += 1
        elif stripped.startswith("."):
            metrics["directive_segment_count"] += 1
            if stripped.startswith(".function "):
                metrics["function_segment_count"] += 1
            elif stripped.startswith(".param "):
                metrics["param_segment_count"] += 1
            elif stripped.startswith(".register "):
                metrics["register_segment_count"] += 1
            elif stripped.startswith(".memory "):
                metrics["memory_segment_count"] += 1
            elif stripped.startswith(".label "):
                metrics["label_segment_count"] += 1
            elif stripped == ".end":
                metrics["end_segment_count"] += 1
        else:
            metrics["instruction_segment_count"] += 1
            if "; source=" in stripped:
                metrics["source_segment_count"] += 1

    metrics["segment_count"] = (
        metrics["directive_segment_count"]
        + metrics["instruction_segment_count"]
        + metrics["blank_line_segment_count"]
        + metrics["source_segment_count"]
    )
    return metrics


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_text_segment_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert TEXT_SEGMENTS_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn text_segment_model_self_check() -> tryte:" in source
    assert "fn is_known_segment(segment: tryte) -> trit:" in source
    assert "fn is_directive_segment(segment: tryte) -> trit:" in source
    assert "fn is_render_line_segment(segment: tryte) -> trit:" in source
    assert "fn validate_fixture_text_segments(fixture: tryte) -> trit:" in source


def test_renderer_text_segment_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "text_segment_model_self_check" in names
    assert "validate_total_text_segments" in names
    assert "text_segments_unknown_segment_probe" in names
    assert "segment_source_metadata" in names


def test_renderer_text_segment_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="text_segment_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_text_segments") == 1
    assert run_source(source, entry="validate_segment_ids") == 1


def test_renderer_text_segment_model_metrics_match_current_goldens() -> None:
    source = _source()
    expected = {
        name: _derive_segment_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["segment_count"] == 25
    assert expected["simple_call"]["segment_count"] == 27
    assert expected["sign"]["segment_count"] == 50

    for metric_name, by_fixture in METRIC_ENTRYPOINTS.items():
        for fixture, entrypoint in by_fixture.items():
            assert run_source(source, entry=entrypoint) == expected[fixture][metric_name]


def test_renderer_text_segment_model_totals_match_current_goldens() -> None:
    source = _source()
    metrics = [_derive_segment_metrics(path) for path in GOLDEN_PATHS.values()]

    assert run_source(source, entry="total_line_count") == sum(
        metric["line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_segment_count") == sum(
        metric["segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_directive_segment_count") == sum(
        metric["directive_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_segment_count") == sum(
        metric["instruction_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_label_segment_count") == sum(
        metric["label_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_blank_line_segment_count") == sum(
        metric["blank_line_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_source_segment_count") == sum(
        metric["source_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="total_end_segment_count") == sum(
        metric["end_segment_count"] for metric in metrics
    )
    assert run_source(source, entry="text_segments_totals_probe") == 0


def test_renderer_text_segment_model_executes_fixture_and_segment_probes() -> None:
    source = _source()

    assert run_source(source, entry="text_segments_first_probe") == 0
    assert run_source(source, entry="text_segments_simple_call_probe") == 0
    assert run_source(source, entry="text_segments_sign_probe") == 0
    assert run_source(source, entry="text_segments_unknown_fixture_probe") == 0
    assert run_source(source, entry="text_segments_known_segment_probe") == 0
    assert run_source(source, entry="text_segments_unknown_segment_probe") == 0
    assert run_source(source, entry="text_segments_directive_probe") == 0
    assert run_source(source, entry="text_segments_instruction_probe") == 0
    assert run_source(source, entry="text_segments_blank_line_probe") == 0


def test_renderer_text_segment_model_is_registered_for_hosted_check() -> None:
    program = find_program(TEXT_SEGMENTS_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_text_segment_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_text_segments.s3" in completed.stdout
    assert "s3 program check: checked 16 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 13 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_text_segment_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_text_segments.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_text_segments.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != TEXT_SEGMENTS_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
