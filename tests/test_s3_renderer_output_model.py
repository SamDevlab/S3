from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


OUTPUT_MODEL_PATH = Path("examples/self_hosting/assembly_renderer_output_model.s3")
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}
METRIC_ENTRYPOINTS = {
    "line_count": {
        "first": "first_line_count",
        "simple_call": "simple_call_line_count",
        "sign": "sign_line_count",
    },
    "function_count": {
        "first": "first_function_count",
        "simple_call": "simple_call_function_count",
        "sign": "sign_function_count",
    },
    "param_count": {
        "first": "first_param_count",
        "simple_call": "simple_call_param_count",
        "sign": "sign_param_count",
    },
    "register_count": {
        "first": "first_register_count",
        "simple_call": "simple_call_register_count",
        "sign": "sign_register_count",
    },
    "memory_count": {
        "first": "first_memory_count",
        "simple_call": "simple_call_memory_count",
        "sign": "sign_memory_count",
    },
    "label_count": {
        "first": "first_label_count",
        "simple_call": "simple_call_label_count",
        "sign": "sign_label_count",
    },
    "instruction_count": {
        "first": "first_instruction_count",
        "simple_call": "simple_call_instruction_count",
        "sign": "sign_instruction_count",
    },
    "directive_count": {
        "first": "first_directive_count",
        "simple_call": "simple_call_directive_count",
        "sign": "sign_directive_count",
    },
    "distinct_opcode_count": {
        "first": "first_distinct_opcode_count",
        "simple_call": "simple_call_distinct_opcode_count",
        "sign": "sign_distinct_opcode_count",
    },
}


def _source() -> str:
    return OUTPUT_MODEL_PATH.read_text(encoding="utf-8")


def _derive_metrics(path: Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    nonblank = [line.strip() for line in lines if line.strip()]
    directives = [line for line in nonblank if line.startswith(".")]
    instructions = [line for line in nonblank if not line.startswith(".")]
    opcodes = {line.split()[0] for line in instructions}

    return {
        "line_count": len(lines),
        "function_count": sum(
            1 for line in nonblank if line.startswith(".function ")
        ),
        "param_count": sum(1 for line in nonblank if line.startswith(".param ")),
        "register_count": sum(
            1 for line in nonblank if line.startswith(".register ")
        ),
        "memory_count": sum(1 for line in nonblank if line.startswith(".memory ")),
        "label_count": sum(1 for line in nonblank if line.startswith(".label ")),
        "instruction_count": len(instructions),
        "directive_count": len(directives),
        "distinct_opcode_count": len(opcodes),
    }


def test_renderer_output_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert OUTPUT_MODEL_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn output_model_self_check() -> tryte:" in source
    assert "fn validate_fixture_output_model(fixture: tryte) -> trit:" in source
    assert "fn validate_all_fixture_output_models() -> trit:" in source
    assert "fn expected_line_count(fixture: tryte) -> tryte:" in source


def test_renderer_output_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "output_model_self_check" in names
    assert "validate_total_output_model" in names
    assert "output_model_unknown_fixture_probe" in names


def test_renderer_output_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="output_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_output_models") == 1


def test_renderer_output_model_metrics_match_current_goldens() -> None:
    source = _source()
    expected = {
        name: _derive_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["line_count"] == 16
    assert expected["simple_call"]["line_count"] == 21
    assert expected["sign"]["line_count"] == 32

    for metric_name, by_fixture in METRIC_ENTRYPOINTS.items():
        for fixture, entrypoint in by_fixture.items():
            assert run_source(source, entry=entrypoint) == expected[fixture][metric_name]


def test_renderer_output_model_totals_match_current_goldens() -> None:
    source = _source()
    metrics = [_derive_metrics(path) for path in GOLDEN_PATHS.values()]

    assert run_source(source, entry="total_line_count") == sum(
        metric["line_count"] for metric in metrics
    )
    assert run_source(source, entry="total_function_count") == sum(
        metric["function_count"] for metric in metrics
    )
    assert run_source(source, entry="total_instruction_count") == sum(
        metric["instruction_count"] for metric in metrics
    )
    assert run_source(source, entry="total_directive_count") == sum(
        metric["directive_count"] for metric in metrics
    )
    assert run_source(source, entry="output_model_totals_probe") == 0


def test_renderer_output_model_executes_fixture_and_unknown_probes() -> None:
    source = _source()

    assert run_source(source, entry="output_model_first_probe") == 0
    assert run_source(source, entry="output_model_simple_call_probe") == 0
    assert run_source(source, entry="output_model_sign_probe") == 0
    assert run_source(source, entry="output_model_unknown_fixture_probe") == 0


def test_renderer_output_model_is_registered_for_hosted_check() -> None:
    program = find_program(OUTPUT_MODEL_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_output_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_output_model.s3" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_output_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_output_model.assembly.txt"
    ).exists()
    assert not Path("tests/golden/inspect/assembly_renderer_output_model.ir.json").exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != OUTPUT_MODEL_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
