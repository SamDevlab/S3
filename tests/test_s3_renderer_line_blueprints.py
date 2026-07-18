from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


LINE_BLUEPRINTS_PATH = Path(
    "examples/self_hosting/assembly_renderer_line_blueprints.s3"
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
    "s3asm_header_count": {
        "first": "first_s3asm_header_count",
        "simple_call": "simple_call_s3asm_header_count",
        "sign": "sign_s3asm_header_count",
    },
    "function_header_count": {
        "first": "first_function_header_count",
        "simple_call": "simple_call_function_header_count",
        "sign": "sign_function_header_count",
    },
    "param_line_count": {
        "first": "first_param_line_count",
        "simple_call": "simple_call_param_line_count",
        "sign": "sign_param_line_count",
    },
    "register_line_count": {
        "first": "first_register_line_count",
        "simple_call": "simple_call_register_line_count",
        "sign": "sign_register_line_count",
    },
    "memory_line_count": {
        "first": "first_memory_line_count",
        "simple_call": "simple_call_memory_line_count",
        "sign": "sign_memory_line_count",
    },
    "label_line_count": {
        "first": "first_label_line_count",
        "simple_call": "simple_call_label_line_count",
        "sign": "sign_label_line_count",
    },
    "instruction_line_count": {
        "first": "first_instruction_line_count",
        "simple_call": "simple_call_instruction_line_count",
        "sign": "sign_instruction_line_count",
    },
    "instruction_with_source_line_count": {
        "first": "first_instruction_with_source_line_count",
        "simple_call": "simple_call_instruction_with_source_line_count",
        "sign": "sign_instruction_with_source_line_count",
    },
    "instruction_without_source_line_count": {
        "first": "first_instruction_without_source_line_count",
        "simple_call": "simple_call_instruction_without_source_line_count",
        "sign": "sign_instruction_without_source_line_count",
    },
    "end_line_count": {
        "first": "first_end_line_count",
        "simple_call": "simple_call_end_line_count",
        "sign": "sign_end_line_count",
    },
    "blank_line_count": {
        "first": "first_blank_line_count",
        "simple_call": "simple_call_blank_line_count",
        "sign": "sign_blank_line_count",
    },
    "directive_blueprint_count": {
        "first": "first_directive_blueprint_count",
        "simple_call": "simple_call_directive_blueprint_count",
        "sign": "sign_directive_blueprint_count",
    },
}


def _source() -> str:
    return LINE_BLUEPRINTS_PATH.read_text(encoding="utf-8")


def _derive_line_blueprint_metrics(path: Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    metrics = {
        "line_count": len(lines),
        "blueprint_count": len(lines),
        "s3asm_header_count": 0,
        "function_header_count": 0,
        "param_line_count": 0,
        "register_line_count": 0,
        "memory_line_count": 0,
        "label_line_count": 0,
        "instruction_line_count": 0,
        "instruction_with_source_line_count": 0,
        "instruction_without_source_line_count": 0,
        "end_line_count": 0,
        "blank_line_count": 0,
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            metrics["blank_line_count"] += 1
        elif stripped.startswith(".s3asm "):
            metrics["s3asm_header_count"] += 1
        elif stripped.startswith(".function "):
            metrics["function_header_count"] += 1
        elif stripped.startswith(".param "):
            metrics["param_line_count"] += 1
        elif stripped.startswith(".register "):
            metrics["register_line_count"] += 1
        elif stripped.startswith(".memory "):
            metrics["memory_line_count"] += 1
        elif stripped.startswith(".label "):
            metrics["label_line_count"] += 1
        elif stripped == ".end":
            metrics["end_line_count"] += 1
        else:
            metrics["instruction_line_count"] += 1
            if "; source=" in line:
                metrics["instruction_with_source_line_count"] += 1
            else:
                metrics["instruction_without_source_line_count"] += 1

    metrics["directive_blueprint_count"] = (
        metrics["s3asm_header_count"]
        + metrics["function_header_count"]
        + metrics["param_line_count"]
        + metrics["register_line_count"]
        + metrics["memory_line_count"]
        + metrics["label_line_count"]
        + metrics["end_line_count"]
    )
    return metrics


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_line_blueprint_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert LINE_BLUEPRINTS_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn line_blueprint_model_self_check() -> tryte:" in source
    assert "fn is_known_blueprint(blueprint: tryte) -> trit:" in source
    assert "fn is_directive_blueprint(blueprint: tryte) -> trit:" in source
    assert "fn is_instruction_blueprint(blueprint: tryte) -> trit:" in source
    assert "fn validate_fixture_line_blueprints(fixture: tryte) -> trit:" in source


def test_renderer_line_blueprint_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "line_blueprint_model_self_check" in names
    assert "validate_total_line_blueprints" in names
    assert "line_blueprints_unknown_blueprint_probe" in names
    assert "blueprint_instruction_with_source" in names


def test_renderer_line_blueprint_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="line_blueprint_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_line_blueprints") == 1
    assert run_source(source, entry="validate_blueprint_ids") == 1


def test_renderer_line_blueprint_model_metrics_match_current_goldens() -> None:
    source = _source()
    expected = {
        name: _derive_line_blueprint_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["blueprint_count"] == 18
    assert expected["simple_call"]["blueprint_count"] == 21
    assert expected["sign"]["blueprint_count"] == 36
    assert expected["first"]["instruction_without_source_line_count"] == 0
    assert expected["simple_call"]["instruction_without_source_line_count"] == 0
    assert expected["sign"]["instruction_without_source_line_count"] == 0

    for metric_name, by_fixture in METRIC_ENTRYPOINTS.items():
        for fixture, entrypoint in by_fixture.items():
            assert run_source(source, entry=entrypoint) == expected[fixture][metric_name]


def test_renderer_line_blueprint_model_totals_match_current_goldens() -> None:
    source = _source()
    metrics = [_derive_line_blueprint_metrics(path) for path in GOLDEN_PATHS.values()]

    assert run_source(source, entry="total_line_count") == sum(
        metric["line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_blueprint_count") == sum(
        metric["blueprint_count"] for metric in metrics
    )
    assert run_source(source, entry="total_s3asm_header_count") == sum(
        metric["s3asm_header_count"] for metric in metrics
    )
    assert run_source(source, entry="total_function_header_count") == sum(
        metric["function_header_count"] for metric in metrics
    )
    assert run_source(source, entry="total_param_line_count") == sum(
        metric["param_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_register_line_count") == sum(
        metric["register_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_memory_line_count") == sum(
        metric["memory_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_label_line_count") == sum(
        metric["label_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_line_count") == sum(
        metric["instruction_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_with_source_line_count") == sum(
        metric["instruction_with_source_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_without_source_line_count") == sum(
        metric["instruction_without_source_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_end_line_count") == sum(
        metric["end_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_blank_line_count") == sum(
        metric["blank_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_directive_blueprint_count") == sum(
        metric["directive_blueprint_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_blueprint_count") == sum(
        metric["instruction_line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_blank_blueprint_count") == sum(
        metric["blank_line_count"] for metric in metrics
    )
    assert run_source(source, entry="line_blueprints_totals_probe") == 0


def test_renderer_line_blueprint_model_executes_fixture_and_blueprint_probes() -> None:
    source = _source()

    assert run_source(source, entry="line_blueprints_first_probe") == 0
    assert run_source(source, entry="line_blueprints_simple_call_probe") == 0
    assert run_source(source, entry="line_blueprints_sign_probe") == 0
    assert run_source(source, entry="line_blueprints_unknown_fixture_probe") == 0
    assert run_source(source, entry="line_blueprints_known_blueprint_probe") == 0
    assert run_source(source, entry="line_blueprints_unknown_blueprint_probe") == 0
    assert run_source(source, entry="line_blueprints_directive_probe") == 0
    assert run_source(source, entry="line_blueprints_instruction_probe") == 0
    assert run_source(source, entry="line_blueprints_blank_probe") == 0


def test_renderer_line_blueprint_model_is_registered_for_hosted_check() -> None:
    program = find_program(LINE_BLUEPRINTS_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_line_blueprint_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "examples/self_hosting/assembly_renderer_line_blueprints.s3"
        in completed.stdout
    )
    assert "s3 program check: checked 10 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 7 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_line_blueprint_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_blueprints.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_blueprints.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != LINE_BLUEPRINTS_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
