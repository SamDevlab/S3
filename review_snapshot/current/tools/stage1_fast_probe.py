"""Foreground diagnostics for the bounded Stage1 semantic candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bootstrap.s3 import ir_emulator
from bootstrap.s3.host_services import SourceResourceRuntime
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import CompilationResult, compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "selfhost" / "compiler" / "stage1_semantic_event_spine.s3"
DEFAULT_CANONICAL = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"


class _MilestoneReached(Exception):
    """Internal unwind used after a complete F record reaches the target."""


def _parse_v3_stream(output: bytes) -> dict[str, list[tuple[int, ...]]]:
    lines = output.decode("ascii").splitlines()
    if not lines or lines[0] != "S3IR2 3":
        raise ValueError("candidate did not emit an S3IR2 v3 stream")
    records: dict[str, list[tuple[int, ...]]] = {}
    for line in lines[1:]:
        fields = line.split()
        if not fields:
            continue
        records.setdefault(fields[0], []).append(tuple(int(field) for field in fields[1:]))
    return records


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value") and not isinstance(value, (str, bytes, int, float, bool)):
        return value.value
    return value


def compiled_ir_digest(compilation: CompilationResult) -> str:
    """Hash semantic compiled structure without object addresses."""

    if compilation.ir is None:
        raise ValueError("candidate compilation has no ordinary IR")
    payload = json.dumps(
        _json_safe(compilation.ir.to_dict()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Stage1Candidate:
    """Compile once and execute isolated candidate runs in one process."""

    def __init__(
        self,
        source_path: Path = DEFAULT_CANDIDATE,
        optimization: OptimizationLevel | str = OptimizationLevel.O0,
        *,
        mode: SyntaxMode = SyntaxMode.V0_6,
    ) -> None:
        self.source_path = source_path.resolve()
        self.source_bytes = self.source_path.read_bytes()
        self.source_sha256 = hashlib.sha256(self.source_bytes).hexdigest()
        self.optimization = OptimizationLevel.parse(optimization).value
        if not isinstance(mode, SyntaxMode):
            raise TypeError("mode must be a SyntaxMode")
        self.mode = mode.value
        started = time.perf_counter()
        self.compilation = compile_source(
            self.source_bytes.decode("utf-8"),
            self.optimization,
            mode=mode,
        )
        self.compile_seconds = time.perf_counter() - started
        if self.compilation.ir is None:
            raise RuntimeError("Stage1 candidate did not produce executable IR")
        self._functions = {
            function.name: function for function in self.compilation.ir.functions
        }
        if "scan_program" not in self._functions:
            raise RuntimeError("Stage1 candidate is missing scan_program")
        self.last_ir_digest_before: str | None = None
        self.last_ir_digest_after: str | None = None
        self.last_resource_runtime: SourceResourceRuntime | None = None
        self.last_output_buffer: bytearray | None = None
        self.last_error_buffer: bytearray | None = None
        self.last_io_hook: Any = None
        self.last_run_metadata: dict[str, Any] = {}

    def run_stream(
        self,
        source: bytes,
        *,
        stop_after_f: int | None = None,
        progress_functions: bool = False,
        progress_interval_seconds: float | None = None,
    ) -> tuple[dict[str, list[tuple[int, ...]]], float]:
        """Run one source replay with fresh runtime and output state."""

        if stop_after_f is not None and stop_after_f <= 0:
            raise ValueError("stop_after_f must be positive")
        if progress_interval_seconds is not None and progress_interval_seconds <= 0:
            raise ValueError("progress_interval_seconds must be positive")

        ir_emulator.functions_module = self.compilation.ir
        runtime = SourceResourceRuntime()
        ir_emulator.resource_runtime = runtime
        output = bytearray()
        error_output = bytearray()
        record_line = bytearray()
        observed_counts: dict[str, int] = {}
        function_emission_elapsed: list[float] = []
        milestone_reached = False
        next_progress_heartbeat: float | None = None
        original_execute = ir_emulator._execute_function

        def execute(functions_module, function, arguments, caller):
            name = function.name
            if name == "s3_stage1_source_length":
                return len(source)
            if name == "s3_stage1_read_byte":
                index = arguments[0]
                return source[index] if 0 <= index < len(source) else 0
            if name == "s3_stage1_write_byte":
                byte_value = arguments[0] & 0xFF
                output.append(byte_value)
                observe_protocol_byte(byte_value)
                return 0
            if name == "s3_stage1_write_error_byte":
                error_output.append(arguments[0] & 0xFF)
                return 0
            if name == "s3_stage1_exit":
                return 0
            return original_execute(functions_module, function, arguments, caller)

        before = compiled_ir_digest(self.compilation)
        self.last_ir_digest_before = before
        self.last_resource_runtime = runtime
        self.last_output_buffer = output
        self.last_error_buffer = error_output
        self.last_io_hook = execute
        ir_emulator._execute_function = execute
        started = time.perf_counter()
        if progress_interval_seconds is not None:
            next_progress_heartbeat = started + progress_interval_seconds

        def observe_protocol_byte(byte_value: int) -> None:
            nonlocal milestone_reached, next_progress_heartbeat
            now = time.perf_counter()
            if (
                progress_interval_seconds is not None
                and next_progress_heartbeat is not None
                and now >= next_progress_heartbeat
            ):
                elapsed = now - started
                print(
                    f"[stage1] alive elapsed={elapsed:.3f}s "
                    f"F={observed_counts.get('F', 0)}",
                    file=sys.stderr,
                    flush=True,
                )
                next_progress_heartbeat = now + progress_interval_seconds
            record_line.append(byte_value)
            if byte_value != 10:
                return
            fields = bytes(record_line).split()
            record_line.clear()
            if not fields:
                return
            kind = fields[0].decode("ascii", errors="replace")
            observed_counts[kind] = observed_counts.get(kind, 0) + 1
            if kind != "F":
                return
            elapsed = now - started
            function_emission_elapsed.append(elapsed)
            if progress_functions:
                print(
                    f"[stage1] F={observed_counts['F']} elapsed={elapsed:.3f}s",
                    file=sys.stderr,
                    flush=True,
                )
            if stop_after_f is not None and observed_counts["F"] >= stop_after_f:
                milestone_reached = True
                raise _MilestoneReached

        try:
            try:
                original_execute(self._functions, self._functions["scan_program"], (2, 0), ())
            except _MilestoneReached:
                pass
        finally:
            ir_emulator._execute_function = original_execute
        elapsed = time.perf_counter() - started
        after = compiled_ir_digest(self.compilation)
        self.last_ir_digest_after = after
        if before != after:
            raise RuntimeError("compiled candidate IR changed during execution")
        records = _parse_v3_stream(b"S3IR2 3\n" + bytes(output))
        self.last_run_metadata = {
            "candidate_compile_seconds": self.compile_seconds,
            "execution_seconds": elapsed,
            "record_counts": _record_counts(records),
            "function_emission_elapsed_seconds": list(function_emission_elapsed),
            "seconds_between_functions": [
                later - earlier
                for earlier, later in zip(
                    function_emission_elapsed, function_emission_elapsed[1:]
                )
            ],
            "stop_after_f": stop_after_f,
            "milestone_reached": milestone_reached,
            "partial_stream": stop_after_f is not None,
            "qualification_complete": stop_after_f is None,
        }
        return records, elapsed

    def run_file(
        self,
        source_path: Path,
        **run_options: Any,
    ) -> tuple[dict[str, list[tuple[int, ...]]], float]:
        return self.run_stream(source_path.read_bytes(), **run_options)


@dataclass(frozen=True, slots=True)
class CandidateCacheKey:
    source_sha256: str
    optimization: str
    mode: int


def candidate_cache_key(
    source_path: Path = DEFAULT_CANDIDATE,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> CandidateCacheKey:
    source_sha256 = hashlib.sha256(source_path.resolve().read_bytes()).hexdigest()
    optimization_value = OptimizationLevel.parse(optimization).value
    if not isinstance(mode, SyntaxMode):
        raise TypeError("mode must be a SyntaxMode")
    return CandidateCacheKey(source_sha256, optimization_value, mode.value)


_CANDIDATE_CACHE: dict[CandidateCacheKey, Stage1Candidate] = {}


def get_cached_candidate(
    source_path: Path = DEFAULT_CANDIDATE,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> Stage1Candidate:
    """Return a process-local candidate keyed by source and compile settings."""

    key = candidate_cache_key(source_path, optimization, mode=mode)
    cached = _CANDIDATE_CACHE.get(key)
    if cached is None:
        cached = Stage1Candidate(source_path, key.optimization, mode=mode)
        _CANDIDATE_CACHE[key] = cached
    return cached


def clear_candidate_cache() -> None:
    _CANDIDATE_CACHE.clear()


def candidate_cache_size() -> int:
    return len(_CANDIDATE_CACHE)


def _record_counts(records: dict[str, list[tuple[int, ...]]]) -> dict[str, int]:
    record_kinds = ("F", "B", "D", "V", "M", "I", "O", "R", "C", "A", "T", "Z")
    return {key: len(records.get(key, ())) for key in record_kinds}


def _canonical_diagnostic(
    records: dict[str, list[tuple[int, ...]]], source: bytes
) -> dict[str, Any]:
    counts = _record_counts(records)
    if counts["Z"]:
        return {
            "FIRST_LOSS": "NONE",
            "DIAGNOSTIC_CODE": "CANONICAL_STREAM_COMPLETE",
            "RULE_ID": "NONE",
        }
    last_function = "UNKNOWN"
    if records.get("F"):
        function_record = records["F"][-1]
        if len(function_record) >= 4:
            name_start = function_record[2]
            name_length = function_record[3]
            last_function = source[name_start : name_start + name_length].decode(
                "ascii", errors="replace"
            )
    rule_id = "S3.CONTROL.MATCH_THREE_WAY" if counts["T"] else "S3.IR.VALUE_SINGLE_PRODUCER"
    return {
        "FIRST_LOSS": {
            "after_function": last_function,
            "condition": "completion record Z was not emitted",
        },
        "DIAGNOSTIC_CODE": "S3IR2_CANONICAL_STREAM_INCOMPLETE",
        "RULE_ID": rule_id,
    }


def _milestone_payload(
    candidate: Stage1Candidate,
    records: dict[str, list[tuple[int, ...]]],
    source: bytes,
    *,
    canonical: bool,
) -> dict[str, Any]:
    metadata = candidate.last_run_metadata
    counts = _record_counts(records)
    payload: dict[str, Any] = {
        "PROBE_MODE": "MILESTONE",
        "CANDIDATE_SHA": candidate.source_sha256,
        "CANONICAL_SHA": hashlib.sha256(source).hexdigest() if canonical else "",
        "TARGET_F": metadata["stop_after_f"],
        "F_OBSERVED": counts["F"],
        "MILESTONE_REACHED": "YES" if metadata["milestone_reached"] else "NO",
        "ELAPSED_SECONDS": metadata["execution_seconds"],
        "PARTIAL_STREAM": "YES",
        "QUALIFICATION_COMPLETE": "NO",
        "counts": counts,
        "candidate_compile_seconds": metadata["candidate_compile_seconds"],
        "function_emission_elapsed_seconds": metadata[
            "function_emission_elapsed_seconds"
        ],
        "seconds_between_functions": metadata["seconds_between_functions"],
    }
    if records.get("F"):
        last_function = records["F"][-1]
        if last_function:
            payload["LAST_FUNCTION_INDEX"] = last_function[0]
        if len(last_function) >= 4:
            name_start = last_function[2]
            name_length = last_function[3]
            payload["LAST_FUNCTION_NAME"] = source[
                name_start : name_start + name_length
            ].decode("ascii", errors="replace")
    return payload


def _smoke_source() -> bytes:
    return b"fn main() -> tryte:\n    return 0\n"


def _fixture_sources() -> dict[str, bytes]:
    return {
        "smoke": _smoke_source(),
        "mutable": (
            b"fn main() -> i64:\n"
            b"    mut value: i64 = 0\n"
            b"    value = value + 1\n"
            b"    return value\n"
        ),
        "call": (
            b"foreign fn host(value: i64) -> i64\n"
            b"fn main() -> i64:\n"
            b"    return 0\n"
        ),
        "match": (
            b"fn main() -> trit:\n"
            b"    mut value: i64 = 1\n"
            b"    match value <=> 2:\n"
            b"        -1:\n"
            b"            return -1\n"
            b"        0:\n"
            b"            return 0\n"
            b"        1:\n"
            b"            return 1\n"
        ),
        "nested-match-while": (
            b"foreign fn read_unit(index: i64) -> tryte\n"
            b"foreign fn is_blank(unit: tryte) -> trit\n"
            b"fn scan(limit: i64) -> i64:\n"
            b"    mut position: i64 = 0\n"
            b"    mut running: trit = -1\n"
            b"    while running == -1:\n"
            b"        match position < limit:\n"
            b"            -1:\n"
            b"                mut unit: tryte = read_unit(position)\n"
            b"                match is_blank(unit):\n"
            b"                    -1:\n"
            b"                        position += 1\n"
            b"                    0:\n"
            b"                        running = 0\n"
            b"                    1:\n"
            b"                        running = 0\n"
            b"            0:\n"
            b"                running = 0\n"
            b"            1:\n"
            b"                running = 0\n"
            b"    return position\n"
            b"fn main() -> i64:\n"
            b"    return 0\n"
        ),
    }


def _run_timings(candidate: Stage1Candidate) -> dict[str, Any]:
    fixture_timings: dict[str, Any] = {}
    all_reused_outputs_equal = True
    for name, source in _fixture_sources().items():
        first, first_seconds = candidate.run_stream(source)
        second, second_seconds = candidate.run_stream(source)
        equal = first == second
        all_reused_outputs_equal = all_reused_outputs_equal and equal
        fixture_timings[name] = {
            "first_execution_seconds": first_seconds,
            "reused_execution_seconds": second_seconds,
            "cold_vs_reuse_equal": equal,
            "first_counts": _record_counts(first),
        }
    return {
        "candidate_sha256": candidate.source_sha256,
        "optimization": candidate.optimization,
        "mode": candidate.mode,
        "candidate_compile_seconds": candidate.compile_seconds,
        "fixtures": fixture_timings,
        "cold_vs_reuse_equal": all_reused_outputs_equal,
        "compiled_ir_reuse": "SAFE" if all_reused_outputs_equal else "UNSAFE",
    }


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--source", type=Path, help="source bytes to replay")
    parser.add_argument(
        "--fixture",
        choices=tuple(_fixture_sources()),
        help="maintained noncanonical execution canary",
    )
    parser.add_argument("--canonical-summary", action="store_true")
    parser.add_argument("--timings", action="store_true")
    parser.add_argument("--cold-vs-reuse", action="store_true")
    parser.add_argument(
        "--stop-after-f",
        type=_positive_int,
        help="stop after emitting this many complete function records",
    )
    parser.add_argument(
        "--progress-functions",
        action="store_true",
        help="report each emitted function on stderr",
    )
    parser.add_argument(
        "--progress-interval-seconds",
        type=_positive_float,
        help="report a bounded alive heartbeat on stderr at this interval",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    candidate = get_cached_candidate(args.candidate)
    run_options = {
        "stop_after_f": args.stop_after_f,
        "progress_functions": args.progress_functions,
        "progress_interval_seconds": args.progress_interval_seconds,
    }
    if args.timings or args.cold_vs_reuse:
        print(json.dumps(_run_timings(candidate), sort_keys=True))
        return 0
    if args.canonical_summary:
        records, elapsed = candidate.run_file(DEFAULT_CANONICAL, **run_options)
        if args.stop_after_f is not None:
            print(
                json.dumps(
                    _milestone_payload(
                        candidate,
                        records,
                        DEFAULT_CANONICAL.read_bytes(),
                        canonical=True,
                    ),
                    sort_keys=True,
                )
            )
            return 0
        payload = {
            "execution_seconds": elapsed,
            "counts": _record_counts(records),
            **_canonical_diagnostic(records, DEFAULT_CANONICAL.read_bytes()),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    source = args.source
    if args.fixture:
        source_bytes = _fixture_sources()[args.fixture]
        records, elapsed = candidate.run_stream(source_bytes, **run_options)
    elif source is not None:
        source_bytes = source.read_bytes()
        records, elapsed = candidate.run_stream(source_bytes, **run_options)
    else:
        raise SystemExit("select --fixture, --source, --timings, or --canonical-summary")
    if args.stop_after_f is not None:
        print(
            json.dumps(
                _milestone_payload(candidate, records, source_bytes, canonical=False),
                sort_keys=True,
            )
        )
    else:
        print(
            json.dumps(
                {"execution_seconds": elapsed, "counts": _record_counts(records)},
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
