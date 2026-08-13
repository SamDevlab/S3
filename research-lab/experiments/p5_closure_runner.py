from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_source


TRACE_RE = re.compile(r"^# P5_TRACE_EVENT (?P<payload>{.*})$")
OBSERVER_OPCODES = {
    "TLOAD",
    "TADDR",
    "TREFLOAD",
    "TREFSTORE",
    "TSLOAD",
    "TSSTORE",
    "TCALL",
}
WRITE_OPCODES = {"TSTORE", "TREFSTORE", "TSSTORE"}


def _bucket(distance: int | None) -> str:
    if distance is None:
        return "never"
    if distance == 0:
        return "0"
    if distance <= 3:
        return "1-3"
    if distance <= 10:
        return "4-10"
    if distance <= 50:
        return "11-50"
    return ">50"


def _histogram(records: list[dict], key: str) -> dict[str, int]:
    result: Counter[str] = Counter()
    for record in records:
        result[_bucket(record.get(key))] += int(record["dynamic_weight"])
    return dict(
        (name, result.get(name, 0))
        for name in ("0", "1-3", "4-10", "11-50", ">50", "never")
        if result.get(name, 0)
    )


def _trace_events(assembly: str) -> list[dict]:
    events = []
    for line in assembly.splitlines():
        match = TRACE_RE.match(line)
        if match:
            events.append(json.loads(match.group("payload")))
    events.sort(key=lambda event: int(event["trace_id"]))
    if [event["trace_id"] for event in events] != list(range(len(events))):
        raise AssertionError("temporary P5 trace IDs are not contiguous")
    return events


def _reset_records(events: list[dict], trace: list[int]) -> list[dict]:
    by_id = {int(event["trace_id"]): event for event in events}
    records: list[dict] = []
    for position, trace_id in enumerate(trace):
        event = by_id[trace_id]
        if event["kind"] != "RESET":
            continue
        function = event["function"]
        memory = event.get("memory")
        register = event.get("register")
        record = {
            "trace_id": trace_id,
            "trace_position": position,
            "function": function,
            "memory": memory,
            "register": register,
            "length": int(event["length"]),
            "reset_kind": event["reset_kind"],
            "reset_reason": event["reset_reason"],
            "first_write_position": None,
            "first_observer_position": None,
            "first_init_check_position": None,
            "first_address_observer_position": None,
            "first_call_observer_position": None,
            "lifetime_end_position": None,
            "first_write_opcode": None,
            "first_observer_opcode": None,
            "classification": "UNKNOWN",
        }
        for later_position in range(position + 1, len(trace)):
            later = by_id[trace[later_position]]
            if later["kind"] != "INSTRUCTION":
                continue
            opcode = later["opcode"]
            same_function = later["function"] == function
            if same_function and opcode == "TRET":
                record["lifetime_end_position"] = later_position
                break
            if not same_function:
                continue
            later_memory = later.get("memory")
            direct_memory = memory is not None and later_memory == memory
            direct_register = (
                memory is None
                and register is not None
                and int(register) in later.get("registers", [])
            )
            if direct_memory and opcode in WRITE_OPCODES:
                if record["first_write_position"] is None:
                    record["first_write_position"] = later_position
                    record["first_write_opcode"] = opcode
            if direct_register and record["first_write_position"] is None:
                record["first_write_position"] = later_position
                record["first_write_opcode"] = opcode
            is_observer = direct_memory and opcode in {"TLOAD", "TADDR"}
            if opcode in {"TREFLOAD", "TREFSTORE", "TSLOAD", "TSSTORE", "TCALL"}:
                # A reference's source provenance is not encoded in Assembly
                # values. These are retained as possible observers, never
                # treated as proof of deadness.
                is_observer = is_observer or record["first_address_observer_position"] is not None
            if is_observer and record["first_observer_position"] is None:
                record["first_observer_position"] = later_position
                record["first_observer_opcode"] = opcode
            if direct_memory and opcode == "TLOAD":
                if record["first_init_check_position"] is None:
                    record["first_init_check_position"] = later_position
            if direct_memory and opcode == "TADDR":
                if record["first_address_observer_position"] is None:
                    record["first_address_observer_position"] = later_position
            if opcode == "TCALL" and record["first_address_observer_position"] is not None:
                if record["first_call_observer_position"] is None:
                    record["first_call_observer_position"] = later_position
        if record["first_write_position"] is not None:
            record["write_distance"] = record["first_write_position"] - position
        else:
            record["write_distance"] = None
        if record["first_observer_position"] is not None:
            record["observer_distance"] = record["first_observer_position"] - position
        else:
            record["observer_distance"] = None
        if memory is None:
            record["classification"] = "UNKNOWN"
        elif record["first_init_check_position"] is not None:
            record["classification"] = "REQUIRED_FOR_UNINITIALIZED_SEMANTICS"
        elif record["first_address_observer_position"] is not None:
            record["classification"] = "REQUIRED_FOR_REFERENCE_OBSERVABILITY"
        elif record["first_write_position"] is not None and record["first_observer_position"] is None:
            record["classification"] = "OVERWRITTEN_BEFORE_OBSERVER"
        elif record["lifetime_end_position"] is not None:
            record["classification"] = "LIFETIME_END_BEFORE_OBSERVER"
        records.append(record)
    return records


def _dynamic_weight(record: dict) -> int:
    """Count reset metadata bytes, including each rep stosb byte."""
    length = int(record["length"])
    if record["reset_kind"] == "allocated-memory-metadata":
        return length * length
    return length


def run(source_path: Path, output_path: Path, optimization: str = "O1") -> None:
    source = source_path.read_text(encoding="utf-8")
    compilation = compile_source(source, optimization)
    try:
        emulator_result = Emulator().execute(compilation.assembly)
        emulator_error = None
    except Exception as error:
        emulator_result = None
        emulator_error = str(error)
    assembly = X8664Backend().generate(compilation.assembly)
    output_path.with_suffix(".s").write_text(assembly, encoding="utf-8")
    events = _trace_events(assembly)
    toolchain = NativeToolchain.detect()
    with tempfile.TemporaryDirectory(prefix="s3-p5-closure-") as temporary:
        root = Path(temporary)
        trace_path = root / "trace.bin"
        trace_file = trace_path.open("w+b")
        executable = toolchain.build(
            assembly,
            root / "program",
            keep_assembly=root / "program.s",
        )

        def _install_trace_fd() -> None:
            os.dup2(trace_file.fileno(), 3)

        try:
            completed = subprocess.run(
                [str(executable)],
                check=False,
                capture_output=True,
                timeout=30.0,
                pass_fds=(trace_file.fileno(),),
                preexec_fn=_install_trace_fd,
            )
        finally:
            trace_file.close()
        raw_trace = trace_path.read_bytes()
    if len(raw_trace) % 8:
        raise RuntimeError(f"trace payload has invalid byte count {len(raw_trace)}")
    trace = list(struct.unpack(f"<{len(raw_trace) // 8}Q", raw_trace))
    output_path.with_suffix(".bin").write_bytes(raw_trace)
    if any(value >= len(events) for value in trace):
        raise RuntimeError("native trace contains an unknown static event id")
    records = _reset_records(events, trace)
    for record in records:
        record["dynamic_weight"] = _dynamic_weight(record)
    memory_records = [
        record
        for record in records
        if record["reset_kind"] == "allocated-memory-metadata"
    ]
    reset_dynamic = sum(record["dynamic_weight"] for record in records)
    memory_reset_dynamic = sum(record["dynamic_weight"] for record in memory_records)
    classifications: Counter[str] = Counter()
    memory_classifications: Counter[str] = Counter()
    for record in records:
        classifications[record["classification"]] += int(record["dynamic_weight"])
        if record in memory_records:
            memory_classifications[record["classification"]] += int(
                record["dynamic_weight"]
            )
    output = {
        "source": str(source_path),
        "optimization": optimization,
        "native_returncode": completed.returncode,
        "native_stdout": completed.stdout.decode(errors="replace"),
        "native_stderr": completed.stderr.decode(errors="replace"),
        "emulator_result": emulator_result,
        "emulator_error": emulator_error,
        "static_trace_event_count": len(events),
        "static_reset_site_count": sum(
            event["kind"] == "RESET" for event in events
        ),
        "dynamic_trace_event_count": len(trace),
        "reset_operation_count": len(records),
        "reset_dynamic_weighted_total": reset_dynamic,
        "allocated_memory_reset_operation_count": len(memory_records),
        "allocated_memory_reset_dynamic_total": memory_reset_dynamic,
        "reset_classification_weighted": dict(classifications),
        "allocated_memory_reset_classification_weighted": dict(
            memory_classifications
        ),
        "reset_to_first_write_histogram": _histogram(records, "write_distance"),
        "reset_to_first_observer_histogram": _histogram(records, "observer_distance"),
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: p5_closure_runner.py SOURCE OUTPUT [O0|O1]")
    run(
        Path(sys.argv[1]).resolve(),
        Path(sys.argv[2]).resolve(),
        sys.argv[3] if len(sys.argv) == 4 else "O1",
    )
