"""Run a bounded, explicit differential corpus against S3C-NG and Python.

The corpus is a set of case samples, not a declaration of whole-family parity.
Canonical IR is compared byte-for-byte through the shared serializer. Hosted
execution is compared only for cases that opt into that level; native execution
is deliberately outside this harness's qualification contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bootstrap.s3.compiler_provider import (
    CompilerKind,
    compile_source_set_with_provider,
)
from bootstrap.s3.diagnostics import S3Error, diagnostic_from_exception
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.native_compiler import (
    NativeS3CTransportError,
    default_s3c_ng_path,
    inspect_s3c_ng_executable,
)
from bootstrap.s3.optimizer import OptimizationLevel


CORPUS_VERSION = "s3-v7-differential-corpus-v1"


@dataclass(frozen=True, slots=True)
class CorpusCase:
    case_id: str
    family: str
    sources: tuple[tuple[str, str], ...]
    expected_return: int
    entry_module: str = "main"
    entry_function: str = "main"
    compare_hosted_execution: bool = True

    def source_map(self) -> dict[str, str]:
        return dict(self.sources)


# Explicit, reviewable samples drawn from already-supported S3 syntax families.
# Passing these samples does not qualify their entire family.
CORPUS: tuple[CorpusCase, ...] = (
    CorpusCase(
        "numeric-tryte-add",
        "numeric.tryte",
        (("main.s3", "fn main() -> tryte:\n    return 9 + 4\n"),),
        13,
    ),
    CorpusCase(
        "numeric-i64-add",
        "numeric.i64",
        (("main.s3", "fn main() -> i64:\n    return 40 + 2\n"),),
        42,
    ),
    CorpusCase(
        "functions-parameters-and-call",
        "functions.calls",
        (
            ("main.s3", "fn combine(a: tryte, b: tryte) -> tryte:\n"
             "    return a + b\n"
             "fn main() -> tryte:\n"
             "    return combine(17, 25)\n"),
        ),
        42,
    ),
    CorpusCase(
        "storage-mutable-local",
        "storage.mutable-local",
        (("main.s3", "fn main() -> tryte:\n"
          "    mut total: tryte = 40\n"
          "    total = total + 2\n"
          "    return total\n"),),
        42,
    ),
    CorpusCase(
        "control-match-arms",
        "control.match",
        (("main.s3", "fn classify(value: i64) -> i64:\n"
          "    match value > 0:\n"
          "        -1:\n"
          "            return 10\n"
          "        0:\n"
          "            return 20\n"
          "        1:\n"
          "            return 30\n"
          "fn main() -> i64:\n"
          "    return classify(2)\n"),),
        10,
    ),
    CorpusCase(
        "control-loop-accumulation",
        "control.loops",
        (("main.s3", "fn main() -> tryte:\n"
          "    mut index: tryte = 0\n"
          "    mut total: tryte = 0\n"
          "    while index < 3:\n"
          "        total = total + 2\n"
          "        index = index + 1\n"
          "    return total\n"),),
        6,
    ),
    CorpusCase(
        "modules-explicit-import",
        "modules.imports",
        (
            ("app.s3", "module app\nfrom math import add\n"
             "fn main() -> i64:\n    return add(19, 23)\n"),
            ("math.s3", "module math\nexport fn add(a: i64, b: i64) -> i64:\n"
             "    return a + b\n"),
        ),
        42,
        entry_module="app",
    ),
)


def _existing_maturity_cases() -> tuple[CorpusCase, ...]:
    """Reuse deterministic workload builders already exercised by the suite."""

    from tests.test_language_maturity_workloads import (
        PEBBLE_CASES,
        VM_CASES,
        _csv_program,
        _hex_program,
        _ordering_program,
        _pebble_program,
        _vm_program,
    )

    return (
        CorpusCase(
            "maturity-ordering-vector-search",
            "real-workload.vectors-and-loops",
            tuple(sorted(_ordering_program((29, -4, 8, 8, 17, 0), (-4, 8, 17, 30)).items())),
            0,
        ),
        CorpusCase(
            "maturity-hex-runtime-bytes",
            "real-workload.bytes",
            tuple(sorted(_hex_program(bytes((0, 1, 15, 16, 127, 128, 254, 255))).items())),
            0,
        ),
        CorpusCase(
            "maturity-csv-records-and-validation",
            "real-workload.records-and-errors",
            (("main.s3", _csv_program("-12,0,25,-3", (10, 4))),),
            0,
        ),
        CorpusCase(
            "maturity-bounded-stack-vm",
            "real-workload.numeric-and-control",
            (("main.s3", _vm_program(VM_CASES)),),
            0,
        ),
        CorpusCase(
            "maturity-pebble-compiler",
            "real-workload.text-and-nested-compilation",
            (("main.s3", _pebble_program(PEBBLE_CASES)),),
            0,
        ),
    )


# Seed cases stay small; these samples come from builders shared with the
# existing repository maturity tests.
ALL_CORPUS_CASES = CORPUS + _existing_maturity_cases()


def validate_corpus(cases: tuple[CorpusCase, ...] = ALL_CORPUS_CASES) -> None:
    """Fail closed on malformed or ambiguous checked-in case data."""

    ids = [case.case_id for case in cases]
    if not cases or len(set(ids)) != len(ids):
        raise ValueError("corpus must contain cases with unique IDs")
    for case in cases:
        if not case.case_id or not case.family or not case.sources:
            raise ValueError("each corpus case needs an ID, family, and source set")
        paths = [path for path, _ in case.sources]
        if len(paths) != len(set(paths)) or any(not path.endswith(".s3") for path in paths):
            raise ValueError(f"case {case.case_id} has duplicate or invalid source paths")
        if not case.entry_module or not case.entry_function:
            raise ValueError(f"case {case.case_id} needs an entry module and function")


def run_case(
    case: CorpusCase,
    *,
    executable: Path,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
) -> dict[str, Any]:
    """Compile one case with both providers and compare declared levels."""

    level = OptimizationLevel.parse(optimization)
    sources = case.source_map()
    python = _compile(case, sources, CompilerKind.PYTHON, executable, level)
    candidate = _compile(case, sources, CompilerKind.S3C_NG, executable, level)
    report: dict[str, Any] = {
        "case_id": case.case_id,
        "family": case.family,
        "scope": "CASE_SAMPLE_ONLY",
        "expected_return": case.expected_return,
        "compilation": {"python": python[1], "s3c_ng": candidate[1]},
        "canonical_ir": {"status": "NOT_COMPARED"},
        "hosted_execution": {"status": "NOT_REQUESTED"},
        "native_execution": {
            "status": "NOT_COMPARED",
            "reason": "native execution requires separate ABI/runtime qualification",
        },
    }

    if python[0] is None or candidate[0] is None:
        report["classification"] = _classify_compile_failures(
            python[1], candidate[1]
        )
        report["status"] = "FAIL"
        return report

    python_compilation, candidate_compilation = python[0], candidate[0]
    python_ir = getattr(python_compilation, "ir", None)
    candidate_ir = getattr(candidate_compilation, "ir", None)
    if python_ir is None or candidate_ir is None:
        report["classification"] = "CANONICAL_IR_UNAVAILABLE"
        report["status"] = "FAIL"
        report["canonical_ir"] = {"status": "UNAVAILABLE"}
        return report

    try:
        python_ir_text = serialize_ir(python_ir)
        candidate_ir_text = serialize_ir(candidate_ir)
    except Exception as error:
        report["classification"] = "CANONICAL_IR_SERIALIZATION_ERROR"
        report["status"] = "FAIL"
        report["canonical_ir"] = {
            "status": "ERROR",
            "error": _stable_error(error),
        }
        return report
    ir_equal = python_ir_text == candidate_ir_text
    report["canonical_ir"] = {
        "status": "MATCH" if ir_equal else "MISMATCH",
        "python_sha256": _sha256(python_ir_text),
        "s3c_ng_sha256": _sha256(candidate_ir_text),
    }

    hosted_equal: bool | None = None
    if case.compare_hosted_execution:
        python_assembly = getattr(python_compilation, "assembly", None)
        candidate_assembly = getattr(candidate_compilation, "assembly", None)
        if python_assembly is None or candidate_assembly is None:
            report["hosted_execution"] = {"status": "UNAVAILABLE"}
            report["classification"] = "HOSTED_EXECUTION_UNAVAILABLE"
            report["status"] = "FAIL"
            return report
        else:
            python_observation = _run_hosted(python_assembly, case.entry_function)
            candidate_observation = _run_hosted(candidate_assembly, case.entry_function)
            if (
                python_observation["status"] == "UNSUPPORTED_RESULT_TYPE"
                or candidate_observation["status"] == "UNSUPPORTED_RESULT_TYPE"
            ):
                report["hosted_execution"] = {
                    "status": "UNSUPPORTED",
                    "python": python_observation,
                    "s3c_ng": candidate_observation,
                }
                report["classification"] = "HOSTED_RESULT_UNSUPPORTED"
                report["status"] = "FAIL"
                return report
            hosted_equal = python_observation == candidate_observation
            expected = {"status": "SUCCESS", "value": case.expected_return}
            reference_expected = python_observation == expected
            report["hosted_execution"] = {
                "status": "MATCH" if hosted_equal else "MISMATCH",
                "python": python_observation,
                "s3c_ng": candidate_observation,
                "python_matches_expected": reference_expected,
            }
            if not reference_expected:
                report["classification"] = "REFERENCE_EXPECTATION_MISMATCH"
                report["status"] = "FAIL"
                return report
    else:
        report["hosted_execution"] = {"status": "NOT_REQUESTED"}

    if not ir_equal and hosted_equal is False:
        classification = "IR_AND_HOSTED_EXECUTION_MISMATCH"
    elif not ir_equal:
        classification = "CANONICAL_IR_MISMATCH"
    elif hosted_equal is False:
        classification = "HOSTED_EXECUTION_MISMATCH"
    else:
        classification = "MATCH"
    report["classification"] = classification
    report["status"] = "PASS" if classification == "MATCH" else "FAIL"
    return report


def run_corpus(
    *,
    executable: Path,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    case_ids: tuple[str, ...] | None = None,
    families: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    validate_corpus()
    selected = tuple(
        case
        for case in ALL_CORPUS_CASES
        if (case_ids is None or case.case_id in case_ids)
        and (families is None or case.family in families)
    )
    unknown_cases = sorted(
        set(case_ids or ()) - {case.case_id for case in ALL_CORPUS_CASES}
    )
    unknown_families = sorted(
        set(families or ()) - {case.family for case in ALL_CORPUS_CASES}
    )
    if unknown_cases or unknown_families:
        return {
            "schema": CORPUS_VERSION,
            "status": "FAIL",
            "classification": "UNKNOWN_SELECTION",
            "unknown_case_ids": unknown_cases,
            "unknown_families": unknown_families,
            "cases": [],
            "summary": {"selected": 0, "passed": 0, "failed": 1},
            "family_evidence": {},
            "parity_claim": "NONE_CASE_SAMPLES_ONLY",
        }
    if not selected:
        return {
            "schema": CORPUS_VERSION,
            "status": "FAIL",
            "classification": "EMPTY_SELECTION",
            "unknown_case_ids": [],
            "unknown_families": [],
            "cases": [],
            "summary": {"selected": 0, "passed": 0, "failed": 1},
            "family_evidence": {},
            "parity_claim": "NONE_CASE_SAMPLES_ONLY",
        }

    results = [
        run_case(case, executable=executable, optimization=optimization)
        for case in selected
    ]
    classifications = Counter(result["classification"] for result in results)
    by_family: dict[str, dict[str, Any]] = {}
    for family in sorted({case.family for case in selected}):
        family_results = [result for result in results if result["family"] == family]
        by_family[family] = {
            "samples": len(family_results),
            "matching_samples": sum(item["status"] == "PASS" for item in family_results),
            "claim": "CASE_SAMPLES_ONLY",
        }
    failed = sum(result["status"] != "PASS" for result in results)
    return {
        "schema": CORPUS_VERSION,
        "status": "PASS" if not failed else "FAIL",
        "optimization": OptimizationLevel.parse(optimization).value,
        "providers": [CompilerKind.PYTHON.value, CompilerKind.S3C_NG.value],
        "cases": results,
        "summary": {
            "selected": len(results),
            "passed": len(results) - failed,
            "failed": failed,
            "classifications": {key: classifications[key] for key in sorted(classifications)},
        },
        "family_evidence": by_family,
        "parity_claim": "NONE_CASE_SAMPLES_ONLY",
    }


def _compile(
    case: CorpusCase,
    sources: dict[str, str],
    compiler: CompilerKind,
    executable: Path,
    optimization: OptimizationLevel,
) -> tuple[Any | None, dict[str, Any]]:
    try:
        compilation = compile_source_set_with_provider(
            sources,
            optimization,
            compiler=compiler,
            executable=executable if compiler is CompilerKind.S3C_NG else None,
            entry_module=case.entry_module,
        )
    except Exception as error:
        return None, {"status": "ERROR", "error": _stable_error(error)}
    ir = getattr(compilation, "ir", None)
    if ir is None:
        return compilation, {"status": "SUCCESS", "ir_status": "UNAVAILABLE"}
    return compilation, {"status": "SUCCESS", "ir_status": "AVAILABLE"}


def _stable_error(error: Exception) -> dict[str, Any]:
    if isinstance(error, S3Error):
        diagnostic = diagnostic_from_exception(error)
        return {
            "kind": "DIAGNOSTIC",
            "category": diagnostic.category.value,
            "code": diagnostic.code.value,
            "phase": diagnostic.phase.value,
        }
    return {
        "kind": "EXCEPTION",
        "type": f"{type(error).__module__}.{type(error).__qualname__}",
    }


def _classify_compile_failures(
    python_result: dict[str, Any], candidate_result: dict[str, Any]
) -> str:
    python_failed = python_result["status"] == "ERROR"
    candidate_failed = candidate_result["status"] == "ERROR"
    if python_failed != candidate_failed:
        return "COMPILE_OUTCOME_MISMATCH"
    if python_failed:
        if python_result["error"] == candidate_result["error"]:
            return "UNEXPECTED_COMPILE_FAILURE_BOTH"
        return "COMPILE_DIAGNOSTIC_MISMATCH"
    return "CANONICAL_IR_UNAVAILABLE"


def _run_hosted(assembly: Any, entry: str) -> dict[str, Any]:
    try:
        value = Emulator().execute(assembly, entry=entry)
    except Exception as error:
        return {"status": "ERROR", "error": _stable_error(error)}
    normalized = _json_value(value)
    if normalized is _UNSUPPORTED:
        return {"status": "UNSUPPORTED_RESULT_TYPE"}
    return {"status": "SUCCESS", "value": normalized}


_UNSUPPORTED = object()


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        normalized = [_json_value(item) for item in value]
        return _UNSUPPORTED if any(item is _UNSUPPORTED for item in normalized) else normalized
    if isinstance(value, dict):
        normalized = {str(key): _json_value(item) for key, item in value.items()}
        if any(item is _UNSUPPORTED for item in normalized.values()):
            return _UNSUPPORTED
        return {key: normalized[key] for key in sorted(normalized)}
    return _UNSUPPORTED


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _selected_args(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
) -> argparse.Namespace:
    parser.add_argument("--executable", type=Path, help="qualified Linux x86-64 S3C-NG ELF")
    parser.add_argument("--optimization", choices=("O0", "O1"), default="O0")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--family", action="append", dest="families")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    args = _selected_args(parser, argv)
    executable = args.executable
    if executable is None:
        configured = os.environ.get("S3C_NG_BOOTSTRAP_EXECUTABLE")
        executable = Path(configured).expanduser() if configured else default_s3c_ng_path()
    availability = inspect_s3c_ng_executable(executable)
    if not availability.available:
        report = {
            "schema": CORPUS_VERSION,
            "status": "BLOCKED",
            "classification": "NATIVE_PROVIDER_UNAVAILABLE",
            "provider_error": _stable_error(
                NativeS3CTransportError(availability.reason or "unavailable")
            ),
            "cases": [],
            "summary": {"selected": 0, "passed": 0, "failed": 0},
            "parity_claim": "NONE_CASE_SAMPLES_ONLY",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    report = run_corpus(
        executable=availability.executable,
        optimization=args.optimization,
        case_ids=tuple(args.case_ids) if args.case_ids else None,
        families=tuple(args.families) if args.families else None,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
