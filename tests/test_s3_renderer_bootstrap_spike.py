from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.pipeline import compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


BOOTSTRAP_PATH = Path("examples/self_hosting/assembly_renderer_bootstrap.s3")


def _source() -> str:
    return BOOTSTRAP_PATH.read_text(encoding="utf-8")


def test_renderer_bootstrap_spike_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert BOOTSTRAP_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn renderer_bootstrap_self_check() -> tryte:" in source
    assert "fn is_supported_opcode(opcode: tryte) -> trit:" in source
    assert "fn validate_fixture_line_count" in source
    assert "fn validate_supported_subset() -> trit:" in source


def test_renderer_bootstrap_spike_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "renderer_bootstrap_self_check" in names
    assert "validate_supported_subset" in names
    assert "bootstrap_unknown_opcode_probe" in names


def test_renderer_bootstrap_spike_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="renderer_bootstrap_self_check") == 0
    assert run_source(source, entry="validate_supported_subset") == 1


def test_renderer_bootstrap_spike_executes_opcode_and_shape_probes() -> None:
    source = _source()

    assert run_source(source, entry="bootstrap_supported_opcode_probe") == 0
    assert run_source(source, entry="bootstrap_unknown_opcode_probe") == 0
    assert run_source(source, entry="bootstrap_operand_shape_probe") == 0


def test_renderer_bootstrap_spike_executes_fixture_line_count_probes() -> None:
    source = _source()

    assert run_source(source, entry="bootstrap_first_line_count_probe") == 0
    assert run_source(source, entry="bootstrap_simple_call_line_count_probe") == 0
    assert run_source(source, entry="bootstrap_sign_line_count_probe") == 0


def test_renderer_bootstrap_spike_is_registered_for_hosted_check() -> None:
    program = find_program(BOOTSTRAP_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_bootstrap_spike() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_bootstrap.s3" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_bootstrap_spike_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_bootstrap.assembly.txt"
    ).exists()
    assert not Path("tests/golden/inspect/assembly_renderer_bootstrap.ir.json").exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != BOOTSTRAP_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
