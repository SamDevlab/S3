"""Prove the native Stage1 fixture corpus exercises every required opcode.

The required set comes from the typed reference-opcode inventory for the exact
canonical compiler source. This tool is hosted coverage evidence only; native
execution of the fixtures remains a separate mandatory gate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "tests" / "stage1_codegen_complete_fixtures.json"
DEFAULT_REFERENCE = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-bootstrap-opcode-inventory.json"
)
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-bootstrap-opcode-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-codegen-fixture-opcode-coverage.json"
)


class FixtureCoverageError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.resolve().read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FixtureCoverageError(f"{label} is missing: {path}") from error
    if not isinstance(document, dict):
        raise FixtureCoverageError(f"{label} must be a JSON object")
    return document


def _fixture_opcode_set(source: str) -> tuple[set[str], Counter[str]]:
    compilation = compile_source(source, optimization="O0")
    ir, _ = compilation.require_ordinary_artifacts()
    histogram: Counter[str] = Counter()
    for function in ir.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                histogram[instruction.opcode.value] += 1
    return set(histogram), histogram


def audit(
    fixtures_document: dict[str, Any],
    reference_document: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    if fixtures_document.get("schema") != "s3.selfhost.stage1-codegen-complete-fixtures.v1":
        raise FixtureCoverageError("Stage1 fixture manifest schema mismatch")
    if reference_document.get("schema") != "s3.selfhost.reference-bootstrap-opcode-inventory.v1":
        raise FixtureCoverageError("reference opcode inventory schema mismatch")
    if contract.get("schema") != "s3.selfhost.reference-bootstrap-opcode-contract.v1":
        raise FixtureCoverageError("reference opcode contract schema mismatch")
    reference_ir = reference_document.get("reference_ir")
    reference_source = reference_document.get("canonical_source")
    if not isinstance(reference_ir, dict) or not isinstance(reference_ir.get("observed_opcodes"), list):
        raise FixtureCoverageError("reference opcode inventory lacks observed_opcodes")
    if not isinstance(reference_source, dict) or not isinstance(reference_source.get("sha256"), str):
        raise FixtureCoverageError("reference opcode inventory lacks canonical source SHA")
    reference_sha = reference_source["sha256"]
    required_opcodes = set(reference_ir["observed_opcodes"])
    capabilities = contract.get("opcode_capabilities")
    if not isinstance(capabilities, dict):
        raise FixtureCoverageError("opcode contract lacks capability mapping")

    fixtures = fixtures_document.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise FixtureCoverageError("fixture manifest has no positive fixtures")
    fixture_reports: list[dict[str, Any]] = []
    aggregate_histogram: Counter[str] = Counter()
    covered_by: dict[str, list[str]] = defaultdict(list)
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise FixtureCoverageError("fixture entry is not an object")
        name = fixture.get("name")
        source = fixture.get("source")
        if not isinstance(name, str) or not isinstance(source, str):
            raise FixtureCoverageError("fixture lacks name/source")
        opcodes, histogram = _fixture_opcode_set(source)
        aggregate_histogram.update(histogram)
        for opcode in opcodes:
            covered_by[opcode].append(name)
        fixture_reports.append(
            {
                "name": name,
                "opcodes": sorted(opcodes),
                "opcode_histogram": dict(sorted(histogram.items())),
                "logical_requirements": fixture.get("logical_requirements", []),
            }
        )

    missing_opcodes = sorted(required_opcodes - set(aggregate_histogram))
    missing_capabilities = sorted(
        {
            capabilities[opcode]
            for opcode in missing_opcodes
            if opcode in capabilities
        }
    )
    unmapped_required = sorted(opcode for opcode in required_opcodes if opcode not in capabilities)
    passed = not missing_opcodes and not unmapped_required
    return {
        "schema": "s3.selfhost.stage1-codegen-fixture-opcode-coverage.v1",
        "status": "PASS_HOSTED_FIXTURE_OPCODE_COVERAGE" if passed else "BLOCKED_FIXTURE_OPCODE_COVERAGE_GAP",
        "authority": "HOSTED_COVERAGE_ONLY_NATIVE_FIXTURE_EXECUTION_STILL_REQUIRED",
        "native_evidence": False,
        "reference_canonical_source_sha256": reference_sha,
        "required_opcodes": sorted(required_opcodes),
        "required_capabilities": sorted(
            {capabilities[opcode] for opcode in required_opcodes if opcode in capabilities}
        ),
        "aggregate_fixture_opcode_histogram": dict(sorted(aggregate_histogram.items())),
        "covered_by": {key: value for key, value in sorted(covered_by.items())},
        "fixtures": fixture_reports,
        "missing_required_opcodes": missing_opcodes,
        "missing_required_capabilities": missing_capabilities,
        "unmapped_required_opcodes": unmapped_required,
        "qualification": {
            "hosted_fixture_coverage": passed,
            "native_fixture_execution": "NOT_RUN_BY_THIS_TOOL",
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "RUN_NATIVE_STAGE1_CODEGEN_COMPLETE_FIXTURES"
                if passed
                else "ADD_MINIMAL_NATIVE_FIXTURES_FOR_MISSING_BOOTSTRAP_OPCODES"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        result = audit(
            _load_json(args.fixtures, "fixture manifest"),
            _load_json(args.reference, "reference opcode inventory"),
            _load_json(args.contract, "reference opcode contract"),
        )
    except (FixtureCoverageError, json.JSONDecodeError) as error:
        parser.exit(2, f"Stage1 fixture opcode coverage blocked: {error}\n")
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"REFERENCE_SOURCE_SHA256={result['reference_canonical_source_sha256']}")
    print("MISSING_OPCODES=" + ",".join(result["missing_required_opcodes"]))
    print("MISSING_CAPABILITIES=" + ",".join(result["missing_required_capabilities"]))
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
