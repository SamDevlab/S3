from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


EVENT_STREAM_PATH = Path("examples/self_hosting/assembly_renderer_event_stream.s3")
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
EVENT_IDS = {
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
PAYLOAD_IDS = {
    "none": 0,
    "directive": 1,
    "symbol": 2,
    "register_decl": 3,
    "memory_decl": 4,
    "instruction_no_operands": 5,
    "instruction_registers": 6,
    "instruction_immediate": 7,
    "instruction_call": 8,
    "instruction_branch": 9,
    "instruction_memory": 10,
    "source_metadata": 11,
    "blank": 12,
}
METRIC_ENTRYPOINTS = {
    "event_count": "total_event_count",
    "header": "total_emit_header_count",
    "function": "total_emit_function_count",
    "param": "total_emit_param_count",
    "register": "total_emit_register_count",
    "memory": "total_emit_memory_count",
    "label": "total_emit_label_count",
    "instruction": "total_emit_instruction_count",
    "end": "total_emit_end_count",
    "blank": "total_emit_blank_count",
    "transition_count": "total_event_transition_count",
    "event_signature": "total_event_signature",
    "payload_signature": "total_payload_signature",
}


def _source() -> str:
    return EVENT_STREAM_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly, entry=entry
    )


def _classify_instruction_payload(opcode: str, operands: list[str]) -> str:
    if opcode == "TCONST":
        return "instruction_immediate"
    if opcode == "TCALL":
        return "instruction_call"
    if opcode in {"TJMP", "TBR3"}:
        return "instruction_branch"
    if opcode in {"TLOAD", "TSTORE"}:
        return "instruction_memory"
    if operands:
        return "instruction_registers"
    return "instruction_no_operands"


def _event_payload_for_line(line: str) -> tuple[str, str]:
    stripped = line.strip()
    if not stripped:
        return "blank", "blank"
    if stripped.startswith("."):
        directive = stripped.split()[0]
        return {
            ".s3asm": ("header", "directive"),
            ".function": ("function", "symbol"),
            ".param": ("param", "register_decl"),
            ".register": ("register", "register_decl"),
            ".memory": ("memory", "memory_decl"),
            ".label": ("label", "symbol"),
            ".end": ("end", "directive"),
        }[directive]

    parts = line.split(";", 1)[0].strip().split()
    return (
        "instruction",
        _classify_instruction_payload(parts[0], parts[1:]),
    )


def _derive_event_metrics(path: Path) -> dict[str, object]:
    rows = tuple(
        _event_payload_for_line(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    events = tuple(event for event, _payload in rows)
    payloads = tuple(payload for _event, payload in rows)
    return {
        "events": events,
        "payloads": payloads,
        "event_count": len(events),
        "transition_count": len(events) - 1,
        "event_signature": sum(EVENT_IDS[event] for event in events),
        "payload_signature": sum(PAYLOAD_IDS[payload] for payload in payloads),
        **{event: events.count(event) for event in EVENT_IDS},
    }


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_event_stream_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert EVENT_STREAM_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn event_stream_model_self_check() -> tryte:" in source
    assert "fn expected_event_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert "fn expected_payload_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert "fn is_valid_event_transition(left: tryte, right: tryte) -> trit:" in source


def test_renderer_event_stream_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "event_stream_model_self_check" in names
    assert "validate_all_fixture_event_streams" in names
    assert "event_stream_transition_probe" in names
    assert "event_stream_payload_probe" in names
    assert "event_stream_signature_probe" in names


def test_renderer_event_stream_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="event_stream_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_event_streams") == 1


def test_renderer_event_stream_model_metrics_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_event_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["event_signature"] == 81
    assert expected["simple_call"]["event_signature"] == 94
    assert expected["sign"]["event_signature"] == 170
    assert expected["first"]["payload_signature"] == 80
    assert expected["simple_call"]["payload_signature"] == 93
    assert expected["sign"]["payload_signature"] == 165

    assert _execute(compilation, "total_event_signature") == sum(
        metric["event_signature"] for metric in expected.values()
    )
    assert _execute(compilation, "total_payload_signature") == sum(
        metric["payload_signature"] for metric in expected.values()
    )


def test_renderer_event_stream_model_totals_match_current_goldens() -> None:
    compilation = compile_source(_source())
    metrics = [
        _derive_event_metrics(path)
        for path in GOLDEN_PATHS.values()
    ]

    totals = {
        "event_count": sum(metric["event_count"] for metric in metrics),
        "transition_count": sum(metric["transition_count"] for metric in metrics),
        "event_signature": sum(metric["event_signature"] for metric in metrics),
        "payload_signature": sum(metric["payload_signature"] for metric in metrics),
    }
    for event in EVENT_IDS:
        totals[event] = sum(metric[event] for metric in metrics)

    assert totals == {
        "event_count": 75,
        "transition_count": 72,
        "event_signature": 345,
        "payload_signature": 338,
        "header": 3,
        "function": 5,
        "param": 3,
        "register": 19,
        "memory": 0,
        "label": 8,
        "instruction": 27,
        "end": 5,
        "blank": 5,
    }
    for metric_name, entrypoint in METRIC_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoint) == totals[metric_name]
    assert _execute(compilation, "event_stream_totals_probe") == 0


def test_renderer_event_stream_model_executes_fixture_payload_transition_probes() -> None:
    compilation = compile_source(_source())

    assert _execute(compilation, "validate_first_event_stream") == 1
    assert _execute(compilation, "validate_simple_call_event_stream") == 1
    assert _execute(compilation, "validate_sign_event_stream") == 1
    assert _execute(compilation, "validate_first_event_transitions") == 1
    assert _execute(compilation, "validate_simple_call_event_transitions") == 1
    assert _execute(compilation, "validate_sign_event_transitions") == 1
    assert _execute(compilation, "event_stream_first_probe") == 0
    assert _execute(compilation, "event_stream_simple_call_probe") == 0
    assert _execute(compilation, "event_stream_sign_probe") == 0
    assert _execute(compilation, "event_stream_payload_probe") == 0
    assert _execute(compilation, "event_stream_transition_probe") == 0
    assert _execute(compilation, "event_stream_signature_probe") == 0


def test_renderer_event_stream_model_is_registered_for_hosted_check() -> None:
    program = find_program(EVENT_STREAM_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_event_stream_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_event_stream.s3" in completed.stdout
    assert "s3 program check: checked 13 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 10 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_event_stream_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_event_stream.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_event_stream.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != EVENT_STREAM_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
