from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


OUTPUT_BUFFER_PATH = Path("examples/self_hosting/assembly_renderer_output_buffer.s3")
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
WRITE_IDS = {
    "header": 0,
    "function": 1,
    "param": 2,
    "register": 3,
    "memory": 4,
    "label": 5,
    "instruction": 6,
    "end": 7,
    "blank": 8,
}
STATE_DONE = 4
FIXTURE_ENTRYPOINTS = {
    "first": {
        "state": "first_buffer_final_state",
        "cursor": "first_buffer_cursor",
        "capacity": "first_buffer_capacity",
        "signature": "first_buffer_signature",
        "sequence": "validate_first_buffer_write_sequence",
        "probe": "output_buffer_first_probe",
    },
    "simple_call": {
        "state": "simple_call_buffer_final_state",
        "cursor": "simple_call_buffer_cursor",
        "capacity": "simple_call_buffer_capacity",
        "signature": "simple_call_buffer_signature",
        "sequence": "validate_simple_call_buffer_write_sequence",
        "probe": "output_buffer_simple_call_probe",
    },
    "sign": {
        "state": "sign_buffer_final_state",
        "cursor": "sign_buffer_cursor",
        "capacity": "sign_buffer_capacity",
        "signature": "sign_buffer_signature",
        "sequence": "validate_sign_buffer_write_sequence",
        "probe": "output_buffer_sign_probe",
    },
}
TOTAL_ENTRYPOINTS = {
    "capacity": "total_buffer_capacity",
    "cursor": "total_final_cursor",
    "writes": "total_write_count",
    "directive": "total_directive_write_count",
    "instruction": "total_instruction_write_count",
    "blank": "total_blank_write_count",
    "header": "total_header_write_count",
    "function": "total_function_write_count",
    "param": "total_param_write_count",
    "register": "total_register_write_count",
    "memory": "total_memory_write_count",
    "label": "total_label_write_count",
    "end": "total_end_write_count",
    "signature": "total_buffer_signature",
}


def _source() -> str:
    return OUTPUT_BUFFER_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly, entry=entry
    )


def _write_for_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "blank"
    if stripped.startswith("."):
        directive = stripped.split()[0]
        return {
            ".s3asm": "header",
            ".function": "function",
            ".param": "param",
            ".register": "register",
            ".memory": "memory",
            ".label": "label",
            ".end": "end",
        }[directive]
    return "instruction"


def _derive_buffer_metrics(path: Path) -> dict[str, object]:
    writes = tuple(
        _write_for_line(line) for line in path.read_text(encoding="utf-8").splitlines()
    )
    capacity = len(writes)
    directive_count = sum(
        1 for write in writes if write not in {"instruction", "blank"}
    )
    signature = (
        STATE_DONE
        + capacity
        + capacity
        + len(writes)
        + directive_count
        + writes.count("instruction")
        + writes.count("blank")
        + writes.count("header")
        + writes.count("function")
        + writes.count("param")
        + writes.count("register")
        + writes.count("memory")
        + writes.count("label")
        + writes.count("end")
    )
    return {
        "writes": writes,
        "state": STATE_DONE,
        "cursor": capacity,
        "capacity": capacity,
        "signature": signature,
        "directive": directive_count,
        **{write: writes.count(write) for write in WRITE_IDS},
    }


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_output_buffer_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert OUTPUT_BUFFER_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn output_buffer_model_self_check() -> tryte:" in source
    assert "fn expected_buffer_capacity(fixture: tryte) -> tryte:" in source
    assert "fn expected_write_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert "fn next_buffer_state(state: tryte, cursor: tryte, capacity: tryte, write: tryte) -> tryte:" in source
    assert "fn validate_overflow_probe() -> trit:" in source


def test_renderer_output_buffer_model_compiles_and_executes() -> None:
    source = _source()
    compilation = compile_source(source)
    names = {function.name for function in compilation.ast.functions}

    assert {
        "main",
        "output_buffer_model_self_check",
        "validate_all_fixture_buffers",
        "output_buffer_counts_probe",
        "output_buffer_signature_probe",
        "output_buffer_transition_probe",
    } <= names
    assert run_source(source) == 0
    assert run_source(source, entry="output_buffer_model_self_check") == 0
    assert _execute(compilation, "validate_all_fixture_buffers") == 1


def test_renderer_output_buffer_model_matches_current_fixture_writes() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_buffer_metrics(path) for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["signature"] == 86
    assert expected["simple_call"]["signature"] == 101
    assert expected["sign"]["signature"] == 168
    for name, entrypoints in FIXTURE_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoints["sequence"]) == 1
        assert _execute(compilation, entrypoints["state"]) == expected[name]["state"]
        assert _execute(compilation, entrypoints["cursor"]) == expected[name]["cursor"]
        assert _execute(compilation, entrypoints["capacity"]) == expected[name]["capacity"]
        assert _execute(compilation, entrypoints["signature"]) == expected[name]["signature"]


def test_renderer_output_buffer_model_totals_match_current_goldens() -> None:
    compilation = compile_source(_source())
    metrics = [_derive_buffer_metrics(path) for path in GOLDEN_PATHS.values()]
    totals = {
        "capacity": sum(metric["capacity"] for metric in metrics),
        "cursor": sum(metric["cursor"] for metric in metrics),
        "writes": sum(len(metric["writes"]) for metric in metrics),
        "directive": sum(metric["directive"] for metric in metrics),
        "signature": sum(metric["signature"] for metric in metrics),
    }
    for write in WRITE_IDS:
        totals[write] = sum(metric[write] for metric in metrics)

    assert totals == {
        "capacity": 75,
        "cursor": 75,
        "writes": 75,
        "directive": 43,
        "instruction": 27,
        "blank": 5,
        "header": 3,
        "function": 5,
        "param": 3,
        "register": 19,
        "memory": 0,
        "label": 8,
        "end": 5,
        "signature": 355,
    }
    for metric_name, entrypoint in TOTAL_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoint) == totals[metric_name]
    assert _execute(compilation, "output_buffer_counts_probe") == 0
    assert _execute(compilation, "output_buffer_signature_probe") == 0


def test_renderer_output_buffer_model_executes_negative_probes() -> None:
    compilation = compile_source(_source())

    for entrypoints in FIXTURE_ENTRYPOINTS.values():
        assert _execute(compilation, entrypoints["probe"]) == 0
    assert _execute(compilation, "output_buffer_transition_probe") == 0
    assert _execute(compilation, "validate_invalid_fixture_probe") == 1
    assert _execute(compilation, "validate_invalid_index_probe") == 1
    assert _execute(compilation, "validate_unknown_write_probe") == 1
    assert _execute(compilation, "validate_unknown_state_probe") == 1
    assert _execute(compilation, "validate_overflow_probe") == 1
    assert _execute(compilation, "validate_invalid_buffer_transition_probe") == 1


def test_renderer_output_buffer_model_is_registered_for_hosted_check() -> None:
    program = find_program(OUTPUT_BUFFER_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_output_buffer_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_output_buffer.s3" in completed.stdout
    assert "s3 program check: checked 15 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 12 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_output_buffer_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_output_buffer.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_output_buffer.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != OUTPUT_BUFFER_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
