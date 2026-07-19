from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


EVENT_WRITER_PATH = Path("examples/self_hosting/assembly_renderer_event_writer.s3")
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
STATE_IDS = {
    "start": 0,
    "after_header": 1,
    "in_function": 2,
    "after_label": 3,
    "after_instruction": 4,
    "after_end": 5,
    "after_blank": 6,
    "done": 7,
}
TOTAL_ENTRYPOINTS = {
    "line_advance_count": "total_line_advance_count",
    "directive_count": "total_directive_event_count",
    "instruction_count": "total_instruction_event_count",
    "blank_count": "total_blank_event_count",
    "function_count": "total_function_event_count",
    "end_count": "total_end_event_count",
    "writer_signature": "total_writer_signature",
}
FIXTURE_ENTRYPOINTS = {
    "first": {
        "final_state": "first_writer_final_state",
        "signature": "first_writer_signature",
        "probe": "event_writer_first_probe",
    },
    "simple_call": {
        "final_state": "simple_call_writer_final_state",
        "signature": "simple_call_writer_signature",
        "probe": "event_writer_simple_call_probe",
    },
    "sign": {
        "final_state": "sign_writer_final_state",
        "signature": "sign_writer_signature",
        "probe": "event_writer_sign_probe",
    },
}


def _source() -> str:
    return EVENT_WRITER_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly, entry=entry
    )


def _event_for_line(line: str) -> str:
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


def _next_state(state: str, event: str) -> str:
    if state == "start" and event == "header":
        return "after_header"
    if state == "after_header" and event == "blank":
        return "after_blank"
    if state == "after_blank" and event == "function":
        return "in_function"
    if state == "in_function" and event in {"param", "register", "memory"}:
        return "in_function"
    if state == "in_function" and event == "label":
        return "after_label"
    if state == "after_label" and event == "instruction":
        return "after_instruction"
    if state == "after_instruction" and event == "instruction":
        return "after_instruction"
    if state == "after_instruction" and event == "label":
        return "after_label"
    if state == "after_instruction" and event == "end":
        return "after_end"
    if state == "after_end" and event == "blank":
        return "after_blank"
    raise AssertionError(f"invalid writer transition: {state} {event}")


def _derive_writer_metrics(path: Path) -> dict[str, object]:
    events = tuple(
        _event_for_line(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    state = "start"
    before_states: list[str] = []
    after_states: list[str] = []
    for event in events:
        before_states.append(state)
        state = _next_state(state, event)
        after_states.append(state)

    final_state = "done" if state == "after_end" else "error"
    directive_count = sum(
        1
        for event in events
        if event not in {"instruction", "blank"}
    )
    signature = (
        STATE_IDS[final_state]
        + len(events)
        + len(events)
        + directive_count
        + events.count("instruction")
        + events.count("blank")
        + events.count("function")
        + events.count("end")
        + 7
    )
    return {
        "events": events,
        "before_states": tuple(before_states),
        "after_states": tuple(after_states),
        "final_state": STATE_IDS[final_state],
        "line_advance_count": len(events),
        "event_count": len(events),
        "directive_count": directive_count,
        "instruction_count": events.count("instruction"),
        "blank_count": events.count("blank"),
        "function_count": events.count("function"),
        "end_count": events.count("end"),
        "writer_signature": signature,
    }


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_event_writer_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert EVENT_WRITER_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn event_writer_model_self_check() -> tryte:" in source
    assert "fn writer_state_start() -> tryte:" in source
    assert "fn next_writer_state(state: tryte, event: tryte) -> tryte:" in source
    assert "fn validate_fixture_writer_states(fixture: tryte) -> trit:" in source


def test_renderer_event_writer_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "event_writer_model_self_check" in names
    assert "validate_all_fixture_writer_models" in names
    assert "event_writer_first_probe" in names
    assert "event_writer_simple_call_probe" in names
    assert "event_writer_sign_probe" in names
    assert "event_writer_signature_probe" in names


def test_renderer_event_writer_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="event_writer_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_writer_models") == 1


def test_renderer_event_writer_model_metrics_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_writer_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["writer_signature"] == 70
    assert expected["simple_call"]["writer_signature"] == 81
    assert expected["sign"]["writer_signature"] == 126
    for name, entrypoints in FIXTURE_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoints["final_state"]) == expected[name][
            "final_state"
        ]
        assert _execute(compilation, entrypoints["signature"]) == expected[name][
            "writer_signature"
        ]


def test_renderer_event_writer_model_totals_match_current_goldens() -> None:
    compilation = compile_source(_source())
    metrics = [
        _derive_writer_metrics(path)
        for path in GOLDEN_PATHS.values()
    ]
    totals = {
        "line_advance_count": sum(
            metric["line_advance_count"] for metric in metrics
        ),
        "directive_count": sum(metric["directive_count"] for metric in metrics),
        "instruction_count": sum(
            metric["instruction_count"] for metric in metrics
        ),
        "blank_count": sum(metric["blank_count"] for metric in metrics),
        "function_count": sum(metric["function_count"] for metric in metrics),
        "end_count": sum(metric["end_count"] for metric in metrics),
        "writer_signature": sum(metric["writer_signature"] for metric in metrics),
    }

    assert totals == {
        "line_advance_count": 75,
        "directive_count": 43,
        "instruction_count": 27,
        "blank_count": 5,
        "function_count": 5,
        "end_count": 5,
        "writer_signature": 277,
    }
    for metric_name, entrypoint in TOTAL_ENTRYPOINTS.items():
        assert _execute(compilation, entrypoint) == totals[metric_name]
    assert _execute(compilation, "event_writer_counts_probe") == 0
    assert _execute(compilation, "event_writer_signature_probe") == 0


def test_renderer_event_writer_model_executes_fixture_and_negative_probes() -> None:
    compilation = compile_source(_source())

    for entrypoints in FIXTURE_ENTRYPOINTS.values():
        assert _execute(compilation, entrypoints["probe"]) == 0
    assert _execute(compilation, "event_writer_transition_probe") == 0
    assert _execute(compilation, "validate_invalid_fixture_probe") == 1
    assert _execute(compilation, "validate_invalid_index_probe") == 1
    assert _execute(compilation, "validate_unknown_event_probe") == 1
    assert _execute(compilation, "validate_unknown_state_probe") == 1
    assert _execute(compilation, "validate_invalid_writer_transition_probe") == 1


def test_renderer_event_writer_model_is_registered_for_hosted_check() -> None:
    program = find_program(EVENT_WRITER_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_event_writer_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_event_writer.s3" in completed.stdout
    assert "s3 program check: checked 19 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 16 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_event_writer_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_event_writer.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_event_writer.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != EVENT_WRITER_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
